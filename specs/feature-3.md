# Feature Spec: RAG + Web Search 兜底（Sprint 3）

## Overview

聊天管线当前只有 RAG（pgvector + BM25），知识库空时返回"未找到相关参考资料"，体验差。
本 Sprint 在 RAG 层下加 web search 兜底：先查知识库，空或质量低则自动搜索网络。

## Components

### 1. `agent/tools/web_tools.py` — Web 搜索工具

- **Files**: `agent/tools/web_tools.py`
- **Purpose**: 封装 DuckDuckGo 搜索，返回结构化结果
- **Interface**: `web_search(query: str, max_results: int = 3) -> list[dict]`
  - 返回 `[{title, url, snippet}, ...]`
  - 异常时返回空列表，不抛异常
- **States**: 成功返回结果 / 网络异常返回 [] / 无结果返回 []
- **依赖**: `duckduckgo-search` 库（检查 requirements.txt 是否已有）

### 2. `rag/rag_service.py` — Fallback 链路

- **Files**: `rag/rag_service.py`
- **新增方法**: `search_with_fallback(query: str) -> str`
  - 先调 `hybrid_search(query, k=3)`
  - 结果非空 → 格式化为现有格式返回
  - 结果为空 → 调 `web_search(query)` → 格式化为参考资料格式返回
  - 都空 → 返回空字符串（LLM prompt 里显示"无相关资料"）

### 3. `backend/api/server.py` — Chat 管线接入

- **Files**: `backend/api/server.py`（`chat_endpoint` 的 `qa`/`report` 分支）
- **修改**: 将 `rag.get_raw_vector_context(query)` 替换为 `rag.search_with_fallback(query)`
- **不影响**: `search_schools`、`match`、`chat` 意图不参与改动

## Acceptance Criteria

- [ ] C1: 对话"出愿需要什么材料" → 回答含具体信息（知识库 PDF 有相关内容）
- [ ] C2: 对话"京都大学情报科托福要多少分" → 回答含分数（web search 兜底）
- [ ] C3: 对话"你好" → 问候，不触发搜索（轻量查询快速通道不受影响）
- [ ] C4: RAG 命中时优先用知识库（不浪费 web search 调用）

## Edge Cases

- DuckDuckGo 超时/网络异常 → 返回空，不抛异常，不影响回答生成
- 知识库和 web 都空 → LLM 收到"无相关资料"，诚实回答
- 用户问敏感内容 → DuckDuckGo 不会返回结果，正常降级
