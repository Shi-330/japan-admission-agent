# Sprint Plan — 2026-07-13

## Goal

实现 Agent 主动照顾学生的三层操作能力：画像驱动生成、状态机追踪+倒计时、主动提醒。后端已有完整支撑（state_machine / matching_engine / greeting 端点），只做浏览器可验收的前端功能。

---

### Sprint 1: 画像驱动看板 (Profile-Driven Dashboard)

- **Scope**: 在 `frontend/src/App.jsx` 新增一个主页/看板视图，聚合画像完整性、个性化建议、下一步行动。配合 `backend/api/server.py` 小改，让 `/v1/greeting` 返回结构化数据（不再仅是一条文本）。
- **Deliverables**:
  1. 新增 `frontend/src/components/DashboardView.jsx` -- 主页看板组件，含：
     - 画像完整度指示器（进度条 + 已填/必填字段数）
     - 基于 `/v1/greeting` 消息的个性化建议区（高亮显示最高优先级的行动项）
     - 按 `applications.stage` 归类的各校状态一览（准备中 / 套磁中 / 出愿中 / 考试 / 等结果 / 已确定）
     - 距最近截止日的倒计时（天），无截止日时显示"暂未设定截止日"
  2. `App.jsx` 新增"首页"Tab（Tabs 顺序：首页 > 对话 > 广场 > 日历），切换 Tab 时自动刷新 greeting
  3. `backend/api/server.py` 改造 `/v1/greeting` 返回结构化 JSON：`{ message, has_reminders, profile_completeness, next_actions, counts: { total_apps, overdue_profs, upcoming_deadlines } }`
  4. 画像空状态：当 profile 全空时展示引导卡片（"填写背景信息，开启个性化推荐"）
- **Acceptance Criteria**:
  - 登录后默认显示首页看板，问候语 + 建议 + 进度一览可见
  - 每项建议点击后跳转到对应 Tab（如"去选校广场"切换到广场页）
  - 画像完成度百分比随着 profile 字段填充实时更新
  - 各校状态卡片可点击展开/收起查看详情
  - 所有 UI 文本不含 emoji
  - 切换 Tab 回首页时 greeting 刷新，反映最新状态机变化
- **Priority**: P0

---

### Sprint 2: 倒计时可视化 + 时间线增强 (Countdown & Timeline)

- **Scope**: `frontend/src/App.jsx`（各校申请卡片）和 `frontend/src/components/CalendarView.jsx` -- 让截止日和阶段倒计时变得醒目、可感知。
- **Deliverables**:
  1. 各校卡片上的 deadline 标签改为 `X 天后` / `已过期 X 天` 格式，带颜色编码：
     - >14 天：灰色
     - 7-14 天：琥珀色
     - 0-7 天：红色 + 闪烁动效（framer-motion pulse）
     - 已过期：红色 + "已过期 X 天" + 斜体
  2. 各校卡片 timeline 从 `<details>` 中取出，改为内联可视进度条（横轴，显示已完成/当前/未来阶段），当前阶段用实心高亮，未来阶段用灰色占位
  3. `CalendarView.jsx` 改造：
     - 截止日标签改为圆点 + 计数字条，hover 显示详情
     - 本月的截止日用红色圆点，下月用黄色，更远用灰色
     - 添加 "X 天后" 文字标注在截止日后方
     - 增加 "+ 添加截止日" 按钮直接在当前日历添加 deadline（调 `/v1/applications`）
  4. 教授超期未回（14+ 天无回复）在各校卡片上显示警告横幅，带"已 X 天未回复，建议跟进"字样
- **Acceptance Criteria**:
  - 每张 deadline 标签显示剩余天数，颜色随紧迫度自动变化
  - 日历页按月份排列的 deadline 标记可读、颜色可区分
  - 已过期截止日显示负天数（"已过期 3 天"）
  - 教授无回复警告在卡片顶部可见，不影响其他操作
  - 时间线进度条交互无闪烁，数据及时刷新（API 调用后自动更新）
  - 数字刷新逻辑使用客户端实时计算（不依赖轮询 API），保障秒级响应
- **Priority**: P0

---

### Sprint 3: 主动提醒中心 (Proactive Reminder Hub)

- **Scope**: `frontend/src/App.jsx` 增加持久化通知系统，配合 `backend/api/server.py` 新增一个聚合提醒端点 `/v1/reminders`，用于周期性获取和标记已读。
- **Deliverables**:
  1. 新增 `frontend/src/components/ReminderBell.jsx` -- 顶部导航铃铛图标，显示未读提醒数量 badge（红点 + 数字）
  2. 新增 `frontend/src/components/ReminderDrawer.jsx` -- 右侧滑出抽屉，列出所有提醒（按紧急度排序），支持单条"忽略"/"标记已读"
  3. `backend/api/server.py` 新增 `GET /v1/reminders` 端点，返回聚合提醒列表：
     ```json
     [
       {
         "id": "prof_no_reply_xxx",
         "type": "professor_no_reply",
         "school": "京都大学 情报理工",
         "professor": "田中太郎",
         "message": "田中太郎 20 天未回复，建议发跟进邮件或换教授",
         "days": 20,
         "severity": "high",
         "created_at": "2026-07-01T00:00:00",
         "acknowledged": false
       }
     ]
     ```
  4. 前端定时轮询（每 120 秒） `/v1/reminders`，新增提醒时弹出 sonner toast
  5. 页面获得焦点（visibilitychange / focus 事件）时立即刷新一次提醒
  6. 各提醒类型点击跳转：教授超期 -> 切换到对话页并自动填入建议 prompt；截止日临近 -> 切换到日历页定位到月份
- **Acceptance Criteria**:
  - 铃铛 badge 数字随提醒状态实时更新
  - 新提醒出现时显示 sonner toast（仅限此前未显示的提醒）
  - 标记已读后再次刷新不再出现
  - 忽略的提醒 24 小时内不再重复推送
  - 抽屉内提醒按紧急度排序（high > medium > low），同级别按时间降序
  - 所有操作（标记已读、忽略、点击跳转）顺利执行，无页面 crash
- **Priority**: P1

---

### Sprint 4: Playwright 评估 + 边界打磨 (Eval & Polish)

- **Scope**: Playwright 端到端测试脚本覆盖三层功能，修复测试中发现的问题。
- **Deliverables**:
  1. 创建 `critiques/eval_sprint_proactive.js` -- Playwright 测试文件，覆盖：
     - 首页看板渲染 + 画像完整度显示
     - 倒计时标签颜色正确性（mock 一个距截止 3 天的日期）
     - 提醒铃铛 + 抽屉打开/关闭/标记已读
     - 教授超期警告的出现和消失
     - 日历 deadline 颜色编码
  2. 修复测试中发现的 bug（如 loading 状态缺失、空数据 crash、计时不准）
  3. 补充各空状态占位符：无学校追踪时显示引导文案 + 跳转广场按钮
  4. 确认所有 console.warn / console.error 在正常操作下为零
- **Acceptance Criteria**:
  - Playwright 测试通过率 >= 90%（<= 10% 因环境差异导致的误报）
  - 所有预期功能在测试中均有断言覆盖
  - 空数据状态显示友好提示而非白屏或报错
  - 已修复的 bug 不再重现
- **Priority**: P2
