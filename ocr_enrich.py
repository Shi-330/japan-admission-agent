"""
Local OCR + table extraction for Japanese 募集要項 PDFs.
Runs on dev machine (not 2GB server). Results stored in Supabase.

Dependencies (install once):
  pip install pytesseract pdf2image camelot-py[cv] pillow
  Download Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
  Install Japanese language data: tesseract-lang/jpn

Usage:
  python ocr_enrich.py --url "https://...pdf" --school "东京大学 理学系研究科"
  python ocr_enrich.py --file "path/to/募集要項.pdf" --school "京都大学 理学研究科"
  python ocr_enrich.py --batch           # process all schools with pdf_url set
"""
import os, sys, json, re, io, tempfile
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
from model.factory import chat_model


def download_pdf(url: str) -> bytes:
    """Download PDF from URL, return bytes. Raises on failure."""
    import requests
    r = requests.get(url, timeout=30, stream=True,
                     headers={"User-Agent": "Mozilla/5.0"},
                     verify=False)
    r.raise_for_status()
    cl = int(r.headers.get("Content-Length", 0))
    if cl > 10 * 1024 * 1024:
        raise ValueError(f"PDF too large: {cl} bytes (max 10MB)")
    return r.content


def ocr_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF via OCR. Falls back to direct text extraction if possible."""
    text = ""
    # Try direct text extraction first (PyPDF2)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t: text += t + "\n"
    except Exception:
        pass

    # If direct extraction got enough text, skip OCR
    if len(text.strip()) > 500:
        return text.strip()

    # OCR via Tesseract (Japanese)
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        images = convert_from_bytes(pdf_bytes, dpi=200)
        for img in images:
            t = pytesseract.image_to_string(img, lang="jpn")
            if t: text += t + "\n"
    except Exception as e:
        print(f"  OCR warning: {e}")
    return text.strip()


def extract_tables(pdf_bytes: bytes) -> list[list]:
    """Extract tables from PDF using camelot-py."""
    try:
        import camelot
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            f.flush()
            tables = camelot.read_pdf(f.name, pages="all", flavor="lattice")
        os.unlink(f.name)
        result = []
        for t in tables:
            result.append(t.df.values.tolist())
        return result
    except Exception as e:
        print(f"  Table extraction skipped: {e}")
        return []


def llm_extract(text: str, tables: list) -> dict:
    """Use LLM to extract structured admission requirements from OCR text + tables."""
    table_text = ""
    for i, t in enumerate(tables):
        table_text += f"\n【表格{i+1}】\n"
        for row in t[:20]:  # cap rows
            table_text += " | ".join(str(c) for c in row) + "\n"

    prompt = f"""以下は日本大学院の募集要項PDFから抽出したテキストです。修士課程の入試情報をJSONで抽出してください。

【本文（先頭2000字）】
{text[:2000]}

{table_text}

以下のJSON形式で返してください（不明な項目はnull、markdownコードブロック禁止）：
{{"jlpt_min":"N1/N2/...","english_req":{{"type":"TOEFL/TOEIC/IELTS","min_score":数値,"required":true/false}},"exam":"筆記+面接など","deadlines":[{{"name":"出願","date":"YYYY-MM-DD"}}],"notes":"備考・特徴"}}
"""
    resp = chat_model.invoke(prompt)
    text_resp = resp.content if hasattr(resp, "content") else str(resp)
    m = re.search(r'\{.*\}', text_resp, re.DOTALL)
    if not m:
        print("  LLM returned no JSON")
        return {}
    return json.loads(m.group(0))


def enrich_from_pdf(school_name: str, pdf_url: str):
    """Full pipeline: download -> OCR -> tables -> LLM -> Supabase."""
    print(f"\n  Processing: {school_name}")
    print(f"  PDF: {pdf_url[:100]}")

    # 1. Download
    print("  [1/4] Downloading PDF...")
    pdf_bytes = download_pdf(pdf_url)
    print(f"    Downloaded {len(pdf_bytes)} bytes")

    # 2. OCR
    print("  [2/4] OCR + text extraction...")
    text = ocr_pdf(pdf_bytes)
    print(f"    Extracted {len(text)} chars of text")

    # 3. Tables
    print("  [3/4] Table extraction...")
    tables = extract_tables(pdf_bytes)
    print(f"    Found {len(tables)} tables")

    # 4. LLM
    print("  [4/4] LLM structured extraction...")
    data = llm_extract(text, tables)
    if not data:
        print("    FAIL: no data extracted")
        return False

    # 5. Update Supabase
    update = {"enrichment_status": "completed", "verified": True}
    if data.get("jlpt_min"): update["jlpt_min"] = data["jlpt_min"]
    if data.get("english_req"): update["english_req"] = json.dumps(data["english_req"], ensure_ascii=False)
    if data.get("exam"): update["exam"] = data["exam"]
    if data.get("deadlines"): update["deadlines"] = json.dumps(data["deadlines"], ensure_ascii=False)
    if data.get("notes"): update["notes"] = data["notes"]

    supabase.table("schools").update(update).eq("name", school_name).execute()
    print(f"    OK: {json.dumps({k:v for k,v in update.items() if k != 'enrichment_status'}, ensure_ascii=False)[:150]}")
    return True


def run_batch():
    """Process all schools that have a pdf_url set (from previous enrichment)."""
    res = supabase.table("schools").select("name,pdf_url").not_.is_("pdf_url", "null").limit(20).execute()
    schools = [(r["name"], r["pdf_url"]) for r in res.data if r.get("pdf_url") and "http" in str(r["pdf_url"])]
    if not schools:
        print("No schools with PDF URLs found. Run enrichment first to populate pdf_url.")
        return
    print(f"Found {len(schools)} schools with PDF URLs")
    ok = 0
    for name, url in schools:
        try:
            if enrich_from_pdf(name, url):
                ok += 1
        except Exception as e:
            print(f"    FAIL: {e}")
    print(f"\nDone: {ok}/{len(schools)} enriched from PDF")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="PDF URL")
    ap.add_argument("--file", help="Local PDF file path")
    ap.add_argument("--school", help="School name (required for --url/--file)")
    ap.add_argument("--batch", action="store_true", help="Process all schools with pdf_url")
    args = ap.parse_args()

    if args.batch:
        run_batch()
    elif args.url and args.school:
        enrich_from_pdf(args.school, args.url)
    elif args.file and args.school:
        with open(args.file, "rb") as f:
            pdf_bytes = f.read()
        text = ocr_pdf(pdf_bytes)
        tables = extract_tables(pdf_bytes)
        data = llm_extract(text, tables)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        ap.print_help()
