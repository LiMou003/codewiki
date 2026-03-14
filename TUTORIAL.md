# CodeWiki 项目启动指南

本文档介绍如何在本地或通过 Docker 启动 **CodeWiki** 项目，包括所需依赖的安装、配置文件的编写以及各服务的启动方法。

---

## 目录

1. [项目简介](#1-项目简介)
2. [环境要求](#2-环境要求)
3. [获取代码](#3-获取代码)
4. [配置环境变量（`.env`）](#4-配置环境变量env)
5. [配置文件说明](#5-配置文件说明)
   - [5.1 生成模型配置（`generator.json`）](#51-生成模型配置generatorjson)
   - [5.2 向量化模型配置（`embedder.json`）](#52-向量化模型配置embedderjson)
   - [5.3 仓库过滤配置（`repo.json`）](#53-仓库过滤配置repojson)
6. [安装 Python 后端依赖](#6-安装-python-后端依赖)
7. [安装前端依赖](#7-安装前端依赖)
8. [启动 Qdrant 向量数据库](#8-启动-qdrant-向量数据库)
9. [启动后端服务](#9-启动后端服务)
10. [启动前端服务](#10-启动前端服务)
11. [使用 Docker Compose 一键启动](#11-使用-docker-compose-一键启动)
12. [向量化模型方案选择](#12-向量化模型方案选择)
    - [方案 A：DashScope（阿里云，默认）](#方案-a-dashscope阿里云默认)
    - [方案 B：OpenAI Embedding](#方案-b-openai-embedding)
    - [方案 C：Google Gemini Embedding](#方案-c-google-gemini-embedding)
    - [方案 D：本地 Ollama Embedding](#方案-d-本地-ollama-embedding)
13. [代码切分（Tree-sitter AST）说明](#13-代码切分tree-sitter-ast说明)
14. [故障排除](#14-故障排除)

---

## 1. 项目简介

CodeWiki 基于 [DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open) 二次开发，在原版基础上做了以下三项关键改进：

| 模块 | 原版 DeepWiki-Open | 本项目（CodeWiki） |
|------|-------------------|--------------------|
| **代码切分** | 按词（word）固定长度切分 | **Tree-sitter AST** 语法树切分，精准提取函数/类/方法 |
| **向量化模型** | OpenAI `text-embedding-3-small` | **DashScope `qwen3-vl-embedding`**（默认），同时支持 OpenAI / Google / Ollama |
| **向量数据库** | FAISS（本地文件） | **Qdrant**（支持内存模式和独立服务两种模式） |

---

## 2. 环境要求

在开始之前，请确保您的机器已安装以下软件：

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.12 | 后端运行时（`.python-version` 中指定） |
| Node.js | 18+ | 前端运行时 |
| npm 或 Yarn | 任意 | 前端包管理器（推荐 Yarn 1.x） |
| Git | 任意 | 克隆仓库 |
| Docker & Docker Compose | 任意 | **仅 Docker 部署时需要** |

> **提示**：推荐使用 [pyenv](https://github.com/pyenv/pyenv) 管理 Python 版本，使用 [nvm](https://github.com/nvm-sh/nvm) 管理 Node 版本。

---

## 3. 获取代码

```bash
git clone https://github.com/LiMou003/codewiki.git
cd codewiki
```

---

## 4. 配置环境变量（`.env`）

在项目**根目录**创建 `.env` 文件。根据您使用的模型提供商，按需填写相应密钥。

```dotenv
# ============================================================
# 必填：至少配置一个生成模型的 API Key
# ============================================================

# DashScope（阿里云通义千问）—— 默认生成模型提供商
DASHSCOPE_API_KEY=your_dashscope_api_key

# Google Gemini（可选）
GOOGLE_API_KEY=your_google_api_key

# OpenAI（可选）
OPENAI_API_KEY=your_openai_api_key

# OpenRouter（可选）
OPENROUTER_API_KEY=your_openrouter_api_key

# ============================================================
# 向量化模型（Embedding）—— 根据 embedder.json 中的配置决定
# ============================================================
# 使用 DashScope Embedding（默认）：需要 DASHSCOPE_API_KEY（同上）
# 使用 OpenAI Embedding：需要 OPENAI_API_KEY（同上），可选自定义端点：
# OPENAI_BASE_URL=https://your-custom-openai-endpoint.com/v1
# 使用 Google Gemini Embedding：需要 GOOGLE_API_KEY（同上）
# 使用本地 Ollama Embedding：无需 API Key，可选配置 Ollama 服务地址：
# OLLAMA_HOST=http://localhost:11434

# ============================================================
# Qdrant 向量数据库（可选）
# ============================================================
# 不配置时使用内存模式（进程结束后数据丢失，仅适合测试）
# 配置后数据持久化到 Qdrant 服务
QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=your_qdrant_api_key   # 仅需认证时填写

# ============================================================
# AWS Bedrock（可选）
# ============================================================
# AWS_ACCESS_KEY_ID=your_aws_access_key_id
# AWS_SECRET_ACCESS_KEY=your_aws_secret_key
# AWS_REGION=us-east-1
# AWS_ROLE_ARN=your_aws_role_arn

# ============================================================
# 服务配置（可选）
# ============================================================
PORT=8001                         # 后端 API 端口，默认 8001
LOG_LEVEL=INFO                    # 日志级别：DEBUG / INFO / WARNING / ERROR
LOG_FILE_PATH=api/logs/app.log    # 日志文件路径

# ============================================================
# 授权模式（可选）
# ============================================================
# 启用后，前端生成 Wiki 需要输入授权码
# DEEPWIKI_AUTH_MODE=true
# DEEPWIKI_AUTH_CODE=your_secret_code

# ============================================================
# 高级：自定义配置文件目录（可选）
# ============================================================
# 不填则使用项目默认的 api/config/ 目录
# DEEPWIKI_CONFIG_DIR=/path/to/custom/config/dir

# ============================================================
# 高级：向量化模型类型覆盖（可选）
# ============================================================
# 默认读取 embedder.json 中的 "embedder" 配置
# 可设为 dashscope / openai / google / ollama / bedrock 来强制指定
# DEEPWIKI_EMBEDDER_TYPE=dashscope
```

> **API Key 获取途径：**
> - DashScope：[阿里云 DashScope 控制台](https://dashscope.aliyuncs.com/)
> - Google：[Google AI Studio](https://makersuite.google.com/app/apikey)
> - OpenAI：[OpenAI Platform](https://platform.openai.com/api-keys)
> - OpenRouter：[OpenRouter Keys](https://openrouter.ai/keys)

---

## 5. 配置文件说明

所有配置文件位于 `api/config/` 目录。您可以直接修改它们，或通过 `DEEPWIKI_CONFIG_DIR` 环境变量指向自定义目录。

### 5.1 生成模型配置（`generator.json`）

文件路径：`api/config/generator.json`

该文件定义了可用的**文本生成模型**提供商及其默认模型。

```json
{
  "default_provider": "dashscope",   // 默认提供商，可改为 google / openai / openrouter / ollama / bedrock / azure
  "providers": {
    "dashscope": {
      "default_model": "qwen-plus",
      "supportsCustomModel": true,
      "models": {
        "qwen-plus":   { "temperature": 0.7, "top_p": 0.8 },
        "qwen-turbo":  { "temperature": 0.7, "top_p": 0.8 },
        "deepseek-r1": { "temperature": 0.7, "top_p": 0.8 }
      }
    },
    "google": {
      "default_model": "gemini-2.5-flash",
      ...
    },
    "openai": {
      "default_model": "gpt-5-nano",
      ...
    },
    "ollama": { ... },
    "openrouter": { ... },
    "bedrock": { ... },
    "azure": { ... }
  }
}
```

**常见修改场景：**

- 切换默认提供商：将 `"default_provider"` 改为目标提供商名称（如 `"google"`）。
- 添加自定义模型：在对应提供商的 `"models"` 对象中新增条目。
- 调整生成参数：修改 `temperature`、`top_p` 等参数值。

### 5.2 向量化模型配置（`embedder.json`）

文件路径：`api/config/embedder.json`

该文件配置**向量化（Embedding）模型**及 RAG 检索参数。

```json
{
  "embedder": {
    "client_class": "DashscopeClient",    // 当前使用的 Embedding 客户端
    "batch_size": 25,
    "model_kwargs": {
      "model": "qwen3-vl-embedding"
    }
  },
  "retriever": {
    "top_k": 20                            // RAG 检索返回的最大文档片段数
  },
  "text_splitter": {
    "split_by": "word",
    "chunk_size": 350,
    "chunk_overlap": 100
  }
}
```

> **注意**：`text_splitter` 配置用于非代码文件（Markdown、文本等）的固定长度切分。对于代码文件，项目会优先使用 Tree-sitter AST 切分（见[第 13 节](#13-代码切分tree-sitter-ast说明)），`text_splitter` 仅作为回退方案。

切换不同 Embedding 提供商的方法详见[第 12 节](#12-向量化模型方案选择)。

### 5.3 仓库过滤配置（`repo.json`）

文件路径：`api/config/repo.json`

该文件控制在索引仓库时**排除哪些文件和目录**，以及仓库大小限制。

```json
{
  "file_filters": {
    "excluded_dirs": [
      "./.venv/", "./node_modules/", "./.git/", ...
    ],
    "excluded_files": [
      "yarn.lock", "*.min.js", "*.pyc", ...
    ]
  },
  "repository": {
    "max_size_mb": 50000    // 允许处理的仓库最大大小（MB）
  }
}
```

通常情况下无需修改此文件。如需排除项目中特定的大文件或目录，可在 `excluded_files` / `excluded_dirs` 中追加条目。

---

## 6. 安装 Python 后端依赖

后端使用 **Poetry** 管理依赖，或使用 **uv** 作为更快的替代方案。

### 方式一：使用 Poetry（推荐）

```bash
# 安装 Poetry（如已安装可跳过）
pip install poetry==2.0.1

# 进入 api/ 目录安装依赖
poetry install -C api
```

### 方式二：使用 uv

```bash
# 安装 uv（如已安装可跳过）
pip install uv

# 安装依赖
uv sync
```

### 方式三：直接 pip 安装

```bash
pip install -r api/requirements.txt
```

> **关键依赖说明：**
>
> | 依赖包 | 用途 |
> |-------|------|
> | `fastapi` / `uvicorn` | 后端 Web 框架 |
> | `tree-sitter` + `tree-sitter-python` 等 | AST 代码切分 |
> | `qdrant-client` | Qdrant 向量数据库客户端 |
> | `adalflow` | RAG 框架（Embedding + 检索） |
> | `openai` | OpenAI / DashScope / 自定义端点客户端 |
> | `ollama` | 本地 Ollama 模型客户端 |
> | `tiktoken` | Token 计数 |

---

## 7. 安装前端依赖

前端使用 **Next.js 15**，需要 Node.js 18+。

```bash
# 使用 Yarn（推荐，package.json 中指定了 Yarn 为包管理器）
yarn install

# 或使用 npm
npm install
```

---

## 8. 启动 Qdrant 向量数据库

本项目使用 **Qdrant** 作为向量数据库。如果不启动独立的 Qdrant 服务，代码会自动使用**内存模式**（数据在进程退出后丢失，仅适合快速测试）。

**生产/开发推荐：启动独立 Qdrant 服务以持久化数据。**

### 方式一：Docker 启动（推荐）

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest
```

启动后在 `.env` 中配置：

```dotenv
QDRANT_URL=http://localhost:6333
```

### 方式二：通过 Docker Compose 启动（与应用一同启动，见第 11 节）

### 方式三：使用内存模式（无需任何配置，仅供测试）

不设置 `QDRANT_URL` 环境变量，程序将自动使用内存实例，数据不会持久化。

---

## 9. 启动后端服务

确保已完成依赖安装（第 6 节）并配置好 `.env` 文件（第 4 节）。

```bash
# 方式一：使用 Python 模块（推荐）
python -m api.main

# 方式二：使用 uv
uv run -m api.main

# 方式三：使用 Poetry
poetry run -C api python -m api.main
```

后端服务默认监听 `http://localhost:8001`。

启动成功后，您可以访问 `http://localhost:8001/health` 检查健康状态。

---

## 10. 启动前端服务

确保已完成前端依赖安装（第 7 节）。

```bash
# 开发模式（支持热重载）
yarn dev
# 或
npm run dev

# 生产模式
yarn build && yarn start
# 或
npm run build && npm start
```

前端默认监听 `http://localhost:3000`。

打开浏览器访问 [http://localhost:3000](http://localhost:3000)，输入 GitHub / GitLab / Bitbucket 仓库地址，点击"生成 Wiki"即可开始使用。

---

## 11. 使用 Docker Compose 一键启动

如果您希望通过 Docker 快速部署整个项目（包括 Qdrant 服务），请按以下步骤操作：

### 步骤 1：确保 `.env` 文件已配置

参考[第 4 节](#4-配置环境变量env)创建并填写 `.env` 文件。Docker Compose 会自动读取该文件中的环境变量。

### 步骤 2：构建并启动所有服务

```bash
docker-compose up --build
```

这将同时启动：
- **qdrant** 服务（向量数据库，端口 6333 / 6334）
- **deepwiki** 服务（后端 API 端口 8001 + 前端端口 3000）

### 步骤 3：停止服务

```bash
docker-compose down
```

### 数据持久化

`docker-compose.yml` 配置了以下挂载点：

| 主机路径 | 容器路径 | 说明 |
|---------|---------|------|
| `~/.adalflow` | `/root/.adalflow` | 克隆的仓库、Embedding 缓存、Wiki 缓存 |
| `./api/logs` | `/app/api/logs` | 后端日志文件 |
| `qdrant_data`（Docker 卷） | `/qdrant/storage` | Qdrant 向量数据 |

即使容器停止或重启，数据也会保留在主机上。

---

## 12. 向量化模型方案选择

本项目支持多种 Embedding 模型，通过修改 `api/config/embedder.json` 切换。

### 方案 A：DashScope（阿里云，默认）

`api/config/embedder.json`（默认内容即为此方案）：

```json
{
  "embedder": {
    "client_class": "DashscopeClient",
    "batch_size": 25,
    "model_kwargs": {
      "model": "qwen3-vl-embedding"
    }
  },
  "embedder_dashscope": {
    "client_class": "DashscopeClient",
    "batch_size": 25,
    "model_kwargs": {
      "model": "qwen3-vl-embedding"
    }
  },
  "retriever": { "top_k": 20 },
  "text_splitter": { "split_by": "word", "chunk_size": 350, "chunk_overlap": 100 }
}
```

**所需环境变量：**

```dotenv
DASHSCOPE_API_KEY=your_dashscope_api_key
```

---

### 方案 B：OpenAI Embedding

将 `api/config/embedder.json` 中的 `embedder` 改为：

```json
{
  "embedder": {
    "client_class": "OpenAIClient",
    "batch_size": 500,
    "model_kwargs": {
      "model": "text-embedding-3-small",
      "dimensions": 256,
      "encoding_format": "float"
    }
  },
  "retriever": { "top_k": 20 },
  "text_splitter": { "split_by": "word", "chunk_size": 350, "chunk_overlap": 100 }
}
```

**所需环境变量：**

```dotenv
OPENAI_API_KEY=your_openai_api_key
# 可选：自定义 API 端点（如使用第三方 OpenAI 兼容服务）
# OPENAI_BASE_URL=https://your-custom-endpoint.com/v1
```

如果您使用**阿里云 Qwen 等 OpenAI 兼容接口**，还可以直接使用项目提供的备用配置：

```bash
cp api/config/embedder.openai_compatible.json.bak api/config/embedder.json
```

然后在 `.env` 中配置 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。

---

### 方案 C：Google Gemini Embedding

将 `api/config/embedder.json` 中的 `embedder` 改为：

```json
{
  "embedder": {
    "client_class": "GoogleEmbedderClient",
    "batch_size": 100,
    "model_kwargs": {
      "model": "gemini-embedding-001",
      "task_type": "SEMANTIC_SIMILARITY"
    }
  },
  "retriever": { "top_k": 20 },
  "text_splitter": { "split_by": "word", "chunk_size": 350, "chunk_overlap": 100 }
}
```

**所需环境变量：**

```dotenv
GOOGLE_API_KEY=your_google_api_key
```

---

### 方案 D：本地 Ollama Embedding

适合完全离线、私有化部署的场景。使用项目提供的备用配置文件：

```bash
cp api/config/embedder.ollama.json.bak api/config/embedder.json
```

该文件内容如下：

```json
{
  "embedder": {
    "client_class": "OllamaClient",
    "model_kwargs": {
      "model": "nomic-embed-text"
    }
  },
  "retriever": { "top_k": 20 },
  "text_splitter": { "split_by": "word", "chunk_size": 350, "chunk_overlap": 100 }
}
```

**前提条件：** 需要先在本机安装并运行 Ollama，然后拉取 Embedding 模型：

```bash
# 安装 Ollama（Linux）
curl -fsSL https://ollama.com/install.sh | sh

# 拉取 Embedding 模型
ollama pull nomic-embed-text
```

**可选环境变量（Ollama 不在本机时）：**

```dotenv
OLLAMA_HOST=http://your-ollama-server:11434
```

详细的 Ollama 使用指南请参阅项目根目录的 `Ollama-instruction.md`。

---

## 13. 代码切分（Tree-sitter AST）说明

本项目将原版的固定长度切分替换为 **Tree-sitter AST 语法树切分**，可以更精准地识别代码结构。

### 工作原理

对于支持的编程语言，系统会解析源代码的语法树，将函数、类、方法等语义单元提取为独立的代码片段（`CodeChunk`），每个片段携带以下元数据：

- `file_path`：文件路径
- `language`：编程语言
- `chunk_type`：片段类型（`function` / `class` / `method` / `fixed_length`）
- `function_name` / `class_name`：所属函数或类名称
- `start_line` / `end_line`：起止行号

### 支持的语言

| 语言 | 文件扩展名 |
|-----|-----------|
| Python | `.py` |
| JavaScript | `.js`, `.jsx` |
| TypeScript | `.ts`, `.tsx` |
| Java | `.java` |
| Go | `.go` |
| Rust | `.rs` |
| C / C++ | `.c`, `.h`, `.cpp`, `.cc`, `.hpp` |
| C# | `.cs` |

对于不支持的语言或非代码文件（如 Markdown、JSON），系统会自动回退到固定长度字符切分。

### 相关 Python 依赖

AST 切分依赖以下 tree-sitter 包，安装后端依赖（`poetry install`）时会自动安装：

```
tree-sitter >= 0.21.0
tree-sitter-python
tree-sitter-javascript
tree-sitter-typescript
tree-sitter-java
tree-sitter-go
tree-sitter-rust
tree-sitter-cpp
tree-sitter-c
tree-sitter-c-sharp
```

---

## 14. 故障排除

### 后端无法启动

| 错误信息 | 可能原因 | 解决方案 |
|---------|---------|---------|
| `ModuleNotFoundError: No module named 'api'` | 未从项目根目录运行 | 在项目根目录执行 `python -m api.main` |
| `ImportError: qdrant-client is required` | 未安装 qdrant-client | 执行 `pip install qdrant-client` 或重新 `poetry install` |
| `ImportError: No module named 'tree_sitter'` | tree-sitter 未安装 | 执行 `pip install tree-sitter` 或重新 `poetry install` |
| `KeyError: DASHSCOPE_API_KEY` | 未配置 API Key | 检查 `.env` 文件是否存在且包含正确的 Key |

### 前端无法访问后端

- 确认后端服务正在运行：`curl http://localhost:8001/health`
- 确认端口未被防火墙拦截
- 默认后端端口为 `8001`，前端配置的 API 地址也应为该端口

### Qdrant 连接失败

- 确认 Qdrant 服务正在运行：`curl http://localhost:6333/healthz`
- 检查 `.env` 中 `QDRANT_URL` 的值是否正确
- 如果不需要持久化，可以删除 `.env` 中的 `QDRANT_URL`，程序将使用内存模式

### Embedding 调用失败

- 确认已配置对应提供商的 API Key
- 检查 `api/config/embedder.json` 中的 `client_class` 与所用提供商是否一致
- 对于 DashScope，确认账户余额充足

### Wiki 生成失败或质量差

- 尝试使用较小的仓库（文件数少于 500 个）进行测试
- 检查 `api/logs/` 目录下的日志文件获取详细错误信息
- 确认生成模型的 API Key 有效且有足够配额

### Docker 相关问题

- 容器内存不足：`docker-compose.yml` 已配置 `mem_limit: 6g`，确保主机有足够内存
- 数据无法持久化：确认 `~/.adalflow` 目录存在且有读写权限
- 端口冲突：修改 `.env` 中的 `PORT` 变量，以及 `docker-compose.yml` 中对应的端口映射

---

如需进一步了解项目功能，请参阅：

- 主要文档：[README.zh.md](./README.zh.md)
- Ollama 本地模型指南：[Ollama-instruction.md](./Ollama-instruction.md)
- 后端 API 文档：[api/README.md](./api/README.md)
