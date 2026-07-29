"""
Backfill pdf_url for schools that are enriched but missing PDFs.
Uses RAG web search + LLM to find PDF links, then downloads and uploads to Supabase Storage.
"""
import os, sys, json, re, time
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])

from model.factory import chat_model
from rag.rag_service import RagSummarizeService
import requests as req

SESSION = req.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
# Use certifi for proper TLS on Windows
import certifi
SESSION.verify = certifi.where()


def find_pdf_url(name: str) -> str | None:
    """Search for a school's 募集要項 PDF URL via web search + LLM."""
    query = f"{name} 大学院 修士課程 募集要項 2027 PDF"
    rag = RagSummarizeService()
    web_text = rag.search_with_fallback(query)
    if not web_text or web_text.startswith("未找到"):
        return None

    prompt = f"""以下はWeb検索結果です。この大学院の募集要項PDFのURLを見つけてください。

{web_text[:2000]}

PDFのURL（.pdfで終わるURL）を1つだけ返してください。見つからない場合は "NOT_FOUND" と返してください。
URLのみを返してください。説明は不要です。"""

    resp = chat_model.invoke(prompt)
    text = resp.content if hasattr(resp, "content") else str(resp)
    text = text.strip()

    if "NOT_FOUND" in text:
        return None

    # Extract URL
    url_match = re.search(r'https?://[^\s<>"]+\.pdf', text)
    if url_match:
        return url_match.group(0)
    # Maybe the LLM returned a non-PDF page URL
    url_match = re.search(r'https?://[^\s<>"]+', text)
    if url_match:
        return url_match.group(0)
    return None


def download_and_upload(name: str, pdf_url: str) -> str | None:
    """Download PDF and upload to Supabase Storage. Returns public URL."""
    # Download
    try:
        r = SESSION.get(pdf_url, timeout=30, stream=True)
        if r.status_code != 200:
            print(f"    Download failed: HTTP {r.status_code}")
            return None
        cl = int(r.headers.get("Content-Length", 0))
        if cl > 10 * 1024 * 1024:  # >10MB
            print(f"    PDF too large: {cl / 1024 / 1024:.1f}MB")
            return None
        pdf_bytes = r.content
        print(f"    Downloaded: {len(pdf_bytes) / 1024:.0f}KB")
    except Exception as e:
        print(f"    Download error: {e}")
        return None

    # Upload to Supabase Storage
    try:
        safe_name = name.replace("/", "_").replace(" ", "_")
        path = f"{safe_name}/{safe_name}_2027_募集要項.pdf"
        supabase.storage.from_("pdfs").upload(
            path, pdf_bytes, {"content-type": "application/pdf"}
        )
        public_url = supabase.storage.from_("pdfs").get_public_url(path)
        print(f"    Uploaded: {public_url[:100]}")
        return public_url
    except Exception as e:
        print(f"    Upload error: {e}")
        return None


def main():
    # Get schools with completed enrichment but no pdf_url
    res = supabase.table("graduate_schools").select("id,name").eq("enrichment_status", "completed").or_("pdf_url.is.null,pdf_url.eq.").execute()
    schools = res.data
    print(f"Schools missing PDF: {len(schools)}")

    ok = 0
    for i, s in enumerate(schools):
        name = s["name"]
        print(f"\n[{i+1}/{len(schools)}] {name}")

        # Check if already has pdf_url (avoid re-download)
        check = supabase.table("graduate_schools").select("pdf_url").eq("id", s["id"]).execute()
        if check.data and check.data[0].get("pdf_url"):
            print("    Already has PDF, skip")
            ok += 1
            continue

        pdf_url = find_pdf_url(name)
        if not pdf_url:
            print("    No PDF URL found")
            continue

        print(f"    Found: {pdf_url[:120]}")
        storage_url = download_and_upload(name, pdf_url)
        if storage_url:
            supabase.table("graduate_schools").update({"pdf_url": storage_url}).eq("id", s["id"]).execute()
            ok += 1

        time.sleep(2)  # Rate limit

    print(f"\nDone: {ok}/{len(schools)} PDFs uploaded")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Only search, don't download")
    p.add_argument("--limit", type=int, default=0, help="Limit to N schools")
    args = p.parse_args()

    if args.dry_run or args.limit:
        res = supabase.table("graduate_schools").select("id,name").eq("enrichment_status", "completed").or_("pdf_url.is.null,pdf_url.eq.").execute()
        schools = res.data
        if args.limit:
            schools = schools[:args.limit]
        print(f"Schools missing PDF: {len(schools)} (dry-run={args.dry_run})")
        for i, s in enumerate(schools):
            name = s["name"]
            print(f"\n[{i+1}/{len(schools)}] {name}")
            pdf_url = find_pdf_url(name)
            if pdf_url:
                print(f"  -> {pdf_url[:150]}")
                if not args.dry_run:
                    storage_url = download_and_upload(name, pdf_url)
                    if storage_url:
                        supabase.table("graduate_schools").update({"pdf_url": storage_url}).eq("id", s["id"]).execute()
            else:
                print("  -> NOT FOUND")
            time.sleep(2)
    else:
        main()
