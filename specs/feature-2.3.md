# Feature Spec: V2.3 私有案例库 — 结构化前辈案例 + Metadata 检索

## Overview

当前 RAG 走通用文档路线（txt/pdf → 500 字切块 → 灌向量），适合方法论文档但不适合前辈案例。
留学咨询的核心查询是"和我背景像的人的结果"（如"GPA 3.2、N1、双非，京大情报有戏吗"），
切碎的文本块无法回答。

本 Feature 把知识库升级为三层内容体系，核心是**结构化案例库**：
案例整条入库不切块，metadata 承载硬字段（学校/专业/GPA/结果），
检索走"metadata 硬过滤 → hybrid_search 语义排序"两段式。

管道不动：`rag/vector_store.py` 的 hybrid_search（vector + BM25 + RRF）和
`filter_metadata` 参数已就位，本 Feature 只补数据结构、入库工具和过滤接入。

## Components

### 1. `rag/case_model.py` — 案例数据模型

- **Files**: `rag/case_model.py`（新建）
- **Purpose**: SenpaiCase Pydantic 模型，案例的唯一 schema 定义
- **Interface**:
  ```python
  class SenpaiCase(BaseModel):
      school: str                    # "大阪大学"
      major: str                     # "情報科学"
      result: str                    # "合格" | "不合格" | "内诺" | "撤退"
      year: int                      # 2025
      background: str                # "双非" | "211" | "985" | "海本" | "日本语言学校"
      gpa: float | None = None       # 归一化到 4.0
      jlpt: str | None = None        # "N1" | "N2" | ...
      english: str | None = None     # "托福89" | "托业850" | None
      research_area: str | None = None
      narrative: str                 # 自然语言叙述：套磁过程、时间线、经验教训（用于向量检索）

      def to_document(self) -> Document  # content=渲染后的完整叙述, metadata=硬字段
  ```
- **States**: 校验失败抛 ValidationError（入库脚本捕获后跳过并记录）；
  `to_document()` 的 content 由模板渲染（背景概要 + narrative），保证检索文本信息完整

### 2. `seed_cases_to_db.py` — 案例入库脚本

- **Files**: `seed_cases_to_db.py`（新建，仿照 `seed_schools_to_db.py` 的单文件数据源模式）
- **Purpose**: 内联 `CASES` 数组（dict 列表）→ Pydantic 校验 → embed → 存入 Supabase documents 表
- **Interface**: `venv/Scripts/python.exe seed_cases_to_db.py`
  - 每条案例整条入库，**不经过 RecursiveCharacterTextSplitter**
  - metadata 额外写 `type: "case"` 与 `case_id`（school+major+year+background 的 hash），
    重跑脚本按 case_id 先删后插，幂等
- **States**: 校验失败的条目打印警告并跳过，不中断整批；
  Supabase 写入失败单条重试一次后记录错误继续
- **数据**: 首批 20-30 条真实/改写案例（信息学、电子、机械方向为主，与学校库对齐）

### 3. `rag/vector_store.py` + `rag/rag_service.py` — 类型过滤接入

- **Files**: 现有文件小改
- **修改**:
  - `rag_service.py` 新增 `search_cases(query: str, school: str = None, major: str = None) -> list[Document]`：
    组装 `filter_metadata={"type": "case", ...}`（school/major 传了才加）调 `hybrid_search`
  - `get_raw_vector_context` 保持不变（通用问答仍全库检索）
- **不影响**: `search_with_fallback`、web search 兜底、现有 load_documents 路线（方法论文档继续走切块）

### 4. `backend/api/server.py` — 案例查询接入 chat 管线

- **Files**: `backend/api/server.py`
- **修改**: 意图分类新增/复用 `case_query` 类意图（"有没有类似背景的前辈"、"我这条件能上X吗"）：
  - 从 UserProfile 取 gpa/语言成绩/背景，从 query 提取目标校（复用现有 CN→JP 归一化）
  - 调 `search_cases(query, school=目标校)`，命中案例连同 profile 一起进 LLM prompt
  - 无命中 → 降级为普通 qa 意图（全库 RAG + web 兜底），回答需注明"暂无相似案例"
- **Prompt 要求**: 回答必须引用具体案例字段（"2025 年一位双非 GPA 3.1 N1 的前辈…"），
  禁止编造库中不存在的案例

### 5. `streamlit_app` 管理端 — 案例录入表单

- **Files**: Streamlit 管理端新增"案例管理"页
- **Purpose**: 逐条录入/编辑案例，替代手改 Python 数组
- **Interface**: 表单字段与 SenpaiCase 一一对应 → 提交时 Pydantic 校验 → 直接写入 documents 表
  （与 seed 脚本共用 `to_document()` 和幂等逻辑）
- **States**: 校验失败在表单内显示具体字段错误；写入成功显示 case_id

### 6. `critiques/golden_set.json` + 检索评测

- **Files**: `critiques/golden_set.json`（新建）、`critiques/eval_rag_golden.py`（新建）
- **Purpose**: 固化 10-20 条真实咨询问题 + 期望命中的 case_id，量化检索质量
- **Interface**: `venv/Scripts/python.exe critiques/eval_rag_golden.py`
  → 输出每条命中情况 + 总 hit@5 命中率
- **验收线**: hit@5 ≥ 80%

## Acceptance Criteria

- [ ] C1: `seed_cases_to_db.py` 跑通，Supabase documents 表出现 ≥ 20 条 `type=case` 记录，重跑不产生重复
- [ ] C2: 对话"我 GPA 3.2 N1 双非，想申京大情报，有类似的前辈吗" → 回答引用具体案例（背景+结果），不编造
- [ ] C3: 对话中目标校无案例（如问一所库里没有的学校）→ 回答明确说明"暂无相似案例"并降级普通建议
- [ ] C4: `search_cases` 传 school 过滤后，返回文档 metadata.school 全部匹配
- [ ] C5: golden set hit@5 ≥ 80%
- [ ] C6: 方法论文档（现有 txt/pdf 切块路线）检索不受影响，`search_with_fallback` 行为不变

## Edge Cases

- 案例 GPA 缺失（gpa=None）→ 正常入库，metadata 不含 gpa 键，过滤时不误伤
- 用户 profile 为空时问案例 → 只按 query 语义检索，不做 profile 字段过滤
- metadata 过滤后为空但全库有语义相关内容 → 降级 qa 意图，不返回空转
- BM25 索引未就绪（冷启动）→ hybrid_search 已有 vector-only 降级，案例检索同样生效
- 中文校名查询（"京大"）→ 依赖现有 CN→JP 归一化，归一失败则不加 school 过滤、只做语义检索

## 依赖与顺序

- 前置：Sprint 3 学校数据补全（案例的 school/major 需与学校库对齐，匹配引擎才能联动）
- 生产环境注意：`EMBEDDING_MODE=api`（DashScope），2GB 服务器不跑本地 bge
- 顺手修：`rag/rag_service.py:74` 自测 query 为上个项目遗留（"扫地机器人"），改为本项目查询
