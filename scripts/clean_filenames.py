"""Strip filename-only PDF references (system2026j.pdf etc.) from notes."""
import os, sys, re, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client

s = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
r = s.table("graduate_schools").select("id,name_jp,notes").ilike("notes", "%system2026j%").execute()

ct = 0
for x in r.data:
    notes = x["notes"] or ""
    # Remove filename references
    notes = re.sub(r'[（(]\s*(?:参照[：:]\s*)?https?://[^\s）)]+[）)]?', '', notes)
    notes = re.sub(r'[（(]?\s*system2026j\.pdf\s*より[）)]?', '', notes)
    notes = notes.strip().strip("|").strip()
    if notes != (x["notes"] or ""):
        s.table("graduate_schools").update({"notes": notes}).eq("id", x["id"]).execute()
        ct += 1
        print(f"  Cleaned: {x['name_jp'][:40]}")

print(f"\nCleaned: {ct} notes")
