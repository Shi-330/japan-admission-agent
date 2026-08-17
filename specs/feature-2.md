# Feature Spec: Chat Output Enrichment + Suggested Follow-ups

## Overview

Improve the chat user experience with richer markdown rendering (proper lists, blockquotes, inline code, tables, and plaza navigation links) and add contextual suggestion chips below each assistant response. After the SSE stream completes, the UI shows 2-3 action chips derived from the user's current needs and 2-3 follow-up question chips that auto-fill the input box. The `/v1/chat` SSE `done` event gains a `suggested_questions` field, and the inline regex renderer in `App.jsx` is replaced by a dedicated `ChatMessage` component. Backend generates follow-up questions via a lightweight post-stream LLM call.

## Components

### Component 1: ChatMessage (`frontend/src/components/ChatMessage.jsx`)

- **Files**: CREATE `frontend/src/components/ChatMessage.jsx`; MODIFY `frontend/src/App.jsx` (lines 1085-1192 — replace the inline chat bubble rendering with `<ChatMessage>`)
- **Purpose**: Render a single chat bubble with rich markdown formatting and all interactive payloads (nav suggestion, suggested schools, school cards, discovered schools, plaza links). Replaces the inline `dangerouslySetInnerHTML` + regex chain at App.jsx lines 1093-1099.
- **Props**:
  - `message: object` — `{ role, content, navSuggestion, suggestedSchools, schoolCards, discoveredSchools }`
  - `stage: object` — current stage data (for tracking which schools are already tracked)
  - `token: string` — auth token for API calls
  - `onNavigate: (tab, params?) => void` — switch to a tab with optional filter
  - `showToast: (msg, type?) => void` — toast notification
- **States**:
  - **Empty/null content**: Render no text area. Nav suggestions, school cards, and other interactive payloads still render if present. Never render the string "undefined" or crash.
  - **Normal content**: Render markdown via extended regex processor into `dangerouslySetInnerHTML`.
  - **Content with plaza link**: `[学校名](plaza:情报理工)` renders as a clickable chip button, not raw markdown.
  - **User messages**: Render as simple `<div>` text (no markdown processing).
  - **Assistant messages with interactive payloads**: Render the payload below the text (nav suggestion card, school card grid, etc.), unchanged from current behavior.
- **Markdown rendering pipeline** (applied in order; input is HTML-escaped first except inside code spans):

  1. **HTML escape**: `&` -> `&amp;`, `<` -> `&lt;`, `>` -> `&gt;` (before markdown processing).
  2. **Code span**: `` `code` `` -> `<code class="bg-muted px-1 rounded text-xs font-mono">code</code>`.
  3. **Blockquote**: Lines starting with `> ` (optionally preceded by whitespace) -> wrap consecutive blockquote lines in `<blockquote class="border-l-2 border-muted-foreground/30 pl-3 italic text-muted-foreground my-1">` (each line as a `<p>`).
  4. `### Title` / `## Title` -> `<h4 class="font-semibold text-sm mt-2 mb-1">Title</h4>`.
  5. **Bold**: `**text**` -> `<strong class="font-semibold">text</strong>`.
  6. **Italic**: `*text*` (single `*`, not double `**`) -> `<em>text</em>`.
  7. **Bullet lists**: Consecutive lines starting with `- ` or `* ` -> `<ul class="list-disc ml-5 space-y-0.5"><li>text</li>...</ul>`. Nested: a line starting with `  - ` (two-space indent) renders as a nested `<ul class="ml-4">` inside the parent `<li>`.
  8. **Numbered lists**: Consecutive lines matching `\d+\. ` -> `<ol class="list-decimal ml-5 space-y-0.5"><li>text</li>...</ol>`.
  9. **Tables**: Groups of lines matching `\|.+\|` pattern (at least 2 rows). A separator row `\|---+\|` is detected and skipped. Header row (first data row) cells get `<th class="font-medium text-left px-2 py-1">`, data rows get `<td class="px-2 py-1">`. Entire table rendered as `<table class="w-full text-xs border-collapse border border-border my-2"><thead>...</thead><tbody>...</tbody></table>`. If only 2 columns, also add a `grid grid-cols-2` fallback on a wrapper for narrow viewports.
  10. **Plaza link**: `[text](plaza:filter)` -> `<button class="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition font-medium" data-plaza-link="true" data-filter="filter">text</button>`. The component attaches a click handler via `useEffect` that calls `onNavigate('plaza', { filter })`.
  11. **Line breaks**: Remaining `\n` -> `<br />` (applied last, after list/table grouping).

- **Grouping algorithm**: The component splits content by `\n` into lines, then iterates with look-ahead to detect consecutive list items, blockquote lines, and table rows. These are replaced with their HTML equivalents before the final join. The algorithm processes left-to-right: plaza links (highest priority, processed before any other inline formatting), then blockquote/lists/tables (block-level, processed after inline).

- **Behavior for interactive payloads**: These are rendered as separate React child elements after the `dangerouslySetInnerHTML` div, using the exact same JSX as the current App.jsx lines 1100-1189. The component checks `message.navSuggestion`, `message.suggestedSchools`, `message.schoolCards`, `message.discoveredSchools` in order and renders each if present.

### Component 2: Suggestion Chips (inline in App.jsx)

- **Files**: MODIFY `frontend/src/App.jsx` (after the SSE done handler, after the message list in the chat tab, around line 1193, before the closing `</AnimatePresence>`)
- **Purpose**: After each complete assistant response in the chat tab, render 2 rows of chips below the last assistant bubble: action chips (tab navigation) and question chips (input fill-in).
- **State variables** (add to App.jsx):
  - `lastSuggestedQuestions: string[]` — cleared to `[]` at the start of each `sendMessage`, set from `parsed.suggested_questions` when `parsed.done` is true in the SSE reader.
- **Behavior**:
  1. After the assistant message is rendered (the last `<motion.div>` in the messages array), if the last message has `role: 'assistant'` and is the final element, render chips below it.
  2. **Action chips row**: At most 3 chips from `greeting?.next_actions || []`. Filter to `priority === 'high'` first, then take 3. If fewer than 2 high-priority actions exist, fill with medium-priority. Each chip is a `<button>` that calls `onNavigate(action.tab, action.params)`. If `greeting?.next_actions` is empty/absent, show 2 static fallback chips: "去广场看看" (`onNavigate('plaza')`) and "查看申请进度" (`onNavigate('home')`).
  3. **Question chips row**: Up to 3 chips from `lastSuggestedQuestions`. Each chip is a `<button>` that calls `setInput(q)` and focuses the input element. If `lastSuggestedQuestions` is empty, this row is not rendered.
  4. **Styling**: Both rows use `flex flex-wrap gap-2 mt-3`. Each chip is `<button class="text-xs px-3 py-1.5 rounded-full border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground transition">`. The action row is separated from the message bubble by `<hr class="my-2 border-muted" />`.
  5. **Positioning**: The chip blocks are rendered inside the chat scroll area (`<div ref={scrollRef}>`), immediately after the last `<motion.div>` in the messages array and before `{loading && ...}`. They are only rendered when the last message is an assistant message (not during streaming — checked via `!loading && messages.length > 0 && messages[messages.length-1].role === 'assistant'`).
- **States**:
  - **Loading (stream in progress)**: Chips are not rendered. Only rendered after `loading` becomes false.
  - **Greeting data available, no suggested questions**: Show action chips only (from `next_actions`). No question row.
  - **Greeting data empty, no suggested questions**: Show 2 fallback action chips. No question row.
  - **Greeting data available, suggested questions available**: Show both rows.
  - **Greeting data empty, suggested questions available**: Show fallback action chips + question chips.
  - **All data empty**: Show only the 2 fallback action chips.
- **Edge cases**:
  - User sends a new message before clicking any chip: `lastSuggestedQuestions` is cleared, chips disappear. New chips appear when the new response completes.
  - Very long action label (> 15 CJK chars): CSS `max-w-[200px] truncate` with full text in `title`.
  - Rapid clicking on "去广场看看" chip: sets activeTab to 'plaza', which unmounts the chat area. This is fine — the chip click is a navigation action.
  - Clicking a question chip that contains special characters: `setInput` sets the input state directly, which is displayed in the controlled `<Input>` component. No injection risk because React handles string rendering safely.

### Component 3: SuggestionChips — rendered inline in the chat area of App.jsx

- **No separate file** — rendered directly in App.jsx after the message list.
- **Props/Inputs** (all from App.jsx state):
  - `greeting: object | null` — from `/v1/greeting` endpoint
  - `lastSuggestedQuestions: string[]` — from the SSE done event
  - `onNavigate: (tab, params?) => void` — tab navigation callback
  - `setInput: (text) => void` — set the input box value
  - `inputRef: RefObject` — ref to the input element for focusing after chip click
  - `loading: boolean` — whether a response is currently streaming
  - `messages: object[]` — to check the last message role
- **Implementation note**: Because this rendering is conditional on `!loading && messages[messages.length-1]?.role === 'assistant'`, it appears after each completed response and disappears when the user starts typing a new message.

### Component 4: Backend Suggested Questions Generator (in `backend/api/server.py`)

- **Files**: MODIFY `backend/api/server.py` (inside `event_generator` in `/v1/chat`, after the main LLM stream and before the final SSE `done` event, around lines 609-642)
- **Purpose**: Generate 2-3 short follow-up questions after each assistant response, appended to the SSE `done` event as `suggested_questions`.
- **Behavior**:
  1. After the main LLM response has been fully streamed (variable `assistant_text` is complete), and after the cache/ finish_turn calls but before the `actions_to_sse_events` + final yield, make a lightweight LLM call to generate follow-up questions.
  2. **Prompt**: `"你是日本升学顾问。根据以下对话，为学生生成3个后续问题。每个问题不超过30个字，用中文。直接输出JSON：{"questions": ["问题1", "问题2", "问题3"]}\n\n对话：\n{query}\n\n助手的回答：\n{assistant_text}"`
  3. **LLM call**: Use `chat_model.invoke()` (synchronous call, not streaming). Set a 5-second timeout via `asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, lambda: chat_model.invoke(...)), timeout=5.0)`.
  4. **Parse**: Attempt `json.loads()` on the response text, extracting `questions` array. Validate each item is a string under 30 characters. If parsing fails or the array is empty, log a warning and skip.
  5. **Add to done event**: `final_event["suggested_questions"] = validated_questions`.
  6. **Error handling**: The entire generation is wrapped in `try/except`. Any failure (timeout, parse error, rate limit, etc.) results in the done event being sent without `suggested_questions`. The endpoint does NOT return HTTP 500 for this.
  7. **Caching**: `suggested_questions` is NOT cached in the response cache — it is always freshly generated even for cached responses (since the user's context changes).
- **Prompt design notes**:
  - Questions should be short enough to fit in a chip label (under 30 CJK characters).
  - Questions should be contextual to the last exchange, not generic (e.g., after explaining N2 requirements, suggest "N2能申请哪些学校?" not "还有什么问题?").
  - The LLM is instructed to prefer questions that would lead to school discovery, application timeline, or language requirements (the most common user intents).

## API Contract

### Modified: `POST /v1/chat` SSE done event

The final SSE `done` event gains an optional `suggested_questions` field:

| Field | Type | Always present? | Description |
|-------|------|----------------|-------------|
| `done` | `true` | always | Signals end of stream |
| `nav_suggestion` | `object\|null` | optional | From intent layer actions |
| `suggested_schools` | `string[]` | optional | School names to track |
| `school_cards` | `object[]` | optional | School match cards |
| `discovered_schools` | `object[]` | optional | Web-discovered schools |
| `reminders` | `object[]` | optional | Professor reminders |
| `suggested_questions` | `string[]` | optional | 2-3 follow-up questions, each under 30 chars, Chinese |

Example done event:

```json
{
  "content": "",
  "is_status": false,
  "done": true,
  "suggested_questions": ["N2能申请哪些学校？", "东京有哪些情报理工方向？", "套磁信怎么写？"]
}
```

### Error behavior

- If the LLM call for question generation times out or returns invalid JSON, the `done` event is sent without `suggested_questions`. No HTTP 500.
- If generated questions are over 30 characters, they are truncated to 30 characters. If truncation makes them meaningless (less than 5 chars), the entire array is dropped.
- If the LLM returns fewer than 2 questions, the array is still included as-is (frontend handles 0-3 chips gracefully).

## Acceptance Criteria

All criteria must be verifiable via Playwright browser automation (click, type, assert visible text, assert element presence, assert console events).

### ChatMessage Markdown Rendering

- [ ] Bullet list items (lines starting with `- `) in assistant responses render as `<ul><li>` HTML elements, not flat `· ` span-dot spans. Verified by `page.evaluate(() => document.querySelector('.chat-message ul'))` or checking innerHTML for `<li>` tags.
- [ ] Numbered list items (lines matching `1. text`, `2. text`) render as `<ol><li>` HTML elements. Verified by checking for `<ol>` in the rendered bubble.
- [ ] Backtick inline code `` `code` `` renders as `<code>` element with monospace font. Verified by checking the tag name of the element containing backtick content.
- [ ] Blockquote lines (starting with `> `) render as `<blockquote>` element with italic text and left border. Verified by checking for `<blockquote>` tag in the rendered bubble.
- [ ] Table rows (`| col1 | col2 |`) render as `<table>` with `<th>/<td>` structure, not raw pipe characters. Verified by checking for `<table>` in the rendered HTML.
- [ ] `[学校名](plaza:情报理工)` renders as a clickable button chip (not an `<a>` tag). Verified by clicking the chip and checking that `activeTab` becomes `'plaza'` and the plaza filter input contains `"情报理工"`.
- [ ] Malformed plaza link `[text](plaza:)` with empty filter still renders as clickable chip; clicking navigates to plaza with no filter change (shows all schools). Verified by checking the tab switches but filter remains the same.

### Suggestion Chips After Assistant Response

- [ ] After streaming completes (`loading` becomes false) and the last message is an assistant message, 2-3 action chips appear below it. Verified by checking for visible `<button>` elements with class containing `rounded-full` after the last motion-div.
- [ ] Action chip labels match those in `greeting.next_actions[].label` (e.g., "设定研究方向", "去广场浏览学校"). Verified by text content.
- [ ] Clicking an action chip navigates to the correct tab (chip with `tab: "plaza"` activates the plaza tab). Verified by checking the tab bar's active state after click.
- [ ] Clicking a question chip fills the input box with that question text. Verified by `page.inputValue('input[placeholder*="输入"]')` matching the clicked chip text.
- [ ] When `greeting.next_actions` is empty (e.g., fresh profile with nothing missing), the 2 fallback chips "去广场看看" and "查看申请进度" appear instead. Verified by asserting those button texts exist after a chat response.
- [ ] Chips do NOT appear during streaming (while `loading` is true). Verified by sending a message and asserting no chip buttons exist until the response completes.

### Suggested Questions (Backend)

- [ ] A chat response triggers the backend to generate 2-3 `suggested_questions` in the done event. Playwright intercepts the SSE stream via `page.route('**/v1/chat', ...)` and captures the last data event, verifying it contains `suggested_questions` as a non-empty array of strings under 30 chars each.
- [ ] When the LLM question generation fails (simulated by making the LLM return invalid JSON), the done event still arrives without `suggested_questions`. Playwright intercepts the SSE and verifies the done event has no `suggested_questions` field, and the frontend does not crash.
- [ ] Each `suggested_questions` item is a valid Chinese question under 30 characters. Verified by checking string length and content.

### Console and Errors

- [ ] Zero `console.error` calls after a full chat session of 10+ messages spanning school search, application help, and greeting topics. Playwright attaches `page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()) })` and asserts the error array is empty.
- [ ] Zero `console.warn` calls from the chat markdown renderer (expected warns from SSE parse in line 502 are the only allowed warn source). Verified by the same console listener.
- [ ] ChatMessage component renders nothing (not "undefined") when `message.content` is null. Verified by sending a message that produces an assistant message with only interactive payloads (e.g., a pure school card response) and asserting no text node containing "undefined".

### UI Consistency

- [ ] No emoji characters in any chip label or rendered markdown text. Verified by checking chip `textContent` against `/\p{Emoji}/u` regex.
- [ ] All chip labels and rendered text use Simplified Chinese (no English fallback for labels).
- [ ] The chat area scrolls to the bottom automatically when new chips appear (existing scroll-to-bottom behavior via `useEffect` on `messages` must include chip rendering height).

## Edge Cases

- **ChatMessage content is null/undefined**: Renders nothing for the text portion but renders navSuggestion, schoolCards, suggestedSchools, discoveredSchools if present. Never renders the string "undefined" or crashes with `.map` on null.
- **ChatMessage content is empty string**: Same as null — renders no text bubble, but interactive payloads still show.
- **No greeting data available at app start**: The action chips fall back to 2 static chips ("去广场看看", "查看申请进度"). This is already handled by the fallback in `loadGreeting()` (App.jsx line 175).
- **`suggested_questions` array from backend is empty**: The question chip row is omitted entirely. Only action chips (or their fallback) are shown.
- **Suggested question text longer than 30 characters**: The backend enforces the 30-char limit at generation time. If the LLM produces longer text, the backend truncates and drops duplicates. The frontend does no additional truncation.
- **Very long list (50+ items)**: The `<ul>`/`<ol>` renderer groups all consecutive list items. No virtual scrolling — the bubble scrolls naturally with the page.
- **Malformed plaza link `[text](plaza:)` with empty filter**: The chip is still rendered but clicking navigates to plaza with no filter change.
- **Rapid consecutive messages (user sends 3 messages quickly)**: Each message's chips replace the previous chips. `lastSuggestedQuestions` is cleared at the start of each `sendMessage` call (before the fetch). Chips from old responses disappear immediately when user sends a new message.
- **Assistant message with only interactive payloads and no text content**: ChatMessage renders the payload cards/chips but shows no text bubble element. Action chips and question chips still render below.
- **Suggested questions generation LLM call times out**: Wrapped in `asyncio.wait_for(..., timeout=5)`. On timeout, the done event is sent without `suggested_questions`. The frontend shows fallback chips. No SSE stream interruption.
- **Chat area empty (no messages yet)**: Chips condition checks `messages.length > 0` and `messages[messages.length-1]?.role === 'assistant'`. With zero messages, no chips render.
- **User message is the latest**: The `role === 'assistant'` check prevents chips from rendering below a user message (they only appear after the assistant has replied).
- **Plaza link inside a list item**: The markdown pipeline processes plaza links first (highest priority) before list grouping, so `- [学校](plaza:filter)` correctly renders as a list item containing a plaza chip button.
