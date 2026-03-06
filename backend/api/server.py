from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from backend.core.agent import HeadlessAgent
from user.profile_manager import UserProfile

app = FastAPI(title="Japan Admission Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development, allow all. Change this for production.
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
        
        def event_generator():
            # Synchronous generator running in a thread-safe way
            for chunk in agent.chat_stream(request.query):
                yield chunk

        from fastapi.concurrency import iterate_in_threadpool
        return StreamingResponse(iterate_in_threadpool(event_generator()), media_type="text/plain")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
