"""
Build a professor name validation database by scraping university faculty pages.
Stores validated names in a JSON file for use by enrichment + draft pipelines.

Usage:
  venv/Scripts/python.exe scripts/build_professor_db.py          # scrape all
  venv/Scripts/python.exe scripts/build_professor_db.py --limit 10  # test first 10
"""

import os, sys, re, json, time, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from supabase import create_client
import requests

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; JapanAdmissionAgent/1.0)"})

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "professor_whitelist.json")

def scrape_faculty_page(url: str) -> list[str]:
    """Scrape a faculty list page for professor names. Returns list of names."""
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code != 200: return []
        text = r.text
        # Japanese name patterns: LastName FirstName (both kanji)
        # Match patterns like: 辻健, 山本希, 清野純史
        names = set()
        patterns = [
            r'([一-龯]{2,4})\s*([一-龯]{1,4})',  # Full name kanji
            r'([A-Z][a-z]+)\s+([A-Z][a-z]+)',    # Latin name
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                full = f"{m.group(1)} {m.group(2)}" if pat.startswith(r'([A-Z]') else f"{m.group(1)}{m.group(2)}"
                names.add(full)
        return list(names)
    except Exception as e:
        print(f"  Scrape failed for {url}: {e}")
        return []

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

    # Get graduate schools with websites
    r = supabase.table("graduate_schools").select("id,name_jp,website").execute()
    schools = [s for s in r.data if s.get("website")]
    if limit: schools = schools[:limit]

    print(f"Processing {len(schools)} graduate schools with websites...")

    whitelist = {}
    for i, s in enumerate(schools):
        url = s["website"]
        if not url.startswith("http"): continue

        print(f"[{i+1}/{len(schools)}] {s['name_jp'][:40]}")
        names = scrape_faculty_page(url)
        if names:
            whitelist[s["name_jp"]] = names
            print(f"  -> {len(names)} names found")
        time.sleep(2)  # Polite delay

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(whitelist, f, ensure_ascii=False, indent=2)

    total_names = sum(len(v) for v in whitelist.values())
    print(f"\nSaved: {len(whitelist)} schools, {total_names} professor names to {OUTPUT}")


def validate():
    """Usage: python scripts/build_professor_db.py --validate "清野純史" "京都大学 工学研究科" """
    idx = sys.argv.index("--validate")
    name = sys.argv[idx + 1]
    school = sys.argv[idx + 2] if len(sys.argv) > idx + 2 else ""

    try:
        with open(OUTPUT, "r", encoding="utf-8") as f:
            whitelist = json.load(f)
    except FileNotFoundError:
        print("No whitelist found. Run without --validate first.")
        return

    if school:
        names = whitelist.get(school, [])
        match = [n for n in names if name in n or n in name]
        print(f"School: {school}")
        print(f"Query: {name}")
        print(f"Match: {match if match else 'NOT FOUND'}")
    else:
        for school, names in whitelist.items():
            if any(name in n or n in name for n in names):
                print(f"Found in {school}: {[n for n in names if name in n or n in name]}")


if __name__ == "__main__":
    if "--validate" in sys.argv:
        validate()
    else:
        main()
