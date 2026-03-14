"""Dashscope (Alibaba Cloud) ModelClient integration."""

import os
import pickle
from typing import (
    Dict,
    Optional,
    Any,
    Callable,
    Generator,
    Union,
    Literal,
    List,
    Sequence,
)

import logging
import backoff
from copy import deepcopy
from tqdm import tqdm

# optional import
from adalflow.utils.lazy_import import safe_import, OptionalPackages

openai = safe_import(OptionalPackages.OPENAI.value[0], OptionalPackages.OPENAI.value[1])

from openai import OpenAI, AsyncOpenAI, Stream
from openai import (
    APITimeoutError,
    InternalServerError,
    RateLimitError,
    UnprocessableEntityError,
    BadRequestError,
)
from openai.types import (
    Completion,
    CreateEmbeddingResponse,
)
from openai.types.chat import ChatCompletionChunk, ChatCompletion

import dashscope
from dashscope import MultiModalEmbedding, AioMultiModalEmbedding

from adalflow.core.model_client import ModelClient
from adalflow.core.types import (
    ModelType,
    EmbedderOutput,
    CompletionUsage,
    GeneratorOutput,
    Document,
    Embedding,
    EmbedderOutputType,
    EmbedderInputType,
)
from adalflow.core.component import DataComponent
from adalflow.core.embedder import (
    BatchEmbedderOutputType,
    BatchEmbedderInputType,
)
import adalflow.core.functional as F
from adalflow.components.model_client.utils import parse_embedding_response

from api.logging_config import setup_logging

# # Disable tqdm progress bars
# os.environ["TQDM_DISABLE"] = "1"

setup_logging()
log = logging.getLogger(__name__)

def get_first_message_content(completion: ChatCompletion) -> str:
    """When we only need the content of the first message."""
    log.info(f"🔍 get_first_message_content called with: {type(completion)}")
    log.debug(f"raw completion: {completion}")
    
    try:
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            choice = completion.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                content = choice.message.content
                log.info(f"✅ Successfully extracted content: {type(content)}, length: {len(content) if content else 0}")
                return content
            else:
                log.error("❌ Choice doesn't have message.content")
                return str(completion)
        else:
            log.error("❌ Completion doesn't have choices")
            return str(completion)
    except Exception as e:
        log.error(f"❌ Error in get_first_message_content: {e}")
        return str(completion)


def parse_stream_response(completion: ChatCompletionChunk) -> str:
    """Parse the response of the stream API."""
    return completion.choices[0].delta.content


def handle_streaming_response(generator: Stream[ChatCompletionChunk]):
    """Handle the streaming response."""
    for completion in generator:
        log.debug(f"Raw chunk completion: {completion}")
        parsed_content = parse_stream_response(completion)
        yield parsed_content


class DashscopeClient(ModelClient):
    """A component wrapper for the Dashscope (Alibaba Cloud) API client.

    Dashscope provides access to Alibaba Cloud's Qwen and other models through an OpenAI-compatible API.
    
    Args:
        api_key (Optional[str], optional): Dashscope API key. Defaults to None.
        workspace_id (Optional[str], optional): Dashscope workspace ID. Defaults to None.
        base_url (str): The API base URL. Defaults to "https://dashscope.aliyuncs.com/compatible-mode/v1".
        env_api_key_name (str): Environment variable name for the API key. Defaults to "DASHSCOPE_API_KEY".
        env_workspace_id_name (str): Environment variable name for the workspace ID. Defaults to "DASHSCOPE_WORKSPACE_ID".

    References:
        - Dashscope API Documentation: https://help.aliyun.com/zh/dashscope/
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace_id: Optional[str] = None,
        chat_completion_parser: Callable[[Completion], Any] = None,
        input_type: Literal["text", "messages"] = "text",
        base_url: Optional[str] = None,
        env_base_url_name: str = "DASHSCOPE_BASE_URL",
        env_api_key_name: str = "DASHSCOPE_API_KEY",
        env_workspace_id_name: str = "DASHSCOPE_WORKSPACE_ID",
    ):
        super().__init__()
        self._api_key = api_key
        self._workspace_id = workspace_id
        self._env_api_key_name = env_api_key_name
        self._env_workspace_id_name = env_workspace_id_name
        self._env_base_url_name = env_base_url_name
        self.base_url = base_url or os.getenv(self._env_base_url_name, "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.sync_client = self.init_sync_client()
        self.async_client = None
        
        # Force use of get_first_message_content to ensure string output
        self.chat_completion_parser = get_first_message_content
        self._input_type = input_type
        self._api_kwargs = {}

    def _prepare_client_config(self):
        """
        Private helper method to prepare client configuration.
        
        Returns:
            tuple: (api_key, workspace_id, base_url) for client initialization
        
        Raises:
            ValueError: If API key is not provided
        """
        api_key = self._api_key or os.getenv(self._env_api_key_name)
        workspace_id = self._workspace_id or os.getenv(self._env_workspace_id_name)
        
        if not api_key:
            raise ValueError(
                f"Environment variable {self._env_api_key_name} must be set"
            )
        
        if not workspace_id:
            log.warning(f"Environment variable {self._env_workspace_id_name} not set. Some features may not work properly.")
        
        # For Dashscope, we need to include the workspace ID in the base URL if provided
        base_url = self.base_url
        if workspace_id:
            # Add workspace ID to headers or URL as required by Dashscope
            base_url = f"{self.base_url.rstrip('/')}"
        
        return api_key, workspace_id, base_url

    def init_sync_client(self):
        api_key, workspace_id, base_url = self._prepare_client_config()
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # Store workspace_id for later use in requests
        if workspace_id:
            client._workspace_id = workspace_id
        
        return client

    def init_async_client(self):
        api_key, workspace_id, base_url = self._prepare_client_config()
        
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        # Store workspace_id for later use in requests
        if workspace_id:
            client._workspace_id = workspace_id
        
        return client

    def parse_chat_completion(
        self,
        completion: Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]],
    ) -> "GeneratorOutput":
        """Parse the completion response to a GeneratorOutput."""
        try:
            # If the completion is already a GeneratorOutput, return it directly (prevent recursion)
            if isinstance(completion, GeneratorOutput):
                return completion
            
            # Check if it's a ChatCompletion object (non-streaming response)
            if hasattr(completion, 'choices') and hasattr(completion, 'usage'):
                # ALWAYS extract the string content directly
                try:
                    # Direct extraction of message content
                    if (hasattr(completion, 'choices') and 
                        len(completion.choices) > 0 and 
                        hasattr(completion.choices[0], 'message') and 
                        hasattr(completion.choices[0].message, 'content')):
                        
                        content = completion.choices[0].message.content
                        if isinstance(content, str):
                            parsed_data = content
                        else:
                            parsed_data = str(content)
                    else:
                        # Fallback: convert entire completion to string
                        parsed_data = str(completion)
                        
                except Exception as e:
                    # Ultimate fallback
                    parsed_data = str(completion)
                
                return GeneratorOutput(
                    data=parsed_data,
                    usage=CompletionUsage(
                        completion_tokens=completion.usage.completion_tokens,
                        prompt_tokens=completion.usage.prompt_tokens,
                        total_tokens=completion.usage.total_tokens,
                    ),
                    raw_response=str(completion),
                )
            else:
                # Handle streaming response - collect all content parts into a single string
                content_parts = []
                usage_info = None
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        content_parts.append(chunk.choices[0].delta.content)
                    # Try to get usage info from the last chunk
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage_info = chunk.usage
                
                # Join all content parts into a single string
                full_content = ''.join(content_parts)
                
                # Create usage object
                usage = None
                if usage_info:
                    usage = CompletionUsage(
                        completion_tokens=usage_info.completion_tokens,
                        prompt_tokens=usage_info.prompt_tokens,
                        total_tokens=usage_info.total_tokens,
                    )
                
                return GeneratorOutput(
                    data=full_content,
                    usage=usage,
                    raw_response="streaming"
                )
        except Exception as e:
            log.error(f"Error parsing completion: {e}")
            raise

    def track_completion_usage(
        self,
        completion: Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]],
    ) -> CompletionUsage:
        """Track the completion usage."""
        if isinstance(completion, ChatCompletion):
            return CompletionUsage(
                completion_tokens=completion.usage.completion_tokens,
                prompt_tokens=completion.usage.prompt_tokens,
                total_tokens=completion.usage.total_tokens,
            )
        else:
            # For streaming, we can't track usage accurately
            return CompletionUsage(completion_tokens=0, prompt_tokens=0, total_tokens=0)

    def parse_embedding_response(
        self, response: Any
    ) -> EmbedderOutput:
        """Parse the DashScope MultiModalEmbedding response to an EmbedderOutput.

        The native dashscope response has the structure:
            response.status_code  -> int (200 on success)
            response.output.embeddings  -> list of embedding objects
            response.output.embeddings[i].embedding  -> list[float]
            response.output.embeddings[i].text_index  -> int
        """
        try:
            if response.status_code != 200:
                error_msg = f"DashScope API error {response.status_code}: {response.message}"
                log.error(f"🔍 {error_msg}")
                return EmbedderOutput(data=[], error=error_msg, raw_response=response)

            raw_embeddings = response.output.get("embeddings", [])
            data = []
            for item in raw_embeddings:
                idx = item.get("text_index", len(data))
                vec = item.get("embedding", [])
                data.append(Embedding(embedding=vec, index=idx))

            log.info(f"🔍 Number of embeddings: {len(data)}")
            if data:
                log.info(f"🔍 First embedding length: {len(data[0].embedding)}")
            return EmbedderOutput(data=data, error=None, raw_response=response)
        except Exception as e:
            log.error(f"🔍 Error parsing DashScope embedding response: {e}")
            log.error(f"🔍 Raw response details: {repr(response)}")
            return EmbedderOutput(data=[], error=str(e), raw_response=response)

    def convert_inputs_to_api_kwargs(
        self,
        input: Optional[Any] = None,
        model_kwargs: Dict = {},
        model_type: ModelType = ModelType.UNDEFINED,
    ) -> Dict:
        """Convert inputs to API kwargs."""
        final_model_kwargs = model_kwargs.copy()
        
        if model_type == ModelType.LLM:
            messages = []
            if isinstance(input, str):
                messages = [{"role": "user", "content": input}]
            elif isinstance(input, list):
                messages = input
            else:
                raise ValueError(f"Unsupported input type: {type(input)}")
            
            api_kwargs = {
                "messages": messages,
                **final_model_kwargs
            }
            
            # Add workspace ID to headers if available
            workspace_id = getattr(self.sync_client, '_workspace_id', None) or getattr(self.async_client, '_workspace_id', None)
            if workspace_id:
                # Dashscope may require workspace ID in headers
                if 'extra_headers' not in api_kwargs:
                    api_kwargs['extra_headers'] = {}
                api_kwargs['extra_headers']['X-DashScope-WorkSpace'] = workspace_id
            
            return api_kwargs
            
        elif model_type == ModelType.EMBEDDER:
            # Convert inputs to dashscope MultiModalEmbedding format: [{'text': '...'}]
            texts: List[str] = []
            if isinstance(input, list):
                for item in input:
                    if hasattr(item, 'text'):
                        texts.append(item.text)
                    elif isinstance(item, str):
                        texts.append(item)
                    else:
                        texts.append(str(item))
            elif hasattr(input, 'text'):
                texts = [input.text]
            elif isinstance(input, str):
                texts = [input]
            else:
                texts = [str(input)]

            # dashscope MultiModalEmbedding expects input as list of {'text': ...} dicts
            dashscope_input = [{'text': t} for t in texts]

            api_kwargs = {
                "input": dashscope_input,
                **final_model_kwargs
            }

            # Pass workspace ID if available
            workspace_id = (self._workspace_id or
                            os.getenv(self._env_workspace_id_name))
            if workspace_id:
                api_kwargs['workspace'] = workspace_id

            return api_kwargs
        else:
            raise ValueError(f"model_type {model_type} is not supported")

    @backoff.on_exception(
        backoff.expo,
        (
            APITimeoutError,
            InternalServerError,
            RateLimitError,
            UnprocessableEntityError,
            BadRequestError,
        ),
        max_time=5,
    )
    def call(self, api_kwargs: Dict = {}, model_type: ModelType = ModelType.UNDEFINED):
        """Call the Dashscope API."""
        if model_type == ModelType.LLM:
            if not api_kwargs.get("stream", False):
                # For non-streaming, enable_thinking must be false.
                # Pass it via extra_body to avoid TypeError from openai client validation.
                extra_body = api_kwargs.get("extra_body", {})
                extra_body["enable_thinking"] = False
                api_kwargs["extra_body"] = extra_body

            completion = self.sync_client.chat.completions.create(**api_kwargs)
            
            if api_kwargs.get("stream", False):
                return handle_streaming_response(completion)
            else:
                return self.parse_chat_completion(completion)
        elif model_type == ModelType.EMBEDDER:
            # api_kwargs["input"] is already formatted as [{'text': ...}] by
            # convert_inputs_to_api_kwargs.
            dashscope_input = api_kwargs.get("input", [])

            if not dashscope_input:
                log.warning("😭 No input texts provided")
                return EmbedderOutput(data=[], error="No input texts provided", raw_response=None)

            # Filter out entries whose 'text' field is empty
            valid_input = []
            valid_indices = []
            for i, item in enumerate(dashscope_input):
                text = item.get("text", "") if isinstance(item, dict) else ""
                if text and text.strip():
                    valid_input.append(item)
                    valid_indices.append(i)
                else:
                    log.warning(f"🔍 Skipping empty text at index {i}")

            if not valid_input:
                log.error("😭 No valid texts found after filtering")
                return EmbedderOutput(data=[], error="No valid texts found after filtering", raw_response=None)

            if len(valid_input) != len(dashscope_input):
                log.warning(
                    f"🔍 Filtered out {len(dashscope_input) - len(valid_input)} "
                    f"empty/invalid texts out of {len(dashscope_input)} total texts"
                )

            model = api_kwargs.get("model", "")
            workspace = api_kwargs.get("workspace")
            log.info(f"🔍 DashScope MultiModalEmbedding call with {len(valid_input)} texts")

            try:
                response = MultiModalEmbedding.call(
                    model=model,
                    input=valid_input,
                    api_key=self._api_key or os.getenv(self._env_api_key_name),
                    workspace=workspace,
                )
                log.info(f"🔍 DashScope API call successful, status: {response.status_code}")
                result = self.parse_embedding_response(response)

                # Re-insert zero embeddings for filtered positions
                if len(valid_input) != len(dashscope_input):
                    log.info(f"🔍 Reconstructing embeddings for {len(dashscope_input)} original positions")
                    embedding_dim = None
                    if result.data:
                        embedding_dim = len(result.data[0].embedding)
                        log.info(f"🔍 Using embedding dimension: {embedding_dim}")

                    if embedding_dim is None:
                        log.error("🔍 Cannot reconstruct embeddings: no valid embeddings returned")
                        return EmbedderOutput(
                            data=[], error="No valid embeddings returned to determine dimension",
                            raw_response=result.raw_response
                        )

                    final_data = []
                    valid_idx = 0
                    for i in range(len(dashscope_input)):
                        if i in valid_indices:
                            final_data.append(result.data[valid_idx])
                            valid_idx += 1
                        else:
                            log.warning(f"🔍 Creating zero embedding for filtered text at index {i}")
                            final_data.append(Embedding(
                                embedding=[0.0] * embedding_dim,
                                index=i
                            ))

                    result = EmbedderOutput(
                        data=final_data,
                        error=None,
                        raw_response=result.raw_response
                    )

                return result

            except Exception as e:
                log.error(f"🔍 DashScope API call failed: {e}")
                return EmbedderOutput(data=[], error=str(e), raw_response=None)
        else:
            raise ValueError(f"model_type {model_type} is not supported")

    @backoff.on_exception(
        backoff.expo,
        (
            APITimeoutError,
            InternalServerError,
            RateLimitError,
            UnprocessableEntityError,
            BadRequestError,
        ),
        max_time=5,
    )
    async def acall(
        self, api_kwargs: Dict = {}, model_type: ModelType = ModelType.UNDEFINED
    ):
        """Async call to the Dashscope API."""
        if not self.async_client:
            self.async_client = self.init_async_client()

        if model_type == ModelType.LLM:
            if not api_kwargs.get("stream", False):
                # For non-streaming, enable_thinking must be false.
                extra_body = api_kwargs.get("extra_body", {})
                extra_body["enable_thinking"] = False
                api_kwargs["extra_body"] = extra_body

            completion = await self.async_client.chat.completions.create(**api_kwargs)

            # For async calls with streaming enabled, wrap the AsyncStream
            # into an async generator of plain text chunks so that callers
            # can simply `async for text in response`.
            if api_kwargs.get("stream", False):

                async def async_stream_generator():
                    async for chunk in completion:
                        log.debug(f"Raw async chunk completion: {chunk}")
                        try:
                            parsed_content = parse_stream_response(chunk)
                        except Exception as e:
                            log.error(f"Error parsing async stream chunk: {e}")
                            parsed_content = None
                        if parsed_content:
                            yield parsed_content

                return async_stream_generator()
            else:
                return self.parse_chat_completion(completion)
        elif model_type == ModelType.EMBEDDER:
            # api_kwargs["input"] is already formatted as [{'text': ...}] by
            # convert_inputs_to_api_kwargs.
            dashscope_input = api_kwargs.get("input", [])

            if not dashscope_input:
                log.warning("😭 No input texts provided")
                return EmbedderOutput(data=[], error="No input texts provided", raw_response=None)

            # Filter out entries whose 'text' field is empty
            valid_input = []
            valid_indices = []
            for i, item in enumerate(dashscope_input):
                text = item.get("text", "") if isinstance(item, dict) else ""
                if text and text.strip():
                    valid_input.append(item)
                    valid_indices.append(i)
                else:
                    log.warning(f"🔍 Skipping empty text at index {i}")

            if not valid_input:
                log.error("😭 No valid texts found after filtering")
                return EmbedderOutput(data=[], error="No valid texts found after filtering", raw_response=None)

            if len(valid_input) != len(dashscope_input):
                log.warning(
                    f"🔍 Filtered out {len(dashscope_input) - len(valid_input)} "
                    f"empty/invalid texts out of {len(dashscope_input)} total texts"
                )

            model = api_kwargs.get("model", "")
            workspace = api_kwargs.get("workspace")
            log.info(f"🔍 DashScope async MultiModalEmbedding call with {len(valid_input)} texts")

            try:
                response = await AioMultiModalEmbedding.call(
                    model=model,
                    input=valid_input,
                    api_key=self._api_key or os.getenv(self._env_api_key_name),
                    workspace=workspace,
                )
                log.info(f"🔍 DashScope async API call successful, status: {response.status_code}")
                result = self.parse_embedding_response(response)

                # Re-insert zero embeddings for filtered positions
                if len(valid_input) != len(dashscope_input):
                    log.info(f"🔍 Reconstructing embeddings for {len(dashscope_input)} original positions")
                    embedding_dim = None
                    if result.data:
                        embedding_dim = len(result.data[0].embedding)
                        log.info(f"🔍 Using embedding dimension: {embedding_dim}")

                    if embedding_dim is None:
                        log.error("🔍 Cannot reconstruct embeddings: no valid embeddings returned")
                        return EmbedderOutput(
                            data=[], error="No valid embeddings returned to determine dimension",
                            raw_response=result.raw_response
                        )

                    final_data = []
                    valid_idx = 0
                    for i in range(len(dashscope_input)):
                        if i in valid_indices:
                            final_data.append(result.data[valid_idx])
                            valid_idx += 1
                        else:
                            log.warning(f"🔍 Creating zero embedding for filtered text at index {i}")
                            final_data.append(Embedding(
                                embedding=[0.0] * embedding_dim,
                                index=i
                            ))

                    result = EmbedderOutput(
                        data=final_data,
                        error=None,
                        raw_response=result.raw_response
                    )

                return result

            except Exception as e:
                log.error(f"🔍 DashScope async API call failed: {e}")
                return EmbedderOutput(data=[], error=str(e), raw_response=None)
        else:
            raise ValueError(f"model_type {model_type} is not supported")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create an instance from a dictionary."""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "api_key": self._api_key,
            "workspace_id": self._workspace_id,
            "base_url": self.base_url,
            "input_type": self._input_type,
        }

    def __getstate__(self):
        """
        Customize serialization to exclude non-picklable client objects.
        This method is called by pickle when saving the object's state.
        """
        state = self.__dict__.copy()
        # Remove the unpicklable client instances
        if 'sync_client' in state:
            del state['sync_client']
        if 'async_client' in state:
            del state['async_client']
        return state

    def __setstate__(self, state):
        """
        Customize deserialization to re-create the client objects.
        This method is called by pickle when loading the object's state.
        """
        self.__dict__.update(state)
        # Re-initialize the clients after unpickling
        self.sync_client = self.init_sync_client()
        self.async_client = None  # It will be lazily initialized when acall is used


class DashScopeEmbedder(DataComponent):
    r"""
    A user-facing component that orchestrates an embedder model via the DashScope model client and output processors.

    Args:
        model_client (ModelClient): The DashScope model client to use for the embedder.
        model_kwargs (Dict[str, Any], optional): The model kwargs to pass to the model client. Defaults to {}.
        output_processors (Optional[Component], optional): The output processors after model call. Defaults to None.
    """

    model_type: ModelType = ModelType.EMBEDDER
    model_client: ModelClient
    output_processors: Optional[DataComponent]

    def __init__(
        self,
        *,
        model_client: ModelClient,
        model_kwargs: Dict[str, Any] = {},
        output_processors: Optional[DataComponent] = None,
    ) -> None:

        super().__init__(model_kwargs=model_kwargs)
        if not isinstance(model_kwargs, Dict):
            raise TypeError(
                f"{type(self).__name__} requires a dictionary for model_kwargs, not a string"
            )
        self.model_kwargs = model_kwargs.copy()

        if not isinstance(model_client, ModelClient):
            raise TypeError(
                f"{type(self).__name__} requires a ModelClient instance for model_client."
            )
        self.model_client = model_client
        self.output_processors = output_processors

    def call(
        self,
        input: EmbedderInputType,
        model_kwargs: Optional[Dict] = {},
    ) -> EmbedderOutputType:
        log.debug(f"Calling {self.__class__.__name__} with input: {input}")
        api_kwargs = self.model_client.convert_inputs_to_api_kwargs(
            input=input,
            model_kwargs=self._compose_model_kwargs(**model_kwargs),
            model_type=self.model_type,
        )
        try:
            output = self.model_client.call(
                api_kwargs=api_kwargs, model_type=self.model_type
            )
        except Exception as e:
            log.error(f"🤡 Error calling the DashScope model: {e}")
            output = EmbedderOutput(error=str(e))
        return output

    async def acall(
        self,
        input: EmbedderInputType,
        model_kwargs: Optional[Dict] = {},
    ) -> EmbedderOutputType:
        log.debug(f"Calling {self.__class__.__name__} with input: {input}")
        api_kwargs = self.model_client.convert_inputs_to_api_kwargs(
            input=input,
            model_kwargs=self._compose_model_kwargs(**model_kwargs),
            model_type=self.model_type,
        )
        output: EmbedderOutputType = None
        try:
            response = await self.model_client.acall(
                api_kwargs=api_kwargs, model_type=self.model_type
            )
            output = self.model_client.parse_embedding_response(response)
        except Exception as e:
            log.error(f"Error calling the DashScope model: {e}")
            output = EmbedderOutput(error=str(e))

        output.input = [input] if isinstance(input, str) else input
        log.debug(f"Output from {self.__class__.__name__}: {output}")
        return output

    def _compose_model_kwargs(self, **model_kwargs) -> Dict[str, object]:
        return F.compose_model_kwargs(self.model_kwargs, model_kwargs)

# Batch Embedding Components for DashScope
class DashScopeBatchEmbedder(DataComponent):
    """Batch embedder specifically designed for DashScope API"""

    def __init__(self, embedder, batch_size: int = 100, embedding_cache_file_name: str = "default") -> None:
        super().__init__(batch_size=batch_size)
        self.embedder = embedder
        self.batch_size = batch_size
        if self.batch_size > 25:
            log.warning(f"DashScope batch embedder initialization, batch size: {self.batch_size}, note that DashScope batch embedding size cannot exceed 25, automatically set to 25")
            self.batch_size = 25
        self.cache_path = f'./embedding_cache/{embedding_cache_file_name}_{self.embedder.__class__.__name__}_dashscope_embeddings.pkl'

    def call(
        self, input: BatchEmbedderInputType, model_kwargs: Optional[Dict] = {}, force_recreate: bool = False
    ) -> BatchEmbedderOutputType:
        """
        Batch call to DashScope embedder
        
        Args:
            input: List of input texts
            model_kwargs: Model parameters
            force_recreate: Whether to force recreation
            
        Returns:
            Batch embedding output
        """
        # Check cache first
        
        if not force_recreate and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'rb') as f:
                    embeddings = pickle.load(f)
                    log.info(f"Loaded cached DashScope embeddings from: {self.cache_path}")
                return embeddings
            except Exception as e:
                log.warning(f"Failed to load cache file {self.cache_path}: {e}, proceeding with fresh embedding")
        
        if isinstance(input, str):
            input = [input]
        
        n = len(input)
        embeddings: List[EmbedderOutput] = []
        
        log.info(f"Starting DashScope batch embedding processing, total {n} texts, batch size: {self.batch_size}")
        
        for i in tqdm(
            range(0, n, self.batch_size),
            desc="DashScope batch embedding",
            disable=False,
        ):
            batch_input = input[i : min(i + self.batch_size, n)]
            
            try:
                # Use correct calling method: directly call embedder instance
                batch_output = self.embedder(
                    input=batch_input, model_kwargs=model_kwargs
                )
                embeddings.append(batch_output)
                
                # Validate batch output
                if batch_output.error:
                    log.error(f"Batch {i//self.batch_size + 1} embedding failed: {batch_output.error}")
                elif batch_output.data:
                    log.debug(f"Batch {i//self.batch_size + 1} successfully generated {len(batch_output.data)} embedding vectors")
                else:
                    log.warning(f"Batch {i//self.batch_size + 1} returned no embedding data")
                    
            except Exception as e:
                log.error(f"Batch {i//self.batch_size + 1} processing exception: {e}")
                # Create error embedding output
                error_output = EmbedderOutput(
                    data=[],
                    error=str(e),
                    raw_response=None
                )
                embeddings.append(error_output)
        
        log.info(f"DashScope batch embedding completed, processed {len(embeddings)} batches")
        
        # Save to cache
        try:
            if not os.path.exists('./embedding_cache'):
                os.makedirs('./embedding_cache')
            with open(self.cache_path, 'wb') as f:
                pickle.dump(embeddings, f)
                log.info(f"Saved DashScope embeddings cache to: {self.cache_path}")
        except Exception as e:
            log.warning(f"Failed to save cache to {self.cache_path}: {e}")
        
        return embeddings
    
    def __call__(self, input: BatchEmbedderInputType, model_kwargs: Optional[Dict] = {}, force_recreate: bool = False) -> BatchEmbedderOutputType:
        """
        Call operator interface, delegates to call method
        """
        return self.call(input=input, model_kwargs=model_kwargs, force_recreate=force_recreate)


class DashScopeToEmbeddings(DataComponent):
    """Component that converts document sequences to embedding vector sequences, specifically optimized for DashScope API"""

    def __init__(self, embedder, batch_size: int = 100, force_recreate_db: bool = False, embedding_cache_file_name: str = "default") -> None:
        super().__init__(batch_size=batch_size)
        self.embedder = embedder
        self.batch_size = batch_size
        self.batch_embedder = DashScopeBatchEmbedder(embedder=embedder, batch_size=batch_size, embedding_cache_file_name=embedding_cache_file_name)
        self.force_recreate_db = force_recreate_db

    def __call__(self, input: List[Document]) -> List[Document]:
        """
        Process list of documents, generating embedding vectors for each document
        
        Args:
            input: List of input documents
            
        Returns:
            List of documents containing embedding vectors
        """
        output = deepcopy(input)
        
        # Convert to text list
        embedder_input: List[str] = [chunk.text for chunk in output]
        
        log.info(f"Starting to process embeddings for {len(embedder_input)} documents")
        
        # Batch process embeddings
        outputs: List[EmbedderOutput] = self.batch_embedder(
            input=embedder_input, 
            force_recreate=self.force_recreate_db
        )
        
        # Validate output
        total_embeddings = 0
        error_batches = 0
        
        for batch_output in outputs:
            if batch_output.error:
                error_batches += 1
                log.error(f"Found error batch: {batch_output.error}")
            elif batch_output.data:
                total_embeddings += len(batch_output.data)
            
        log.info(f"Embedding statistics: total {total_embeddings} valid embeddings, {error_batches} error batches")
        
        # Assign embedding vectors back to documents
        doc_idx = 0
        for batch_idx, batch_output in tqdm(
            enumerate(outputs), 
            desc="Assigning embedding vectors to documents",
            disable=False
        ):
            if batch_output.error:
                # Create empty vectors for documents in error batches
                batch_size_actual = min(self.batch_size, len(output) - doc_idx)
                log.warning(f"Creating empty vectors for {batch_size_actual} documents in batch {batch_idx}")
                
                for i in range(batch_size_actual):
                    if doc_idx < len(output):
                        output[doc_idx].vector = []
                        doc_idx += 1
            else:
                # Assign normal embedding vectors
                for embedding in batch_output.data:
                    if doc_idx < len(output):
                        if hasattr(embedding, 'embedding'):
                            output[doc_idx].vector = embedding.embedding
                        else:
                            log.warning(f"Invalid embedding format for document {doc_idx}")
                            output[doc_idx].vector = []
                        doc_idx += 1
        
        # Validate results
        valid_count = 0
        empty_count = 0
        
        for doc in output:
            if hasattr(doc, 'vector') and doc.vector and len(doc.vector) > 0:
                valid_count += 1
            else:
                empty_count += 1
        
        log.info(f"Embedding results: {valid_count} valid vectors, {empty_count} empty vectors")
        
        if valid_count == 0:
            log.error("❌ All documents have empty embedding vectors!")
        elif empty_count > 0:
            log.warning(f"⚠️ Found {empty_count} empty embedding vectors")
        else:
            log.info("✅ All documents successfully generated embedding vectors")
        
        return output

    def _extra_repr(self) -> str:
        return f"batch_size={self.batch_size}" 