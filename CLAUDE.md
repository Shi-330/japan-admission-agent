# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

Japan-Admission-Agent — AI consultant for Japanese university (master's) admissions.
Core capabilities: student profile memory, private knowledge base (RAG), school matching,
application stage tracking, and report generation.

Backend: FastAPI. Frontends: React (students) + Streamlit (admin).
Supabase handles auth, profiles, RAG vectors, and school data.

## How to Start

```bash
# Single command: backend + frontend both on port 8000
venv/Scripts/python.exe -m uvicorn backend.api.server:app --host 0.0.0.0 --port 8000

# Visit: http://localhost:8000
```

After editing frontend code: `cd frontend && npm run build`, refresh browser.

No separate frontend server needed (FastAPI serves `frontend/dist/` as static files).

Test account: `test@example.com` / `AgentV2_test!`

## Architecture

```
                    ┌── agent/orchestrator.py (chat pipeline, zero-UI)
FastAPI (:8000) ───┼── agent/state_machine.py (per-school stage tracking)
                    ├── user/profile_manager.py (UserProfile V2 + Supabase CRUD)
                    ├── rag/rag_service.py (pgvector semantic search)
                    └── demo/matching_engine.py (deterministic school matching)

React (:5173) ─── consumes /v1/* endpoints (chat SSE, profile, match, rag, stage)
Streamlit (:8501) ─── admin panel, also consumes same agent/ modules
```

Key rule: `agent/`, `rag/`, `user/`, `utils/` are Streamlit-free.
Both FastAPI and Streamlit call the same `agent/orchestrator.py`.

## API Endpoints (FastAPI :8000)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | no | Health check |
| GET | /v1/profile | JWT | Read user profile |
| PUT | /v1/profile | JWT | Update profile fields |
| POST | /v1/match | JWT | Deterministic school matching |
| POST | /v1/rag | no | Semantic search knowledge base |
| POST | /v1/chat | JWT | Intent classify → route → SSE stream |
| GET | /v1/stage | JWT | Current application stage + timeline |
| POST | /v1/stage/advance | JWT | Advance to next stage |

Auth: `backend/api/auth.py` — verifies Supabase JWT via API call (fallback: local decode).

## UserProfile V2 (`user/profile_manager.py`)

Pydantic model with these key additions over V1:
- `target_degree` (default "修士"), `research_area`
- `gpa_score` + `gpa_scale` (normalized to 4.0 via `gpa` property)
- `facts: dict` — AI free-form storage, no schema. LLM drops anything worth remembering.
- `events: list[dict]` — timeline entries `{date, event, source}`, deduplicated
- `applications: list[dict]` — per-school tracking (see V2.2 below)
- `field_sources: dict` — `{field: {source: "form"|"chat_inferred", at: ISO}}`. Form always wins.

ProfileManager methods:
- `merge_delta(profile, delta)` — merge LLM-extracted changes with source priority
- `extract_facts_from_chat(profile, conversation, chat_model)` — LLM scans for new facts
- `format_for_prompt(profile)` — renders full profile including facts, events, applications
- `upsert_application(school, **kwargs)` / `add_professor_attempt(school, prof, status, date)`

## V2.2 Application Tracking (WIP)

Per-school, per-professor data model:

```python
applications: [
    {
        "school": "京都大学 情报理工",
        "stage": "contacting",          # preparing/contacting/applying/exam/waiting/decided
        "needs_contact": True,
        "professors": [
            {"name": "田中太郎", "status": "sent", "date": "2026-06-20"},
            {"name": "山田花子", "status": "sent", "date": "2026-07-05"}
        ],
        "deadlines": {"出願": "2026-12-15"},
        "notes": "田中2周未回，已换山田"
    },
    {
        "school": "北海道大学 情报科学",
        "stage": "preparing",
        "needs_contact": False,
        "professors": [],
        "deadlines": {"出願": "2027-01-20"}
    }
]
```

Key: each school has its own stage. Each professor within a school has independent
contact status. 2-week no-reply → switch professor or school.

State machine definitions in `agent/state_machine.py` (STAGES dict).

## V2 Remaining Tasks

| Task | Status | What |
|------|--------|------|
| V2.1 Profile 2.0 | done | facts, events, field_sources, gpa_scale, extraction |
| V2.2 State Machine | WIP | per-school tracks + professor attempts done. TODO: extraction prompt, React cards, reminder logic |
| V2.3 Private DB | todo | real senpai cases, structured import |
| V2.4 Hybrid Search | todo | metadata filter + vector + BM25 |
| V2.5 Frontend Dashboard | todo | stage cards UI in React |
| V2.6 Email Automation | todo | OAuth + draft + confirm + track |
| FastAPI + Auth | done | 8 endpoints, JWT middleware |
| React Frontend | done | login/chat/profile/stage progress |

## Configuration

- `.env` — `OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `EMBEDDING_MODE`
- `config/rag.yml` — model names (documentation only, factory.py hardcodes values)
- `frontend/.env` — `VITE_SUPABASE_URL`, `VITE_SUPABASE_KEY`, `VITE_API_URL`
- Model: `deepseek-chat` via DeepSeek API. Embedding: `BAAI/bge-small-zh-v1.5` (local) or DashScope `text-embedding-v4` (api)

## Key Patterns

- All state in Supabase: auth, profiles, RAG vectors, school data. No local DB.
- Agent modules (`agent/`, `rag/`, `user/`, `utils/`) never import Streamlit.
- Caching: TTLCache (200 entries, 30min TTL) for RAG and web search. DecisionCache (LRU+TTL) for intent.
- No emoji in UI strings (user preference).
- Deterministic logic first, LLM as lubricant not engine.
