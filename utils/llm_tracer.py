"""
LLM prompt/response tracer for debugging and regression testing.
Logs every LLM call with metadata, stores last N entries in memory.

Usage:
  from utils.llm_tracer import trace
  resp = trace(chat_model.invoke, prompt, intent="qa", query="...")

  # Review in admin:
  from utils.llm_tracer import get_recent, get_summary
  get_recent(10)  # last 10 calls
  get_summary()   # stats by intent
"""
import time, json, hashlib, os, threading
from collections import deque
from typing import Optional

MAX_ENTRIES = 200
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "llm_traces.jsonl")
_lock = threading.Lock()

_trace_buffer = deque(maxlen=MAX_ENTRIES)


def _append_file(entry: dict):
    """Append one entry to JSONL file (thread-safe)."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # best-effort, don't crash on disk write

def trace(fn, prompt: str, *, intent: str = "", query: str = "", user_id: str = "") -> str:
    """Wrap an LLM call. Captures prompt + response with metadata."""
    t0 = time.time()
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "intent": intent,
        "query": query[:200],
        "user_id": user_id[:20] if user_id else "",
        "prompt_hash": hashlib.md5(prompt.encode()).hexdigest()[:8],
        "prompt": prompt[:2000],  # truncate for storage
        "prompt_full_len": len(prompt),
    }
    try:
        result = fn(prompt)
        elapsed = time.time() - t0
        content = result.content if hasattr(result, "content") else str(result)
        entry["response"] = content[:2000]
        entry["response_len"] = len(content)
        entry["elapsed"] = round(elapsed, 2)
        entry["status"] = "ok"
    except Exception as e:
        entry["status"] = f"error: {e}"
        entry["elapsed"] = round(time.time() - t0, 2)
        raise
    finally:
        _trace_buffer.append(entry)
        with _lock:
            _append_file(entry)
    return result


def get_recent(n: int = 20) -> list[dict]:
    """Return last N traced calls."""
    return list(_trace_buffer)[-n:]


def get_summary() -> dict:
    """Return stats grouped by intent."""
    from collections import Counter
    entries = list(_trace_buffer)
    if not entries:
        return {"total": 0}
    intents = Counter(e["intent"] for e in entries)
    statuses = Counter(e["status"] for e in entries)
    avg_elapsed = sum(e.get("elapsed", 0) for e in entries) / len(entries)
    return {
        "total": len(entries),
        "intents": dict(intents),
        "statuses": dict(statuses),
        "avg_elapsed": round(avg_elapsed, 2),
        "oldest": entries[0]["ts"] if entries else "",
        "newest": entries[-1]["ts"] if entries else "",
    }


def get_by_hash(hash_prefix: str) -> Optional[dict]:
    """Find a specific call by prompt hash prefix."""
    for e in reversed(_trace_buffer):
        if e["prompt_hash"].startswith(hash_prefix):
            return e
    return None
