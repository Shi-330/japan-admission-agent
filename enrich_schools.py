"""
Background enrichment worker: gradually hydrate skeleton schools.

Searches for official admission PDFs, extracts structured requirements
(JLPT/English/deadlines/exam), and updates the school record.

Usage:
  python enrich_schools.py              # process up to 5 pending schools
  python enrich_schools.py --all        # process all pending
  python enrich_schools.py --school "东京大学 人文社会系研究科"  # single school
  python enrich_schools.py --loop 300   # run every 300s (daemon mode)
"""
import os, sys, json, re, time
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

from model.factory import chat_model


def enrich_school(school: dict) -> bool:
    """Try to hydrate one skeleton school. Returns True on success."""
    name = school.get("name", "")
    print(f"\n  Enriching: {name}")

    # Mark as enriching
    supabase.table("schools").update({"enrichment_status": "enriching"}).eq("name", name).execute()

    try:
        # Step 0: Search Bing for PDF URLs directly
        pdf_url = None
        try:
            import requests as _req
            from urllib.parse import quote
            _uq = quote(f"{name} 大学院 募集要項 2027 filetype:pdf site:ac.jp")
            _r = _req.get(f"https://www.bing.com/search?q={_uq}&count=5",
                          timeout=10, verify=False,
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            pdf_matches = re.findall(r'https?://[^\s<>"]+\.pdf', _r.text)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                print(f"    Found PDF: {pdf_url[:120]}")
        except Exception as e:
            print(f"    PDF search skipped: {e}")

        # Step 1: Web search for official admission text
        query = f"{name} 修士課程 募集要項 2027 site:ac.jp"
        from rag.rag_service import RagSummarizeService
        rag = RagSummarizeService()
        web_text = rag.search_with_fallback(query)
        if not web_text or web_text.startswith("未找到"):
            query2 = f"{name} 大学院 入試要項 PDF"
            web_text = rag.search_with_fallback(query2)
        if not web_text or web_text.startswith("未找到"):
            supabase.table("schools").update({"enrichment_status": "failed"}).eq("name", name).execute()
            print(f"    No web results")
            return False

        # Step 2: LLM extract structured fields
        pdf_hint = f"\n\n【PDF URL】{pdf_url}" if pdf_url else ""
        prompt = f"""以下は日本大学院の募集要項に関するWeb検索結果です。この学校の修士課程入試情報を抽出してください。
入学試験情報は必ずPDFに記載があるので、PDFがあれば優先して参照してください。{pdf_hint}

{web_text[:1500]}

以下のJSON形式で返してください（不明な項目はnull）：
{{"jlpt_min":"N1/N2/...", "english_req":{{"type":"TOEFL/TOEIC/IELTS","min_score":数値,"required":true/false}}, "exam":"筆記+面接など", "deadlines":[{{"name":"出願","date":"YYYY-MM-DD"}}], "pdf_url":"PDFのURLがあれば", "notes":"備考"}}
"""
        resp = chat_model.invoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)

        # Parse JSON from LLM response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            supabase.table("schools").update({"enrichment_status": "failed"}).eq("name", name).execute()
            print(f"    LLM returned no JSON")
            return False

        data = json.loads(json_match.group(0))

        # Step 3: Update school
        update = {"enrichment_status": "completed", "verified": True}
        if data.get("jlpt_min"): update["jlpt_min"] = data["jlpt_min"]
        if data.get("english_req"): update["english_req"] = data["english_req"]
        if data.get("exam"): update["exam"] = data["exam"]
        if data.get("deadlines"): update["deadlines"] = data["deadlines"]
        if data.get("notes"): update["notes"] = (school.get("notes","") + " | " + data["notes"]).strip(" |")
        # Use LLM-found PDF URL or dedicated-search-found URL
        _final_pdf = data.get("pdf_url") or pdf_url
        # PDF download + upload to Supabase Storage
        if _final_pdf:
            try:
                import requests as _req
                _r = _req.get(_final_pdf, timeout=15, stream=True, headers={"User-Agent": "Mozilla/5.0"})
                _cl = int(_r.headers.get("Content-Length", 0))
                if _r.status_code == 200 and _cl < 5 * 1024 * 1024:
                    pdf_bytes = _r.content
                    storage_path = f"{name}/{name}_{data.get('year','2027')}_募集要項.pdf"
                    supabase.storage.from_("pdfs").upload(storage_path, pdf_bytes, {"content-type": "application/pdf"})
                    storage_url = supabase.storage.from_("pdfs").get_public_url(storage_path)
                    update["pdf_url"] = storage_url
            except Exception:
                pass  # keep original URL if storage upload fails

        supabase.table("schools").update(update).eq("name", name).execute()
        print(f"    OK: {json.dumps({k:v for k,v in update.items() if k != 'enrichment_status'}, ensure_ascii=False)[:120]}")
        return True

    except Exception as e:
        supabase.table("schools").update({"enrichment_status": "failed"}).eq("name", name).execute()
        print(f"    FAIL: {e}")
        return False


def run(batch_size=5):
    """Process a batch of pending schools."""
    res = supabase.table("schools").select("name,notes").eq("enrichment_status", "skeleton").limit(batch_size).execute()
    pending = res.data
    if not pending:
        # Also retry failed ones
        res = supabase.table("schools").select("name,notes").eq("enrichment_status", "failed").limit(batch_size).execute()
        pending = res.data
    if not pending:
        print("No pending schools to enrich")
        return

    print(f"Found {len(pending)} pending school(s)")
    ok = 0
    for s in pending:
        if enrich_school(s):
            ok += 1
    print(f"\nDone: {ok}/{len(pending)} enriched")


if __name__ == "__main__":
    if "--school" in sys.argv:
        idx = sys.argv.index("--school")
        name = sys.argv[idx + 1]
        school = supabase.table("schools").select("name,notes").eq("name", name).execute()
        if school.data:
            enrich_school(school.data[0])
        else:
            print(f"School not found: {name}")
    elif "--loop" in sys.argv:
        idx = sys.argv.index("--loop")
        interval = int(sys.argv[idx + 1])
        print(f"Enrichment daemon — running every {interval}s")
        while True:
            run(batch_size=3)
            time.sleep(interval)
    else:
        batch = 100 if "--all" in sys.argv else 5
        run(batch_size=batch)
