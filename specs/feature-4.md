# Feature Spec: Eval + Edge Case Polish

## Overview

Create a consolidated Playwright eval file (`critiques/eval_sprint_tracking.js`) that covers all acceptance criteria from Sprint 1 (Countdown + Urgency), Sprint 2 (Chat Enrichment), and Sprint 3 (Calendar + Timeline). Fix bugs surfaced during eval: countdown off-by-one, overflow text clipping, missing loading states for calendar deadline creation, null-array `map` crashes, and empty-state gaps. After fixes, confirm zero console warnings/errors during nominal flow with 15+ assertions across all three feature sprints.

---

## Deliverables

### Deliverable 1: `critiques/eval_sprint_tracking.js`

- **File to create**: `C:\Users\86158\Documents\PythonProject\Japan-Admission-Agent\critiques\eval_sprint_tracking.js`
- **Purpose**: Consolidated Playwright eval that tests all acceptance criteria from Sprint 1, 2, and 3 features. Follows the same pattern as `eval_sprint3.cjs` (chromium launch, `page.on('console')` for error tracking, JWT extraction from localStorage, seed data via authenticated fetch, pass/fail results array, JSON results written to disk).

#### Required Assertions (minimum 15)

**Sprint 1 -- Countdown + Urgency (5+ assertions):**
1. Every deadline shown in a sidebar school card displays a client-side computed countdown ("15 天后" or "已过期 3 天"), not a raw ISO date string (e.g. not "2026-12-15"). Verify by seeding a known deadline date and asserting `page.locator('aside')` contains the computed label format.
2. Deadline countdown color matches urgency band: seed a deadline 3 days away and assert the element has the `text-urgency-high` class (or computed style matching red); seed a deadline 20 days away and assert `text-muted-foreground`.
3. Professor overdue banner appears on the specific school card whose professor has >=14 days no reply (not just in the global reminders section). Seed a professor with a `date` field 16 days old. Assert the card text includes a banner message or the professor status shows `no_reply` or "超期".
4. DashboardView nearest deadline countdown in the deadline KPI card updates from a fresh computed value on mount. Verify the text matches `{N} 天后` format (not the raw date string).
5. DashboardView KPI card shows "已过期 X 个" counter when one or more deadlines are past due, alongside "最近: X 天后" for non-expired ones.

**Sprint 2 -- Chat Output Enrichment (5+ assertions):**
6. Lists in assistant messages render as proper HTML lists. Seed a persisted chat message with `- item1\n- item2\n- item3` content; assert the rendered HTML contains `<ul>` or `<ol>` and `<li>` elements, not flat `<span>` elements with "· " prefix.
7. Suggestion chips (2-3 pills) appear below the last complete assistant message after streaming finishes. Assert there is a `.suggestion-chip` or button element below the assistant bubble when `suggested_actions` or fallback defaults exist. If no greeting actions, fallback chips "去广场看看" and "查看申请进度" should render.
8. Clicking a suggestion chip navigates to the correct tab. Click the "去广场看看" chip, assert `activeTab` state changes to `plaza` (or the plaza content renders).
9. The `<ChatMessage>` component renders nothing (empty/fragment) when `content` is `null` or empty string, not the literal text "undefined" or "null". Verify by examining innerHTML of an empty assistant message bubble.
10. Zero console errors after a full chat session of 3+ messages. Use `page.on('console')` to capture and assert count of `error` and `warning` type messages.

**Sprint 3 -- Calendar + Timeline (5+ assertions):**
11. Calendar shows 3 month columns at a time. Navigate to calendar tab, count month-header elements (elements matching `X月` pattern). Assert exactly 3.
12. Left/right arrow buttons shift the visible month window. Click left arrow, assert the set of month labels changes.
13. Deadline dot colors differ by proximity: seed a deadline <=30 days away and assert `bg-urgency-high/15`; seed a deadline 31-60 days away and assert `bg-urgency-medium/15`.
14. "+" button in the calendar opens an inline form with name and date inputs. Click "+", assert an input with placeholder containing "截止日" or "名称" becomes visible.
15. Sidebar timeline is rendered as a 6-segment inline bar (not `<details>`). Assert that a `<details>` or `<summary>` element does NOT appear in the timeline area of school cards; instead a 6-child flex container with colored segments exists.

**Nominal flow (1+ assertion):**
16. Zero `console.warn` or `console.error` during the complete nominal flow: login, load dashboard, open 2 sidebar cards, send 3 chat messages, open reminder drawer, browse 2 calendar months, add one deadline via calendar "+" form.

#### Test Data Seeding Strategy

The eval must seed test data via authenticated API calls (JWT extracted from `localStorage` after login), not rely on pre-existing data.

**Seed data contract (seed via `PUT /v1/profile` -> `applications` array):**

```js
const seedApp = {
  school: '东京大学 工学系研究科',
  stage: 'contacting',
  stage_id: 'contacting',
  professors: [
    { name: '佐藤教授', status: 'no_reply', date: '2026-07-01' } // 16+ days ago
  ],
  deadlines: [
    { name: '出願締切', date: '2026-08-01' } // ~4 days from now (during eval window)
  ],
  // No timeline, no official_deadlines for simplicity
};
```

The eval should remove this seeded application after all tests run (cleanup via `PUT /v1/profile` with the application removed).

#### Console Error Capture

```js
const consoleErrors = [];
page.on('console', msg => {
  if (msg.type() === 'error' || msg.type() === 'warning') {
    consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
  }
});
page.on('pageerror', err => consoleErrors.push('PageError: ' + err.message));
```

Any captured console errors during the nominal flow assertion should cause that assertion to fail.

#### Results Output

Write results to `critiques/eval_sprint_tracking_results.json` in the same format as existing evals:

```json
{
  "results": [{"label": "...", "pass": true, "detail": "..."}],
  "passed": 16,
  "failed": 0,
  "total": 16,
  "score": 100
}
```

---

### Deliverable 2: Fix eval-revealed bugs

All bug fixes target the following files only:
- `frontend/src/App.jsx`
- `frontend/src/components/DashboardView.jsx`
- `frontend/src/components/CalendarView.jsx`
- `frontend/src/components/ChatMessage.jsx` (to be created)

#### Bug 1: Countdown off-by-one

- **File**: `frontend/src/components/DashboardView.jsx` line 100, and wherever `Math.ceil((d - new Date()) / 86400000)` appears
- **Problem**: `Math.ceil` overcounts when the deadline is late in the day. If a deadline is "2026-07-28" and the local time is 2026-07-27 23:00, the diff is ~1 hour but `ceil(0.04)` rounds up to 1 day, showing "1 天后" instead of "0 天后" or "今天". Similarly for expired deadlines, `ceil` on a negative number rounds toward zero (e.g. `Math.ceil(-0.04)` = 0 not -1).
- **Fix**: Replace `Math.ceil` with `Math.round` for accurate day rounding, OR compute using date-only (midnight) values: normalize both dates to midnight before subtraction: `const d1 = new Date(dateStr); d1.setHours(0,0,0,0); const d2 = new Date(); d2.setHours(0,0,0,0); const diff = Math.round((d1 - d2) / 86400000);`
- **Files changed**: `DashboardView.jsx` line 100, and any other spot using `ceil` for deadline diff (check `App.jsx` sidebar code if it uses similar logic).

#### Bug 2: Overflow text clipping on long school/deadline names

- **File**: `frontend/src/App.jsx` sidebar school card section
- **Problem**: School names longer than ~18 characters (e.g. "东京大学大学院工学系研究科電気電子工学専攻") overflow and clip without ellipsis, or truncation with `max-w-[130px]` is too aggressive. The deadline label text also overflows when countdown labels are appended ("XX天后" appended to multi-byte names).
- **Fix**: Increase `max-w-[130px]` on the school name span (line 723) to `max-w-[180px]`. Ensure the deadline container (lines 792-820) uses `overflow-hidden` + `text-ellipsis` + `whitespace-nowrap` classes on individual deadline `<span>` elements so long combined names get an ellipsis instead of clipping.
- **Files changed**: `App.jsx` sidebar card section lines 720-820.

#### Bug 3: Missing loading states for calendar deadline add

- **File**: `frontend/src/components/CalendarView.jsx`
- **Problem**: When clicking the "+" button in calendar and submitting, there is no loading indicator during the API call. Users may click "保存" multiple times, triggering duplicate deadline creation.
- **Fix**: Add a local `addingLoading` state boolean. Set to `true` before calling `onAddDeadline`, set to `false` in `.finally()`. While `addingLoading` is true, disable the save button (add `disabled` prop) and show text "保存中...". Disable the name and date inputs as well during loading.
- **Files changed**: `CalendarView.jsx` in the inline-form rendering section.

#### Bug 4: Console errors from `map` on null arrays

- **File**: `frontend/src/App.jsx` lines 685-931, `frontend/src/components/DashboardView.jsx`
- **Problem**: If `stage.applications` is null or undefined (still loading, or API error), `stage.applications.map(...)` throws a TypeError. Similarly `app.professors?.map(...)` with optional chaining works but later code `app.professors.filter(...)` or `app.professors.length` without optional chaining crashes.
- **Fix**: Audit every `.map()` call on `stage.applications` and derived arrays. Ensure arrays that may be null use `?.map()` or default to `[]`. Specific locations:
  - `App.jsx` line 705: `stage.applications?.map` already uses optional chaining -- ensure the `|| []` fallback guards `stage?.applications?.length > 0` checks.
  - `App.jsx` line 742: `app.professors?.length > 0` -- after this guard, `app.professors.map` is safe. But line 763 `app.professors.filter` should be `(app.professors || []).filter`.
  - `CalendarView.jsx` line 59: `if (!applications?.length)` already guards the main render, but the school row rendering at line 79 still uses `applications.map` -- safe because of the early return on line 59.
  - `DashboardView.jsx` line 90: `(applications || []).filter` already guards.
- **Files changed**: `App.jsx` lines around 763 (professor filter), `CalendarView.jsx` and `DashboardView.jsx` ensure consistent optional chaining.

#### Bug 5: ChatMessage content null renders "undefined"

- **File**: `frontend/src/components/ChatMessage.jsx` (to be created)
- **Problem**: The current inline chat rendering in `App.jsx` lines 1094-1099 uses `msg.content && <div>...</div>`. When `msg.content` is empty string `""` (as used for school cards, nav suggestions, etc.), the `<div>` with `dangerouslySetInnerHTML` is correctly not rendered. However if `msg.content` is `null`, the condition `msg.content &&` also short-circuits -- currently no bug, but the new `ChatMessage` component must handle this explicitly to avoid regression.
- **Fix**: In the new `ChatMessage` component, at the start of render: `if (!content) return null;` before any markdown processing. The component returns `null` (renders nothing) when content is falsy.
- **Files changed**: New file `ChatMessage.jsx`.

---

### Deliverable 3: Fill empty states

All empty states must show a visible placeholder with a CTA button, never a blank screen or error boundary.

#### Empty State 1: No applications + no deadlines in DashboardView

- **File**: `frontend/src/components/DashboardView.jsx`
- **Current behavior**: When `pc.filled === 0` AND no applications, line 76 shows `EmptyState` with "填写背景信息..." -- this is correct.
- **Missing state**: When `pc.filled > 0` AND `applications.length > 0` but ALL applications have zero deadlines, line 95-105 `nearestDl` is `null`, line 150 shows "暂无临近截止日" -- acceptable.
- **Gap**: When `applications.length === 0` AND `pc.filled > 0` (user has profile but no tracked schools), `nearestDl` is null and the KPI cards render with zero counts. This is fine -- the `EmptyState` at line 311 already covers this.
- **Fix**: None needed for DashboardView -- existing behavior is sufficient.

#### Empty State 2: CalendarView with no deadlines (but has schools)

- **File**: `frontend/src/components/CalendarView.jsx`
- **Current behavior**: Line 59 checks `!applications?.length` -- returns empty state "还没有追踪的学校".
- **Gap**: If applications exist but none have parseable deadlines, the calendar renders a grid with empty month columns (no dots). This is confusing -- the user sees a grid but no dots and no message.
- **Fix**: After computing all dots across all applications (line 104), if total dots across all months is 0, render an inline empty-state banner below the legend: "当前学校均无截止日，在日历中点击 + 添加" with a link/button to the plaza.
- **Files changed**: `CalendarView.jsx`, after the legend at line 126-130, conditionally render this empty-state text when total dot count across all months is 0.

#### Empty State 3: ChatMessage when content is null

- **File**: `frontend/src/components/ChatMessage.jsx` (to be created)
- **Fix**: `if (!content) return null;` -- renders nothing, not even an empty bubble.
- **Edge case**: A message with `content: ""` but `navSuggestion` present should still render the nav suggestion card. The component must check `content` separately from other fields.

---

### Deliverable 4: Zero console errors on nominal flow

These locations in the current codebase produce console warnings during normal operation and must be fixed:

1. **`App.jsx` line 151**: `apiCall('/v1/schools', token)` catches errors silently -- this is acceptable. But `console.error('school catalog load failed:', ...)` produces a console.error on any transient failure. Change to `console.warn` for catalog load failures, or suppress entirely (the catalog reloads on every plaza filter change anyway).

2. **`App.jsx` line 502**: `console.warn('SSE parse:', ...)` on malformed SSE chunks -- these are expected during streaming (partial JSON). Change to `console.debug` or remove.

3. **`App.jsx` line 176**: `setGreeting(fallback)` is called when greeting API fails -- this path does not produce console errors currently, but confirm after fixes.

4. **`CalendarView.jsx`**: If `applications` is an empty array and the code still renders the calendar grid, the school-name rows render but no dots appear. No console errors expected. Guard with early return at line 59 already handles this.

Apply these console-log severity changes so that the Playwright eval's `page.on('console')` filter for `error` and `warning` catches only genuine issues.

---

## Acceptance Criteria

- [ ] `critiques/eval_sprint_tracking.js` runs to completion with >= 90% pass rate on a clean checkout with server running on `localhost:8000` (<=10% flaky due to timing/environment)
- [ ] Eval file contains 15+ Playwright assertions across all 3 feature sprints (Sprint 1 countdown/urgency, Sprint 2 chat enrichment, Sprint 3 calendar/timeline)
- [ ] All deadline countdowns use day-accurate computation (`Math.ceil` replaced with midnight-normalized `Math.round` or equivalent) -- verified by eval with a deadline set to "today" showing "0 天后" or "今天"
- [ ] Long school names (>18 characters) display with ellipsis truncation, not clipped overflow -- verified by eval with a seed school name like "东京大学大学院工学系研究科電気電子工学専攻"
- [ ] Calendar "+" button form disables save button during submission and shows "保存中..." text -- verified by eval by asserting save button `disabled` attribute is true after click, before API response
- [ ] Application cards in sidebar do not crash when `professors` or `deadlines` is null -- verified by eval with a seed application that has no `professors` and no `deadlines` fields
- [ ] ChatMessage component renders nothing (not "undefined") when content is null -- verified by eval by inspecting innerHTML of an empty assistant message
- [ ] Calendar with schools but no parseable deadlines shows a friendly inline message ("当前学校均无截止日") with CTA -- verified by eval with seed applications that have empty deadlines arrays
- [ ] Zero `console.warn` or `console.error` during Playwright eval nominal flow (login, dashboard load, sidebar card expand, 3 chat messages, calendar navigation, calendar add deadline) -- verified by eval using `page.on('console')` capture
- [ ] All fixed bugs from eval results in "fix" commits are verified as non-regressed by re-running the same assertions
- [ ] Eval results JSON written to `critiques/eval_sprint_tracking_results.json` at the end of the run

## Edge Cases

- **Calendar with zero applications**: shows "还没有追踪的学校，去「广场」添加吧" empty state (existing behavior, no regression)
- **Calendar with schools but all deadlines unparseable (`raw`-only)**: `getDeadlineDates` returns empty array for all schools -- inline empty-state banner triggers with "当前学校均无截止日"
- **Sidebar card `stage_id` is `null`/`undefined`/`"browsing"`**: timeline section renders nothing (no crash)
- **Chat message content is empty string `""` with `navSuggestion` present**: ChatMessage renders the nav suggestion card, no empty bubble
- **Multiple rapid clicks on calendar "+" save button**: `addingLoading` guard prevents duplicate submissions
- **`stage.applications` is `null` while loading**: all `.map()` calls use optional chaining or `|| []` fallback -- no TypeError
- **Professor `date` field is missing or invalid**: overdue calculation skips or treats as 0 days -- no crash
- **Deadline dates at month boundaries (e.g. July 31 to August 1)**: `getDeadlineDates` with month-based filtering handles this correctly via `getMonth()` and `getFullYear()` comparison
- **Deadline 0 days away (today)**: countdown shows "0 天后" (or "今天"), not negative or blank
