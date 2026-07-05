"""
FastAPI server — shared backend for Streamlit / React / whatever frontend.

Run: uvicorn backend.api.server:app --host 0.0.0.0 --port 8000 --reload
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import json

from backend.api.auth import get_user_id
from user.profile_manager import ProfileManager, UserProfile
from agent.orchestrator import ChatOrchestrator
from model.factory import chat_model
from utils.logger_handler import logger

app = FastAPI(title="Japan Admission Agent API")

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:8501",
        "http://127.0.0.1:5173", "http://127.0.0.1:8501",
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
    return {
        "name": "Japan Admission Agent API",
        "docs": "/docs",
        "endpoints": ["/health", "/v1/profile", "/v1/match", "/v1/rag", "/v1/chat"],
    }


# ── Chat endpoint (SSE streaming) ──
@app.post("/v1/chat")
async def chat_endpoint(body: ChatRequest, user_id: str = Depends(get_user_id)):
    """Intent classification → route to match/RAG/chat → SSE streaming response."""
    profile = profile_mgr.get_profile(user_id)
    profile_str = profile_mgr.format_for_prompt(profile)

    # 1. Intent classification
    intent = orchestrator.classify_intent(body.query, profile_str, chat_model)

    async def event_generator():
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
                summary = f"""你是日本升学顾问。
【资料】{ctx[:800] if ctx else "无"}
【学生】{profile_str}
【问题】{body.query}
简洁中文回答。资料为空则说明知识库暂无相关内容。"""
                resp = chat_model.invoke(summary)
                text = resp.content if hasattr(resp, "content") else str(resp)
                yield f"data: {json.dumps({'content': text, 'is_status': False, 'done': False})}\n\n"
                yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"

            else:  # chat
                resp = chat_model.invoke(
                    f"学生说：{body.query}。背景：{profile_str}。友好回复1-2句，直接给出建议。")
                text = resp.content if hasattr(resp, "content") else str(resp)
                yield f"data: {json.dumps({'content': text, 'is_status': False, 'done': False})}\n\n"
                yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"

            # 3. Extract new facts from this turn
            orchestrator.finish_turn(user_id, profile, body.query, "", chat_model)

        except Exception as e:
            logger.error(f"Chat error: {e}")
            yield f"data: {json.dumps({'content': f'Error: {e}', 'is_status': False, 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Stage endpoints ──
@app.get("/v1/stage")
async def get_stage(user_id: str = Depends(get_user_id)):
    from agent.state_machine import get_current_stage_info, generate_timeline, check_reminders
    profile = profile_mgr.get_profile(user_id)
    stage = profile.application_stage or "preparing"
    info = get_current_stage_info(stage)
    # Get stage_started_at from field_sources
    started = profile.field_sources.get("application_stage", {}).get("at")
    return {
        **info,
        "timeline": generate_timeline(stage, started),
        "reminders": check_reminders(stage, started),
    }


class AdvanceRequest(BaseModel):
    target_stage: str

@app.post("/v1/stage/advance")
async def advance_stage_endpoint(body: AdvanceRequest, user_id: str = Depends(get_user_id)):
    from agent.state_machine import advance_stage, STAGES
    profile = profile_mgr.get_profile(user_id)
    current = profile.application_stage or "preparing"
    if not advance_stage(current, body.target_stage):
        valid = STAGES.get(current, {}).get("next_stages", [])
        raise HTTPException(400, f"Cannot advance from '{current}' to '{body.target_stage}'. Valid: {valid}")
    profile.set_field("application_stage", body.target_stage, "form")
    profile_mgr.save_profile(user_id, profile)
    return {"stage": body.target_stage, "label": STAGES[body.target_stage]["label"]}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
