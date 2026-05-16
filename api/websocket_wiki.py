import logging
import os
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import unquote

from adalflow.core.types import ModelType
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, Field

from api.config import (
    get_model_config,
    configs,
)
from api.data_pipeline import count_tokens, get_file_content
from api.dashscope_client import DashscopeClient
from api.rag import RAG

# Configure logging
from api.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


# Models for the API
class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatCompletionRequest(BaseModel):
    repo_url: str = Field(..., description="URL of the repository to query")
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    filePath: Optional[str] = Field(None, description="Optional path to a file in the repository to include in the prompt")
    token: Optional[str] = Field(None, description="Personal access token for private repositories")
    type: Optional[str] = Field("github", description="Type of repository (e.g., 'github', 'local')")
    provider: str = Field("dashscope", description="Model provider (dashscope)")
    model: Optional[str] = Field(None, description="Model name for the specified provider")
    language: Optional[str] = Field("en", description="Language for content generation (e.g., 'en', 'zh')")
    excluded_dirs: Optional[str] = Field(None, description="Comma-separated list of directories to exclude")
    excluded_files: Optional[str] = Field(None, description="Comma-separated list of file patterns to exclude")
    included_dirs: Optional[str] = Field(None, description="Comma-separated list of directories to include exclusively")
    included_files: Optional[str] = Field(None, description="Comma-separated list of file patterns to include exclusively")


# =============================================================
# Shared helpers
# =============================================================

async def _prepare_rag(request: ChatCompletionRequest) -> RAG:
    """Prepare and return a RAG instance for the given request."""
    request_rag = RAG(provider=request.provider, model=request.model)

    dimension = None
    try:
        from api.settings_router import read_user_dimension_from_db
        dimension = await read_user_dimension_from_db()
        if dimension is not None:
            logger.info("Using user dimension %d from database", dimension)
    except Exception as exc:
        logger.warning("Could not read user dimension from DB: %s", exc)

    excluded_dirs = None
    excluded_files = None
    included_dirs = None
    included_files = None

    if request.excluded_dirs:
        excluded_dirs = [unquote(d) for d in request.excluded_dirs.split('\n') if d.strip()]
    if request.excluded_files:
        excluded_files = [unquote(f) for f in request.excluded_files.split('\n') if f.strip()]
    if request.included_dirs:
        included_dirs = [unquote(d) for d in request.included_dirs.split('\n') if d.strip()]
    if request.included_files:
        included_files = [unquote(f) for f in request.included_files.split('\n') if f.strip()]

    request_rag.prepare_retriever(
        request.repo_url, request.type, request.token,
        excluded_dirs, excluded_files, included_dirs, included_files,
        dimension=dimension,
    )
    return request_rag


def _build_conversation_history(request_rag: RAG) -> str:
    """Build a formatted conversation history string from RAG memory."""
    history = ""
    for turn_id, turn in request_rag.memory().items():
        if not isinstance(turn_id, int) and hasattr(turn, 'user_query') and hasattr(turn, 'assistant_response'):
            history += (
                "<turn>\n"
                f"<user>{turn.user_query.query_str}</user>\n"
                f"<assistant>{turn.assistant_response.response_str}</assistant>\n"
                "</turn>\n"
            )
    return history


def _retrieve_context(request_rag: RAG, query: str, file_path: Optional[str], language: Optional[str], top_k: Optional[int] = None) -> str:
    """Perform RAG retrieval and return formatted context text."""
    rag_query = query
    if file_path:
        rag_query = f"Contexts related to {file_path}"

    try:
        retrieved = request_rag(rag_query, language=language, top_k=top_k)
        if retrieved and retrieved[0].documents:
            docs = retrieved[0].documents
            docs_by_file: Dict[str, list] = {}
            for doc in docs:
                fp = doc.meta_data.get('file_path', 'unknown')
                docs_by_file.setdefault(fp, []).append(doc)

            parts = []
            for fp, file_docs in docs_by_file.items():
                header = f"## File Path: {fp}\n\n"
                content = "\n\n".join([d.text for d in file_docs])
                parts.append(f"{header}{content}")
            return "\n\n" + "-" * 10 + "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Error in RAG retrieval: {str(e)}")
    return ""


def _build_prompt(
    system_prompt: str,
    conversation_history: str,
    file_content: str,
    file_path: Optional[str],
    context_text: str,
    query: str,
) -> str:
    prompt = f"/no_think {system_prompt}\n\n"

    if conversation_history:
        prompt += f"<conversation_history>\n{conversation_history}</conversation_history>\n\n"

    if file_content and file_path:
        prompt += f"<currentFileContent path=\"{file_path}\">\n{file_content}\n</currentFileContent>\n\n"

    if context_text.strip():
        prompt += f"<START_OF_CONTEXT>\n{context_text}\n<END_OF_CONTEXT>\n\n"
    else:
        prompt += "<note>Answering without retrieval augmentation.</note>\n\n"

    prompt += f"<query>\n{query}\n</query>\n\nAssistant: "
    return prompt


async def _stream_llm_response(
    websocket: WebSocket,
    model: DashscopeClient,
    model_kwargs: dict,
    prompt: str,
    page_type: Optional[str] = None,
    page_title: Optional[str] = None,
) -> Optional[str]:
    """Stream LLM response over WebSocket.

    Returns the full accumulated text on success, None on failure.
    """
    api_kwargs = model.convert_inputs_to_api_kwargs(
        input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM,
    )

    if page_type and page_title:
        await websocket.send_text(f"@@PAGE|{page_type}|{page_title}@@")

    full_text = ""

    try:
        response = await model.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        async for text in response:
            if text:
                full_text += text
                await websocket.send_text(text)
        return full_text
    except Exception as e:
        error_message = str(e)
        logger.error(f"Dashscope API error: {error_message}")

        if any(kw in error_message.lower() for kw in ("maximum context length", "token limit", "too many tokens")):
            logger.warning("Token limit exceeded, retrying without context")
            simplified_prompt = _strip_context_from_prompt(prompt)
            fallback_api_kwargs = model.convert_inputs_to_api_kwargs(
                input=simplified_prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM,
            )
            try:
                if page_type and page_title:
                    await websocket.send_text(f"@@PAGE|{page_type}|{page_title}@@")
                full_text = ""
                fallback_response = await model.acall(api_kwargs=fallback_api_kwargs, model_type=ModelType.LLM)
                async for text in fallback_response:
                    if text:
                        full_text += text
                        await websocket.send_text(text)
                return full_text
            except Exception as e2:
                logger.error(f"Dashscope API fallback error: {str(e2)}")
                await websocket.send_text(f"\nError: {str(e2)}")
                return None
        else:
            await websocket.send_text(f"\nError with Dashscope API: {error_message}")
            return None


def _strip_context_from_prompt(prompt: str) -> str:
    """Remove <START_OF_CONTEXT>...<END_OF_CONTEXT> block from prompt, replace with a note."""
    import re
    return re.sub(
        r'<START_OF_CONTEXT>.*?<END_OF_CONTEXT>\n\n',
        '<note>Answering without retrieval augmentation due to input size constraints.</note>\n\n',
        prompt,
        flags=re.DOTALL,
    )


async def _stream_deep_research(
    websocket: WebSocket,
    model: DashscopeClient,
    model_kwargs: dict,
    prompt: str,
    page_type: str,
    page_title: str,
) -> Tuple[Optional[str], str]:
    """Stream LLM, detect @@NEXT_QUERY||...@@ marker, extract next query.

    The LLM is instructed to end its response with:
      @@NEXT_QUERY||the refined question for next iteration@@

    Everything before the marker is streamed to the frontend.
    The marker and next query are stripped before returning.
    Returns (response_text, next_query). response_text is None on error.
    """
    import re

    _MARKER = "@@NEXT_QUERY||"
    _NEXT_QUERY_RE = re.compile(r'@@NEXT_QUERY\|\|(.+?)@@\s*$', re.DOTALL)

    if page_type and page_title:
        await websocket.send_text(f"@@PAGE|{page_type}|{page_title}@@")

    api_kwargs = model.convert_inputs_to_api_kwargs(
        input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM,
    )

    full_text = ""
    sent_length = 0

    try:
        response = await model.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        async for text in response:
            if text:
                full_text += text
                unsent = full_text[sent_length:]
                marker_idx = unsent.find(_MARKER)
                if marker_idx != -1:
                    if marker_idx > 0:
                        await websocket.send_text(unsent[:marker_idx])
                        sent_length += marker_idx
                    sent_length = len(full_text)
                else:
                    partial = False
                    for i in range(1, len(_MARKER)):
                        if unsent.endswith(_MARKER[:i]):
                            partial = True
                            break
                    if not partial and unsent:
                        await websocket.send_text(unsent)
                        sent_length = len(full_text)
    except Exception as e:
        logger.error(f"Deep research LLM call error: {str(e)}")
        await websocket.send_text(f"\nError: {str(e)}")
        return None, ""

    match = _NEXT_QUERY_RE.search(full_text)
    next_query = match.group(1).strip() if match else ""
    response_text = _NEXT_QUERY_RE.sub('', full_text).rstrip()

    logger.info("Deep research: response_len=%d, next_query=%s",
                len(response_text), next_query[:80] if next_query else "")
    return response_text, next_query


# =============================================================
# Normal chat handler
# =============================================================

async def handle_websocket_chat(websocket: WebSocket):
    """Handle a normal chat WebSocket connection (single Q&A, no deep research)."""
    await websocket.accept()

    try:
        request_data = await websocket.receive_json()
        request = ChatCompletionRequest(**request_data)

        # Validate
        if not request.messages or len(request.messages) == 0:
            await websocket.send_text("Error: No messages provided")
            await websocket.close()
            return

        last_message = request.messages[-1]
        if last_message.role != "user":
            await websocket.send_text("Error: Last message must be from the user")
            await websocket.close()
            return

        query = last_message.content

        # Prepare RAG
        try:
            request_rag = await _prepare_rag(request)
        except ValueError as e:
            if "No valid documents with embeddings found" in str(e):
                await websocket.send_text("Error: No valid document embeddings found. Please try again.")
            else:
                await websocket.send_text(f"Error preparing retriever: {str(e)}")
            await websocket.close()
            return
        except Exception as e:
            await websocket.send_text(f"Error preparing retriever: {str(e)}")
            await websocket.close()
            return

        # Build conversation history
        for i in range(0, len(request.messages) - 1, 2):
            if i + 1 < len(request.messages):
                u = request.messages[i]
                a = request.messages[i + 1]
                if u.role == "user" and a.role == "assistant":
                    request_rag.memory.add_dialog_turn(
                        user_query=u.content, assistant_response=a.content,
                    )
        conversation_history = _build_conversation_history(request_rag)

        # Check input size
        input_too_large = False
        if len(query) > 0:
            tokens = count_tokens(query)
            if tokens > 8000:
                input_too_large = True

        # RAG context — read top_k from DB
        from api.settings_router import read_user_top_k_from_db
        _top_k = await read_user_top_k_from_db()
        context_text = _retrieve_context(request_rag, query, request.filePath, request.language, _top_k) if not input_too_large else ""

        # Repo info (normal chat)
        repo_name = request.repo_url.split("/")[-1] if "/" in request.repo_url else request.repo_url
        repo_type = request.type or "github"
        language_code = request.language or configs["lang_config"]["default"]
        language_name = configs["lang_config"]["supported_languages"].get(language_code, "English")

        # File content
        file_content = ""
        if request.filePath:
            try:
                file_content = get_file_content(request.repo_url, request.filePath, request.type, request.token)
            except Exception as e:
                logger.error(f"Error retrieving file content: {str(e)}")

        # System prompt (normal mode only)
        system_prompt = f"""<role>
You are an expert code analyst examining the {repo_type} repository: {request.repo_url} ({repo_name}).
You provide direct, concise, and accurate information about code repositories.
You NEVER start responses with markdown headers or code fences.
IMPORTANT:You MUST respond in {language_name} language.
</role>

<guidelines>
- Answer the user's question directly without ANY preamble or filler phrases
- DO NOT include any rationale, explanation, or extra comments.
- Strictly base answers ONLY on existing code or documents
- DO NOT speculate or invent citations.
- DO NOT start with preambles like "Okay, here's a breakdown" or "Here's an explanation"
- DO NOT start with markdown headers like "## Analysis of..." or any file path references
- DO NOT start with ```markdown code fences
- DO NOT end your response with ``` closing fences
- DO NOT start by repeating or acknowledging the question
- JUST START with the direct answer to the question

<example_of_what_not_to_do>
```markdown
## Analysis of `adalflow/adalflow/datasets/gsm8k.py`

This file contains...
```
</example_of_what_not_to_do>

- Format your response with proper markdown including headings, lists, and code blocks WITHIN your answer
- For code analysis, organize your response with clear sections
- Think step by step and structure your answer logically
- Start with the most relevant information that directly addresses the user's query
- Be precise and technical when discussing code
- Your response language should be in the same language as the user's query
</guidelines>

<style>
- Use concise, direct language
- Prioritize accuracy over verbosity
- When showing code, include line numbers and file paths when relevant
- Use markdown formatting to improve readability
</style>"""

        prompt = _build_prompt(system_prompt, conversation_history, file_content, request.filePath, context_text, query)

        model_config = get_model_config(request.provider, request.model)["model_kwargs"]
        model = DashscopeClient()
        model_kwargs = {
            "model": request.model,
            "stream": True,
            "temperature": model_config["temperature"],
            "top_p": model_config["top_p"],
        }

        await _stream_llm_response(websocket, model, model_kwargs, prompt)
        await websocket.close()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in normal chat handler: {str(e)}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close()
        except Exception:
            pass


# =============================================================
# Deep Research handler (server-side iteration loop)
# =============================================================

DEEP_RESEARCH_MAX_ITERATIONS = 5

_DEEP_RESEARCH_PLAN_PROMPT = """\
<role>
You are an expert code analyst examining the {repo_type} repository: {repo_url} ({repo_name}).
You are conducting a multi-turn Deep Research process to thoroughly investigate the specific topic in the user's query.
Your goal is to provide detailed, focused information EXCLUSIVELY about this topic.
IMPORTANT:You MUST respond in {language_name} language.
</role>

<guidelines>
- This is the first iteration of a multi-turn research process focused EXCLUSIVELY on the user's query
- Start your response with "## Research Plan"
- Outline your approach to investigating this specific topic
- If the topic is about a specific file or feature, focus ONLY on that file or feature
- Clearly state the specific topic you're researching to maintain focus throughout all iterations
- Identify the key aspects you'll need to research
- Provide initial findings based on the information available
- End with "## Next Steps" indicating what you'll investigate in the next iteration
- Do NOT provide a final conclusion yet - this is just the beginning of the research
- Do NOT include general repository information unless directly relevant to the query
- Focus EXCLUSIVELY on the specific topic being researched - do not drift to related topics
- Your research MUST directly address the original question
- NEVER respond with just "Continue the research" as an answer - always provide substantive research findings
</guidelines>

<style>
- Be concise but thorough
- Use markdown formatting to improve readability
- Cite specific files and code sections when relevant
</style>

<next_query_instruction>
At the very END of your response (after all your markdown content), you MUST append the refined question for the next research iteration. Use this EXACT format, on its own line:
@@NEXT_QUERY||your refined question here@@

Rules:
- The next query MUST be a NEW, more specific question that digs deeper into one aspect
- Focus on details NOT yet covered - do NOT repeat the original query
- Write it as a natural search query that would retrieve relevant code/documentation
- Keep it concise (under 100 characters)
- Do NOT include any text after the closing @@
- Do NOT wrap it in code fences or JSON
</next_query_instruction>"""

_DEEP_RESEARCH_UPDATE_PROMPT = """\
<role>
You are an expert code analyst examining the {repo_type} repository: {repo_url} ({repo_name}).
You are currently in iteration {iteration} of a Deep Research process focused EXCLUSIVELY on the latest user query.
Your goal is to build upon previous research iterations and go deeper into this specific topic without deviating from it.
IMPORTANT:You MUST respond in {language_name} language.
</role>

<guidelines>
- CAREFULLY review the conversation history to understand what has been researched so far
- Your response MUST build on previous research iterations - do not repeat information already covered
- Identify gaps or areas that need further exploration related to this specific topic
- Focus on one specific aspect that needs deeper investigation in this iteration
- Start your response with "## Research Update {iteration}"
- Clearly explain what you're investigating in this iteration
- Provide new insights that weren't covered in previous iterations
- Do NOT include general repository information unless directly relevant to the query
- Focus EXCLUSIVELY on the specific topic being researched - do not drift to related topics
- NEVER respond with just "Continue the research" as an answer - always provide substantive research findings
- Your research MUST directly address the original question
- Maintain continuity with previous research iterations - this is a continuous investigation
</guidelines>

<style>
- Be concise but thorough
- Focus on providing new information, not repeating what's already been covered
- Use markdown formatting to improve readability
- Cite specific files and code sections when relevant
</style>

<next_query_instruction>
At the very END of your response (after all your markdown content), you MUST append the refined question for the next research iteration. Use this EXACT format, on its own line:
@@NEXT_QUERY||your refined question here@@

Rules:
- The next query MUST be a NEW question that explores an aspect NOT yet covered
- Focus on a different angle or deeper detail than previous iterations
- Do NOT repeat the original query or previous next queries
- Write it as a natural search query that would retrieve relevant code/documentation
- Keep it concise (under 100 characters)
- Do NOT include any text after the closing @@
- Do NOT wrap it in code fences or JSON
</next_query_instruction>"""

_DEEP_RESEARCH_CONCLUSION_PROMPT = """\
<role>
You are an expert code analyst examining the {repo_type} repository: {repo_url} ({repo_name}).
You are in the final iteration of a Deep Research process.
Your goal is to synthesize all previous findings and provide a comprehensive conclusion that directly addresses this specific topic and ONLY this topic.
IMPORTANT:You MUST respond in {language_name} language.
</role>

<guidelines>
- This is the final iteration of the research process
- CAREFULLY review the entire conversation history to understand all previous findings
- Synthesize ALL findings from previous iterations into a comprehensive conclusion
- Start with "## Final Conclusion"
- Your conclusion MUST directly address the original question
- Stay STRICTLY focused on the specific topic - do not drift to related topics
- Include specific code references and implementation details related to the topic
- Highlight the most important discoveries and insights about this specific functionality
- Provide a complete and definitive answer to the original question
- Do NOT include general repository information unless directly relevant to the query
- Focus exclusively on the specific topic being researched
- NEVER respond with "Continue the research" as an answer - always provide a complete conclusion
</guidelines>

<style>
- Be concise but thorough
- Use markdown formatting to improve readability
- Cite specific files and code sections when relevant
- Structure your response with clear headings
- End with actionable insights or recommendations when appropriate
</style>"""


async def handle_websocket_chat_deep_research(websocket: WebSocket):
    """Handle a deep research WebSocket connection.

    The backend receives ONE user question and internally loops through
    5 iterations (plan → 3 updates → conclusion), streaming everything
    within a single WebSocket connection with @@PAGE|type|title@@ markers.
    """
    await websocket.accept()

    try:
        request_data = await websocket.receive_json()
        request = ChatCompletionRequest(**request_data)

        # Validate
        if not request.messages or len(request.messages) == 0:
            await websocket.send_text("Error: No messages provided")
            await websocket.close()
            return

        last_message = request.messages[-1]
        if last_message.role != "user":
            await websocket.send_text("Error: Last message must be from the user")
            await websocket.close()
            return

        query = last_message.content.strip()

        # Prepare RAG once for all iterations
        try:
            request_rag = await _prepare_rag(request)
        except ValueError as e:
            if "No valid documents with embeddings found" in str(e):
                await websocket.send_text("Error: No valid document embeddings found. Please try again.")
            else:
                await websocket.send_text(f"Error preparing retriever: {str(e)}")
            await websocket.close()
            return
        except Exception as e:
            await websocket.send_text(f"Error preparing retriever: {str(e)}")
            await websocket.close()
            return

        # Repo info
        repo_name = request.repo_url.split("/")[-1] if "/" in request.repo_url else request.repo_url
        repo_type = request.type or "github"
        language_code = request.language or configs["lang_config"]["default"]
        language_name = configs["lang_config"]["supported_languages"].get(language_code, "English")

        # File content (fetch once)
        file_content = ""
        if request.filePath:
            try:
                file_content = get_file_content(request.repo_url, request.filePath, request.type, request.token)
            except Exception as e:
                logger.error(f"Error retrieving file content: {str(e)}")

        from api.settings_router import read_user_top_k_from_db
        _top_k = await read_user_top_k_from_db()

        model_config = get_model_config(request.provider, request.model)["model_kwargs"]
        model = DashscopeClient()
        model_kwargs = {
            "model": request.model,
            "stream": True,
            "temperature": model_config["temperature"],
            "top_p": model_config["top_p"],
        }

        accumulated_responses: List[str] = []
        next_queries: List[str] = []
        current_query = query

        prompt_vars = {
            "repo_type": repo_type,
            "repo_url": request.repo_url,
            "repo_name": repo_name,
            "language_name": language_name,
        }

        # --- Iteration 1: Research Plan ---
        input_too_large = count_tokens(current_query) > 8000
        context_text = _retrieve_context(request_rag, current_query, request.filePath, request.language, _top_k) if not input_too_large else ""

        system_prompt = _DEEP_RESEARCH_PLAN_PROMPT.format(**prompt_vars)
        conversation_history = ""
        prompt = _build_prompt(system_prompt, conversation_history, file_content, request.filePath, context_text, current_query)
        response_text, next_query = await _stream_deep_research(
            websocket, model, model_kwargs, prompt, "plan", "研究计划",
        )

        if response_text is None:
            await websocket.close()
            return
        accumulated_responses.append(response_text)
        next_queries.append(next_query)
        current_query = next_query or current_query

        # --- Iterations 2-4: Research Updates ---
        for iteration in range(2, DEEP_RESEARCH_MAX_ITERATIONS):
            input_too_large = count_tokens(current_query) > 8000
            context_text = _retrieve_context(request_rag, current_query, request.filePath, request.language, _top_k) if not input_too_large else ""

            prompt_vars["iteration"] = str(iteration)
            system_prompt = _DEEP_RESEARCH_UPDATE_PROMPT.format(**prompt_vars)

            conversation_history = "\n".join(
                f"<turn>\n<user>{next_queries[i - 1] if i > 0 else query}</user>\n"
                f"<assistant>{resp}</assistant>\n</turn>"
                for i, resp in enumerate(accumulated_responses)
            )

            prompt = _build_prompt(system_prompt, conversation_history, file_content, request.filePath, context_text, current_query)
            response_text, next_query = await _stream_deep_research(
                websocket, model, model_kwargs, prompt,
                "update", f"研究更新 {iteration - 1}",
            )

            if response_text is None:
                await websocket.close()
                return
            accumulated_responses.append(response_text)
            next_queries.append(next_query)
            current_query = next_query or current_query

        # --- Final iteration: Conclusion (no retrieval, use previous research) ---
        system_prompt = _DEEP_RESEARCH_CONCLUSION_PROMPT.format(**prompt_vars)

        conversation_history = "\n".join(
            f"<turn>\n<user>{next_queries[i - 1] if i > 0 else query}</user>\n"
            f"<assistant>{resp}</assistant>\n</turn>"
            for i, resp in enumerate(accumulated_responses)
        )

        prompt = _build_prompt(system_prompt, conversation_history, file_content, request.filePath, "", query)
        await _stream_llm_response(websocket, model, model_kwargs, prompt, "conclusion", "最终结论")

        await websocket.close()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in deep research handler: {str(e)}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close()
        except Exception:
            pass
