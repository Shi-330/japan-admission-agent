# Sprint Plan — 2026-07-12

## 路线图回顾（通电 → 窗帘）

```
① 核心流程稳  ✓ (E2E Playwright 83/100)
② RAG 通      ← 当前 Sprint 3
③ 部署公网    ✓ (agent.shi330.xyz)
④ 补学校数据  ✓ (7→15 所, Supabase 化)
⑤ 发朋友试
```

---

## Sprint 2 回顾：学校数据上云（done）

**做了什么**：`SCHOOL_CATALOG` 从 server.py 硬编码 → Supabase `schools` 表。7 所扩到 15 所（帝大+东科+筑波 MARCH 早稻田）。日历修了 `official_deadlines` 合并逻辑。seed 脚本用 service key 灌数据。

**没做的事**：跑 Playwright 验证 15 所学校在广场渲染、日历截止日显示、追踪后侧栏卡片出现。**本次 Sprint 验收前补上。**

---

## Sprint 3：RAG + Web Search 兜底（P0）

**目标**：聊天框问任何问题都能返回有用答案。知识库答不上的，web search 兜底。

### Scope

| 文件 | 改动 |
|------|------|
| `agent/tools/web_tools.py` | 新增 `web_search_fallback(query)` — DuckDuckGo 搜索，返回摘要 |
| `rag/rag_service.py` | 新增 `search_with_fallback(query)` — 先 RAG，空则 web |
| `backend/api/server.py` | chat 管线里 RAG 节点接入 fallback |
| `requirements.txt` | 加 `duckduckgo-search>=6.0`（已有一行但可能版本不对） |

### Deliverables

1. **Web search 工具** — `web_search_fallback(query)` → 返回前 3 条搜索结果的标题+摘要
2. **RAG fallback 链路** — `RagSummarizeService.search_with_fallback()` → 先调 `hybrid_search`，空结果则调 web search
3. **Chat 接入** — `/v1/chat` 里 RAG 分支（intent=qa/search_schools 时）用 fallback 链路

### Acceptance Criteria（全部 Playwright 可测）

- [ ] C1: 对话输入"出愿需要什么材料" → 返回包含具体信息的回答（非"未找到"、非"抱歉"）
- [ ] C2: 对话输入"京都大学情报科托福要多少分" → 返回包含分数要求的回答（web search 兜底，知识库里没有这项）
- [ ] C3: 对话输入"你好" → 正常打招呼，不触发 web search（轻量查询走快速通道）
- [ ] C4: RAG 知识库命中时优先用知识库——输入"日本考学流程" → 回答引用 PDF 内容

### Priority: P0

---

## 当前验收任务

在 Sprint 3 开始前，跑 Playwright 验证 Sprint 2 的产出：

| # | 验证点 | 标准 |
|---|--------|------|
| A1 | 广场 15 校 | `h3.text-sm.font-semibold` count ≥ 15 |
| A2 | 筛选过滤 | 输入"情报" → 结果数变化 → 清除恢复 |
| A3 | 追踪→侧栏 | 点"追踪" → toast "已添加" → 侧栏卡片出现 |
| A4 | 日历截止日 | 追踪后切日历 → 显示出願/試験/締切 |
| A5 | 删除学校 | 点 × → 确认 → toast "已删除" |

**通过标准**：5/5。跑 `node critiques/eval_sprint2.js`。
