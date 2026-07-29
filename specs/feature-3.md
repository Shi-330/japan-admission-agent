# Feature Spec: Calendar Interaction + Inline Timeline

## Overview

Replace the static 10-month calendar with an interactive 3-month navigable view that supports adding deadlines inline, replace the `<details>` timeline in sidebar school cards with a 6-segment progress bar, and apply color-coded urgency to deadline dots. This sprint makes the calendar a live tool for deadline management and gives each school card a compact visual stage overview.

---

## Components

### Component 1: Interactive Calendar Navigation

- **Files to modify**: `frontend/src/components/CalendarView.jsx`
- **Purpose**: Replace the fixed `getMonths()` function (which returns 10 months at once) with interactive navigation that shows a 3-month window, with left/right arrows to shift the window forward/backward by one month, and a "今天" reset button.
- **State variables to add**:
  - `[viewYear, setViewYear]` — the year of the leftmost visible month (initial: `now.getFullYear()`)
  - `[viewMonth, setViewMonth]` — the month (0-indexed) of the leftmost visible month (initial: `now.getMonth()`)
- **Behavior**:
  1. On mount, compute 3 consecutive months starting from `(viewYear, viewMonth)`.
  2. Left arrow (`<`): decrement `viewMonth` by 1; if `viewMonth` goes below 0, decrement `viewYear` by 1 and set `viewMonth` to 11.
  3. Right arrow (`>`): increment `viewMonth` by 1; if `viewMonth` goes above 11, increment `viewYear` by 1 and set `viewMonth` to 0.
  4. "今天" button: reset `viewYear` and `viewMonth` to the current real month.
  5. Render the 3-month grid with the same school-row structure as the current code, but only 3 month columns instead of 10.
  6. Legend at bottom remains.
- **States**:
  - **Normal**: 3-month window with school deadline dots, arrows enabled.
  - **Boundary (far past/future)**: no special restriction — the user can navigate arbitrarily far. Dots only appear for months that contain deadlines.
  - **Empty (no deadlines)**: same empty state as existing — the "还没有追踪的学校" prompt is shown.
- **Edge cases**:
  - Rapid repeated arrow clicks: each click shifts by 1 month, no debounce needed.
  - "今天" button resets via state setter, not page reload.
  - Month/year wraps correctly at January/December boundaries.
- **Playwright test strategy**: Click left arrow 3 times, assert visible month labels shifted. Click "今天" button, assert visible months include the current month.

### Component 2: Color-Coded Deadline Dots + Countdown Labels

- **Files to modify**: `frontend/src/components/CalendarView.jsx`
- **Purpose**: Replace the uniform `bg-urgency-high/10 text-urgency-high` dot style with proximity-based coloring, and append countdown labels to dot tooltips and visible text.
- **Helper functions to add**:
  ```js
  function dotUrgencyClass(dotDate, now) {
    const diffDays = Math.ceil((dotDate - now) / 86400000);
    if (diffDays <= 30) return 'bg-urgency-high/15 text-urgency-high';
    if (diffDays <= 60) return 'bg-urgency-medium/15 text-urgency-medium';
    return 'bg-muted text-muted-foreground';
  }
  function daysLabel(dotDate, now) {
    const diffDays = Math.ceil((dotDate - now) / 86400000);
    if (diffDays < 0) return ` (已过期 ${Math.abs(diffDays)} 天)`;
    if (diffDays <= 30) return ` (${diffDays} 天后)`;
    return '';
  }
  ```
- **Behavior**:
  1. Each dot's `<div>` gets its class from `dotUrgencyClass` instead of the hardcoded `bg-urgency-high/10 text-urgency-high`.
  2. The `title` attribute (hover tooltip) appends the output of `daysLabel()` to show countdown on hover for all deadlines.
  3. The visible inline label text (currently `{dot.label}`) appends `daysLabel()` output only when the deadline is within 30 days or expired (to avoid cramming too much text for far-future deadlines).
  4. The legend at the bottom updates to show three color swatches instead of two, with labels: "<=30天", "31-60天", ">60天".
- **States**:
  - **Normal**: dots colored by proximity bands.
  - **Empty dot lists**: if `getDeadlineDates` returns an empty array for a month, no dots render. No crash.
  - **Unparseable dates**: `getDeadlineDates` already skips `raw`-only items — no change needed.
- **Edge cases**:
  - A dot whose date is the current day (`diffDays === 0`): renders as `bg-urgency-high/15`, label shows " (0 天后)" — accurate and fine.
  - Multiple dots on the same month: stacked vertically using existing `top: ${3 + di * 18}px` offset logic.
  - Very long deadline label text: `truncate` class already handles overflow with ellipsis.
- **Playwright test strategy**: Inject a deadline 15 days from now via the API, assert the dot element has `bg-urgency-high/15`. Mock a deadline 45 days away, assert `bg-urgency-medium/15`. Mock an expired deadline, assert the tooltip contains "已过期".

### Component 3: Add Deadline from Calendar

- **Files to modify**: `frontend/src/components/CalendarView.jsx`, `frontend/src/App.jsx`
- **Purpose**: Add a "+" button at the end of each school row in the calendar that opens an inline form to add a deadline for that school.
- **State variables in CalendarView**:
  - `[addingSchool, setAddingSchool]` — school name currently being added to, or `null`.
  - `[newDlName, setNewDlName]` — deadline name (e.g. "出願締切").
  - `[newDlDate, setNewDlDate]` — date string in `YYYY-MM-DD` format.
  - `[addingLoading, setAddingLoading]` — loading state for submission.
- **Props**:
  ```jsx
  CalendarView({ applications, onAddDeadline })
  // onAddDeadline: (school, deadlineItem) => Promise<void>
  ```
- **Behavior in CalendarView**:
  1. At the end of each school row (last element in the row, aligned to the right end of the month columns), render a small "+" button: `<button className="text-xs text-muted-foreground hover:text-foreground px-1">+</button>`.
  2. Clicking "+" sets `addingSchool` to that school's name. If `addingSchool` is already set for a different school, move the form to the newly clicked row.
  3. When `addingSchool` matches the row, replace the "+" button with an inline form: two small inputs (deadline name, deadline date) + "保存" / "取消" buttons, rendered below the existing dots (or in place of the dots area for that row).
  4. The name input is a text input with placeholder "截止日名称". The date input is `<input type="date">` with placeholder text.
  5. "保存" button: validate name and date are non-empty and the date is parseable. Call `onAddDeadline(school, { name: newDlName.trim(), date: newDlDate.trim() })`. On success, reset all add state. On error, the parent shows a toast and keeps the form state.
  6. "取消" button: reset `addingSchool`, `newDlName`, `newDlDate`.
- **Behavior in App.jsx**:
  - Add `handleCalendarAddDeadline(school, item)` function that:
    1. Finds the existing application for `school` in `stage.applications`.
    2. Reads current deadlines (if any). If `deadlines` is an array, appends `item`. If `deadlines` is a dict (old format), converts both to array format and appends. If `deadlines` is undefined, creates `[item]`.
    3. Calls `updateApplication(school, { deadlines: newArray })`.
    4. Refreshes stage via existing `updateApplication` flow.
  - Pass `onAddDeadline={handleCalendarAddDeadline}` to CalendarView.
- **States**:
  - **Idle**: "+" button visible on each row.
  - **Form open**: inline inputs with placeholders, save/cancel buttons.
  - **Saving**: inputs disabled, save button shows "保存中..." indicator.
  - **Error**: toast shown; form stays open so user can retry.
- **Edge cases**:
  - School has no `deadlines` field yet: code initialises `deadlines` as an empty array before pushing.
  - School has deadlines in old dict format `{"出願": "2026-12-15"}`: conversion to array `[{name: "出願", date: "2026-12-15"}]` must happen transparently in the parent callback.
  - Two "+" clicks in different rows: the form moves to the most recently clicked row.
- **Playwright test strategy**: Click "+" on a school row, type deadline name "出願" and date "2026-12-15", click "保存". Assert a new dot with label "出願" appears in the December column. Reload the page and verify the deadline persists.

### Component 4: Inline Stage Progress Bar (Timeline Replacement)

- **Files to modify**: `frontend/src/App.jsx` (the timeline section within the per-school card, around lines 914-927)
- **Purpose**: Replace the `<details>` collapse in each sidebar school card with a compact 6-segment horizontal progress bar that visually shows the application stage progression.
- **Data dependency**: Each school card `app` has:
  - `stage_id` (string, e.g. `"contacting"`)
  - `timeline` (optional array of `{stage, label, start, end}` — kept for date display)
- **Stage order and definitions** (same ordering as `agent/state_machine.py` and `DashboardView.jsx`):
  ```js
  const STAGE_ORDER = ['preparing', 'contacting', 'applying', 'exam', 'waiting', 'decided'];
  const STAGE_LABELS = { preparing: '准备', contacting: '套磁', applying: '出愿', exam: '考试', waiting: '等待', decided: '确定' };
  const STAGE_COLORS = {
    preparing: 'hsl(var(--stage-preparing))',
    contacting: 'hsl(var(--stage-contacting))',
    applying: 'hsl(var(--stage-applying))',
    exam: 'hsl(var(--stage-exam))',
    waiting: 'hsl(var(--stage-waiting))',
    decided: 'hsl(var(--stage-decided))',
  };
  ```
- **Behavior**:
  1. For each school card that has a valid `stage_id` (one of the 6 stages, or "browsing"), render a horizontal flex container with 6 segments.
  2. If `app.stage_id` is "browsing" or not set, render nothing for the timeline section (the card may not need the bar).
  3. Each segment:
     - Width: `flex-1` (equal width).
     - Height: 6px.
     - Background color logic using the index of the current stage in `STAGE_ORDER`:
       - If 0-indexed position < current index: `fill="hsl(var(--stage-{id}) / 0.3)"` — completed, muted fill.
       - If equal to current index: `fill="hsl(var(--stage-{id}))"` — full color.
       - If greater than current index: `fill="hsl(var(--muted))"` — not yet reached.
     - First segment has `rounded-l-full`, last has `rounded-r-full`.
     - Segments have a 1px gap between them (`gap-px` or `gap-0.5`).
  4. Below the bar, render a label line: a small colored dot using the current stage color, followed by text like "当前: 套磁阶段" in `text-xs text-muted-foreground`.
  5. If `app.timeline` is an array with items, append the date range of the current stage below the label, e.g. "2026-10 ~ 2026-12" in even smaller text (`text-[10px] text-muted-foreground/60`).
- **States**:
  - **Stage is a valid tracking stage**: 6-segment bar is always rendered (no conditional hiding). Even "decided" renders all segments filled.
  - **Stage is "browsing" or missing/undefined**: skip rendering entirely. The card is in browsing state and doesn't need a timeline visual.
  - **No timeline dates available**: render the bar and label without the date line below.
- **Edge cases**:
  - Very narrow sidebar (after collapse-expand): use `min-w-0` to prevent overflow. Text truncation with CSS.
  - `app.stage_id` is `null` or `undefined`: treat as "browsing", skip rendering.
  - `app.timeline` exists but is an empty array: skip date display.
- **Playwright test strategy**: For a school in stage "contacting", assert 6 segments in the sidebar card. Assert the preparing and contacting segments are filled, and future ones are grey. Assert the label reads "当前: 套磁阶段".

---

## API Contract

No new endpoints. The existing `POST /v1/applications` is reused.

| Endpoint | Method | Request | Response | Errors |
|----------|--------|---------|----------|--------|
| /v1/applications | POST | `{ "school": "京都大学 情报理工", "deadlines": [{"name": "出願締切", "date": "2026-12-15"}] }` | `{ "ok": true, "school": "...", "applications": [...] }` | 401 (no auth), 500 (server error) |

The parent component `App.jsx` already provides `updateApplication(school, updates)` which calls this endpoint and refreshes both the stage data and greeting. Calendar adds a `handleCalendarAddDeadline` wrapper that appends to the existing deadlines array before calling `updateApplication`.

---

## Acceptance Criteria

- [ ] Calendar shows exactly 3 month columns at a time (verify by counting month header `<div>` elements — should be 3)
- [ ] Left arrow button (`<`) shifts the 3-month window backward by 1 month; right arrow (`>`) shifts forward by 1 month
- [ ] "今天" button resets the calendar to show the current month as the leftmost column
- [ ] Arrow navigation wraps correctly across year boundaries (navigating December to January changes the year label)
- [ ] Deadline dot background color changes by proximity band: <= 30 days uses `bg-urgency-high/15`, 31-60 days uses `bg-urgency-medium/15`, > 60 days uses `bg-muted`
- [ ] Expired deadlines use `bg-urgency-high/15` with "已过期 X 天" in the tooltip
- [ ] Deadline dots with <= 30 days remaining show "(X 天后)" in the visible inline label text
- [ ] Deadline dots with > 30 days remaining show no countdown suffix in the visible label (the tooltip still shows the countdown)
- [ ] Each school row in the calendar has a "+" button at the end
- [ ] Clicking "+" opens an inline form with a deadline name input and a date input
- [ ] Submitting the form calls `POST /v1/applications` and the new deadline dot appears in the correct month column immediately (no page refresh needed)
- [ ] Canceling the inline form closes it without adding a deadline
- [ ] Empty deadline name or empty date disables the save button
- [ ] Sidebar school card timeline section renders a 6-segment horizontal bar (there should be no `<details>` or `<summary>` elements in the timeline area)
- [ ] Each of the 6 segments corresponds to a stage: preparing, contacting, applying, exam, waiting, decided (in that order)
- [ ] Completed stages (index < current stage index) show the stage color at reduced opacity (muted/30% fill)
- [ ] Current stage shows the stage color at full opacity
- [ ] Future stages (index > current stage index) show the muted/default background color
- [ ] Below the bar, text reads "当前: {stage label}" (e.g. "当前: 套磁阶段") in the stage color
- [ ] When `app.timeline` contains items, the date range for the current stage appears below the label
- [ ] All UI text uses Chinese; no emoji appears in any label, button, or tooltip
- [ ] Zero console errors when navigating the calendar (left arrow, right arrow, today button, adding a deadline)
- [ ] Calendar with zero applications still shows "还没有追踪的学校，去「广场」添加吧" empty state (existing behavior, no regression)
- [ ] Sidebar school card with `stage_id: "browsing"` does not render the 6-segment bar
