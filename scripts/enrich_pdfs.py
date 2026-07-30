"""
PDF enrichment pipeline: find real PDF URLs via RAG search + LLM extraction.
Runs overnight — processes all 398 schools, skips those already with valid PDFs.

Usage:
  venv/Scripts/python.exe scripts/enrich_pdfs.py
  venv/Scripts/python.exe scripts/enrich_pdfs.py --limit 20
"""
import os, sys, json, re, time, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from model.factory import chat_model

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def find_pdf_url(name: str) -> str | None:
    """Search for a school's 募集要項 PDF URL via RAG web search + LLM."""
    try:
        from rag.rag_service import RagSummarizeService
        rag = RagSummarizeService()
        web_text = rag.search_with_fallback(f"{name} 大学院 修士課程 募集要項 PDF 2027")
        if not web_text or web_text.startswith("未找到"):
            return None

        prompt = f"""以下のWeb検索結果から、{name}の修士課程募集要項PDFのURLを抽出してください。
PDFのURL（.pdfで終わる完全なURL）を1つだけ返してください。見つからない場合は NOT_FOUND と返してください。
URLのみを返してください。説明は不要です。

{web_text[:2000]}"""
        resp = chat_model.invoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        text = text.strip()
        if "NOT_FOUND" in text: return None
        url_match = re.search(r'https?://[^\s<>"]+\.pdf', text)
        if url_match: return url_match.group(0)
    except Exception as e:
        print(f"  Search error: {e}")
    return None


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

    # Get schools needing PDF URLs
    r = supabase.table("graduate_schools").select("id,name_jp,pdf_url").execute()
    # Filter: need PDF URL (empty or invalid)
    needs_pdf = [s for s in r.data if not (s.get("pdf_url") or "").startswith("http")]
    if limit: needs_pdf = needs_pdf[:limit]

    print(f"Schools needing PDF: {len(needs_pdf)}/{len(r.data)}")
    ok = 0
    for i, s in enumerate(needs_pdf):
        name = s["name_jp"]
        print(f"\n[{i+1}/{len(needs_pdf)}] {name[:50]}")

        # Skip if already got one (safety check)
        check = supabase.table("graduate_schools").select("pdf_url").eq("id", s["id"]).execute()
        if check.data and (check.data[0].get("pdf_url") or "").startswith("http"):
            print("  Already has valid PDF, skip")
            ok += 1
            continue

        pdf_url = find_pdf_url(name)
        if pdf_url:
            try:
                supabase.table("graduate_schools").update({"pdf_url": pdf_url}).eq("id", s["id"]).execute()
                print(f"  -> {pdf_url[:100]}")
                ok += 1
            except Exception as e:
                print(f"  DB error: {e}")
        else:
            print("  -> NOT FOUND")

        time.sleep(3)  # Rate limit: 3s between searches

        if (i + 1) % 20 == 0:
            print(f"\n--- Progress: {ok}/{i+1} found ---")

    print(f"\nDone: {ok}/{len(needs_pdf)} PDF URLs found")


if __name__ == "__main__":
    main()
