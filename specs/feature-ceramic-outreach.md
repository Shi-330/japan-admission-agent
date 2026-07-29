# Feature: 套磁信生成 + 出愿 Timeline

## Context
Chat 现在能精准定位到实验室/教授级别，但用户还需要自己写套磁信（日语/英语）和跟踪出愿时间。
这两个是留学申请中用户最焦虑、最愿意付钱的功能。

## Deliverables

### 1. `/v1/draft` — AI 生成套磁信草稿

**Input:**
```json
{
  "school_name": "東京大学 情報理工学系研究科",
  "professor_name": "田中太郎",        // optional, LLM may extract from chat
  "research_topic": "FWI 全波形反演",  // from chat context
  "style": "formal_jp" | "formal_en",  // 日文敬语 or 英文
  "include_papers": true               // 能否提及教授的近期论文
}
```

**Output:**
```json
{
  "subject": "東京大学大学院入学のご相談（研究生・修士）",
  "body": "拝啓\n\n突然のご連絡失礼いたします。...",
  "suggestions": ["建议在第三段提及具体论文DOI"],
  "translation": "English translation..."
}
```

**How:**
- LLM prompt with: student profile + target school/professor + research direction
- Template includes 自己紹介 → 研究兴趣 → 与教授方向的契合点 → 询问接收可能性
- Japanese version uses 敬語 (keigo), English version is academic style

**Files:**
- `backend/api/server.py` — new endpoint `POST /v1/draft`
- `frontend/src/components/OutreachDraft.jsx` — existing! Already has draft UI, just needs API hookup

### 2. `/v1/timeline` — 出愿 Timeline 生成

**Input:**
```json
{
  "schools": ["東京大学 情報理工学系研究科", "京都大学 情報学研究科"]
}
```

**Output:**
```json
{
  "events": [
    {"date": "2026-10-01", "school": "東京大学", "event": "出願開始", "type": "deadline"},
    {"date": "2026-12-15", "school": "東京大学", "event": "出願締切", "type": "deadline"},
    {"date": "2026-08-01", "school": "京都大学", "event": "事前連絡期限", "type": "contact"}
  ],
  "warnings": ["東京大学 TOEFL需要在11月前取得", "京都大学 教授内諾必須"]
}
```

**How:**
- Read deadlines JSONB from graduate_schools for tracked schools
- Parse structured dates, sort chronologically
- Add LLM-generated reminders (e.g. "建议在截止前2个月完成语言考试")

**Files:**
- `backend/api/server.py` — new endpoint `GET /v1/timeline`
- `frontend/src/App.jsx` — hook into existing CalendarView

### 3. Chat integration: "生成套磁信" quick action

In chat flow, when LLM identifies a school+professor match, add a quick-action:
```json
{"type": "draft_email", "school": "...", "professor": "..."}
```
Frontend renders a "写套磁信" button next to the card.

## File Changes
- `backend/api/server.py` — 2 new endpoints
- `frontend/src/components/OutreachDraft.jsx` — hook to real API
- `frontend/src/components/CalendarView.jsx` — show generated timeline
- `specs/feature-ceramic-outreach.md` — this file

## Verification
1. Chat: ask "帮我给东大情报理工的田中教授写封套磁信"
2. Timeline: track 2 schools, visit calendar tab, see generated events
