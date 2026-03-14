# 🚀 DeepWiki API

This is the backend API for DeepWiki, providing smart code analysis and AI-powered documentation generation.

## ✨ Features

- **Streaming AI Responses**: Real-time responses using Dashscope Qwen models
- **Smart Code Analysis**: Automatically analyzes GitHub repositories
- **RAG Implementation**: Retrieval Augmented Generation for context-aware responses
- **Local Storage**: All data stored locally - no cloud dependencies
- **Conversation History**: Maintains context across multiple questions

## 🔧 Quick Setup

### Step 1: Install Dependencies

```bash
# From the project root
python -m pip install poetry==2.0.1 && poetry install -C api
```

### Step 2: Set Up Environment Variables

Create a `.env` file in the project root:

```
# Required API Keys
DASHSCOPE_API_KEY=your_dashscope_api_key  # Required for Qwen models and embeddings

# Optional Dashscope Configuration
DASHSCOPE_WORKSPACE_ID=your_workspace_id  # Optional, for workspace-scoped requests

# Server Configuration
PORT=8001  # Optional, defaults to 8001
```

> 💡 **Where to get these keys:**
> - Get a Dashscope API key from [Alibaba Cloud DashScope](https://dashscope.aliyun.com/)

#### Advanced Environment Configuration

##### Provider-Based Model Selection
DeepWiki uses Dashscope as the only provider for both text generation and embeddings:

- **Dashscope (Qwen)**: Requires `DASHSCOPE_API_KEY`

##### Configuration Files
DeepWiki uses JSON configuration files to manage various system components instead of hardcoded values:

1. **`generator.json`**: Configuration for text generation models
   - Located in `api/config/` by default
   - Defines available Qwen models via Dashscope provider
   - Specifies default and available models
   - Contains model-specific parameters like temperature and top_p

2. **`embedder.json`**: Configuration for embedding models and text processing
   - Located in `api/config/` by default
   - Defines embedding models for vector storage
   - Contains retriever configuration for RAG
   - Specifies text splitter settings for document chunking

3. **`repo.json`**: Configuration for repository handling
   - Located in `api/config/` by default
   - Contains file filters to exclude certain files and directories
   - Defines repository size limits and processing rules

You can customize the configuration directory location using the environment variable:

```
DEEPWIKI_CONFIG_DIR=/path/to/custom/config/dir  # Optional, for custom config file location
```

This allows you to maintain different configurations for various environments or deployment scenarios without modifying the code.

### Step 3: Start the API Server

```bash
# From the project root
python -m api.main
```

The API will be available at `http://localhost:8001`

## 🧠 How It Works

### 1. Repository Indexing
When you provide a GitHub repository URL, the API:
- Clones the repository locally (if not already cloned)
- Reads all files in the repository
- Creates embeddings for the files using Dashscope (text-embedding-v3)
- Stores the embeddings in a local database

### 2. Smart Retrieval (RAG)
When you ask a question:
- The API finds the most relevant code snippets
- These snippets are used as context for the AI
- The AI generates a response based on this context

### 3. Real-Time Streaming
- Responses are streamed in real-time
- You see the answer as it's being generated
- This creates a more interactive experience

## 📡 API Endpoints

### GET /
Returns basic API information and available endpoints.

### POST /chat/completions/stream
Streams an AI-generated response about a GitHub repository.

**Request Body:**

```json
{
  "repo_url": "https://github.com/username/repo",
  "messages": [
    {
      "role": "user",
      "content": "What does this repository do?"
    }
  ],
  "filePath": "optional/path/to/file.py"  // Optional
}
```

**Response:**
A streaming response with the generated text.

## 📝 Example Code

```python
import requests

# API endpoint
url = "http://localhost:8001/chat/completions/stream"

# Request data
payload = {
    "repo_url": "https://github.com/AsyncFuncAI/deepwiki-open",
    "messages": [
        {
            "role": "user",
            "content": "Explain how React components work"
        }
    ]
}

# Make streaming request
response = requests.post(url, json=payload, stream=True)

# Process the streaming response
for chunk in response.iter_content(chunk_size=None):
    if chunk:
        print(chunk.decode('utf-8'), end='', flush=True)
```

## 💾 Storage

All data is stored locally on your machine:
- Cloned repositories: `~/.adalflow/repos/`
- Embeddings and indexes: `~/.adalflow/databases/`
- Generated wiki cache: `~/.adalflow/wikicache/`

No cloud storage is used - everything runs on your computer!
