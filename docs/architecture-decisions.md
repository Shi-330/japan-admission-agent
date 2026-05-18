# 架构决策日志

## ADR-001: 为什么选 ReAct Agent，后来为什么反悔

**决策时间**: 2025年初  
**状态**: 已推翻，处于演进中

### 初始理由
- ReAct (Reasoning + Acting) 模式让 Agent 自主决定"回答问题 / 查资料 / 搜网页 / 生成报告"
- 7 个 tool 覆盖了业务需求：RAG 检索、网页搜索、月份查询、CSV 数据、报告生成、画像更新
- LangChain 的 `create_agent` 提供了开箱即用的 ReAct 实现

### 实践中发现的问题
1. **意图分类太粗糙**：4 个标签 ([ANSWER] / [UPDATE_PLAN] / [MISSING_INFO] / [REPORT]) 覆盖不了真实场景。日本升学咨询的实际意图只有两类：查学校信息、做匹配规划。
2. **LLM 调用链路过长**：每个用户问题都要先决策 → 再执行 tool → 再汇总。延迟 3-5 秒，用户体验差。
3. **过度自由发挥**：Agent 可以自由选择 tool 组合，但升学咨询需要的是确定性（某校托福要求是确定的），不是 LLM 的"合理猜测"。
4. **Token 消耗大**：每次对话都要把所有 tool description 和 system prompt 塞进 context。

### 演进方向
```
ReAct Agent (现状)
      ↓
Tool Router（按用户操作分流，不猜意图）
      ↓
结构化匹配引擎 + RAG 知识库 QA + LLM 润色层（三个独立模块）
```
Agent 只留在知识库 QA 这个环节，其他地方用确定性逻辑。

---

## ADR-002: pgvector vs Pinecone vs ChromaDB

**决策时间**: 2025年初  
**状态**: 已采用 pgvector，维持

### 选项对比

| 维度 | pgvector (Supabase) | Pinecone | ChromaDB |
|------|---------------------|----------|----------|
| 部署 | 零运维，已有 Supabase | SaaS | 自托管 |
| 成本 | 免费额度内 | 付费起步 | 免费但需服务器 |
| 中文检索 | 取决于 embedding 模型 | 取决于 embedding | 取决于 embedding |
| 与业务数据共存 | 同库，auth/profiles/documents 都在 PostgreSQL | 独立服务 | 独立服务 |
| 查询灵活性 | SQL 直接查 metadata | API 受限 | 受限 |

### 为什么选 pgvector
1. 项目已经在用 Supabase 做 Auth 和用户画像存储。pgvector 作为 PostgreSQL 扩展，不需要引入新服务。
2. 97 条文档的规模不需要 Pinecone 的扩展能力。pgvector 在十万级向量上表现足够。
3. 可以用 SQL 做混合查询：按学校名 + 向量相似度同时过滤。

### 踩过的坑
- 向量维度与 embedding 模型绑定。DashScope `text-embedding-v4` 是 1024 维，切到 BGE 模型时必须选 `bge-large-zh-v1.5`（1024 维），不能选 `bge-small`（512 维）。
- Supabase 免费项目 7 天不活跃会自动暂停，导致 DNS 解析失效。生产环境需要付费计划。

---

## ADR-003: 为什么缓存分两层

**决策时间**: 2025年中  
**状态**: 已采用

### 设计
```
第一层：决策意图缓存（DecisionCache）
  - LRU + 30min TTL
  - Key: MD5(profile + user_input)
  - 命中 → 跳过 LLM 决策调用

第二层：工具结果缓存（Tool Cache）
  - 无上限 dict（后续需改为 TTL）
  - Key: MD5(query)
  - 命中 → 跳过 RAG 检索 / 网页搜索
```

### 为什么不直接用 Redis
1. 当前阶段是单机 demo，不需要分布式缓存。
2. 设计上留了接口：`DecisionCache` 接受一个类似 dict 的后端，未来可以注入 Redis。
3. 面试价值：展示"我知道什么时候需要分布式缓存，也知道什么时候不需要"的判断力。

### 为什么缓存 key 要拼接 profile
防止背景不同的学生得到同一个缓存结果。缓存 key 包括 `jlpt_level + eju_score + gpa + target_major` 等字段。

---

## ADR-004: 为什么从 DashScope 切到 DeepSeek + 本地 Embedding

**决策时间**: 2026年5月  
**状态**: 已完成迁移

### 原因
1. DashScope 免费额度耗尽（`AllocationQuota.FreeTierOnly`）
2. DeepSeek 的 OpenAI 兼容端点可以直接用 `langchain-openai` 的 `ChatOpenAI`
3. 成本对比：DeepSeek 的 pricing 比 DashScope coding plan 更低

### Embedding 为什么选 BGE 本地模型
1. DeepSeek 不提供 embedding 模型
2. `BAAI/bge-large-zh-v1.5` 专门为中文优化，1024 维匹配现有 pgvector schema
3. 本地推理：零 API 调用成本，不受网络影响
4. 通过 `hf-mirror.com` 解决国内 HuggingFace 不可达问题

### 技术细节
- Chat: `ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com/v1")`
- Embedding: `HuggingFaceEmbeddings(model_name="BAAI/bge-large-zh-v1.5")`，懒加载避免阻塞
- 系统代理干扰：在 `app.py` 和 `factory.py` 最顶部清理 HTTP_PROXY 等环境变量

---

## ADR-005: Supabase 作为唯一后端

**决策时间**: 2025年初  
**状态**: 已采用

### 为什么 all-in Supabase
- Auth（用户登录/注册/密码重置）：Supabase Auth
- 用户画像（JLPT/EJU/GPA）：`user_profiles` 表
- 向量存储（RAG）：`documents` 表 + pgvector
- 提示词管理（版本控制）：`prompts` 表 + `is_active` 标记

### 为什么不用独立服务
一个 1-2 人的项目不需要微服务。Supabase 提供的 PostgREST 自动生成 REST API，省掉了大量 CRUD 代码。面试时可以讲："选型原则是用最少的运维开销支撑最多的功能——Supabase 一行 `create_client(url, key)` 替代了 Auth0 + Pinecone + 自建 profile API 三个服务。"

### 风险
- 供应商锁定：迁移成本高。但作为 demo/POC 项目可接受。
- 免费项目 7 天暂停：已在 docs 中记录。

---

## ADR-006: Streamlit vs React + FastAPI

**决策时间**: 2025年初 / 2025年中演进  
**状态**: Streamlit 为主，FastAPI 解耦进行中

### 为什么先选 Streamlit
1. Python 全栈，不需要写 JavaScript
2. 原型验证速度快
3. `st.chat_message` 和 `st.write_stream` 天然支持流式对话

### 为什么开始解耦
1. Streamlit 的 session state 与 Agent 逻辑耦合太重
2. 生产环境需要独立的 API 服务
3. React 前端可以做更精细的 UI 控制（loading 状态、SSE 流式、侧边栏交互）

### 解耦原则
- `agent/`、`rag/`、`user/`、`utils/` 模块零 Streamlit 依赖
- `views/` 只管 UI，`backend/api/` 只管 HTTP
- 同一個 `ReactAgent` 可以同时服务于 Streamlit 和 FastAPI

---

## ADR-007: 项目整体认知 —— 我学到的

### ReAct Agent 的正确使用场景
ReAct 适合**开放式任务**——你不知道用户下一步要干什么，Agent 需要在多种 tool 之间灵活选择。适用场景：个人助手、代码助手、客服机器人。

ReAct 不适合**确定性业务流程**——操作步骤是已知的，只是实施需要领域知识。日本升学咨询属于这一类：操作就是"匹配条件 → 查学校信息 → 给出规划"，不需要 Agent 在中间"思考"。

### 技术选型的判断框架
1. 先想清楚"这个问题是检索问题还是推理问题"
2. 如果是检索问题，RAG 够用，不要上 Agent
3. 如果上了 Agent，先问："用户真的需要 Agent 做这个决策吗？"
4. 缓存是弹药不是盔甲——先有瓶颈再加缓存，不要提前设计

### 如果重来
- 先做匹配引擎（确定性逻辑），再考虑哪里需要 LLM
- 先确认学校数据来源，再设计 RAG 结构
- 先做单轮工具调用，再考虑是否需要多轮 ReAct
