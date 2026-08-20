# Feature Spec: 学校数据补全 (Sprint 3)

## Overview

Supabase schools 表现在有 15 条记录（seed_schools_to_db.py 写入），但覆盖范围有限且部分日期已过期（2025 年）。本 Sprint 将学校数扩充至 30+ 所，聚焦修士（硕士）层次的信息/电子/机械方向，并将所有日期更新为 2026-2027 申请季。同时将 seed 脚本从交互式 `delete+insert` 改造为幂等 `upsert`（按 name 去重），消除人工确认步骤，支持重复执行而不产生重复行。

本 Sprint **不做 schema 迁移** — 字段结构维持现状（jlpt/english 为自由文本、deadlines 为 dict/jsonb），schema 统一由后续 feature-schema.md 处理。

前置依赖：feature-schema.md 的迁移脚本会消费本 Sprint 的输出数据，因此本 Sprint 优先完成。

---

## Components

### Component 1: `seed_schools_to_db.py` — 幂等 upsert + 移除交互

- **File**: `seed_schools_to_db.py`
- **Purpose**: 消除交互阻塞，使脚本可在 CI 或部署 pipeline 中安全重跑；写入逻辑由`delete+insert`改为按 `name` 字段 upsert。
- **Behavior**:
  1. 删除文件顶部的 `input()` 交互式确认代码块（第 18-23 行："if existing.count > 0 ... delete" 整段）。
  2. 将第 50 行的 `supabase_admin.table("schools").insert(row).execute()` 替换为 `supabase_admin.table("schools").upsert(row, on_conflict="name").execute()`。
  3. 确认 Supabase `schools` 表在 `name` 列上有 unique 约束或主键约束；若没有，在脚本开头增加一条 SQL 确保约束存在（`ALTER TABLE schools ADD CONSTRAINT schools_name_key UNIQUE (name);` 以 SPL 方式执行）。
  4. 保留 `SUPABASE_SERVICE_KEY` 认证（admin client），无需改用户认证层。
- **States**:
  - **正常**: 逐条 upsert，打印 `OK` 或 `UPDATED`；末尾打印总数。
  - **重复执行**: 数据行数不变，已有行按新数据覆盖更新（幂等）。
  - **Supabase 不可达**: 打印错误行并继续下一条（不中断整批），最终 exit code 仍然为 0（数据可分批重跑）。
  - **约束不存在**: upsert 退化为 insert，可能产生重复行。脚本应在开头检查/创建唯一约束以避免此问题。

### Component 2: SCHOOLS 数组 — 新增 15-20 所院校

- **File**: `seed_schools_to_db.py`（SCHOOLS 数组）
- **Purpose**: 扩充学校数据至 30+ 条，侧重信息/电子/机械方向修士课程。
- **Data fields**（与现有 SCHOOLS 数组中每条的字段一致）:
  ```python
  {
      "name": str,           # "大学名 研究科名"
      "majors": list[str],   # 专攻列表
      "degree": str,         # 默认为"修士"
      "jlpt": str,           # 日语要求文本，如"N2以上"
      "english": str,        # 英语要求文本，如"TOEFL/TOEIC"
      "exam": str,           # 考试形式，如"筆記+面接"
      "deadlines": dict,     # {名称: 日期文本}，全为2026-2027
      "notes": str,          # 内部经验/备注
      "tags": list[str],     # 搜索标签
  }
  ```
- **新增院校列表**（至少选中以下 15 所，可据实际信息调整；必须保证数据真实性，不允许 LLM 编造）:
  1. 庆应义塾大学 理工学研究科 — 情报工学/电子工学/机械工学
  2. 东京理科大学 理工学研究科 — 情报科学/电气工学/机械工学
  3. 电气通信大学 情报理工学研究科 — 情报/通信/电子
  4. 东京农工大学 工学府 — 情报工学/机械系统工学
  5. 广岛大学 先进理工系科学研究科 — 情报/电子
  6. 神户大学 システム情报学研究科 — 系统情报/计算科学
  7. 冈山大学 环境生命自然科学研究科 — 情报工学/机械系统
  8. 千叶大学 融合理工学府 — 情报/电子
  9. 金泽大学 自然科学研究科 — 情报工学/电子工学
  10. 名古屋工业大学 工学研究科 — 机械/电子/情报
  11. 大阪公立大学 情报学研究科 — 情报科学/人工智能
  12. 会津大学 コンピュータ理工学研究科 — 计算机科学/信息系统
  13. 奈良先端科学技术大学院大学 情报科学研究科 — 情报科学/AI
  14. 立命馆大学 情报理工学研究科 — 情报理工/电子
  15. 同志社大学 理工学研究科 — 情报工学/机械工学/电气电子
  16. 熊本大学 自然科学研究科 — 情报工学/机械工学
  17. 新泻大学 自然科学研究科 — 情报工学/电子电气
  18. 长崎大学 工学研究科 — 情报/电子/机械
- **States**:
  - **数据真实**: 每所的 jlpt/english/exam/deadlines 应基于官网或可靠来源，不得凭空虚构。
  - **全部 2026-2027**: deadlines 字段禁止出现 2025 或更早的日期。
  - **重复 name**: 与已有 15 条不重复（按 name 判重）。

### Component 3: SCHOOLS 数组 — 修复已有学校的过期日期

- **File**: `seed_schools_to_db.py`（SCHOOLS 数组中已有条目）
- **Purpose**: 更新已有学校中仍为 2025 年的日期为 2026-2027 年对应时段。
- **受影响条目**（至少以下 7 条）:
  - 九州大学 システム情报科学府 — 一般选抜出願 2025-07-07~11 → 2026-07-06~10；一般試験 2025 年 8 月 → 2026 年 8 月；グローバル出願同步调整
  - 北海道大学 情报科学研究院 — 内諾期間 2025-10-01~12-25 → 2026-10-01~12-25
  - 明治大学 理工学研究科 — I期出願 2025-06-05~10 → 2026-06-04~09；I期試験 2025-07-19 → 2026-07-18；II期出願 2025-12-01~09 → 2026-12-01~09；II期試験 2026-02-25 保持（已在 2026）
  - 青山学院大学 理工学研究科 — 秋入試出願 2025 年 7 月 → 2026 年 7 月；秋試験 2025 年 9 月 → 2026 年 9 月
  - 立教大学 人工知能科学研究科 — 夏季推薦出願 2025 年 6 月下旬 → 2026 年 6 月下旬；秋季一般出願 2025 年 8 月中旬 → 2026 年 8 月中旬
  - 中央大学 理工学研究科 — 夏季出願 2025 年 7 月 → 2026 年 7 月；夏季試験 2025 年 9 月 → 2026 年 9 月
  - 法政大学 情报科学研究科 — 秋季出願 2025 年 8 月 → 2026 年 8 月；秋季試験 2025 年 9~10 月 → 2026 年 9~10 月
- **States**:
  - **保持含义**: 仅修改年份，不改变月日或日期语义（如"7月上旬"保持"7月上旬"只改年份）。
  - **全部覆盖**: 脚本中无任何学校包含 2025 或更早的日期文本。

---

## API Contract

无新增端点。seed 脚本执行后，现有端点行为不变：

| Endpoint | Method | Changes |
|----------|--------|---------|
| `GET /v1/schools` | GET | 返回行数由 15 增至 30+；已有返回字段格式不变 |
| `POST /v1/match` | POST | 匹配引擎读 schools 表，新增学校自动参与匹配 |

---

## Acceptance Criteria

每个 AC 必须是 Playwright 可测试的，使用测试账号 `test@example.com`（密码见 Supabase），app 运行在 `http://localhost:8100`。

- [ ] **AC1**: 执行 `venv/Scripts/python.exe seed_schools_to_db.py`，终端输出行数显示 30+ schools in DB（无交互式 prompt，直接完成）。
  - Playwright: 执行 `node critiques/run_eval.cjs` 中的 `exec` 调用或使用 `page.evaluate` 包裹 fetch 到 seed 脚本的 CLI 包装端点（若无 CL1 直接 run script，则使用 `node critiques/run_eval.cjs` 的 shell 组件运行 seed 脚本并捕获 stdout）。

- [ ] **AC2**: 立即重跑一次 seed 脚本，行数与第一次一致（幂等性验证，不产生重复行）。
  - Playwright: 同 AC1 执行两次，比较行数输出相同。

- [ ] **AC3**: 访问 `http://localhost:8100/v1/schools`（或通过页面广场），返回的 school 列表总数 >= 30。
  - Playwright: `await page.goto('http://localhost:8100')` → 登录 → 点击"广场"Tab → 等待学校列表渲染 → `const cards = page.locator('[data-testid="school-card"]'); await expect(cards).toHaveCount(30)` 或获取 count 断言 >= 30。

- [ ] **AC4**: 广场搜索"计算机"，结果展示包含"情报工学/コンピュータ科学"等 majors 的学校（至少 3 所）。
  - Playwright: `page.fill('input[placeholder*=筛选]', '计算机')` → 等待结果过滤 → 确认至少 3 个 school-card 可见 → `page.click('text=清除筛选')` → 列表恢复为全部学校。

- [ ] **AC5**: 检查任意学校卡片的 deadline 文本，无 2025 年份出现。
  - Playwright: `page.locator('[data-testid="school-card"]').first().textContent()` → 断言不包含字符串 "2025"。

- [ ] **AC6**: 访问 `http://localhost:8100/v1/schools?major=电子`，返回列表中包含 majors 含"電気電子/電子情報"的学校。
  - Playwright: `const res = await page.evaluate(() => fetch('/v1/schools?major=电子').then(r => r.json())); expect(res.total).toBeGreaterThan(0)`，且结果中至少一个对象的 majors 包含"電気"或"電子"。

- [ ] **AC7**: 广场可见各学校卡片显示正确的 majors、degree、tags 等字段，无渲染错误或空白卡片。
  - Playwright: 遍历每张 school-card，确认 `.school-name`、`.school-majors`、`.school-tags` 等元素均存在且非空文本。

---

## Edge Cases

- **Supabase 约束缺失**: 若 `schools` 表的 `name` 列无 unique 约束，upsert 退化为 insert，重跑会产生重复行。脚本需在开头执行 `ALTER TABLE schools ADD CONSTRAINT IF NOT EXISTS`，使用 `supabase.rpc()` 或 `supabase.table("schools").execute_sql()` 执行。
- **网络中断/超时**: 单条 upsert 失败时 print `FAIL: {name} - {error}` 并继续下一条，不中断批量。重跑时已成功的行跳过（幂等），仅重试失败行。
- **重复 name**: 若 SCHOOLS 数组中存在两个相同 name（人为错误），第二行的 upsert 覆盖第一行，不会产生双倍数据。开发应在 PR 审查阶段通过 reviewer 避免此情况。
- **空字段**: 某个 school 缺少 majors/notes/tags 等可选字段时，upsert 写入空数组/空字符串，不崩溃。`/v1/schools` 的 `_load_school_catalog` 已用 `.get(key, [])` 兜底。
- **编码问题**: 日语汉字字符在 Supabase 中应正常存储和返回。若出现乱码，检查 Python 源文件的 `# -*- coding: utf-8 -*-` 和 Supabase 表字符集（应为 UTF8）。
- **旧数据覆盖**: upsert 按 name 匹配，会覆盖同名校的旧行。若旧行有 seed_schools_to_db.py 以外的字段（如 feature-schema 新增的 jlpt_min/gpa_min），upsert 时这些字段不会被主动删除（Supabase upsert 保持未在 data 中出现的列不变），确保不损坏后续迁移。
