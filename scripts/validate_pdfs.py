"""
Validate and clean PDF URLs in graduate_schools.
Fixes: filename-only URLs (e.g. "system2026j.pdf" -> "") and invalid URLs.
"""
import os, sys, re, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

def is_valid_pdf_url(url: str) -> bool:
    if not url or len(url) < 10: return False
    if not url.startswith("http"): return False  # filename-only
    if not re.match(r'https?://[^\s]+\.pdf', url, re.IGNORECASE):
        # Accept non-.pdf URLs too (some schools use HTML pages for admission info)
        if not url.startswith("http"): return False
    return True

r = supabase.table("graduate_schools").select("id,name_jp,pdf_url").execute()
total = len(r.data)
valid = 0
filename_only = 0
cleaned = 0

for s in r.data:
    url = s.get("pdf_url", "") or ""
    if not url:
        valid += 1  # empty is fine
        continue
    if is_valid_pdf_url(url):
        valid += 1
    else:
        # Clean: set to empty string
        supabase.table("graduate_schools").update({"pdf_url": ""}).eq("id", s["id"]).execute()
        cleaned += 1
        if url.endswith(".pdf") and not url.startswith("http"):
            filename_only += 1
        print(f"  CLEANED: {s['name_jp'][:40]} -> {url[:60]}")

print(f"\nTotal: {total}, Valid: {valid}, Cleaned: {cleaned} (filename-only: {filename_only})")
