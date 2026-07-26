# Japan Admission Agent

AI 留学申请管理助手。覆盖院校检索、套磁信生成、申请进度追踪全流程。
本项目的源起是作者本人申请日本留学时，亲身经历过信息分散、搜集困难的痛点。

线上服务网址：https://agent.shi330.xyz

---

## 架构

项目最初是标准 ReAct agent 循环，跑了几周后基于性能优化的考虑，被拆分为如下架构。

```
用户消息
   -> 意图分类（1 次 LLM 调用：5 类意图 x 5 类流程 x 3 级深度）
   -> 确定性路由（规则引擎，非 LLM）
        match  -> 匹配引擎
        qa     -> RAG hybrid search -> web search 兜底
        search -> 学校检索 + CN-JP 术语转义
        chat   -> 通用生成
   -> 后处理（事实抽取 -> 画像更新 + 缓存 + SSE 流式）
```

LLM 调用次数从 ReAct 的 3-8 次降至最多 2 次。路由是确定性的，系统在收敛场景里不发散。

---

## 学术数据库

109 所大学（86 国立 + 8 公立 + 15 私立）+ 396 研究科，四层结构：

```
大学
  └─ 研究科（院系）
       └─ 专攻（专业）
            ├─ 语言要求（JLPT / 英语，区分 required / recommended / benchmark）
            ├─ 入试日程
            ├─ 研究方向
            └─ 文档（募集要项 / 过去问 / 入试日程，valid_from/until 自动标记过期）
```

**要求继承链**：研究科（院系）设默认值，专攻（专业）可覆盖。`program.english ?? graduate_school.english`

**CN-JP 术语转义**：用户写如"地震勘探"，系统转义为"地震学 / 地球物理学 / 地球惑星科学"再匹配。静态映射覆盖高频词，LLM 兜底低频词。在保存画像时计算一次，降低学校匹配时的延迟。

---

## 检索

- **RAG**：Supabase pgvector + BGE-small-zh-v1.5（512-dim 本地离线加载，零填充对齐 1024-dim schema）
- **Hybrid Search**：vector + BM25 + RRF 融合，BM25 索引惰性构建
- **缓存**：TTLCache（200 条 / 30min）+ DecisionCache（LRU + TTL）
- **兜底**：web search 双引擎（DuckDuckGo -> Bing），RAG 无结果时自动触发

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python / FastAPI / SSE 流式 |
| 前端 | React + Vite + shadcn/ui + Tailwind |
| LLM | DeepSeek V4 |
| Embedding | BGE-small-zh-v1.5（本地离线） |
| 数据库 | Supabase（PostgreSQL + pgvector + Auth） |
| 部署 | 阿里云 ECS + Nginx + systemd |

---

## 本地运行

```powershell
pip install -r requirements.txt
venv\Scripts\python.exe -m uvicorn backend.api.server:app --host 0.0.0.0 --port 8000
cd frontend && npm install && npm run build
```

需要 `.env`：`DEEPSEEK_API_KEY` / `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY`

