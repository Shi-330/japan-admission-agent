# Agent 优化工单 — 输入 / 输出 / 完成标准

> 基于 2026-08-19 代码审计。每项都定义了「输入」「输出」「确定完成的验收标准（DoD）」。
> 顺序即优先级:先做可信度止血,再做成本/架构,最后才碰检索。

| # | 工单 | 优先级 | 预估 | 状态 |
|---|------|--------|------|------|
| 1 | 自动入库隔离(pending_review) | P0 | 0.5 天 | todo |
| 2 | cn2jp_normalize 缓存 | P1 | 0.5 天 | todo |
| 3 | 事实抽取惰性化 | P1 | 1 天 | todo |
| 4 | 删死代码(旧 ReAct 链路) | P1 | 0.5 天 | todo |
| 5 | 抽 intent handlers(拆巨石) | P1 | 1–2 天 | todo |
| 6 | RAG 检索评测(先有尺子) | P1 | 1 天 | todo |

---

## 执行中新增发现(非原 6 项)

- **qa 分支 `q_terms` NameError(既有 bug,已修)**:`server.py` qa 意图的 broaden 循环里 `for t in q_terms`,但该分支定义的是 `terms`。已修为 `terms`,qa 匹配 <8 所时现在能正常显示学校卡片(行为变化:从"静默不显示"→"正常显示")。
- **第 5 项剩余部分**:匹配逻辑已全部统一(match/search/qa/`/v1/match` 都走 `_match_for_query()` + `_build_student_profile()`)。剩余:组卡片构建仍有 2 份(search_schools vs qa)、chat_endpoint 尚未瘦身到 <200 行(需继续抽 intent handlers,高风险低价值,暂缓)。

---

## 1. 自动入库隔离(P0)

### 输入
- 现有 4 处「LLM / web 来源直接写生产库」的代码:
  - `server.py:453-481` — `_background_auto_ingest`(web 搜 → LLM 抽学校 → `upsert_school`)
  - `server.py:540-559` — search_schools 的 LLM fallback,`graduate_schools.upsert(... verified=False)`
  - `server.py:682-687` — qa 分支的 `upsert_school(School(source="web_search", verified=False))`
  - `server.py:1404-1453` — `_enrich_skeletons`,直接 `update` 正式目录
- Supabase 现有 `graduate_schools` 表;新建 `pending_schools` 表(或给 graduate_schools 加 `verification_status` 字段,默认 `pending`)
- Streamlit admin panel(`views/`)作为审批入口

### 输出
- 自动入库的学校**一律写 `pending_schools` / `pending` 状态,不再直接进正式目录**
- 正式目录读取路径(`demo/school_database.py::get_all_schools`)只返回 `verified/approved` 记录
- Streamlit 管理端一个「待审核学校」页:通过 / 拒绝两个按钮

### 完成标准(DoD)
- [ ] 全仓库 `grep` 无任何代码把 `verified=False` 或 `source in ("web_search","llm_suggestion")` 的学校写入正式目录查询路径
- [ ] 手动验证:搜冷门方向触发 auto-ingest → `/v1/schools`、`/v1/schools/search`、`match_schools` 结果里**不含**该校 → 管理端点「通过」→ 该校才出现
- [ ] 现有 109 + 396 已入库学校不受影响(迁移时默认 `approved`)
- [ ] `/v1/schools/discovered` 端点一并改走 pending(或删除该未加鉴权的入口)

---

## 2. cn2jp_normalize 缓存(P1)

### 输入
- `utils/cn2jp.py::normalize()`(纯函数:中文词 → 日文词表;静态未命中时发 1 次 LLM,当前**无缓存**)
- 现有缓存基建:`agent/memory.py::DecisionCache`、RAG 的 `TTLCache`
- 调用点:`server.py` 的 match / search_schools / qa 三处 + `matching_engine.py:142` + `/v1/schools`、`/v1/schools/search`、`/v1/normalize`

### 输出
- `normalize()` 结果按输入 `term` 做 TTL 缓存,命中时零 LLM 调用
- 缓存跨 chat_model 实例共享(归一化结果是确定性的,不绑定模型实例)

### 完成标准(DoD)
- [ ] 同一 `term` 第二次调用不发 LLM(用 `utils/llm_tracer.py` 的 trace 或日志计数验证)
- [ ] 一轮 chat 内 match/search/qa 对同一 `q_major` 的多次 normalize 只触发 1 次 LLM
- [ ] 静态命中(`CN_JP_SYNONYMS`)路径行为不变(本就零 LLM)
- [ ] 单测:断言缓存命中不触发 `chat_model.invoke`(加到 `tests/test_agent_tools.py` 或新建)

---

## 3. 事实抽取惰性化(P1)

### 输入
- `agent/orchestrator.py::finish_turn()` — 当前**每轮**流式结束后都调 `extract_facts_from_chat`
- `user/profile_manager.py::extract_facts_from_chat()`(L286)
- 调用点 `server.py:740`

### 输出
- 一个纯规则的「事实信号」判断函数:检测消息是否含成绩 / 学校 / 方向 / 日期 / 经历类关键词(零 LLM)
- `finish_turn` 先跑信号判断:无信号 → 直接返回原 profile,不调 LLM
- 有信号才调 `extract_facts_from_chat`,且挪到后台线程(不阻塞下一轮)

### 完成标准(DoD)
- [ ] 用户发「谢谢」「好的」等无事实消息时,`extract_facts_from_chat` 不被调用(trace 验证)
- [ ] 用户发「我 N1 145 分」「我在做 NLP 方向的毕设」时,仍正常抽取并写回 profile(无回归)
- [ ] 用 llm_trace 统计:同一段 10 轮对话,fact-extraction LLM 调用数从 10 降到按信号比例(<3)
- [ ] 单测:`tests/test_profile_manager.py` 覆盖信号判断的真 / 假用例

---

## 4. 删死代码(旧 ReAct 链路)(P1)

### 输入
- 死代码清单:`agent/react_agent.py`、`agent/decision_engine.py`、`agent/conversation_router.py`、`agent/prompts.py`、`backend/core/agent.py`
- 唯一引用方:`views/main_agent.py`(Streamlit)、`tests/script_agent_logic.py`

### 输出
- 确认 Streamlit admin 是否仍用旧链路;若用,先迁到 `IntentLayerEngine` 或删掉旧入口
- 删除上述文件 + 唯一引用 + 对应测试
- 清理 `model/factory.py` 中仅旧链路使用的导出

### 完成标准(DoD)
- [ ] 全仓库 `grep` 无 `ReactAgent` / `DecisionEngine` / `ConversationRouter` / `PLANNER_PROMPT` 引用
- [ ] `uvicorn backend.api.server:app` 正常启动,`/v1/chat` 走通
- [ ] Streamlit admin panel 启动无 import 错误
- [ ] 现有测试(除删除的那个外)全绿

---

## 5. 抽 intent handlers(拆巨石)(P1)

### 输入
- `server.py::chat_endpoint`(L289-813,~520 行)的巨石结构
- 7 种 intent:`chat` / `qa` / `search_schools` / `match` / `report` / `explore_field` / `find_professor`
- match 与 search_schools 中重复的「cn2jp + match_schools + 组卡片」代码

### 输出
- `agent/handlers/` 目录,每个 intent 一个 handler 函数(或按相近性分组)
- `chat_endpoint` 退化为「分类 → dispatch → 统一后处理(缓存 / 事实抽取 / SSE 事件)」
- match 与 search_schools 的匹配逻辑合并为**一份**共享函数

### 完成标准(DoD)
- [ ] `chat_endpoint` 行数从 ~520 降到 <200,路由处是纯 dispatch
- [ ] 匹配 + cn2jp + 组卡片逻辑全仓库只有一份实现(不再三处复制)
- [ ] 7 个 intent 行为与重构前逐一对齐:`critiques/run_eval.cjs` E2E 回归通过 + 手工点一遍 7 个 intent
- [ ] SSE 事件类型不变(前端无感,`frontend` 零改动)

---

## 6. RAG 检索评测(先有尺子)(P1)

### 输入
- `tests/rag_eval.py`(已有骨架,未接入 harness)
- 检索现状:7 文件 / 89 chunk;已知 bug — 向量阈值卡 0.5(`SPRINT_HISTORY.md:173`)、similarity 恒 0(:174)

### 输出
- 20–30 条带标准答案的评测集(中文查询 → 期望命中的 chunk / 学校)
- 评测脚本:算 `recall@k`、`MRR`,对比 hybrid vs 纯向量 vs 纯 BM25
- 一份结果报告 + 结论:瓶颈在「检索算法」还是「知识覆盖不足」

### 完成标准(DoD)
- [ ] `tests/rag_eval.py` 一键跑出 recall@k / MRR 数字
- [ ] 输出三路(hybrid / vector / bm25)对比表
- [ ] 依据结果落地至少一个动作:修 threshold(0.5→0.3)或修 similarity 展示或补数据
- [ ] 评测集 + 脚本提交仓库,可重复运行
