# Feature Spec: 主动提醒 + 行动中心（Agent Proactivity）

## Overview

Agent 的核心差异化：不等用户问，自己盯进度、主动提醒、并且**附带已准备好的行动**。
用户登录看到的不是"田中教授 14 天未回复"这句话，而是"14 天未回 → 建议换人跟进 →
[查看拟好的套磁信草稿]"。感知 → 判断 → 预备行动的完整闭环。

已有底子：
- 分支 `sprint-reminder-hub`（commit 8451552）有完整的 ReminderBell/ReminderDrawer/轮询/3 个后端端点实现，
  但基于旧 master（ae5e265）。**参考其实现重写或 cherry-pick 后解决冲突均可**，以当前 master 为准。
- `backend/api/server.py` 已有 `_collect_all_reminders()` 聚合逻辑和 `/v1/draft/outreach` 草稿端点。
- 前端已有 `OutreachDraft.jsx` 组件。

## Components

### 1. `backend/api/server.py` — Reminders API

- `GET /v1/reminders` → `{reminders: [...], total: int}`。聚合四类（复用 `_collect_all_reminders` 逻辑）：
  - `professor_no_reply`：status sent/no_reply 且 ≥14 天
  - `deadline_approaching`：≤14 天（读 application deadlines；学校官方 deadline 只读可解析条目）
  - `deadline_expired`：已过期（不再对过期项生成"临近"提醒）
  - `profile_incomplete`：completeness < 50% 时一条
  - 每条：`{id, type, school, professor?, message, days, severity(high/medium/low), action}`
  - `action` 字段（本 feature 的核心增量）：
    - professor_no_reply → `{type: "draft_outreach", school, professor, hint: "换人或跟进"}`
    - deadline_* → `{type: "goto_calendar"}`
    - profile_incomplete → `{type: "open_profile"}`
- `POST /v1/reminders/ack` body `{id}` / `{all: true}` → 记入 `profile.facts["dismissed_reminders"]`
  `{id: expiry_iso}`，24h 过期自动重现；读取时惰性清理过期项
- 幂等、无新表：全部状态存 profile.facts

### 2. `frontend/src/components/ReminderBell.jsx` + `ReminderDrawer.jsx`

- Bell：tab 栏右侧，未读数徽标；0 条无徽标；接口失败时整个组件返回 null 不崩
- Drawer：右侧滑出，按 severity 降序 + days 排序；每条显示类型图标/消息/天数徽标/操作按钮
- **行动按钮**（区别于普通提醒列表的关键）：
  - professor_no_reply 条目 → "拟套磁信" 按钮 → 调 `/v1/draft/outreach`（点击时才生成，不预生成）
    → 弹出 OutreachDraft 组件预填 school/professor
  - deadline 条目 → "去日历" 切 tab；profile_incomplete → 打开背景表单
- "已读"/"全部已读" → ack API → 本地隐藏 + 下轮拉取确认

### 3. `frontend/src/App.jsx` — 集成

- 挂载 Bell；120s 轮询 + window focus 立即刷新；unmount/登出清 interval
- 新提醒（本次 fetch 出现的新 id）触发一条 sonner toast，按 id 去重不重复弹
- 登录后首次拉取

## Acceptance Criteria（≤10，全部可对 :8100 验证）

- [ ] C1: `GET /v1/reminders` 返回 200 + `{reminders, total}` 结构；无 JWT 返回 401
- [ ] C2: 测试账号造一个 15 天前 status=sent 的教授 → reminders 含 professor_no_reply，severity=high，action.type=draft_outreach（API 造数据：POST /v1/applications）
- [ ] C3: 造一个 7 天后的 deadline → 出现 deadline_approaching；造一个已过期的 → 出现 deadline_expired 且不重复计为 approaching
- [ ] C4: `POST /v1/reminders/ack {id}` → 该条从下次 GET 消失；ack-all 后 total=0
- [ ] C5: 登录后 Bell 可见且徽标数 = API total；0 条时无徽标
- [ ] C6: 点 Bell 开 Drawer，条目按 severity 排序，含行动按钮文案（"拟套磁信"/"去日历"）
- [ ] C7: 点"拟套磁信" → 出现草稿弹窗且内容非空（1 次 LLM 调用，评测全场唯一）
- [ ] C8: 点"已读"后条目消失，刷新页面不复现（24h 窗口内）
- [ ] C9: 全流程 0 console error；UI 无 emoji、全中文
- [ ] C10: 现有四个 tab 功能回归正常（首页渲染、广场 33 所、日历、对话输入框存在）

## Edge Cases

- applications 为空 → reminders 只可能有 profile_incomplete；Bell 无徽标或小徽标，不崩
- 教授 status 变为 replied/rejected → 对应提醒自然消失
- dismissed_reminders 中的 id 对应提醒源已消失 → 惰性清理，不残留脏数据
- 轮询期间 token 过期 → 前端已有 401 自动刷新，提醒轮询复用 apiCall 即可
- draft_outreach 调用失败 → 弹 toast 报错，提醒条目不消失

## 约束（builder/evaluator 必读）

- 测试数据用 API 造（POST /v1/applications），评测结束清理（DELETE /v1/applications）
- 写 Supabase 一律走现有 profile_mgr（service 权限已配好），不新增表、不动 schools 表
- 评测用 critiques/eval_helpers.cjs 登录，整场只允许 C7 一次 LLM 往返
- 不 push、不碰主目录、不动 :8000 开发服务
