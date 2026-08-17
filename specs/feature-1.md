# Feature Spec: Countdown + Urgency Visualization on Tracking Cards

## Overview

Replace all static deadline date text and professor contact-status timestamps across the sidebar school cards and the DashboardView with live, client-side computed countdown labels and urgency-colored visual cues. This lets the user see at a glance how many days remain before each deadline, which deadlines are past due, and which professors have not replied beyond a reasonable window -- all without mentally computing dates from raw ISO strings. All countdowns are recomputed at render time, so they survive tab switches without stale intervals.

## Components

### Component 1: Sidebar School Card -- Deadline Countdown Labels

- **Files to modify**: `frontend/src/App.jsx` (lines 792-820)
- **Purpose**: Replace raw deadline date strings (`item.date`, `item.start`, `item.raw`) with computed countdown labels that reflect time remaining or days past due. Both array format (`[{name, date, start, end, raw}]`) and object format (`{[key]: string}`) are handled for both `app.deadlines` and `app.official_deadlines`.
- **Props/Inputs**: `app.deadlines` and `app.official_deadlines` -- already available in the per-school card render scope.
- **States**:
  - `>14 days away`: label `"X 天后"`, class `text-muted-foreground` (grey via `hsl(var(--muted-foreground))`)
  - `7-14 days away`: label `"X 天后"`, class `text-urgency-medium` (amber via `hsl(var(--urgency-medium))`)
  - `0-7 days away`: label `"X 天后"`, class `text-urgency-high` (red via `hsl(var(--urgency-high))`) + framer-motion `<motion.span>` with pulse animation (`animate={{ opacity: [1, 0.5, 1] }} transition={{ repeat: Infinity, duration: 2 }}`)
  - `expired` (days < 0): label `"已过期 X 天"`, class `text-urgency-high italic` (red + italic)
  - `unparseable date` (only `raw` field, no `date` or `start`): render `item.raw` as-is without countdown, no urgency class
- **Behavior**:
  1. For each deadline entry in both `app.deadlines` and `app.official_deadlines`, compute `days = Math.ceil((new Date(dateStr) - new Date()) / 86400000)` at render time.
  2. If `days >= 0`, render `"{days} 天后"` inside a `<span>` with the appropriate urgency class.
  3. If `days < 0`, render `"已过期 {Math.abs(days)} 天"` with `text-urgency-high italic`.
  4. For the 0-7 day band, wrap the countdown text in `<motion.span animate={{ opacity: [1, 0.5, 1] }} transition={{ repeat: Infinity, duration: 2 }}>` (framer-motion is already imported at App.jsx line 3).
  5. The countdown label replaces the date portion in the existing format: `"{name}: {countdownLabel}"`. Keep the `[锁]` prefix for official deadlines and the `×` delete button for user-added deadlines unchanged.
  6. Span-level `onClick` handlers for deleting user-added deadlines are preserved exactly as-is (lines 797-801, 809-815).
  7. No emoji anywhere.
  8. To extract the countdown logic cleanly and avoid repetition across the four branches (array deadlines, object deadlines, array official, object official), define a small helper function at the top of the component scope (or inline in the render block):

     ```js
     function deadlineLabel(dateStr) {
       if (!dateStr) return null;
       const d = new Date(dateStr);
       if (isNaN(d.getTime())) return null;
       const days = Math.ceil((d - new Date()) / 86400000);
       if (days < 0) return { text: `已过期 ${Math.abs(days)} 天`, cls: 'text-urgency-high italic', expired: true };
       if (days <= 7) return { text: `${days} 天后`, cls: 'text-urgency-high', urgent: true };
       if (days <= 14) return { text: `${days} 天后`, cls: 'text-urgency-medium' };
       return { text: `${days} 天后`, cls: 'text-muted-foreground' };
     }
     ```

### Component 2: Sidebar School Card -- Professor Overdue Banner

- **File to modify**: `frontend/src/App.jsx` (insert after line 768, within the per-school card, after the professors `<div>` and before the deadline sections)
- **Purpose**: Show an inline banner on a school card when any professor has `status === "no_reply"` and the time elapsed since their `date` >= 14 days.
- **Props/Inputs**: `app.professors` (already in scope), `setSelectedProf` state setter (already in scope at line 327)
- **States**:
  - `no overdue professors`: render nothing (no container, no zero-height element)
  - `one or more overdue professors`: render one banner row per overdue professor
- **Behavior**:
  1. After the professors section (`</div>` at line 768), loop through `app.professors`.
  2. For each professor where `p.status === 'no_reply'` and `p.date` is truthy, compute `daysSinceContact = Math.ceil((new Date() - new Date(p.date)) / 86400000)`.
  3. If `daysSinceContact >= 14`, render a banner `<div>` with classes: `"text-xs bg-urgency-medium/10 border border-urgency-medium/30 rounded px-2 py-1 mb-1 flex items-center justify-between"`.
  4. Banner text: `"教授 {p.name} {daysSinceContact} 天未回复，建议跟进"`.
  5. Append a clickable icon or button that calls `setSelectedProf({ school: app.school, professorName: p.name })`. Reuse the same `FileText` icon pattern from the existing professor chip (line 758) or use a simple `<button>` with `className="text-urgency-medium hover:text-urgency-high underline"` and text `"写邮件"`.
  6. If multiple professors are overdue, render one banner per professor, each as a separate `<div>` stacked vertically.
  7. No emoji.

### Component 3: DashboardView Nearest Deadline Card -- Live Countdown Ticker

- **File to modify**: `frontend/src/components/DashboardView.jsx` (lines 243-271)
- **Purpose**: Replace the static render of `nearestDl.days` with a live countdown that recalculates every 60 seconds using `useEffect` + `setInterval`, so the displayed days-remaining visibly ticks down without a page refresh.
- **Props/Inputs**: `nearestDl` object `{school, name, days, date}` (already computed at lines 94-105). No new props.
- **States**:
  - `nearestDl present`: card visible with live countdown
  - `nearestDl null`: card not rendered (no change from current behavior)
- **Behavior**:
  1. Inside the IIFE at line 243 (`nearestDl && (() => { ... })()`) or by extracting a small sub-component, introduce a local tick state:
     ```js
     const [tick, setTick] = useState(Date.now());
     useEffect(() => {
       const id = setInterval(() => setTick(Date.now()), 60000);
       return () => clearInterval(id);
     }, []);
     ```
  2. Compute `liveDays = Math.ceil((new Date(nearestDl.date) - new Date(tick)) / 86400000)` instead of using `nearestDl.days` directly.
  3. Pass `liveDays` to the existing `urgencyClasses()` function (lines 24-29) for the background, text, and border colors.
  4. The progress bar at lines 260-267 uses `liveDays` instead of `nearestDl.days`: `style={{ width: \`${Math.max(5, 100 - liveDays * 3)}%\` }}`.
  5. The label at line 256: `liveDays >= 0 ? \`${liveDays} 天后\` : \`已过期 ${Math.abs(liveDays)} 天\``.
  6. Cleanup via `clearInterval` on unmount via the `useEffect` return.
  7. On tab switch back to DashboardView, the `useEffect` runs again, starting a fresh interval. No stale closure issue since `nearestDl.date` is read from the closure at each interval tick (or use a ref if needed).

### Component 4: DashboardView KPI Deadline Card -- Overdue Counter

- **File to modify**: `frontend/src/components/DashboardView.jsx` (lines 139-153, specifically the subtitle on line 150)
- **Purpose**: Add a counter `"已过期 X 个"` to the KPI deadline card's subtitle alongside the existing `"最近: X 天后"` text, so the user can see at a glance how many deadlines have passed.
- **Props/Inputs**: `applications` array (already in scope at line 60). No new props.
- **States**:
  - `overdueCount > 0`: subtitle shows `"{overdueCount} 个已过期 / 最近: {nearestDl.days} 天后"`
  - `overdueCount === 0`: subtitle shows `"最近: {nearestDl.days} 天后"` (unchanged)
  - `nearestDl === null`: subtitle shows `"暂无临近截止日"` (unchanged)
- **Behavior**:
  1. Before the return statement (e.g., near line 106), compute overdue count:
     ```js
     let overdueCount = 0;
     if (applications) {
       for (const app of applications) {
         for (const [, dateStr] of Object.entries(app.deadlines || {})) {
           const d = new Date(dateStr);
           if (isNaN(d.getTime())) continue;
           if (Math.ceil((d - new Date()) / 86400000) < 0) overdueCount++;
         }
       }
     }
     ```
  2. On line 150, replace the template literal:
     ```js
     nearestDl
       ? overdueCount > 0
         ? `${overdueCount} 个已过期 / 最近: ${nearestDl.days} 天后`
         : `最近: ${nearestDl.days} 天后`
       : '暂无临近截止日'
     ```
  3. The overdue count is static at render time (no interval needed -- it only changes when `applications` data changes via greeting load).
  4. No emoji.

## Acceptance Criteria

- [ ] Every deadline shown in a sidebar school card displays a client-side computed countdown label ("15 天后", "已过期 3 天"), never the raw ISO date string. Verified by Playwright inspecting deadline span text for the pattern `/\d+ 天后|已过期 \d+ 天/` after loading a user with known deadlines.
- [ ] Countdown labels in sidebar cards use the correct urgency color classes: grey (`text-muted-foreground`) for >14 days, amber (`text-urgency-medium`) for 7-14 days, red (`text-urgency-high`) for 0-7 days, red+italic (`text-urgency-high italic`) for expired. Verified by Playwright `toHaveClass` assertions on the countdown `<span>` element.
- [ ] Sidebar deadline in the 0-7 day band renders a framer-motion `<motion.span>` wrapper that applies a pulsing opacity animation. Verified by checking that the inner span's inline `style` attribute contains an `animation` property or that its computed opacity changes over time (observed via `page.evaluate` at two snapshots 1 second apart).
- [ ] Professor overdue banner appears on the specific school card when a professor has `status === "no_reply"` and `date` >= 14 days ago. Banner text matches pattern `"教授 .+ \d+ 天未回复，建议跟进"`. Verified by Playwright `toContainText` or regex match on the banner element.
- [ ] Clicking the overdue banner's action button opens the OutreachDraft dialog. Verified by Playwright clicking the banner button and asserting the dialog with heading "套磁邮件草稿" is visible (`page.locator('text=套磁邮件草稿')`).
- [ ] No overdue banner renders when all professors have `status` values other than `no_reply`, or when `no_reply` professors have `date` less than 14 days ago. Verified by asserting the banner locator `locator('.bg-urgency-medium\\/10')` has `count === 0` in the card.
- [ ] DashboardView nearest deadline card countdown updates visibly within 60 seconds without page refresh. Verified by Playwright: read the liveDays text, advance the system clock 61 seconds via `page.clock.fastForward(61000)`, then assert the displayed number has changed. If `page.clock` is unavailable, verify that the `useEffect` + `setInterval` mechanism exists by asserting the tick state changes after a manual wait (accepting a slower test), or verify the DOM re-renders by checking the countdown span contains a numeric value that matches the expected decrement.
- [ ] DashboardView KPI deadline card shows `"X 个已过期 / 最近: Y 天后"` when at least one deadline is past due. Verified by seeding a user with an expired deadline and asserting the subtitle text matches the combined pattern.
- [ ] DashboardView KPI deadline card shows only `"最近: X 天后"` when no deadlines are past due. Verified with a user whose nearest deadline is in the future (all deadlines have positive days).
- [ ] DashboardView KPI deadline card shows `"暂无临近截止日"` when there are no deadlines (nearestDl is null). Verified with a user who has no applications.
- [ ] All countdowns survive tab switches: navigating from "申请进度" to "聊天" and back recomputes countdowns fresh on mount. Verified by Playwright clicking the chat tab, waiting 2 seconds, clicking the tracking tab back, then asserting the countdown `<span>` still contains a valid `\d+` number.
- [ ] Sidebar card with a deadline entry that has only a `raw` field (no `date` or `start`) shows the raw string as-is, not a countdown label. Verified by adding a deadline with only `{name: "test", raw: "2026年春頃"}` and asserting the rendered text does not contain "天后" or "过期".
- [ ] No emoji characters appear in any countdown label, overdue banner text, or KPI subtitle. Verified by Playwright asserting that no element's textContent matches the Unicode emoji pattern `/\p{Emoji}/u` within the relevant sections.

## Edge Cases

- **Multiple overdue professors on one school**: Each renders a separate banner, stacked vertically. Verified by testing two professors both with `no_reply` and dates 20 days ago -- two banner `<div>` elements should appear.
- **Professor with `no_reply` but no `date` field**: Skip -- do not render a banner for that professor. The date field is optional.
- **Professor with `no_reply` and date less than 14 days ago**: No banner. Threshold is strictly `>= 14`.
- **Deadline exactly 0 days away (today)**: `Math.ceil(0) = 0`, caught by `days >= 0 && days <= 7` band. Shows as "0 天后" in red with pulse. This is correct -- the deadline is today.
- **Deadline at exactly 7 days**: `Math.ceil(7) = 7`, belongs in 7-14 day amber band. The condition `days >= 7 && days <= 14` yields amber.
- **Deadline at exactly 14 days**: `Math.ceil(14) = 14`, belongs in >14 day grey band. The condition `days > 14` yields grey.
- **Deadline that expired earlier today**: `Math.ceil((pastToday - now) / 86400000)` could be `0` or `-0`. If `0`, treat as expired (red+italic) since the deadline day has arrived and is effectively past. Use `days <= 0` for the expired branch.
- **Leap year date `2028-02-29`**: Standard `new Date("2028-02-29")` parses correctly in JS. Countdown computes normally.
- **Sidebar card with no deadlines at all**: Existing conditional `{(app.deadlines && ...length > 0) && (...)}` skips rendering. No change needed.
- **DashboardView nearest deadline card when `nearestDl` is null**: Not rendered (existing `{nearestDl && ...}` wrapper). No change needed.
- **DashboardView loading state**: The entire component returns a spinner at line 64. No deadline card is rendered. No change needed.
- **User edits deadline via sidebar inline form**: `updateApplication` at line 425 calls the API and re-fetches stage data, which triggers a re-render with fresh countdown values. No additional synchronization needed.
- **Very large deadline count (e.g., 365+ days)**: Displayed as "365 天后" with grey `text-muted-foreground` class. No truncation needed.
- **Very old expired deadline (e.g., 2 years ago)**: Displayed as "已过期 730 天" with `text-urgency-high italic`. Overflow is possible in the card's flex-wrap container -- verify the text wraps cleanly without breaking the layout. Test with a deadline 999 days past.
- **DashboardView overdue count and nearest deadline refer to different data**: These are independent computations. The overdue count counts all past-due deadlines across all schools. The nearest deadline shows the soonest upcoming deadline. They can coexist in the same KPI card subtitle.
