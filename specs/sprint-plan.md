# Sprint Plan — 2026-07-27

## Goal

Improve the two core user-facing surfaces — chat and application tracking — by adding live urgency visualization, richer chat rendering, interactive calendar controls, and end-to-end eval coverage.

---

### Sprint 1: Countdown + Urgency Visualization on Tracking Cards

- **Scope**: `frontend/src/App.jsx` lines 705-931 (sidebar per-school cards) and `frontend/src/components/DashboardView.jsx` lines 94-108 (nearest deadline), lines 243-272 (deadline card). `frontend/src/components/CalendarView.jsx` lines 107-118 (deadline dots).

- **Deliverables**:
  1. Replace raw deadline date text in sidebar cards (App.jsx lines 792-820) with live countdown labels: "X 天后 / 已过期 X 天" computed client-side from the ISO date string. Apply urgency color classes:
     - `>14 days`: `text-muted-foreground` grey
     - `7-14 days`: `text-urgency-medium` amber
     - `0-7 days`: `text-urgency-high` red + framer-motion `animate-pulse`
     - `expired`: `text-urgency-high` red + italic + "已过期 X 天"
  2. Add professor overdue banner (`>=14 days no reply`) directly on the specific sidebar card (App.jsx, after the professors section around line 768), not just in the global reminders section at the bottom. Banner copy: "教授 {name} {days} 天未回复，建议跟进" with a click handler that opens the OutreachDraft dialog.
  3. In DashboardView's nearest deadline card (lines 243-272): replace the static progress bar with a live countdown ticker that recalculates every 60 seconds using `setInterval` + `useEffect`, showing remaining days decreasing in real time.
  4. In DashboardView's KPI deadline card (lines 140-153): add a "已过期 X 个" counter alongside "最近: X 天后" when deadlines are past due.

- **Acceptance Criteria**:
  - Every deadline shown in a sidebar school card displays a client-side computed countdown ("15 天后", "已过期 3 天"), not the raw ISO date
  - Countdown colors match the urgency bands (grey >14d, amber 7-14d, red <7d, red+italic expired)
  - Professor overdue banner appears on the specific school card whose professor has >=14 days no reply, with action button to open outreach draft
  - DashboardView nearest deadline countdown updates visibly within 60s without page refresh
  - All countdowns survive tab switches (computed fresh on mount via `useEffect`)
  - No emoji in any label text

- **Priority**: P0

---

### Sprint 2: Chat Output Enrichment + Suggested Follow-ups

- **Scope**: `frontend/src/App.jsx` lines 1085-1192 (chat message rendering), `frontend/src/App.jsx` around lines 437-559 (`sendMessage` flow for follow-up extraction), `agent/intent_layer.py` lines 47-111 (classify prompt for suggested_actions).

- **Deliverables**:
  1. Replace the simple regex-based markdown renderer (App.jsx lines 1094-1099) with a dedicated `ChatMessage` component in `frontend/src/components/ChatMessage.jsx` that renders:
     - Bold / italic / inline code / blockquote via regex (current approach but extended to cover `|` tables as simple horizontal layout)
     - Bullet and numbered lists as `<ul>` / `<ol>` with proper indentation (currently all rendered as `<span>` with `· ` prefix)
     - Inline `[学校名](plaza:{filter})` links that the user can click to navigate to plaza with that filter pre-applied
  2. After each assistant streaming response completes (App.jsx lines 598-627 in the `done` event handler), inject a row of 2-3 contextual suggestion chips below the last assistant bubble:
     - Chips are derived from `next_actions` in the greeting data: e.g., "设定研究方向", "去广场浏览学校", "查看临近截止日"
     - Chips render as small `<button>` pills below the message, clicking calls the corresponding tab navigation
     - If no suggested actions from greeting, fall back to static defaults: "去广场看看" / "查看申请进度"
  3. Add a `/v1/chat/suggest` endpoint or reuse the `intent` classification to return suggested follow-up questions for the current conversational context, returned as an SSE `suggested_questions` array in the final done event. Limit to 3 suggestions, max 30 chars each. The frontend renders them as clickable chips that auto-fill the input box.

- **Acceptance Criteria**:
  - Lists in assistant messages render as proper indented list items, not flat "· " spans
  - `[xxx](plaza:yyy)` links in any assistant response render as clickable chips that navigate to plaza with filter "yyy"
  - After each complete assistant response, 2-3 suggestion chips appear below the message
  - Clicking a suggestion chip navigates to the correct tab or fills the input box
  - The `/v1/chat/suggest` fallback returns reasonable options even when greeting data is empty
  - Zero console errors after a full chat session of 10+ messages
  - No emoji in chip labels

- **Priority**: P0

---

### Sprint 3: Calendar Interaction + Inline Timeline

- **Scope**: `frontend/src/components/CalendarView.jsx` (entire file), `frontend/src/App.jsx` lines 915-927 (timeline `<details>`), `backend/api/server.py` `POST /v1/applications` endpoint (lines 1337-1345) for calendar-sourced deadline creation.

- **Deliverables**:
  1. **Calendar month navigation** (CalendarView.jsx lines 9-16 `getMonths()`): replace the fixed 10-month view with an interactive left/right arrow navigation that shifts the visible 3-month window. Add "今天" button to jump back to current month. The visible range is stored as `[startMonth, startYear]` in component state.
  2. **Color-coded deadline dots** (CalendarView.jsx lines 107-118): change dot background color by proximity:
     - Current month and days <= 30: `bg-urgency-high/15 text-urgency-high` red
     - Next month: `bg-urgency-medium/15 text-urgency-medium` amber
     - Beyond 2 months: `bg-muted text-muted-foreground` grey
  3. **Days-remaining label on each dot**: Append " (X 天后)" or " (已过期 X 天)" to the dot label tooltip. For visible inline text, show countdown only for <= 30 days.
  4. **Add deadline from calendar**: Add a "+" button at the top-right of each school row in the calendar that opens a small inline form (school pre-filled, deadline name + date input) and calls `POST /v1/applications` with the new deadline. On success, refresh the calendar data.
  5. **Replace timeline `<details>` in sidebar** (App.jsx lines 915-927): render an inline horizontal progress bar showing all 6 stages (preparing→contacting→applying→exam→waiting→decided) with the current stage highlighted in the stage colour and completed stages in muted fill. Use a 6-segment `<div>` bar with CSS `flex`, not a `<details>` collapse.

- **Acceptance Criteria**:
  - Calendar shows 3 months at a time, left/right arrows shift the window by 1 month
  - "今天" button resets to the current month window
  - Deadline dots are colored by proximity: red (<=30d), amber (31-60d), grey (>60d) — verified by mocking a deadline in each range
  - Deadlines show "(X 天后)" suffix for <=30d, "(已过期 X 天)" for past-due
  - "+" button in calendar adds a deadline via API and the new dot appears immediately
  - Sidebar timeline is rendered as a 6-segment inline bar, current stage visually distinct, completed stages filled at reduced opacity
  - All UI text uses Chinese, no emoji

- **Priority**: P1

---

### Sprint 4: Eval + Edge Case Polish

- **Scope**: Create `critiques/eval_sprint_tracking.js` covering all new features. Fix bugs found during eval. Target `frontend/src/App.jsx`, `frontend/src/components/DashboardView.jsx`, `frontend/src/components/CalendarView.jsx`, `frontend/src/components/ChatMessage.jsx`.

- **Deliverables**:
  1. Create `critiques/eval_sprint_tracking.js` — Playwright test file covering:
     - Login and home tab renders with dashboard data
     - Sidebar school card shows countdown labels on deadlines, not raw dates
     - Deadline countdown color reflects urgency band (mock a deadline 3 days away → red)
     - Professor overdue banner visible on card when >=14 days no reply
     - Calendar month navigation arrows work and change visible months
     - Calendar deadline dot colors differ by proximity
     - "Add deadline" form in calendar creates a new deadline (verify via API re-read)
     - Chat messages with list markdown render as proper HTML lists
     - Suggestion chips appear below the last assistant message
     - Suggested question chips fill the input on click
  2. Fix all bugs revealed during eval: countdown off-by-one, overflow text clipping, missing loading states for calendar deadline add, console errors from `map` on null arrays.
  3. Fill empty states: no applications + no deadlines → DashboardView shows "暂无截止日" not crash; CalendarView with no deadlines → shows friendly empty state with link to plaza; ChatMessage component when content is null → renders nothing not "undefined".
  4. Confirm zero `console.warn` / `console.error` during nominal flow: login, load dashboard, open 2 sidebar cards, send 3 chat messages, open reminder drawer, browse 2 calendar months.

- **Acceptance Criteria**:
  - Playwright test pass rate >= 90% (<=10% flaky due to timing/environment)
  - All empty states render a visible placeholder with a CTA button, never a blank screen or error boundary
  - Zero console.warn or console.error on the nominal flow (verified by Playwright `page.on('console')` filter)
  - Fixed bugs from eval do not regress
  - 15+ assertions across the 3 feature sprints

- **Priority**: P2
