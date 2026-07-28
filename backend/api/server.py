"""
FastAPI server — shared backend for Streamlit / React / whatever frontend.

Run: uvicorn backend.api.server:app --host 0.0.0.0 --port 8000 --reload
"""
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import hashlib
import asyncio
import json
import re
import time

from backend.api.auth import get_user_id
from user.profile_manager import ProfileManager, UserProfile, deadlines_to_items
from agent.orchestrator import ChatOrchestrator
from agent.intent_layer import IntentLayerEngine, is_light_greeting, is_short_query
from model.factory import chat_model
from utils.supabase_client import supabase
from supabase import create_client
from utils.logger_handler import logger
from utils.cn2jp import normalize as cn2jp_normalize, CN_JP_SYNONYMS

# ── Constants ──
OUTREACH_DRAFTS_KEY = "outreach_drafts"
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="Japan Admission Agent API")

# ── Simple TTL cache for chat responses ──
_chat_cache: dict = {}  # key -> (response_text, timestamp)
_search_cache: dict = {}  # key -> (cards, actions, timestamp)
_CACHE_TTL = 300  # 5 minutes


def _cache_key(user_id: str, query: str, profile_hash: str) -> str:
    """Cache key from user + query + profile state."""
    raw = f"{user_id}|{query.strip().lower()}|{profile_hash}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> Optional[str]:
    """Get cached response text if not expired."""
    entry = _chat_cache.get(key)
    if entry:
        text, ts = entry
        if time.time() - ts < _CACHE_TTL:
            return text
        del _chat_cache[key]
    return None


def _cache_set(key: str, text: str):
    """Store response in cache."""
    _chat_cache[key] = (text, time.time())
    # Simple cleanup: keep max 200 entries
    if len(_chat_cache) > 200:
        oldest = min(_chat_cache, key=lambda k: _chat_cache[k][1])
        del _chat_cache[oldest]

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
        "http://localhost:8000",
        "http://localhost:8501",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8501",
        "https://agent.shi330.xyz",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ──
profile_mgr = ProfileManager()
orchestrator = ChatOrchestrator(profile_mgr)


# ── Request schemas ──
class ProfileUpdate(BaseModel):
    jlpt_level: Optional[str] = None
    english_score: Optional[str] = None
    gpa_score: Optional[float] = None
    gpa_scale: Optional[float] = None
    target_major: Optional[str] = None
    research_area: Optional[str] = None
    undergraduate_school: Optional[str] = None
    target_degree: Optional[str] = None
    eju_score: Optional[int] = None

class ChatRequest(BaseModel):
    query: str
    history: list = []  # [{role, content}] — last 5 messages for context

class MatchRequest(BaseModel):
    target_major: Optional[str] = None

class RagRequest(BaseModel):
    query: str

class OutreachRequest(BaseModel):
    school: str
    professor_name: str

class AckRequest(BaseModel):
    id: Optional[str] = None
    all: Optional[bool] = None


# ── Profile endpoints ──
@app.get("/v1/profile")
async def get_profile(user_id: str = Depends(get_user_id)):
    profile = profile_mgr.get_profile(user_id)
    return profile.to_dict()


@app.put("/v1/profile")
async def update_profile(body: ProfileUpdate, user_id: str = Depends(get_user_id)):
    profile = profile_mgr.get_profile(user_id)
    for field, value in body.model_dump(exclude_none=True).items():
        if hasattr(profile, field) and value is not None:
            profile.set_field(field, value, "form")
    # Normalise research_area to JP terms once on save (avoids LLM latency in search)
    if body.research_area and body.research_area.strip():
        terms = cn2jp_normalize(body.research_area, chat_model=chat_model)
        profile.facts["normalized_research_terms"] = terms
        logger.info(f"Normalised research_area '{body.research_area}' -> {terms}")
    profile_mgr.save_profile(user_id, profile)
    return profile.to_dict()


# ── Match endpoint ──
@app.post("/v1/match")
async def match_schools_endpoint(body: MatchRequest, user_id: str = Depends(get_user_id)):
    from demo.matching_engine import StudentProfile, match_schools, STATUS_LABELS, STATUS_LABELS
    profile = profile_mgr.get_profile(user_id)
    target = body.target_major or profile.target_major
    sp = StudentProfile(
        jlpt_level=profile.jlpt_level,
        gpa=float(profile.gpa),
        target_major=target,
        english_score=profile.english_score,
        undergraduate_school=profile.undergraduate_school,
    )
    matches = match_schools(sp, chat_model=chat_model)
    if not matches:
        raise HTTPException(status_code=503, detail="学校数据加载失败，无法执行匹配")
    # Run extraction after match
    orchestrator.finish_turn(
        user_id, profile,
        f"院校匹配: {target}",
        f"匹配到 {len(matches)} 所学校: {', '.join(m.school_name for m in matches[:5])}",
        chat_model,
    )
    return {
        "matches": [
            {
                "school_name": m.school_name,
                "status": m.status,
                "status_label": STATUS_LABELS[m.status],
                "gaps": [{"field": g.field, "required": g.required, "current": g.current, "met": g.met} for g in m.gaps],
                "deadlines": m.deadlines,
                "exam_info": m.exam_info,
                "notes": m.notes,
            }
            for m in matches
        ]
    }


# ── RAG endpoint ──
@app.post("/v1/rag")
async def rag_endpoint(body: RagRequest):
    from rag.rag_service import RagSummarizeService
    try:
        rag = RagSummarizeService()
        result = rag.get_raw_vector_context(body.query)
        return {"query": body.query, "context": result[:1000] if result else ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Serve frontend at root, API docs at /docs."""
    if os.path.isdir(FRONTEND_DIR):
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    return {
        "name": "Japan Admission Agent API",
        "docs": "/docs",
        "endpoints": ["/health", "/v1/profile", "/v1/match", "/v1/rag", "/v1/chat", "/v1/stage", "/v1/applications", "/v1/reminders"],
    }


def _build_stage_context(profile: UserProfile) -> str:
    """Build per-school stage context + professor reminders for LLM prompt."""
    if not profile.applications:
        return ""

    lines = ["\n【各校申请状态】"]
    stage_label = {"preparing": "准备", "contacting": "套磁", "applying": "出愿",
                   "exam": "考试", "waiting": "等结果", "decided": "确定"}
    for app in profile.applications:
        school = app.get("school", "")
        stage = app.get("stage", "preparing")
        label = stage_label.get(stage, stage)
        line = f"- {school}: {label}"
        profs = app.get("professors", [])
        if profs:
            prof_strs = []
            for p in profs:
                status_cn = {"pending": "待联系", "sent": "已发信", "replied": "已回复",
                            "rejected": "婉拒", "no_reply": "无回复", "interview": "获面试"}
                ps = status_cn.get(p.get("status", ""), p.get("status", "?"))
                prof_strs.append(f"{p['name']}({ps})")
            line += f" | 教授: {', '.join(prof_strs)}"
        deadlines = app.get("deadlines", [])
        if deadlines:
            d_strs = [f"{name}:{date}" for name, date in deadlines_to_items(deadlines)]
            line += f" | 截止: {'; '.join(d_strs)}"
        if app.get("notes"):
            line += f" | {app['notes']}"
        lines.append(line)

    # Add reminder context
    reminders = _collect_all_reminders(profile)
    if reminders:
        lines.append("\n【提醒】")
        for r in reminders:
            school = r.get("school", "")
            msg = r.get("message", "")
            lines.append(f"- [{school}] {msg}")

    lines.append("\n在回答时，结合每所学校的具体阶段给出针对性建议。如有教授超期未回复，主动提醒学生。")
    return "\n".join(lines)


# ── Chat endpoint (SSE streaming) ──
@app.post("/v1/chat")
async def chat_endpoint(body: ChatRequest, user_id: str = Depends(get_user_id)):
    """Intent classification → route to match/RAG/chat → SSE streaming response."""
    # ── Rate limit check — per-user sliding window, 5 req/min ──
    from backend.middleware.rate_limit import check_rate_limit
    if not check_rate_limit(user_id):
        raise HTTPException(429, detail="请求过于频繁，请稍后再试。")

    # 0. Lightweight greeting — no LLM, no DB needed
    if is_light_greeting(body.query):
        async def greet_generator():
            yield f"data: {json.dumps({'content': '你好！有什么可以帮你的？', 'is_status': False, 'done': False})}\n\n"
            yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"
        return StreamingResponse(
            greet_generator(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    profile = profile_mgr.get_profile(user_id)
    profile_str = profile_mgr.format_for_prompt(profile)
    stage_ctx = _build_stage_context(profile)

    # 1. Response cache lookup
    profile_hash = hashlib.md5(profile_str.encode()).hexdigest()[:8]
    cache_key = _cache_key(user_id, body.query, profile_hash)
    cached = _cache_get(cache_key)
    if cached:
        async def cached_generator():
            for i in range(0, len(cached), 2):
                chunk = cached[i:i+2]
                yield f"data: {json.dumps({'content': chunk, 'is_status': False, 'done': False})}\n\n"
                await asyncio.sleep(0.003)
            yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"
        return StreamingResponse(
            cached_generator(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # 2. Unified intent + flow + action classification
    if is_short_query(body.query):
        # Simple query without application keywords → skip LLM, go straight to chat
        result = {"intent": "chat", "flow": "general", "depth": 0, "prompt": "", "actions": []}
    else:
        result = intent_engine.classify(
            body.query, body.history or [], profile_str, stage_ctx, chat_model
        )
    intent = result["intent"]
    actions = result["actions"]

    # ── Pre-filter: force "search_schools" for "考XX" / "推荐XX" patterns ──
    if re.search(r'(?:考|推荐|推荐一下|推荐几所|有哪些|什么|想学)(?:.{0,15}(?:研究|方向|専攻|专攻|专业|学校|大学|研究室))?', body.query):
        if intent != "search_schools":
            logger.info(f"Pre-filter overriding intent {intent} -> search_schools for: {body.query[:30]}")
        intent = "search_schools"
        result["flow"] = "school_search"
        result["depth"] = 1

    async def event_generator():
        assistant_text = ""
        final_event = {'content': '', 'is_status': False, 'done': True}

        async def _stream(prompt: str):
            """Stream LLM response as SSE content chunks."""
            nonlocal assistant_text
            for chunk in chat_model.stream(prompt):
                c = chunk.content if hasattr(chunk, "content") else str(chunk)
                if c:
                    assistant_text += c
                    yield f"data: {json.dumps({'content': c, 'is_status': False, 'done': False})}\n\n"
                    await asyncio.sleep(0.003)

        try:
            # 3. Route by intent
            logger.info(f"Intent: {intent}, flow: {result.get('flow','')}, query: {body.query[:40]}")
            if intent == "match":
                from demo.matching_engine import StudentProfile, match_schools, STATUS_LABELS, STATUS_LABELS
                from utils.cn2jp import normalize as cn2jp_norm
                q_terms = cn2jp_norm(body.query, chat_model=chat_model)
                # q_terms[0] is the original query, prefer the first normalized JP term
                if len(q_terms) > 1:
                    q_major = q_terms[1]
                elif q_terms:
                    q_major = q_terms[0]
                else:
                    q_major = profile.target_major or ""
                sp = StudentProfile(
                    jlpt_level=profile.jlpt_level,
                    gpa=float(profile.gpa), target_major=q_major,
                    english_score=profile.english_score,
                    undergraduate_school=profile.undergraduate_school,
                )
                matches = match_schools(sp, chat_model=chat_model)
                if not matches:
                    yield f"data: {json.dumps({'content': '学校数据加载失败，无法执行匹配。去广场手动筛选吧。', 'is_status': False, 'done': False})}\n\n"
                else:
                    nl = "\n"
                    for m in matches:
                        line = f"{STATUS_LABELS[m.status]} {m.school_name}{nl}"
                        yield f"data: {json.dumps({'content': line, 'is_status': False, 'done': False})}\n\n"

            elif intent == "search_schools":
                # ── Cache check for repeated searches ──
                sk = _cache_key(user_id, body.query, profile_hash)
                cached = _search_cache.get(sk)
                if cached:
                    cards, cached_actions, ts = cached
                    if time.time() - ts < _CACHE_TTL:
                        logger.info(f"Search cache HIT for: {body.query[:30]}")
                        yield f"data: {json.dumps({'content': f'为你匹配了{len(cards)}所学校：', 'is_status': False})}\n\n"
                        yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True, 'school_cards': cards, **{k:v for k,v in cached_actions.items() if v}})}\n\n"
                        return
                    del _search_cache[sk]

                # Use matching engine to find schools, then render as actionable cards
                from demo.matching_engine import StudentProfile, match_schools, STATUS_LABELS
                # Extract intended major from query — not from profile (user may ask about a different field)
                from utils.cn2jp import normalize as cn2jp_norm
                q_terms = cn2jp_norm(body.query, chat_model=chat_model)
                # q_terms[0] is the original query, prefer the first normalized JP term
                if len(q_terms) > 1:
                    q_major = q_terms[1]
                elif q_terms:
                    q_major = q_terms[0]
                else:
                    q_major = profile.target_major or ""
                sp = StudentProfile(
                    jlpt_level=profile.jlpt_level,
                    gpa=float(profile.gpa), target_major=q_major,
                    english_score=profile.english_score,
                    undergraduate_school=profile.undergraduate_school,
                )
                matches = match_schools(sp, chat_model=chat_model)
                cards = []
                if matches:
                    top_count = min(len(matches), 8)
                    top_names = [m.school_name for m in matches[:top_count]]
                    actions.append({"type": "suggested_schools", "schools": top_names})
                    actions.append({"type": "nav_plaza", "filter": q_major or "", "prompt": f"去广场查看{len(top_names)}所{q_major or ''}方向学校"})
                    # Build school cards with match status (same as qa intent)
                    for m in matches[:8]:
                        full = next((s for s in SCHOOL_CATALOG if s.get("name") == m.school_name), {})
                        cards.append({
                            "name": m.school_name, "type": full.get("type",""),
                            "majors": full.get("majors",[]), "jlpt_min": full.get("jlpt_min",""),
                            "english_req": full.get("english_req",{}), "exam": full.get("exam",""),
                            "notes": full.get("notes",""),
                            "status_label": STATUS_LABELS.get(m.status, m.status),
                            "gaps": [{"field": g.field, "required": g.required, "current": g.current, "met": g.met} for g in (m.gaps or [])],
                        })
                    if cards:
                        actions.append({"type": "school_cards", "cards": cards})
                    # Broaden when few matches — web search + auto-ingest
                    if len(matches) < 8:
                        logger.info(f"search_schools: only {len(matches)} matches, triggering web search")
                        try:
                            from rag.rag_service import RagSummarizeService as R
                            web = R().search_with_fallback(f"{body.query} 日本 大学院 {q_major} 研究科")
                            if web and not web.startswith("未找到"):
                                found = list(set(re.findall(
                                    r'([一-鿿]{2,6}(?:大学|大学院)[一-鿿]*)', web)))
                                existing = {s.get("name","") for s in SCHOOL_CATALOG}
                                new_names = [n for n in found[:5] if n not in existing]
                                if new_names:
                                    from demo.school_database import upsert_school, School
                                    for n in new_names:
                                        try: upsert_school(School(name=n, source="web_search", verified=False))
                                        except: pass
                                    actions.append({"type": "discovered_schools",
                                        "schools": [{"name": n, "source": "web_search"} for n in new_names]})
                                    logger.info(f"Auto-ingested {len(new_names)} schools from web")
                        except Exception as e2:
                            logger.warning(f"Web search failed in search_schools: {e2}")
                    prompt = f"学生正在找{q_major or '合适'}方向的学校。根据背景（JLPT{profile.jlpt_level}、GPA{profile.gpa}），为他匹配了{len(top_names)}所学校。请1句话告诉学生已匹配，然后建议去广场查看更多。"
                else:
                    # No DB matches — use LLM to suggest relevant schools directly
                    prompt = f"数据库暂无{q_major or '该'}方向的学校记录。"
                    try:
                        llm_prompt = (
                            f"列出日本有{q_major}相关研究科的5-8所日本大学。每行一个，格式：\n"
                            f"大学名 | 研究科名 | JLPT要求 | 英语要求 | 一句话特点\n"
                            f"例如：东京大学 | 人文社会系研究科 | N1 | TOEFL 80 | 日本社会学发源地\n"
                            f"重要：只列日本国内的大学（日本の大学のみ），不要列中国或欧美的大学。"
                            f"JLPT/英语如不确定写'要確認'。不要其他解释。"
                        )
                        resp = chat_model.invoke(llm_prompt)
                        llm_text = resp.content if hasattr(resp, "content") else str(resp)
                        logger.info(f"LLM school suggestion for {q_major}: {llm_text[:200]}")
                        for line in llm_text.strip().split("\n"):
                            line = line.strip().lstrip("0123456789.-) ").strip()
                            if not line or len(line) < 6: continue
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) < 2: continue
                            uni_name = parts[0]
                            gs_name = parts[1] if len(parts) > 1 else ""
                            # Normalize to canonical university name (prevent 东京/東京 split)
                            try:
                                _uni_r = supabase.table("universities").select("name").or_(
                                    f"name.ilike.%{uni_name}%,name_jp.ilike.%{uni_name}%").limit(1).execute()
                                if _uni_r.data:
                                    uni_name = _uni_r.data[0]["name"]
                            except Exception:
                                pass
                            full_name = f"{uni_name} {gs_name}" if gs_name else uni_name
                            jlpt = parts[2] if len(parts) > 2 else ""
                            eng = parts[3] if len(parts) > 3 else ""
                            note = parts[4] if len(parts) > 4 else "AI推荐·请核实官网"
                            # Try to find university type from catalog
                            uni_type = ""
                            for s in SCHOOL_CATALOG:
                                if uni_name in s.get("name", ""):
                                    uni_type = s.get("type", "")
                                    break
                            cards.append({
                                "name": full_name, "type": uni_type, "majors": [],
                                "jlpt_min": jlpt if jlpt and jlpt != "要確認" else "",
                                "english_req": {"type": eng, "required": bool(eng and eng != "要確認")} if eng and eng != "要確認" else {},
                                "exam": "", "notes": note,
                                "status_label": "参考", "gaps": [],
                            })
                            # Auto-ingest into DB (service key) + in-memory catalog
                            import os as _os
                            _sk = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
                            try:
                                _sk.table("schools").upsert({
                                    "name": full_name, "type": uni_type, "majors": [],
                                    "jlpt_min": jlpt if jlpt and jlpt != "要確認" else "",
                                    "english_req": {"type": eng, "required": bool(eng and eng != "要確認")} if eng and eng != "要確認" else {},
                                    "exam": "", "notes": note, "tags": ["llm_suggestion"],
                                    "deadlines": [], "source": "llm_suggestion", "verified": False,
                                "enrichment_status": "skeleton",
                                }, on_conflict="name").execute()
                                logger.info(f"Auto-ingested: {full_name}")
                            except Exception as e3:
                                logger.warning(f"Auto-ingest DB failed for {full_name}: {e3}")
                            # Always update in-memory catalog
                            SCHOOL_CATALOG.append({
                                "name": full_name, "type": uni_type, "majors": [],
                                "jlpt_min": jlpt if jlpt and jlpt != "要確認" else "",
                                "english_req": {"type": eng, "required": bool(eng and eng != "要確認")} if eng and eng != "要確認" else {},
                                "exam": "", "notes": note, "tags": ["llm_suggestion"],
                                "deadlines": [], "source": "llm_suggestion", "verified": False,
                            })
                            if len(cards) >= 8: break
                    except Exception as e2:
                        logger.warning(f"LLM fallback failed for {q_major}: {e2}")

                    if cards:
                        actions.append({"type": "school_cards", "cards": cards})
                        actions.append({"type": "nav_plaza", "filter": q_major or "",
                                        "prompt": f"去广场查看{len(cards)}所{q_major or ''}方向学校"})
                        prompt += f"为你找到{len(cards)}所{q_major or '相关'}方向的学校（见下方卡片）。1句话简介即可，具体信息在卡片里。"
                        # Fire-and-forget: enrich skeletons in background
                        from threading import Thread
                        Thread(target=_enrich_skeletons, args=(cards,), daemon=True).start()
                    else:
                        prompt += "1句话建议学生手动搜索或换个专业方向试试。"
                # Cache the search result for future identical queries
                _search_cache[sk] = (cards, actions, time.time())
                if len(_search_cache) > 100:
                    oldest = min(_search_cache, key=lambda k: _search_cache[k][2])
                    del _search_cache[oldest]
                async for event in _stream(prompt):
                    yield event

            elif intent in ("qa", "report"):
                # ── Adaptive detail level ──
                app_count = len(profile.applications) if profile.applications else 0
                detail_instruction = "用2-3句话简洁回答。" if app_count >= 3 else \
                    "新手用户，请详细解释申请路径、语言要求和备考建议。分步骤给出建议。" if app_count <= 1 else \
                    "根据用户的问题给出恰当详尽的回答。"

                # ── RAG / web search ──
                from rag.rag_service import RagSummarizeService
                try:
                    rag = RagSummarizeService()
                    ctx = rag.search_with_fallback(body.query)
                except Exception:
                    ctx = ""

                # ── School matching injected into qa context ──
                school_cards_data = []
                schools_context = ""
                try:
                    from demo.matching_engine import StudentProfile as SP, match_schools, STATUS_LABELS
                    from utils.cn2jp import normalize as cn2jp_norm
                    terms = cn2jp_norm(body.query, chat_model=chat_model)
                    q_major = terms[0] if terms else (profile.target_major or profile.research_area or "")
                    sp = SP(
                        jlpt_level=profile.jlpt_level, gpa=float(profile.gpa),
                        target_major=q_major,
                        english_score=profile.english_score,
                        undergraduate_school=profile.undergraduate_school,
                    )
                    matches = match_schools(sp, chat_model=chat_model)
                    logger.info(f"QA matching: q_major={q_major}, terms={terms}, matches={len(matches or [])}")

                    # Broaden search: also match schools where ANY research_area overlaps with query terms
                    matched_names = {m.school_name for m in (matches or [])}
                    extra_schools = []
                    if len(matched_names) < 8:
                        for s in SCHOOL_CATALOG:
                            if s.get("name") in matched_names: continue
                            text = " ".join([s.get("name","")] + (s.get("majors") or []) + (s.get("tags") or []))
                            if any(t.lower() in text.lower() for t in q_terms):
                                extra_schools.append(s)
                                if len(extra_schools) + len(matched_names) >= 10:
                                    break

                    all_schools = list(matches or [])
                    if all_schools:
                        top = all_schools[:8]
                        lines = []
                        for m in top:
                            status_label = STATUS_LABELS.get(m.status, m.status)
                            lines.append(
                                f"- {status_label} {m.school_name}: "
                                f"JLPT={m.gaps[0].required if m.gaps and len(m.gaps)>0 else '无要求'}, "
                                f"GPA={m.gaps[1].required if m.gaps and len(m.gaps)>1 else '无要求'}")
                            full = next((s for s in SCHOOL_CATALOG if s.get("name") == m.school_name), {})
                            school_cards_data.append({
                                "name": m.school_name, "type": full.get("type", ""),
                                "majors": full.get("majors", []),
                                "jlpt_min": full.get("jlpt_min", ""),
                                "english_req": full.get("english_req", {}),
                                "exam": full.get("exam", ""), "notes": full.get("notes", ""),
                                "status_label": status_label,
                                "gaps": [{"field": g.field, "required": g.required, "current": g.current, "met": g.met} for g in (m.gaps or [])],
                            })
                        # Add extra schools (no match status, shown as "参考")
                        for s in extra_schools:
                            if len(school_cards_data) >= 10: break
                            school_cards_data.append({
                                "name": s.get("name",""), "type": s.get("type",""),
                                "majors": s.get("majors", []),
                                "jlpt_min": s.get("jlpt_min", s.get("jlpt","")),
                                "english_req": s.get("english_req", {}),
                                "exam": s.get("exam",""), "notes": s.get("notes",""),
                                "status_label": "参考",
                                "gaps": [],
                            })
                        schools_context = "\n【匹配学校】\n" + "\n".join(lines)
                        if extra_schools:
                            schools_context += f"\n【相关领域】还发现{len(extra_schools)}所相关学校"
                        actions.append({"type": "school_cards", "cards": school_cards_data})
                        actions.append({"type": "nav_plaza", "filter": q_major or "", "prompt": f"去广场查看{len(school_cards_data)}所匹配学校"})

                        logger.info(f"School cards before enrichment: {len(school_cards_data)}")
                        # Web search enrichment + auto-ingest into DB
                        if len(school_cards_data) < 8:
                            try:
                                web_hint = rag.search_with_fallback(f"{body.query} 日本 大学院 推荐 研究科")
                                if web_hint and not web_hint.startswith("未找到"):
                                    schools_context += f"\n【网络补充】\n{web_hint[:600]}"
                                    found = list(set(re.findall(
                                        r'([一-鿿]{2,6}(?:大学|大学院)[一-鿿]*)', web_hint)))
                                    existing = {s.get("name","") for s in SCHOOL_CATALOG}
                                    new_names = [n for n in found[:5] if n not in existing]
                                    if new_names:
                                        # Auto-ingest: write to DB immediately
                                        from demo.school_database import upsert_school, School
                                        for n in new_names:
                                            try:
                                                upsert_school(School(name=n, source="web_search", verified=False))
                                            except Exception:
                                                pass
                                        # Still show as discovered cards for context
                                        actions.append({"type": "discovered_schools",
                                                        "schools": [{"name": n, "source": "web_search"} for n in new_names]})
                                        logger.info(f"Auto-ingested {len(new_names)} schools from web search")
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"School matching in qa failed: {e}")

                prompt = f"""你是日本升学顾问。
【资料】{ctx[:800] if ctx else "无"}
{schools_context}
【学生】{profile_str}
{stage_ctx}
【问题】{body.query}
{detail_instruction}资料为空则说明暂无相关内容。"""
                async for event in _stream(prompt):
                    yield event

            else:  # chat
                prompt = f"学生说：{body.query}。背景：{profile_str}。{stage_ctx}你正在{result['flow']}场景中(depth={result['depth']})。{result['prompt']} 规则：1. 2-3句简洁回复 2. 纯文本不用markdown。"
                async for event in _stream(prompt):
                    yield event

            # 4. Post-stream: cache, extract facts, emit final done event
            if assistant_text:
                _cache_set(cache_key, assistant_text)
                orchestrator.finish_turn(
                    user_id, profile, body.query, assistant_text, chat_model,
                    history=body.history,
                )

            # Auto-apply remind_prof actions to profile (batch, save once)
            remind_applied = False
            for action in actions:
                if action.get("type") == "remind_prof":
                    school = action.get("school", "")
                    professor = action.get("professor", "")
                    if school and professor:
                        try:
                            profile.add_professor_attempt(
                                school, professor, status="no_reply"
                            )
                            remind_applied = True
                        except Exception:
                            pass  # best-effort
            if remind_applied:
                try:
                    profile_mgr.save_profile(user_id, profile)
                except Exception:
                    pass

            sse_extra = intent_engine.actions_to_sse_events(actions)
            if sse_extra:
                final_event.update(sse_extra)
            yield f"data: {json.dumps(final_event)}\n\n"

        except Exception as e:
            logger.error(f"Chat error: {e}")
            yield f"data: {json.dumps({'content': f'Error: {e}', 'is_status': False, 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Stage endpoints (V2.2: per-school application tracking) ──
@app.get("/v1/stage")
async def get_stage(user_id: str = Depends(get_user_id)):
    from agent.state_machine import get_current_stage_info, generate_timeline, check_reminders, STAGES
    profile = profile_mgr.get_profile(user_id)

    # Build per-school stage info from applications list
    app_tracks = []
    for app in profile.applications:
        school = app.get("school", "")
        stage_id = app.get("stage", "preparing")
        info = get_current_stage_info(stage_id)
        # Use the app's own field_sources or application_stage timestamp as start
        started = profile.field_sources.get(f"app_stage_{school}", {}).get("at")
        deadlines = app.get("deadlines", {})
        app_tracks.append({
            "school": school,
            **info,
            "prev_stages": info.get("prev_stages", []),
            "professors": app.get("professors", []),
            "deadlines": deadlines,
            "notes": app.get("notes", ""),
            "needs_contact": app.get("needs_contact", False),
            "timeline": generate_timeline(stage_id, started, deadlines),
            "reminders": check_reminders(stage_id, started),
        })

    # Backward compat: single-stage summary (for old UI or no applications yet)
    fallback_stage = profile.application_stage or "preparing"
    fallback_info = get_current_stage_info(fallback_stage)
    fallback_started = profile.field_sources.get("application_stage", {}).get("at")

    return {
        "applications": app_tracks,
        # Backward-compat top-level fields (used by single-bar UI)
        "stage_id": fallback_info.get("stage_id", fallback_stage),
        "label": fallback_info.get("label", ""),
        "progress": fallback_info.get("progress", 0),
        "description": fallback_info.get("description", ""),
        "actions": fallback_info.get("actions", []),
        "conditions": fallback_info.get("conditions", []),
        "next_stages": fallback_info.get("next_stages", []),
        "prev_stages": fallback_info.get("prev_stages", []),
        "timeline": generate_timeline(fallback_stage, fallback_started),
        "reminders": check_reminders(fallback_stage, fallback_started),
        # Also include per-application professor reminders
        "all_reminders": _collect_all_reminders(profile),
    }


class AdvanceRequest(BaseModel):
    target_stage: str
    school: Optional[str] = None  # If set, advance this specific school; else advance global stage

@app.post("/v1/stage/advance")
async def advance_stage_endpoint(body: AdvanceRequest, user_id: str = Depends(get_user_id)):
    from agent.state_machine import can_transition, get_allowed_stages, STAGES
    profile = profile_mgr.get_profile(user_id)

    if body.school:
        # V2.2: advance a specific school's stage
        app = None
        for a in profile.applications:
            if a.get("school") == body.school:
                app = a
                break
        if not app:
            raise HTTPException(404, f"School '{body.school}' not found in applications")
        current = app.get("stage", "preparing")
        if body.target_stage == current:
            # Idempotent: already at target
            return {"stage": current, "school": body.school, "label": STAGES[current]["label"], "unchanged": True}
        if not can_transition(current, body.target_stage):
            allowed = get_allowed_stages(current)
            valid = allowed["next"] + allowed["prev"]
            valid_labels = [f"{s}({STAGES.get(s,{}).get('label','')})" for s in valid]
            raise HTTPException(400, f"「{STAGES.get(current,{}).get('label',current)}」不能直接到「{STAGES.get(body.target_stage,{}).get('label',body.target_stage)}」，允许: {', '.join(valid_labels)}")
        profile.upsert_application(body.school, stage=body.target_stage)
        profile.field_sources[f"app_stage_{body.school}"] = {"source": "form", "at": datetime.now().isoformat()}
    else:
        # Backward compat: advance global stage
        current = profile.application_stage or "preparing"
        if body.target_stage == current:
            return {"stage": current, "label": STAGES[current]["label"], "unchanged": True}
        if not can_transition(current, body.target_stage):
            allowed = get_allowed_stages(current)
            valid = allowed["next"] + allowed["prev"]
            valid_labels = [f"{s}({STAGES.get(s,{}).get('label','')})" for s in valid]
            raise HTTPException(400, f"「{STAGES.get(current,{}).get('label',current)}」不能直接到「{STAGES.get(body.target_stage,{}).get('label',body.target_stage)}」，允许: {', '.join(valid_labels)}")
        profile.set_field("application_stage", body.target_stage, "form")

    profile_mgr.save_profile(user_id, profile)
    return {"stage": body.target_stage, "school": body.school, "label": STAGES[body.target_stage]["label"]}


@app.get("/v1/greeting")
async def get_greeting(user_id: str = Depends(get_user_id)):
    """Proactive greeting with structured dashboard data."""
    profile = profile_mgr.get_profile(user_id)
    parts = []
    today = datetime.now().date()

    # 1. Professor reminders + deadline scan (single pass over applications)
    overdue_profs = 0
    upcoming_dl = 0
    has_prof_reminders = False
    has_dl_warnings = False
    for app in profile.applications:
        school = app.get("school", "")
        for prof in app.get("professors", []):
            status = prof.get("status", "")
            date_str = prof.get("date", "")
            if status in ("sent", "no_reply") and date_str:
                try:
                    elapsed = (datetime.now() - datetime.fromisoformat(date_str)).days
                    if elapsed >= 14:
                        has_prof_reminders = True
                        overdue_profs += 1
                except (ValueError, TypeError):
                    pass
        for name, date_str in deadlines_to_items(app.get("deadlines", [])):
            try:
                dl = datetime.fromisoformat(date_str).date()
                days_left = (dl - today).days
                if 0 <= days_left <= 14:
                    has_dl_warnings = True
                    upcoming_dl += 1
                elif days_left < 0:
                    has_dl_warnings = True
            except (ValueError, TypeError):
                pass
    # 3. Stage nudge
    stage = profile.application_stage or "preparing"
    if stage == "preparing":
        if not profile.research_area:
            parts.append("还没有设定研究方向，聊聊你想研究什么？")
        elif not profile.applications:
            parts.append("研究计划准备中，可以跟我说说你想申请的学校。")
    elif stage == "contacting":
        active = sum(1 for a in profile.applications if a.get("stage") == "contacting")
        if active == 0:
            parts.append("准备好联系教授了吗？告诉我你想联系哪位教授。")
    elif stage == "applying":
        parts.append("出愿材料准备中，确认各校截止日期。")
    elif stage == "exam":
        parts.append("临近考试，别忘复习专业课。需要模拟面试吗？")
    elif stage == "waiting":
        parts.append("结果等待中，也可以准备备选方案。")

    if not profile.applications and not profile.research_area:
        parts.insert(0, "欢迎！我是你的日本升学顾问。告诉我你的研究方向，帮你匹配学校。")

    # 4. Profile completeness
    fields = {
        "jlpt": profile.jlpt_level and profile.jlpt_level != "无",
        "english": bool(profile.english_score and profile.english_score.strip()),
        "gpa": profile.gpa_score > 0,
        "school": profile.undergraduate_school and profile.undergraduate_school != "未设定",
        "major": profile.target_major and profile.target_major != "未设定",
        "research": bool(profile.research_area and profile.research_area.strip()),
    }
    filled = sum(1 for v in fields.values() if v)
    total = len(fields)

    # 5. Next actions
    actions = []
    if not fields["research"]:
        actions.append({"label": "设定研究方向", "tab": "chat", "reason": "研究方向未设定", "priority": "high"})
    if not profile.applications:
        actions.append({"label": "去广场浏览学校", "tab": "plaza", "reason": "还没有关注的学校", "priority": "high"})
    elif upcoming_dl > 1:
        actions.append({"label": f"查看 {upcoming_dl} 个临近截止日", "tab": "calendar", "reason": "多个截止日临近", "priority": "high"})
    if overdue_profs > 0:
        actions.append({"label": f"{overdue_profs} 位教授超期未回", "tab": "chat", "reason": "教授未回复建议跟进", "priority": "high"})
    if not fields["jlpt"]:
        actions.append({"label": "填写日语成绩", "tab": "chat", "reason": "日语成绩未填", "priority": "normal"})
    if not fields["english"]:
        actions.append({"label": "填写英语成绩", "tab": "chat", "reason": "英语成绩未填", "priority": "normal"})

    # ── 6. when: per-school verdicts ──
    when_list = []
    for app in profile.applications:
        school = app.get("school", "")
        major = app.get("major", "") or ""
        deadlines = app.get("deadlines", {})
        professors = app.get("professors", [])

        shutsugan_str = deadlines.get("出願") or deadlines.get("出愿")
        shutsugan_date = None
        if shutsugan_str:
            try:
                shutsugan_date = datetime.fromisoformat(shutsugan_str).date()
            except (ValueError, TypeError):
                pass

        exam_str = deadlines.get("校内考") or deadlines.get("考试")
        exam_date = None
        if exam_str:
            try:
                exam_date = datetime.fromisoformat(exam_str).date()
            except (ValueError, TypeError):
                pass

        verdict = ""
        reason = ""
        days = 0

        if shutsugan_date and exam_date:
            if today < shutsugan_date - timedelta(days=30):
                days = (shutsugan_date - today).days
                if not professors:
                    verdict = "该套磁"
                    reason = f"出願还剩 {days} 天，你一个教授都没联系"
                else:
                    verdict = "套磁中"
                    reason = f"已联系 {len(professors)} 位教授"
            elif today <= shutsugan_date:
                days = (shutsugan_date - today).days
                verdict = "收尾出愿"
                reason = f"出願剩 {days} 天，确认材料"
            elif today < exam_date:
                days = (exam_date - today).days
                weeks = max(days // 7, 1)
                verdict = "该复习"
                reason = f"考试剩 {weeks} 周，过去问刷起来"
            else:
                days = (exam_date - today).days
                verdict = "已考完/等待"
                reason = ""
        elif shutsugan_date:
            if today < shutsugan_date - timedelta(days=30):
                days = (shutsugan_date - today).days
                if not professors:
                    verdict = "该套磁"
                    reason = f"出願还剩 {days} 天，你一个教授都没联系"
                else:
                    verdict = "套磁中"
                    reason = f"已联系 {len(professors)} 位教授"
            elif today <= shutsugan_date:
                days = (shutsugan_date - today).days
                verdict = "收尾出愿"
                reason = f"出願剩 {days} 天，确认材料"
            else:
                days = (shutsugan_date - today).days
                verdict = "已考完/等待"
                reason = ""
        elif exam_date:
            if today < exam_date:
                days = (exam_date - today).days
                weeks = max(days // 7, 1)
                verdict = "该复习"
                reason = f"考试剩 {weeks} 周，过去问刷起来"
            else:
                days = (exam_date - today).days
                verdict = "已考完/等待"
                reason = ""
        else:
            verdict = "还早"
            reason = "补一下出願/考试日期，我才能告诉你节奏"
            days = 0

        when_list.append({
            "school": school,
            "major": major,
            "verdict": verdict,
            "reason": reason,
            "days": days,
        })

    # ── 7. structural_risk ──
    structural_risk = None
    if profile.applications:
        advanced = any(a.get("stage") in ("applying", "exam", "waiting", "decided") for a in profile.applications)
        all_stuck = True
        for a in profile.applications:
            for p in a.get("professors", []):
                if p.get("status") == "replied":
                    all_stuck = False
                    break
            if not all_stuck:
                break
        if not advanced and all_stuck:
            structural_risk = {
                "level": "warn",
                "message": f"你追踪了 {len(profile.applications)} 所，但没有一条线推进到出願——缺一条在走的线。"
            }

    # ── 8. gates: unmet hard requirements ──
    gates = []
    try:
        from demo.matching_engine import _schools_from_db, _jlpt_met, _english_met
        school_records = _schools_from_db()
        for app in profile.applications:
            school_name = app.get("school", "")
            matched = None
            for s in school_records:
                if school_name in s["name"] or s["name"] in school_name:
                    matched = s
                    break
            if not matched:
                continue
            if not _jlpt_met(matched["jlpt_min"], profile.jlpt_level):
                gates.append({
                    "school": school_name,
                    "field": "JLPT",
                    "required": matched["jlpt_min"],
                    "current": profile.jlpt_level or "无",
                })
            if not _english_met(matched["english_note"], profile.english_score or "无"):
                gates.append({
                    "school": school_name,
                    "field": "英语",
                    "required": matched["english_note"],
                    "current": profile.english_score or "未提供",
                })
    except Exception:
        pass

    return {
        "message": "\n\n".join(parts) if parts else ("有几项待办需要关注，见下方卡片。" if (has_prof_reminders or has_dl_warnings) else "欢迎回来！当前一切顺利。"),
        "has_reminders": has_prof_reminders or has_dl_warnings,
        "profile_completeness": {"filled": filled, "total": total, "percentage": round(filled / total * 100)},
        "next_actions": actions[:5],
        "counts": {"total_apps": len(profile.applications), "overdue_profs": overdue_profs, "upcoming_deadlines": upcoming_dl},
        "when": when_list,
        "structural_risk": structural_risk,
        "gates": gates,
    }


# ── Outreach draft endpoint ──
@app.post("/v1/draft/outreach")
async def draft_outreach(body: OutreachRequest, user_id: str = Depends(get_user_id)):
    """Generate a professor outreach email draft with placeholders (no professor facts)."""
    profile = profile_mgr.get_profile(user_id)
    profile_str = profile_mgr.format_for_prompt(profile)

    prompt = f"""你是日本留学套磁信写作助手。根据学生画像生成套磁信草稿，需要高度个性化——充分利用学生已填写的背景信息，让草稿"补几个教授关键词就能发"。

【学生画像】
{profile_str}

【目标学校】{body.school}
【教授姓名】{body.professor_name} — 仅用于抬头称谓（如「{body.professor_name}先生」），不得用于事实断言。
【学生研究方向】{profile.research_area or '未设定'}
【学生本科背景】{profile.undergraduate_school or '未设定'} / {profile.target_major or '未设定'}

请按以下结构生成套磁信（日文正文），输出 JSON 格式，不要解释：

## 正文结构（日文 300-500 字）
1. **自我介绍**：出身大学・学部、現在の専攻、日本語・英語能力（有数据的写，没有的跳过）
2. **研究背景与动机**：结合学生的研究方向和经历（facts 中有项目/实习/论文的直接引用），自然过渡到为什么对该教授的研究感兴趣。学生已填的研究方向务必写进正文，教授的研究方向用占位符
3. **志望理由**：为什么选这所学校这个教授（学校名可用，教授具体研究方向用占位符）
4. **結び**：请求指导、询问是否接受研究生/修士、附上简历和研究计划书等

## 硬性规则
1. 正文只允许出现学生自报事实 + 通用日语套磁敬语 + 学校名
2. 教授的研究方向・论文・业绩 → 用占位符（如[教授の研究分野]），绝不猜测
3. 教授姓名仅用于抬头称谓，正文中不出现
4. 学生有研究方向/经历的一定要写进正文，不要浪费已填的信息
5. 学生未填的不要编造；缺信息就跳过或用通用表达

## 输出格式
{{
  "subject": "邮件主题（日文）",
  "body_ja": "套磁信正文（日文，[xxx]为占位符）",
  "body_zh": "正文中文翻译",
  "placeholders": [
    {{"id": "kyouju_kenkyuu", "hint_ja": "教授の研究分野", "hint_zh": "教授的研究方向"}},
    {{"id": "kyouju_ronbun", "hint_ja": "教授の関連論文・業績", "hint_zh": "教授的相关论文或成果"}}
  ]
}}

JSON:"""

    resp = chat_model.invoke(prompt)
    raw = resp.content if hasattr(resp, "content") else str(resp)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw.strip())
    except json.JSONDecodeError:
        raise HTTPException(500, "LLM 返回格式异常")

    # Auto-save to profile.facts[OUTREACH_DRAFTS_KEY] (cap 20 most recent)
    import uuid as _uuid
    try:
        drafts = profile.facts.get(OUTREACH_DRAFTS_KEY, [])
        draft_id = str(_uuid.uuid4())
        # Remove duplicate (same school + professor)
        drafts = [d for d in drafts
                  if not (d.get("school") == body.school and d.get("professor_name") == body.professor_name)]
        drafts.insert(0, {
            "id": draft_id,
            "school": body.school,
            "professor_name": body.professor_name,
            "subject": result.get("subject", ""),
            "body_ja": result.get("body_ja", ""),
            "body_zh": result.get("body_zh", ""),
            "placeholders": result.get("placeholders", []),
            "created_at": datetime.now().isoformat(),
        })
        profile.facts[OUTREACH_DRAFTS_KEY] = drafts[:20]
        profile_mgr.save_profile(user_id, profile)
        result["draft_id"] = draft_id
    except Exception as e:
        logger.warning(f"Failed to auto-save draft: {e}")
        result["draft_id"] = None
    return result


# ── Drafts endpoints ──
@app.get("/v1/drafts")
async def list_drafts(user_id: str = Depends(get_user_id)):
    """List saved outreach drafts (max 20, newest first)."""
    profile = profile_mgr.get_profile(user_id)
    drafts = profile.facts.get(OUTREACH_DRAFTS_KEY, [])
    return {"drafts": drafts, "total": len(drafts)}


class DeleteDraftRequest(BaseModel):
    draft_id: str


@app.delete("/v1/drafts")
async def delete_draft(body: DeleteDraftRequest, user_id: str = Depends(get_user_id)):
    """Delete a saved draft by ID."""
    profile = profile_mgr.get_profile(user_id)
    drafts = profile.facts.get(OUTREACH_DRAFTS_KEY, [])
    drafts = [d for d in drafts if d.get("id") != body.draft_id]
    profile.facts[OUTREACH_DRAFTS_KEY] = drafts
    profile_mgr.save_profile(user_id, profile)
    return {"ok": True}


# ── Doc fetch + LLM extraction ──
class DocFetchRequest(BaseModel):
    url: str
    school: str = ""  # optional, if known

@app.post("/v1/docs/fetch")
async def fetch_and_extract(body: DocFetchRequest, user_id: str = Depends(get_user_id)):
    """Fetch a URL, extract text, use LLM to find deadlines/exam info."""
    import urllib.request


    # 1. Fetch the URL
    try:
        req = urllib.request.Request(body.url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; JapanAdmissionAgent/1.0)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(400, f"无法访问该链接: {e}")

    # 2. Strip HTML tags, keep text
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    # Keep first 8000 chars for LLM
    text = text[:8000].strip()

    if len(text) < 100:
        raise HTTPException(400, "页面内容过少，可能为动态页面，请尝试直接粘贴关键信息")

    # 3. LLM extraction
    extract_prompt = f"""从以下日本大学募集要项网页内容中，提取关键日期和信息。
只输出 JSON，不要解释。

网页内容：
{text}

提取以下信息（没有就 null）：
- school_name: 大学+研究科名称
- degree: 修士/博士/研究生
- deadlines: 对象，key用中文，如 {{"出願期間":"2026-7-1 ~ 2026-7-15","試験日":"2026-8-25","合格発表":"2026-9-5","入学手続期限":"2026-9-20"}}
- exam_type: 考试类型（書類選考/筆記/面接/口頭試問 等）
- exam_subjects: 考试科目列表
- fees: {{"入学検定料":"30000円","入学金":"282000円","授業料":"535800円/年"}}
- notes: 其他重要信息

JSON:"""

    resp = chat_model.invoke(extract_prompt)
    raw = resp.content if hasattr(resp, "content") else str(resp)
    # Strip markdown fences
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        extracted = json.loads(raw.strip())
    except json.JSONDecodeError:
        extracted = {"raw": raw, "error": "JSON parse failed"}

    # 4. If school specified, upsert deadlines
    if body.school:
        profile = profile_mgr.get_profile(user_id)
        deadlines_from_extract = extracted.get("deadlines", {}) if isinstance(extracted, dict) else {}
        if deadlines_from_extract:
            profile.upsert_application(body.school, deadlines=deadlines_from_extract,
                notes=f"来源: {body.url}")
            profile_mgr.save_profile(user_id, profile)

    return {
        "url": body.url,
        "school": body.school,
        "extracted": extracted,
        "text_preview": text[:300],
        "updated": bool(body.school and extracted.get("deadlines")),
    }


# ── Web-discovered school ingestion ──

@app.post("/v1/schools/discovered")
async def add_discovered_school(body: dict, user_id: str = Depends(get_user_id)):
    """Add a school discovered via web search. Requires admin or service role."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "School name required")
    try:
        from demo.school_database import upsert_school, School
        s = School(name=name, degree=body.get("degree", "修士"),
                   majors=body.get("majors", []), tags=body.get("tags", []),
                   jlpt_min=body.get("jlpt_min", ""), exam=body.get("exam", ""),
                   notes=body.get("notes", ""), source="web_search", verified=False)
        upsert_school(s)
        # Refresh catalog (lazy — next restart picks it up)
        return {"ok": True, "name": name}
    except Exception as e:
        raise HTTPException(500, str(e))


def _enrich_skeletons(cards: list[dict]):
    """Background: web-search & LLM-extract requirements for skeleton schools."""
    import time as _time, re as _re, json as _json
    _time.sleep(1)  # let the SSE response finish first
    for card in cards:
        name = card.get("name","")
        try:
            from rag.rag_service import RagSummarizeService
            rag = RagSummarizeService()
            query = f"{name} 修士課程 募集要項 site:ac.jp"
            web = rag.search_with_fallback(query)
            if not web or web.startswith("未找到"):
                query2 = f"{name} 大学院 入試要項"
                web = rag.search_with_fallback(query2)
            if not web or web.startswith("未找到"):
                continue
            import json as _json, re as _re
            prompt = f"""以下は日本大学院のWeb検索結果です。入試情報を抽出しJSONで返してください。
{web[:1500]}
形式: {{"jlpt_min":"N1など","english_req":{{"type":"TOEFL/TOEIC/IELTS","min_score":数値,"required":true/false}},"exam":"筆記+面接","deadlines":[{{"name":"出願","date":"YYYY-MM-DD"}}],"pdf_url":"PDF_URLがあれば","notes":"備考"}} 不明項目はnull。"""
            resp = chat_model.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            m = _re.search(r'\{.*\}', text, re.DOTALL)
            if not m: continue
            data = _json.loads(m.group(0))
            update = {"enrichment_status": "completed", "verified": True}
            if data.get("jlpt_min"): update["jlpt_min"] = data["jlpt_min"]
            if data.get("english_req"): update["english_req"] = _json.dumps(data["english_req"], ensure_ascii=False)
            if data.get("exam"): update["exam"] = data["exam"]
            if data.get("deadlines"): update["deadlines"] = _json.dumps(data["deadlines"], ensure_ascii=False)
            if data.get("notes"): update["notes"] = data["notes"]
            _sk = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
            # PDF download + upload to Supabase Storage
            if data.get("pdf_url"):
                try:
                    import requests as _req
                    _r = _req.get(data["pdf_url"], timeout=15, stream=True, headers={"User-Agent": "Mozilla/5.0"})
                    _cl = int(_r.headers.get("Content-Length", 0))
                    if _r.status_code == 200 and _cl < 5 * 1024 * 1024:
                        pdf_bytes = _r.content
                        storage_path = f"{name}/{name}_{data.get('year','2027')}_募集要項.pdf"
                        _sk.storage.from_("pdfs").upload(storage_path, pdf_bytes, {"content-type": "application/pdf"})
                        storage_url = _sk.storage.from_("pdfs").get_public_url(storage_path)
                        update["pdf_url"] = storage_url
                except Exception:
                    pass  # keep original URL if storage upload fails
            _sk.table("schools").update(update).eq("name", name).execute()
            logger.info(f"Enriched: {name}")
        except Exception as e:
            logger.warning(f"Enrich failed for {name}: {e}")


# ── School catalog loaded from Supabase at startup ──
def _load_school_catalog() -> list[dict]:
    """Load school catalog from Supabase via _row_to_school for consistent V2 field handling."""
    try:
        from demo.school_database import _row_to_school
        res = supabase.table("schools").select("*").order("id").execute()
        catalog = []
        for row in res.data:
            school_obj = _row_to_school(row)
            if school_obj:
                d = school_obj.model_dump()
                # Preserve extra fields not in School model but useful for frontend
                for extra in ("website", "jlpt", "english", "type"):
                    if extra in row:
                        d[extra] = row.get(extra, "")
                catalog.append(d)
        return catalog
    except Exception as e:
        logger.warning(f"Failed to load school catalog from Supabase: {e}")
        return []

SCHOOL_CATALOG = _load_school_catalog()

# ── Intent layer engine ──
intent_engine = IntentLayerEngine(SCHOOL_CATALOG)


@app.get("/v1/normalize")
async def normalize_query(q: str = ""):
    """CN→JP term normalisation for school search. Uses static map + LLM fallback."""
    if not q:
        return {"terms": [], "query": q}
    terms = cn2jp_normalize(q, chat_model=chat_model)
    return {"terms": terms, "query": q}


@app.get("/v1/schools")
async def list_schools(major: str = ""):
    """Browse available schools. Uses cn2jp normalization (static map + LLM fallback)."""
    results = SCHOOL_CATALOG
    if major:
        terms = cn2jp_normalize(major, chat_model=chat_model)
        results = [s for s in results if any(
            t in s.get("name", "") or
            any(t in m for m in s.get("majors", [])) or
            any(t in tag for tag in s.get("tags", []))
            for t in terms
        )]
    return {"schools": results, "total": len(results)}


# ── V2.4: Hybrid school search (vector + BM25 + metadata filters) ──
@app.get("/v1/schools/search")
async def hybrid_search_schools(
    q: str = "",
    k: int = 10,
    jlpt: str = "",
    degree: str = "",
    english: Optional[bool] = None,
):
    """
    Hybrid search schools: semantic (vector) + keyword (BM25) with RRF fusion.
    Optional filters: jlpt (N1/N2/...), degree (修士/学部), english (true/false).
    Falls back to substring search if vector index is unavailable.
    """
    if not q:
        return {"schools": [], "total": 0}

    try:
        from demo.school_search import hybrid_search_schools as hss
        results = hss(
            query=q, k=k, jlpt_min=jlpt.upper() if jlpt else "",
            degree=degree, english_required=english,
        )
        if results:
            return {"schools": results, "total": len(results), "method": "hybrid"}
    except Exception as e:
        logger.warning(f"Hybrid school search failed, falling back to substring: {e}")

    # Fallback: substring search on school catalog
    terms = cn2jp_normalize(q, chat_model=chat_model)
    results = [s for s in SCHOOL_CATALOG if any(
        t in s.get("name", "") or
        any(t in m for m in s.get("majors", [])) or
        any(t in tag for tag in s.get("tags", []))
        for t in terms
    )]
    # Post-filters for fallback
    if jlpt:
        jlpt_order = ["N5", "N4", "N3", "N2", "N1"]
        try:
            jlpt_idx = jlpt_order.index(jlpt.upper())
            results = [s for s in results
                       if s.get("jlpt_min", "") in jlpt_order[:jlpt_idx + 1]]
        except ValueError:
            pass
    if degree:
        results = [s for s in results if s.get("degree", "") == degree]
    if english is not None:
        results = [s for s in results
                   if s.get("english_req", {}).get("required", False) == english]
    return {"schools": results[:k], "total": len(results), "method": "substring"}


# ── Application CRUD (V2.2: manual school management) ──
class ApplicationUpsert(BaseModel):
    school: str
    # None = 未提供 → 部分更新时不覆盖已有字段
    major: Optional[str] = None
    stage: Optional[str] = None
    needs_contact: Optional[bool] = None
    professors: Optional[List[Dict[str, Any]]] = None
    deadlines: Optional[Any] = None     # Dict[str, str] (old) or list[dict] (new)
    official_deadlines: Optional[Any] = None  # School deadlines passed from plaza
    notes: Optional[str] = None

@app.post("/v1/applications")
async def upsert_application(body: ApplicationUpsert, user_id: str = Depends(get_user_id)):
    """Add or update a school application entry. Partial update: only provided fields change."""
    profile = profile_mgr.get_profile(user_id)
    # 部分更新：exclude_none 保证未提供的字段不覆盖已有值（official_deadlines 提供时随 model_dump 透传）
    kwargs = body.model_dump(exclude={"school", "major"}, exclude_none=True)
    profile.upsert_application(body.school, body.major or "", **kwargs)
    profile_mgr.save_profile(user_id, profile)
    return {"ok": True, "school": body.school, "applications": profile.applications}


@app.delete("/v1/applications")
async def delete_application(school: str, user_id: str = Depends(get_user_id)):
    """Remove a school application entry."""
    profile = profile_mgr.get_profile(user_id)
    profile.applications = [a for a in profile.applications if a.get("school") != school]
    profile_mgr.save_profile(user_id, profile)
    return {"ok": True, "school": school, "applications": profile.applications}


def _collect_all_reminders(profile: UserProfile) -> list[dict]:
    """Collect all active reminders with structured format.

    Each reminder: {id, type, school, professor?, message, days, severity, action, acknowledged}
    Sorted: severity desc (high first), days asc within same severity.
    """
    reminders = []
    today = datetime.now().date()

    for app in profile.applications:
        school = app.get("school", "")

        # Per-professor no-reply checks (high severity)
        for prof in app.get("professors", []):
            status = prof.get("status", "")
            if status in ("sent", "no_reply"):
                try:
                    sent_date = prof.get("date", "")
                    if sent_date:
                        sent = datetime.fromisoformat(sent_date).date()
                        elapsed = (today - sent).days
                        if elapsed >= 14:
                            rid = f"prof_no_reply_{school}_{prof['name']}"
                            reminders.append({
                                "id": rid,
                                "type": "professor_no_reply",
                                "school": school,
                                "professor": prof["name"],
                                "message": f"{prof['name']} {elapsed}天未回复，建议发跟进邮件或换教授",
                                "days": elapsed,
                                "severity": "high",
                                "action": {
                                    "type": "draft_outreach",
                                    "school": school,
                                    "professor": prof["name"],
                                    "hint": "换人或跟进"
                                }
                            })
                except (ValueError, TypeError):
                    pass

        # Deadline reminders (approaching + expired, mutually exclusive)
        for dl_name, dl_date_str in deadlines_to_items(app.get("deadlines", [])):
            try:
                dl = datetime.fromisoformat(dl_date_str).date()
                days_left = (dl - today).days
                if days_left < 0:
                    rid = f"deadline_expired_{school}_{dl_name}"
                    reminders.append({
                        "id": rid,
                        "type": "deadline_expired",
                        "school": school,
                        "message": f"{dl_name} 已过期 {abs(days_left)} 天",
                        "days": days_left,
                        "severity": "high",
                        "action": {"type": "goto_calendar"}
                    })
                elif days_left <= 14:
                    rid = f"deadline_{school}_{dl_name}"
                    severity = "high" if days_left <= 7 else "medium"
                    reminders.append({
                        "id": rid,
                        "type": "deadline_approaching",
                        "school": school,
                        "message": f"{dl_name} 还剩 {days_left} 天",
                        "days": days_left,
                        "severity": severity,
                        "action": {"type": "goto_calendar"}
                    })
            except (ValueError, TypeError):
                pass

    # Profile completeness check (< 50% triggers one reminder)
    fields = {
        "jlpt": profile.jlpt_level and profile.jlpt_level != "无",
        "english": bool(profile.english_score and profile.english_score.strip()),
        "gpa": profile.gpa_score > 0,
        "school": profile.undergraduate_school and profile.undergraduate_school != "未设定",
        "major": profile.target_major and profile.target_major != "未设定",
        "research": bool(profile.research_area and profile.research_area.strip()),
    }
    filled = sum(1 for v in fields.values() if v)
    total = len(fields)
    completeness_pct = round(filled / total * 100) if total > 0 else 0
    if completeness_pct < 50:
        reminders.append({
            "id": "profile_incomplete",
            "type": "profile_incomplete",
            "school": "",
            "message": f"学生档案仅完成 {completeness_pct}%，补全背景信息可获得更准的推荐",
            "days": 0,
            "severity": "medium",
            "action": {"type": "open_profile"}
        })

    # Filter out dismissed reminders (24h expiry stored in profile.facts)
    dismissed = profile.facts.get("dismissed_reminders", {})
    now = datetime.now()
    active_dismissals = {}
    for rid, expiry_str in dismissed.items():
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if expiry > now:
                active_dismissals[rid] = expiry_str
        except (ValueError, TypeError):
            pass

    # Sort: high(0) > medium(1) > low(2), then by days ascending
    severity_order = {"high": 0, "medium": 1, "low": 2}
    reminders.sort(key=lambda r: (severity_order.get(r["severity"], 3), r["days"]))

    # Mark acknowledged status
    for r in reminders:
        r["acknowledged"] = r["id"] in active_dismissals

    return reminders


# ── Reminder endpoints ──
@app.get("/v1/reminders")
async def get_reminders(user_id: str = Depends(get_user_id)):
    """Return reminders split into unread/read groups. Read items persist 24h for review."""
    profile = profile_mgr.get_profile(user_id)
    reminders = _collect_all_reminders(profile)
    unread = [r for r in reminders if not r.get("acknowledged")]
    read = [r for r in reminders if r.get("acknowledged")]
    return {"unread": unread, "read": read}


@app.post("/v1/reminders/ack")
async def ack_reminder(body: AckRequest, user_id: str = Depends(get_user_id)):
    """Acknowledge one or all reminders (24h dismiss, stored in profile.facts)."""
    profile = profile_mgr.get_profile(user_id)
    dismissed = profile.facts.get("dismissed_reminders", {})
    expiry = (datetime.now() + timedelta(hours=24)).isoformat()

    if body.all:
        # Dismiss all currently visible reminders
        all_reminders = _collect_all_reminders(profile)
        count = 0
        for r in all_reminders:
            if not r["acknowledged"]:
                dismissed[r["id"]] = expiry
                count += 1
        profile.facts["dismissed_reminders"] = dismissed
        profile_mgr.save_profile(user_id, profile)
        return {"ok": True, "count": count}
    elif body.id:
        dismissed[body.id] = expiry
        profile.facts["dismissed_reminders"] = dismissed
        profile_mgr.save_profile(user_id, profile)
        return {"ok": True}
    else:
        raise HTTPException(400, "Provide 'id' or 'all: true'")


# ── Demo mode: one-click seed / clear sample data for interview demos ──

DEMO_APPS = [
    {
        "school": "京都大学 情报理工学研究科",
        "stage": "contacting",
        "major": "知能情报学",
        "professors": [
            {"name": "田中太郎", "status": "sent", "date": "2026-06-20"},
            {"name": "山田花子", "status": "no_reply", "date": "2026-07-05"},
        ],
        "deadlines": {"I期出願": "2026-08-15", "II期出願": "2026-12-10"},
        "notes": "田中2周未回，已换山田。I期8月截止需抓紧。",
    },
    {
        "school": "东京工业大学 情报理工学院",
        "stage": "preparing",
        "major": "情报工学",
        "professors": [],
        "deadlines": {"夏季入试": "2026-09-01"},
        "notes": "",
    },
    {
        "school": "大阪大学 情报科学研究科",
        "stage": "applying",
        "major": "知能系统",
        "professors": [{"name": "中村健一", "status": "replied", "date": "2026-07-10"}],
        "deadlines": {"冬季出願": "2026-12-15"},
        "notes": "中村教授回复积极，建议申请",
    },
]


@app.post("/v1/demo/seed")
async def demo_seed(user_id: str = Depends(get_user_id)):
    """Inject demo data: 3 tracked schools, professors, deadlines, profile fields."""
    profile = profile_mgr.get_profile(user_id)
    profile.facts["demo_mode"] = True
    profile.facts["demo_injected_at"] = datetime.now().isoformat()
    # Profile fields
    profile.target_degree = "修士"
    profile.research_area = "自然语言处理"
    profile.jlpt_level = "N1"
    profile.gpa_score = 3.2
    profile.gpa_scale = 4.0
    profile.ielts = 7.0
    profile.undergrad_school = "北京邮电大学"
    profile.undergrad_major = "计算机科学与技术"

    # Upsert demo applications (idempotent by school name)
    for app_data in DEMO_APPS:
        profile.upsert_application(**app_data)

    profile_mgr.save_profile(user_id, profile)
    return {"ok": True, "message": "Demo data injected. Reload to see full dashboard."}


@app.delete("/v1/demo/seed")
async def demo_clear(user_id: str = Depends(get_user_id)):
    """Remove all demo-injected data, restore clean profile."""
    profile = profile_mgr.get_profile(user_id)
    # Remove demo applications
    demo_schools = {a["school"] for a in DEMO_APPS}
    profile.applications = [a for a in (profile.applications or []) if a.get("school") not in demo_schools]
    # Clear demo facts
    profile.facts.pop("demo_mode", None)
    profile.facts.pop("demo_injected_at", None)
    profile.facts.pop("dismissed_reminders", None)
    profile_mgr.save_profile(user_id, profile)
    return {"ok": True, "message": "Demo data cleared."}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Serve React frontend (production build) ──
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback: serve index.html for all non-API routes."""
        # Already handled: /v1/*, /health, /docs, /openapi.json, /assets/*
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
