# V2 TODO

> Last updated: 2026-07-07

## Done

### V2.2 State Machine
- [x] Per-school applications: extraction prompt, merge_delta, stage API, React cards
- [x] Professor reminders (14-day no-reply detection)
- [x] Bidirectional stages (forward + rollback)
- [x] Manual school CRUD (add/delete via sidebar)
- [x] Real-date timeline from 募集要項 deadlines

### UX
- [x] Streaming chat (invoke → stream)
- [x] Chat response cache (5-min TTL)
- [x] Keyword intent classification (skip LLM for known patterns)
- [x] Toast notifications (replaced alert())
- [x] Proactive greeting on login (/v1/greeting)
- [x] Single-server setup (FastAPI serves React build, port 8000)
- [x] School auto-suggestion from chat (one-click add to tracking)

### School Plaza
- [x] 7-school catalog with majors, deadlines, requirements
- [x] Filter by major/name
- [x] One-click "追踪" to add to sidebar

### Calendar
- [x] Horizontal timeline with month columns
- [x] Deadline markers from applications[].deadlines
- [x] Current month highlighted

### Data
- [x] v2_migration.sql for Supabase user_profiles columns
- [x] seed_schools.py with 5-school deadline reference

## Next

- [ ] PDF 募集要項 upload + LLM extraction → auto-fill deadlines
- [ ] Application card inline editing (professors, deadlines, notes)
- [ ] Date-driven stage progression (real deadlines drive the timeline)
- [ ] V2.3 Private Case Database (senpai cases)
- [ ] V2.4 Hybrid Search
- [ ] V2.5 Dashboard polish
- [ ] V2.6 Email automation
