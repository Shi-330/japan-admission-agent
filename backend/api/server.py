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
import json
import time

from backend.api.auth import get_user_id
from user.profile_manager import ProfileManager, UserProfile
from agent.orchestrator import ChatOrchestrator
from model.factory import chat_model
from utils.logger_handler import logger
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="Japan Admission Agent API")

# ── Simple TTL cache for chat responses ──
_chat_cache: dict = {}  # key -> (response_text, timestamp)
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
        "http://localhost:8501",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175",
        "http://127.0.0.1:8501",
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

class MatchRequest(BaseModel):
    target_major: Optional[str] = None

class RagRequest(BaseModel):
    query: str


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
    profile_mgr.save_profile(user_id, profile)
    return profile.to_dict()


# ── Match endpoint ──
@app.post("/v1/match")
async def match_schools_endpoint(body: MatchRequest, user_id: str = Depends(get_user_id)):
    from demo.matching_engine import StudentProfile, match_schools, STATUS_LABELS
    profile = profile_mgr.get_profile(user_id)
    target = body.target_major or profile.target_major
    sp = StudentProfile(
        jlpt_level=profile.jlpt_level,
        eju_score=int(profile.eju_score),
        gpa=float(profile.gpa),
        target_major=target,
        english_score=profile.english_score,
        undergraduate_school=profile.undergraduate_school,
    )
    matches = match_schools(sp)
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
                "capacity": m.capacity,
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
        "endpoints": ["/health", "/v1/profile", "/v1/match", "/v1/rag", "/v1/chat", "/v1/stage", "/v1/applications"],
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
        deadlines = app.get("deadlines", {})
        if deadlines:
            d_strs = [f"{k}:{v}" for k, v in deadlines.items()]
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
    profile = profile_mgr.get_profile(user_id)
    profile_str = profile_mgr.format_for_prompt(profile)
    stage_ctx = _build_stage_context(profile)

    # 1. Intent classification (with cache)
    profile_hash = hashlib.md5(profile_str.encode()).hexdigest()[:8]
    cache_key = _cache_key(user_id, body.query, profile_hash)
    cached = _cache_get(cache_key)
    if cached:
        async def cached_generator():
            for i in range(0, len(cached), 2):
                chunk = cached[i:i+2]
                yield f"data: {json.dumps({'content': chunk, 'is_status': False, 'done': False})}\n\n"
                await __import__('asyncio').sleep(0.01)
            yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"
        return StreamingResponse(
            cached_generator(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    intent = orchestrator.classify_intent(body.query, profile_str, chat_model)

    async def event_generator():
        assistant_text = ""
        try:
            # 2. Route by intent
            if intent == "match":
                from demo.matching_engine import StudentProfile, match_schools, STATUS_LABELS
                sp = StudentProfile(
                    jlpt_level=profile.jlpt_level, eju_score=int(profile.eju_score),
                    gpa=float(profile.gpa), target_major=profile.target_major,
                    english_score=profile.english_score,
                    undergraduate_school=profile.undergraduate_school,
                )
                matches = match_schools(sp)
                nl = "\n"
                for m in matches:
                    line = f"{STATUS_LABELS[m.status]} {m.school_name}{nl}"
                    yield f"data: {json.dumps({'content': line, 'is_status': False, 'done': False})}\n\n"
                yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"

            elif intent in ("qa", "report"):
                from rag.rag_service import RagSummarizeService
                try:
                    rag = RagSummarizeService()
                    ctx = rag.get_raw_vector_context(body.query)
                except Exception:
                    ctx = ""
                prompt = f"""你是日本升学顾问。
【资料】{ctx[:800] if ctx else "无"}
【学生】{profile_str}
{stage_ctx}
【问题】{body.query}
简洁中文回答，结合学生当前申请状态给出建议。资料为空则说明知识库暂无相关内容。"""
                for chunk in chat_model.stream(prompt):
                    c = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if c:
                        assistant_text += c
                        yield f"data: {json.dumps({'content': c, 'is_status': False, 'done': False})}\n\n"
                plaza = _detect_plaza_action(body.query, assistant_text)
                done_event = {'content': '', 'is_status': False, 'done': True}
                if plaza:
                    done_event['plaza_action'] = plaza
                yield f"data: {json.dumps(done_event)}\n\n"

            else:  # chat
                prompt = f"学生说：{body.query}。背景：{profile_str}。{stage_ctx}你是一位日本升学顾问。结合学生的申请状态，友好回复并给出针对性建议。如果有教授长时间未回复，提醒学生跟进。"
                for chunk in chat_model.stream(prompt):
                    c = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if c:
                        assistant_text += c
                        yield f"data: {json.dumps({'content': c, 'is_status': False, 'done': False})}\n\n"
                # Check for plaza action
                plaza = _detect_plaza_action(body.query, assistant_text)
                done_event = {'content': '', 'is_status': False, 'done': True}
                if plaza:
                    done_event['plaza_action'] = plaza
                yield f"data: {json.dumps(done_event)}\n\n"

            # 3. Extract new facts + cache response
            if assistant_text:
                _cache_set(cache_key, assistant_text)
                orchestrator.finish_turn(user_id, profile, body.query, assistant_text, chat_model)
                # 4. Detect schools mentioned in reply but not yet tracked
                suggested = _detect_new_schools(profile, assistant_text)
                if suggested:
                    yield f"data: {json.dumps({'suggested_schools': suggested, 'done': True})}\n\n"
                    return

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
    """Generate a proactive greeting/reminder based on current application state."""
    profile = profile_mgr.get_profile(user_id)
    parts = []

    # 1. Check per-school professor reminders
    prof_reminders = []
    for app in profile.applications:
        school = app.get("school", "")
        for prof in app.get("professors", []):
            status = prof.get("status", "")
            date_str = prof.get("date", "")
            if status in ("sent", "no_reply") and date_str:
                try:
                    elapsed = (datetime.now() - datetime.fromisoformat(date_str)).days
                    if elapsed >= 14:
                        prof_reminders.append(f"{prof['name']}({school}) 已 {elapsed} 天未回复，建议发跟进邮件或换教授")
                except (ValueError, TypeError):
                    pass

    if prof_reminders:
        parts.append("提醒：" + "；".join(prof_reminders))

    # 2. Check upcoming deadlines
    deadline_warnings = []
    today = datetime.now().date()
    for app in profile.applications:
        school = app.get("school", "")
        for name, date_str in app.get("deadlines", {}).items():
            try:
                dl = datetime.fromisoformat(date_str).date()
                days_left = (dl - today).days
                if 0 <= days_left <= 14:
                    deadline_warnings.append(f"{school}「{name}」还剩 {days_left} 天 ({date_str})")
                elif days_left < 0:
                    deadline_warnings.append(f"{school}「{name}」已过期 {abs(days_left)} 天 ({date_str})")
            except (ValueError, TypeError):
                pass

    if deadline_warnings:
        parts.append("截止日期提醒：" + "；".join(deadline_warnings))

    # 3. Stage-based nudges
    stage = profile.application_stage or "preparing"
    from agent.state_machine import get_current_stage_info
    info = get_current_stage_info(stage)

    if stage == "preparing":
        if not profile.research_area:
            parts.append("你还没有设定研究方向，要不要聊聊你想研究什么？")
        elif not profile.target_professors and not profile.applications:
            parts.append("研究计划准备得怎么样了？可以跟我说说你想申请的学校和方向。")

    elif stage == "contacting":
        active = sum(1 for a in profile.applications if a.get("stage") == "contacting")
        if active == 0:
            parts.append("准备好联系教授了吗？告诉我你想联系哪位教授，我帮你跟进。")

    elif stage == "applying":
        parts.append("出愿材料准备中？确认一下各校的截止日期，别错过了。")

    elif stage == "exam":
        parts.append("临近考试，别忘复习专业课+练面试陈述。需要模拟面试吗？")

    elif stage == "waiting":
        parts.append("结果等待中。也可以准备备选方案，有需要随时聊。")

    # 4. No data at all? Welcome
    if not profile.applications and stage == "preparing" and not profile.research_area:
        parts.insert(0, "欢迎回来！我是你的日本升学顾问。告诉我你的研究方向，我帮你匹配学校和教授。")

    return {
        "message": "\n\n".join(parts) if parts else "欢迎回来！当前一切顺利。有什么需要帮助的？",
        "has_reminders": bool(prof_reminders or deadline_warnings),
    }


# ── Doc fetch + LLM extraction ──
class DocFetchRequest(BaseModel):
    url: str
    school: str = ""  # optional, if known

@app.post("/v1/docs/fetch")
async def fetch_and_extract(body: DocFetchRequest, user_id: str = Depends(get_user_id)):
    """Fetch a URL, extract text, use LLM to find deadlines/exam info."""
    import urllib.request
    import re

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


# ── School Plaza (browse/discover) ──
# Reference school data with deadlines from 募集要項
SCHOOL_CATALOG = [
    {"name": "京都大学 情报学研究科", "majors": ["知能情報学", "社会情報学", "数理工学", "システム科学", "通信情報システム", "データ科学"], "degree": "修士", "jlpt": "N1", "english": "TOEFL/TOEIC", "exam": "筆記+面接", "deadlines": {"出願期間": "2026-12-10 ~ 2027-01-09", "試験日": "2027年2月", "合格発表": "2027年2月下旬"}, "notes": "一般入試+国際プログラム。教授内諾不要。", "tags": ["情報", "筆記", "面接", "英語必要", "国際プログラム"]},
    {"name": "东京科学大学 情報理工学院", "majors": ["情報工学", "数理計算科学"], "degree": "修士", "jlpt": "N2以上", "english": "TOEFL/TOEIC", "exam": "筆記(数学+専門)+面接", "deadlines": {"A日程出願": "2026年6月", "A日程試験": "2026年8月", "B日程出願": "2026年11~12月", "B日程試験": "2027年1~2月"}, "notes": "旧东京工业大学。A/B两轮入试。", "tags": ["情報", "筆記", "面接", "英語必要"]},
    {"name": "筑波大学 システム情報工学研究群", "majors": ["情報理工", "知能機能システム", "エンパワーメント情報学"], "degree": "修士", "jlpt": "N2以上", "english": "TOEIC/TOEFL/IELTS", "exam": "書類+面接(筆記なしの場合も)", "deadlines": {"8月選考出願": "2026-07-09~22", "8月試験": "2026-08-19~21", "1-2月選考出願": "2026-11-30~12-10", "1-2月試験": "2027-01-26~28"}, "notes": "8月+1-2月两轮。英語スコア必須。", "tags": ["情報", "書類選考", "面接", "英語必要", "筆記なし可能"]},
    {"name": "大阪大学 情報科学研究科", "majors": ["情報数理学", "コンピュータサイエンス", "情報システム工学", "情報ネットワーク学", "マルチメディア工学", "バイオ情報工学"], "degree": "修士", "jlpt": "N2以上", "english": "TOEIC/TOEFL必須", "exam": "口頭試問+書類審査", "deadlines": {"一般出願": "2026-05-21~23", "一般試験": "2026-07-07", "留学生夏出願": "2026-06-23~27", "留学生冬出願": "2026-10-27~31"}, "notes": "6専攻。受入教員の承認印必須。ITSCE英語コース有。", "tags": ["情報", "口頭試問", "書類選考", "英語必要", "英語コース"]},
    {"name": "名古屋大学 情報学研究科", "majors": ["数理情報学", "複雑系科学", "社会情報学"], "degree": "修士", "jlpt": "N2以上", "english": "TOEFL/TOEIC", "exam": "筆記+面接(専攻による)", "deadlines": {"第1回出願": "2026-06-26~07-02", "第1回試験": "2026-08-05~06", "第2回出願": "2026-12-17~23", "第2回試験": "2027年2月"}, "notes": "年2回入試。出願前に志望教員に連絡必須。", "tags": ["情報", "筆記", "面接", "英語必要", "事前連絡必須"]},
    {"name": "早稻田大学 基幹理工学研究科", "majors": ["情報理工", "情報通信"], "degree": "修士", "jlpt": "N2以上", "english": "TOEFL/TOEIC", "exam": "筆記+面接", "deadlines": {"7月入試出願": "2026年5月", "7月試験": "2026年7月", "2月入試出願": "2026年12月", "2月試験": "2027年2月"}, "notes": "情報理工学専攻。年2回入試。", "tags": ["情報", "筆記", "面接", "英語必要"]},
    {"name": "东北大学 情報科学研究科", "majors": ["情報基礎科学", "システム情報科学", "人間社会情報科学", "応用情報科学"], "degree": "修士", "jlpt": "N2以上", "english": "TOEFL/TOEIC", "exam": "筆記+口頭試問", "deadlines": {"8月入試出願": "2026年7月", "8月試験": "2026年8月", "2月入試出願": "2026年12月", "2月試験": "2027年2月"}, "notes": "4専攻。教授事前連絡推奨。", "tags": ["情報", "筆記", "口頭試問", "英語必要"]},
]

@app.get("/v1/schools")
async def list_schools(major: str = ""):
    """Browse available schools, optionally filter by major."""
    results = SCHOOL_CATALOG
    if major:
        results = [s for s in results if any(major in m for m in s.get("majors", []))]
    return {"schools": results, "total": len(results)}


# ── Application CRUD (V2.2: manual school management) ──
class ApplicationUpsert(BaseModel):
    school: str
    stage: str = "preparing"
    needs_contact: bool = False
    professors: List[Dict[str, Any]] = []
    deadlines: Dict[str, str] = {}
    notes: str = ""

@app.post("/v1/applications")
async def upsert_application(body: ApplicationUpsert, user_id: str = Depends(get_user_id)):
    """Add or update a school application entry."""
    profile = profile_mgr.get_profile(user_id)
    profile.upsert_application(
        body.school,
        stage=body.stage,
        needs_contact=body.needs_contact,
        professors=body.professors,
        deadlines=body.deadlines,
        notes=body.notes,
    )
    profile_mgr.save_profile(user_id, profile)
    return {"ok": True, "school": body.school, "applications": profile.applications}


@app.delete("/v1/applications")
async def delete_application(school: str, user_id: str = Depends(get_user_id)):
    """Remove a school application entry."""
    profile = profile_mgr.get_profile(user_id)
    profile.applications = [a for a in profile.applications if a.get("school") != school]
    profile_mgr.save_profile(user_id, profile)
    return {"ok": True, "school": school, "applications": profile.applications}


def _detect_plaza_action(query: str, assistant_text: str) -> Optional[dict]:
    """Detect if user is searching/filtering schools. Extract keywords for filter."""
    p = query.lower()
    triggers = ["哪些学校", "有没有", "帮我找", "帮我选", "推荐", "找", "怎么选"]
    if not any(t in p for t in triggers):
        return None

    # Extract meaningful filter keywords
    keywords = []
    # English requirements
    if any(k in p for k in ["不要英语", "不需要英语", "免英语", "英语不要", "不要toefl", "不要托福", "英语不要"]):
        keywords.append("英語不要")
    elif any(k in p for k in ["英语", "toefl", "toeic", "托福"]):
        keywords.append("英語")
    # Exam type
    if any(k in p for k in ["免笔试", "不要笔试", "免筆試", "没有笔试", "书类", "書類"]):
        keywords.append("書類選考")
    elif any(k in p for k in ["笔试", "筆試", "筆記"]):
        keywords.append("筆記")
    elif any(k in p for k in ["面试", "面接"]):
        keywords.append("面接")
    # JLPT
    if "n1" in p:
        keywords.append("N1")
    elif "n2" in p:
        keywords.append("N2")
    # Majors
    if any(k in p for k in ["情报", "情報", "计算机", "cs", "nlp", "自然语言"]):
        keywords.append("情報")
        if any(k in p for k in ["nlp", "自然语言"]):
            keywords.append("NLP")
    # Only meaningful if we extracted keywords
    if not keywords:
        # Fallback: use the whole query
        keywords.append(query.strip())
    kw_str = " ".join(keywords)
    return {"action": "filter_plaza", "filter": kw_str, "prompt": f"已按「{'、'.join(keywords)}」筛选"}


def _detect_new_schools(profile: UserProfile, text: str) -> list[str]:
    """Find university names mentioned in text that aren't yet in applications."""
    import re
    existing = {a.get("school", "") for a in profile.applications}
    # Match Japanese university names: XX大学, XX大学院, or specific patterns like 北海道大学
    found = set()
    for pattern in [r'([一-鿿]{2,6}(?:大学|大学院))', r'(北海道大学|东京大学|京都大学|大阪大学|名古屋大学|九州大学|东北大学|早稻田大学|庆应义塾大学|筑波大学|神户大学|广岛大学|一桥大学|东京工业大学|横滨国立大学)']:
        for m in re.finditer(pattern, text):
            name = m.group(0)
            if name not in existing and name not in [a.split()[0] if ' ' in a else a for a in existing]:
                found.add(name)
    return list(found)[:3]  # max 3 suggestions


def _collect_all_reminders(profile: UserProfile) -> list:
    """Collect professor no-reply reminders across all applications."""
    from agent.state_machine import check_reminders
    reminders = []
    for app in profile.applications:
        school = app.get("school", "")
        stage_id = app.get("stage", "preparing")
        started = profile.field_sources.get(f"app_stage_{school}", {}).get("at")
        stage_reminders = check_reminders(stage_id, started)
        for r in stage_reminders:
            reminders.append({"school": school, "message": r})
        # Per-professor no-reply checks
        for prof in app.get("professors", []):
            status = prof.get("status", "")
            if status in ("sent", "no_reply"):
                try:
                    sent_date = prof.get("date", "")
                    if sent_date:
                        sent = datetime.fromisoformat(sent_date)
                        elapsed = (datetime.now() - sent).days
                        if elapsed >= 14 and status != "no_reply":
                            reminders.append({
                                "school": school,
                                "professor": prof["name"],
                                "message": f"{prof['name']} {elapsed}天未回复，建议发跟进邮件或换教授"
                            })
                except (ValueError, TypeError):
                    pass
    return reminders


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
