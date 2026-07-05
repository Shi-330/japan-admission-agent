# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Japan-Admission-Agent is an AI chatbot for Japanese university admission consulting. It uses a LangChain ReAct agent with RAG (pgvector on Supabase), user profiles (Supabase), web search, and report generation. The primary frontend is Streamlit; a FastAPI + React decoupled variant is in progress.

## Commands

```bash
# Streamlit app (primary)
streamlit run app.py

# FastAPI backend (decoupled mode)
uvicorn backend.api.server:app --host 0.0.0.0 --port 8000 --reload

# React frontend (decoupled mode)
cd frontend && npm install && npm run dev      # dev server on :5173
cd frontend && npm run build && npm run preview  # production

# Tests
pytest                                  # all tests
pytest tests/test_profile_manager.py    # single file
```

## Architecture

The project has two runtime modes sharing the same agent core:

### Streamlit Mode (primary)
```
app.py → views/auth_pages.py (login/register via Supabase Auth)
       → views/main_agent.py (chat UI + dashboard)
              → agent/react_agent.py (ReAct agent with 7 tools)
              → user/profile_manager.py (Supabase CRUD)
```

### FastAPI + React Mode (in progress)
```
frontend/ (React 19 + Vite + Tailwind) → SSE → backend/api/server.py (:8000)
                                                   → backend/core/agent.py (HeadlessAgent wrapper)
```

### Core Agent (`agent/react_agent.py`)

`ReactAgent` is initialized with a `user_profile` dict. On each user query, it runs a **decision engine** (`make_decision`) before execution that classifies intent into 4 categories: `[ANSWER]` (respond directly), `[UPDATE_PLAN]` (RAG retrieval needed), `[MISSING_INFO]` (prompt user for profile data), or `[REPORT]` (generate a full planning report). Decisions are cached via `DecisionCache` (LRU + 30-min TTL in `agent/memory.py`).

Execution uses LangChain `create_agent` with `astream_events` for streaming. Middleware (`agent/tools/middleware.py`) hooks tool calls, model invocations, and dynamically swaps the system prompt when report generation is triggered.

### Tools (7 total, in `agent/tools/agent_tools.py`)
- `rag_fetch_context` — private knowledge base retrieval via Supabase pgvector
- `web_search_tool` — DuckDuckGo web search
- `get_current_month` — returns YYYY-MM
- `generate_external_data` / `fetch_external_data` — CSV-based data lookups
- `fill_context_for_report` — signal tool that triggers report-mode prompt switching via middleware
- `update_report_suggestions` — persists generated reports to Supabase `user_profiles`

### Model Factory (`model/factory.py`)

Abstract factory pattern. `ChatModelFactory` produces `ChatOpenAI` pointed at Alibaba DashScope's coding plan (`https://coding.dashscope.aliyuncs.com/v1`) using `OPENAI_API_KEY`. `EmbeddingModelFactory` produces `DashScopeEmbeddings` using `DASHSCOPE_API_KEY`. Both are instantiated as module-level singletons (`chat_model`, `embedding_model`).

### RAG (`rag/rag_service.py`, `rag/vector_store.py`)

Uses `SupabaseVectorStore` (PostgreSQL pgvector). Documents are chunked via `RecursiveCharacterTextSplitter` (chunk_size: 200, overlap: 20) with MD5 deduplication. The `match_documents` SQL function does cosine similarity search.

### User Profiles (`user/profile_manager.py`)

Pydantic `UserProfile` model stored in Supabase `user_profiles` table. Fields: `jlpt_level`, `eju_score`, `gpa`, `target_major`, `undergraduate_school`, `english_score`, `report_suggestions`. Profile data is injected into the agent's system prompt dynamically.

## Key Patterns

- **All external state in Supabase**: auth, user profiles, prompt templates (`prompts` table), and RAG vectors (`documents` table with pgvector). No local database.
- **Prompt loading**: Fetched from Supabase `prompts` table (active version) via `utils/prompt_loader.py`, with local YAML fallback in `config/prompts.yml`.
- **Caching**: Decision cache (LRU+TTL), RAG context cache (dict by query hash), web search cache (dict), and prompt cache (cachetools TTL). All in-memory.
- **Centralized paths**: `utils/path_tool.py` provides `get_abs_path()` for resolving relative paths from any module.
- **Agent modules must not import Streamlit**: `agent/`, `rag/`, `user/`, `utils/` are kept Streamlit-free so the decoupled FastAPI backend can use them directly.

## Configuration

- `.env` — `OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
- `config/rag.yml` — model names and chunking parameters
- `config/agent.yml` — external data paths
- Model is `qwen3.5-plus` via DashScope coding plan; embeddings via `text-embedding-v4`

## V2 方向（2026.07）

V1 的核心问题是 **ReAct 不适合确定性业务流程**——日本升学咨询的步骤是已知的，不需要 Agent 在中间"思考"用什么 tool。V2 的核心转变：从匹配工具 → 项目管理系统。

### 为什么需要专用 Agent（不是通用 Chat）

1. **长期记忆**：记住学生的 JLPT 从 N2 考到 N1、三个月前套磁的教授回复了什么。
2. **私有数据库**：学长真实案例，公开数据没有，通用 AI 拿不到。
3. **当学生的手**：不只是告诉你怎么写，是帮你发出去、追踪回复、提醒下一步。

### V2 Todo 依赖树

```
V2.1 ───────── 用户画像升级（对话中自然积累 + 显式更新优先）
    │
    ├──→ V2.5 ── 前端适配（看板式 UI：阶段进度 + 操作区 + 问答）
    │
V2.2 ───────── 状态机引擎（阶段锁定 + 倒计时 + 确定性流转）
    │
    ├──→ V2.5 ── 前端适配
    ├──→ V2.6 ── 邮件自动化（OAuth + 草稿 + 确认 + 追踪）
    │
V2.3 ───────── 私有案例库（学长 Timeline + 教授信息 + 结果）
    │
    ├──→ V2.5 ── 前端适配
    ├──→ V2.4 ── 混合检索（元数据 + 向量 + BM25）
    └──→ V2.6 ── 邮件自动化

并行：
  #8  FastAPI 骨架（Supabase JWT 认证 + HeadlessAgent 重构）
       ├── #9  端点 Profile CRUD
       ├── #10 端点 院校匹配 + RAG
       └── #11 端点 智能对话（意图分类 + SSE 流式）
```

### 前后端策略

- **后端**：FastAPI，与 `agent/` `rag/` `user/` 共享模块（已解耦，零 Streamlit 依赖）
- **前端**：Streamlit 跑通 V2 逻辑 → 状态机稳定后切 React
- **Embedding**：开发 `EMBEDDING_MODE=local`（BGE-small 24MB），生产 `=api`（DashScope text-embedding-v4）

### 关键原则

- 先做匹配引擎（确定性逻辑），再考虑哪里需要 LLM
- LLM 是润滑剂，不是引擎
- 切到 React 的触发信号：需要拖拽发文件 / 第 3 个学生反馈体验烂 / 主动想学 React
