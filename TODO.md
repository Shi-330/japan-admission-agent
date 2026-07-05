# V2 TODO

> Last updated: 2026-07-06

## Now: V2.2 State Machine (in progress)

- [ ] Update extraction prompt in `user/profile_manager.py` to recognize per-school applications
- [ ] React frontend: replace single stage bar with per-school tracking cards
- [ ] `/v1/stage` and `/v1/stage/advance` API — adapt to `applications` list (currently single-stage)
- [ ] Professor no-reply reminder: 2 weeks → prompt to switch professor or school
- [ ] Chat flow: LLM aware of each school's stage when generating advice

## Next: V2.3 Private Case Database

- [ ] Design `senpai_cases` table schema (school, major, profile, timeline, result, tips)
- [ ] Import path: manual form + batch CSV
- [ ] Case-driven matching: "students like you who got into 東大 had..."
- [ ] UI: case browser with filtering by major/school/result

## Next: V2.4 Hybrid Search

- [ ] Metadata pre-filter (time range, school, major) before vector search
- [ ] Add BM25 keyword scoring alongside cosine similarity
- [ ] Stage-aware search (different search strategies per application stage)

## Later

- [ ] V2.5 Frontend dashboard (stage cards, timeline view, action center)
- [ ] V2.6 Email automation (OAuth, draft generation, send tracking)
- [ ] Streamlit → thin admin panel only
