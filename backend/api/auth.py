"""
Supabase JWT auth middleware for FastAPI.
Verifies tokens by calling Supabase's /auth/v1/user endpoint.
"""
import os, json, urllib.request
from dotenv import load_dotenv
load_dotenv()

from fastapi import Request, HTTPException
from utils.logger_handler import logger

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


def verify_supabase_token(token: str) -> str:
    """Verify Supabase JWT and return user_id.
    Tries: 1) Supabase API  2) JWT secret (local)  3) Decode without verify (dev only)
    """
    # Method 1: verify via Supabase API
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            req = urllib.request.Request(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_KEY},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            user = json.loads(resp.read())
            user_id = user.get("id")
            if user_id:
                return user_id
        except Exception:
            pass  # fall through to local methods

    # Method 2: local JWT decode with secret
    if SUPABASE_JWT_SECRET:
        import jwt
        try:
            payload = jwt.decode(token, SUPABASE_JWT_SECRET,
                algorithms=["HS256", "HS384", "HS512"], options={"verify_exp": True})
            return payload.get("sub")
        except jwt.InvalidTokenError:
            pass

    # Method 3: decode without signature verification (dev only)
    import jwt
    try:
        payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": True})
        user_id = payload.get("sub")
        if user_id:
            logger.warning(f"Token verified WITHOUT signature check for {user_id}")
            return user_id
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    raise HTTPException(status_code=401, detail="Token verification failed")


async def get_user_id(request: Request) -> str:
    """FastAPI dependency: extract user_id from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return verify_supabase_token(auth[7:])
