# Feature Spec: 学校数据 Schema 统一 + 匹配引擎修复

## Overview

学校数据现状是"一张表、两套 schema、三个消费者"：
`seed_schools_to_db.py` 写入的字段（majors/jlpt/english/tags/deadlines 自由文本）与
`demo/school_database.py` 的 School dataclass（jlpt_min/eju_min/gpa_min/english_note/...）互不兼容。
`_row_to_school` 按 dataclass 字段过滤后，匹配引擎拿到的每所学校全是默认值
（jlpt_min="N2"、gpa_min=0、english_note=""），**确定性匹配引擎实际在空转**——
只要学生 N2 以上几乎全部判"可报考"。

本 Feature 统一为单一 schema，三个消费者（广场 /v1/schools、匹配引擎、日历/提醒）共用；
修复匹配引擎的专业过滤和硬条件检查；deadlines 从自由文本改为可解析的结构化数组；
删除 `demo/school_data.py` 硬编码 fallback。

前置：Sprint 3 学校数据补全已落库（旧 schema 数据由迁移脚本转换，不白费）。

## 目标 Schema（schools 表）

```python
{
  "name": "大阪大学 情報科学研究科",           # 唯一键（upsert on_conflict）
  "degree": "修士",
  "majors": ["情報数理学", "コンピュータサイエンス", ...],   # 展示 + 搜索 + 匹配（保留）
  "tags": ["情報", "口頭試問", ...],                        # 展示 + 搜索（保留）
  "exam": "口頭試問+書類審査",
  "notes": "6専攻。受入教員の承認印必須。",
  # ── 匹配引擎硬字段（新增列）──
  "jlpt_min": "N2",                            # "N1"/"N2"/"N3"/""（空=不要求）
  "gpa_min": 0.0,                              # 4.0 制，0=不设线
  "english_req": {"type": "TOEFL", "min": 80, "required": true},  # jsonb；不要求时 {"required": false}
  # ── 结构化 deadlines（改造现有列）──
  "deadlines": [
    {"name": "留学生夏出願", "start": "2026-06-23", "end": "2026-06-27", "round": "夏"},
    {"name": "試験日", "date": "2026-07-07", "round": "夏"},
    {"name": "合格発表", "raw": "2027年2月下旬"}    # 解析不出精确日期时保留 raw，无 date/start
  ],
  # ── 数据治理（新增列）──
  "source": "official",                        # official / manual / crawled / imported
  "verified": true,
  "updated_at": "2026-07-16T00:00:00Z"
}
```

规则：修士匹配**不使用 EJU**（EJU 是学部考试），School 模型删除 eju_min/eju_subjects。
deadline 条目：`date`（单日）或 `start`+`end`（区间）二选一，均为 ISO 格式；
无法解析时只留 `name`+`raw`，日历/提醒跳过该条但广场详情仍可展示原文。

## Components

### 1. `migrations/schools_v2.sql` — 表结构迁移

- **Files**: `migrations/schools_v2.sql`（新建，在 Supabase SQL Editor 手工执行）
- **内容**: `ALTER TABLE schools ADD COLUMN IF NOT EXISTS` — jlpt_min text、gpa_min float8、
  english_req jsonb、source text、verified bool、updated_at timestamptz；
  deadlines 列类型不变（jsonb），内容格式由迁移脚本转换
- **不删旧列**: jlpt/english 文本列保留一个版本周期，迁移验证通过后再手工清理

### 2. `demo/school_database.py` — School 模型重写（唯一 schema 定义）

- **Files**: `demo/school_database.py`
- **修改**:
  - School 改为 Pydantic BaseModel，字段与目标 schema 一一对应；
    删除 eju_min/eju_subjects/deadline_april/deadline_september/capacity/target_major
  - `_row_to_school` 直接 `School(**row)` 解析，缺失字段用模型默认值并 `logger.warning`
  - `upsert_school(s)` 保持 on_conflict="name"，自动写 updated_at
  - 删除 `import_from_hardcoded`
- **States**: 行解析失败（脏数据）→ 跳过该行并 warning，不让一条坏数据拖垮全表读取

### 3. `migrate_schools_v2.py` — 存量数据转换脚本

- **Files**: `migrate_schools_v2.py`（新建，一次性）
- **Purpose**: 把 Sprint 3 落库的旧格式行转换为新 schema，幂等可重跑
- **逻辑**:
  - `jlpt` 文本 → `jlpt_min`：正则提取 N1/N2/N3（"N2以上"→"N2"），提取失败 → ""
  - `english` 文本 → `english_req`：提取考试类型和分数线（"TOEFL 85+"→{type:TOEFL,min:85,required:true}），
    含"推奨/不强制" → required:false，纯列举（"TOEFL/TOEIC"）→ {type:"any",required:true}
  - `deadlines` dict → 结构化数组：正则解析 `YYYY-MM-DD ~ YYYY-MM-DD`（区间）、
    `YYYY-MM-DD`（单日）、`YYYY年M月`（→ raw）；已过期条目（end/date < 今天）打印警告清单
  - 逐行 upsert 回写，末尾打印转换统计（成功/raw 兜底/过期）
- **States**: 单行转换异常 → 记录 name 跳过，不中断整批

### 4. `seed_schools_to_db.py` — 改用新 schema + upsert

- **Files**: `seed_schools_to_db.py`
- **修改**:
  - SCHOOLS 数组按新 schema 重写（含 jlpt_min/gpa_min/english_req/结构化 deadlines/source/verified）
  - 删除"清空重插"逻辑，改为逐条 `upsert_school`（与管理端共用同一写路径）
  - 入库前过 School Pydantic 校验，失败打印字段错误并跳过
- **States**: 重跑幂等；已有行按 name 覆盖更新

### 5. `demo/matching_engine.py` — 匹配逻辑修复

- **Files**: `demo/matching_engine.py`、`utils/cn2jp.py`（新建）
- **修改**:
  - **专业过滤**：`utils/cn2jp.py` 收编 server.py 的静态 CN→JP 映射 + LLM 归一化 fallback
    （单一实现，server.py 和 matching_engine 都 import 它；frontend 的 CN2JP 副本本期不动）。
    过滤条件改为：归一化后的关键词命中 `school.majors` 或 `school.name` 或 `school.tags`
  - **硬条件**：JLPT 用 `jlpt_min`（空=通过）；GPA 用 `gpa_min`（0=通过）；
    英语用 `english_req`（required:false=通过；type:"any" 且学生有任意成绩=通过；
    有 min 时数值比较，学生成绩解析失败不阻断）
  - **删除 EJU 检查**（修士不适用），GapDetail 相应减为 JLPT/GPA/英语三项
  - **判定档位**：全过=match；1 项不满足=warning；≥2 项不满足或 JLPT 差 2 级=reject
  - **fallback 删除**：`_schools_from_db` 读库失败/为空时返回 []，`/v1/match` 对空结果返回
    明确错误信息（"学校数据加载失败"），删除 `from .school_data import SCHOOLS` 及该文件
- **不影响**: `generate_timeline` 改读结构化 deadlines（有 date/start 的条目），接口签名不变

### 6. `backend/api/server.py` + 日历/提醒 — 消费端适配

- **Files**: `backend/api/server.py`、`frontend/src/components/CalendarView.jsx`、`DashboardView.jsx`
- **修改**:
  - `/v1/schools` 返回体不变（原样整行），前端广场卡片展示 deadlines 时：
    有 date/start 的条目格式化为日期，raw 条目原文展示
  - 日历/提醒（`_collect_all_reminders` 等）读学校 deadlines 时只取可解析条目，
    过期条目不再生成提醒
  - server.py 的 CN→JP 归一化改为调用 `utils/cn2jp.py`（行为不变，去重实现）

## Acceptance Criteria

- [ ] C1: 执行 migrations + migrate 脚本后，schools 表全部行通过 School Pydantic 校验（脚本零跳过或跳过项已人工修复）
- [ ] C2: `/v1/match`（测试账号 N2、GPA 3.0、无英语成绩）不再全表"可报考"——对 english_req.required=true 且有分数线的学校给出英语 gap
- [ ] C3: 匹配专业过滤：profile.target_major="计算机" 能命中 majors 含"情報工学/コンピュータサイエンス"的学校（不再依赖校名子串）
- [ ] C4: 日历视图展示结构化 deadline（单日 + 区间），raw 条目不出现在日历但广场详情可见
- [ ] C5: 过期 deadline（date < 今天）不生成提醒
- [ ] C6: `demo/school_data.py` 已删除，全仓 grep 无残留 import；DB 读取失败时 `/v1/match` 返回明确错误而非静默空转
- [ ] C7: `seed_schools_to_db.py` 重跑两次，行数不变、updated_at 更新（幂等 upsert）
- [ ] C8: 广场 `/v1/schools?major=计算机` 行为与改造前一致（Playwright 回归）

## Edge Cases

- 学校不要求 JLPT（英语项目）→ jlpt_min=""，JLPT 检查直接通过
- english_req.type="any" 且学生只有 TOEIC → 通过（不做考试类型换算）
- deadline 只有 raw（"2027年2月下旬"）→ 广场展示原文，日历/提醒/timeline 跳过
- 学生 profile 缺 GPA → GPA 检查按通过处理并在 gap 里标注"未填写"
- CN→JP LLM 归一化超时/失败 → 静态映射兜底，再失败则退化为原词子串匹配（不抛错）
- 迁移脚本重跑：已转换的行（deadlines 已是数组）跳过转换直接校验

## 依赖与顺序

- 前置：Sprint 3 学校数据落库（本 Feature 的迁移脚本负责转换其产出）
- 后续：V2.3 案例库（specs/feature-2.3.md）依赖本 Feature 的 school/major 规范名对齐
- 部署顺序：SQL migration → migrate 脚本 → 代码部署 → 跑 Playwright 回归 → 清理旧列
