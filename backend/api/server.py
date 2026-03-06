from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from backend.core.agent import HeadlessAgent
from user.profile_manager import UserProfile

app = FastAPI(title="Japan Admission Agent API")

# Configure allowed origins for CORS
allowed_origins = [
    "http://localhost:5173",  # Local Vite frontend
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "https://japan-admission-agent.vercel.app"  # Production Vercel frontend
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    user_profile: UserProfile

@app.post("/v1/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint for the decoupled agent.
    Expects a query and a full user profile.
    Returns a streaming response.
    """
    try:
        agent = HeadlessAgent(request.user_profile)
        
        async def event_generator():
            import json
            async for chunk in agent.chat_stream(request.query):
                print(f"DEBUG[API]: 即将派发 -> {repr(chunk)}")
                if not chunk:
                    continue
                    
                # 统一封装
                is_status_flag = isinstance(chunk, str) and chunk.startswith("[STATUS:")
                payload = {
                    "content": chunk,
                    "is_status": is_status_flag, # 标记是否为状态信息
                    "done": False
                }
                yield f"data: {json.dumps(payload)}\n\n"
                
            # 结束信号也用 JSON
            yield f"data: {json.dumps({'content': '', 'is_status': False, 'done': True})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
