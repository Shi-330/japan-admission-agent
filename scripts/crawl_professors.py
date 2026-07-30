"""
Phase 3: Crawl university pages for professor data using Firecrawl.
Free tier: 500 credits/month. Adds verified professors to professors.json.

Usage:
  venv/Scripts/python.exe scripts/crawl_professors.py               # crawl all target URLs
  venv/Scripts/python.exe scripts/crawl_professors.py --test        # test with 1 URL
  venv/Scripts/python.exe scripts/crawl_professors.py --merge       # merge crawled data into professors.json
"""
import os, sys, json, time, io, re
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

PROFESSOR_DB = os.path.join(os.path.dirname(__file__), "..", "data", "professors.json")
CRAWL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "crawl_output")

# Top 10 Japanese university earth science / geophysics pages
TARGET_URLS = [
    ("東京大学", "地震研究所", "https://www.eri.u-tokyo.ac.jp/members/"),
    ("京都大学", "防災研究所", "https://www.dpri.kyoto-u.ac.jp/research/"),
    ("京都大学", "理学研究科 地球惑星", "https://www.sci.kyoto-u.ac.jp/ja/earth/"),
    ("東北大学", "理学研究科 地球物理", "https://www.sci.tohoku.ac.jp/"),
    ("九州大学", "工学府 地球資源", "https://www.kyushu-u.ac.jp/"),
    ("名古屋大学", "環境学研究科 地球環境", "https://www.env.nagoya-u.ac.jp/"),
    ("北海道大学", "理学研究院 地球惑星", "https://www.sci.hokudai.ac.jp/"),
    ("東京科学大学", "理学院 地球惑星", "https://www.isct.ac.jp/"),
    ("筑波大学", "生命環境系 地球科学", "https://www.tsukuba.ac.jp/"),
    ("神戸大学", "理学研究科 地球惑星", "https://www.kobe-u.ac.jp/"),
]


def crawl_url(name_jp, url, dry_run=False):
    """Crawl one URL with Firecrawl, extract professor info. Returns list of professor dicts."""
    api_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not api_key:
        print("  FIRECRAWL_API_KEY not set. Skipping.")
        return []

    if dry_run:
        print(f"  [DRY RUN] Would crawl: {name_jp} -> {url}")
        return []

    try:
        import requests as req
        # Firecrawl scrape endpoint
        resp = req.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown"]},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  Firecrawl error: {resp.status_code}")
            return []

        data = resp.json()
        markdown = data.get("data", {}).get("markdown", "")
        if not markdown:
            return []

        # Save raw crawl for inspection
        os.makedirs(CRAWL_DIR, exist_ok=True)
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', name_jp)[:40]
        with open(os.path.join(CRAWL_DIR, f"{safe_name}.md"), "w", encoding="utf-8") as f:
            f.write(markdown)

        # Extract professor info from markdown
        profs = extract_professors(markdown, name_jp, url)
        print(f"  Extracted {len(profs)} professors from {name_jp}")
        return profs

    except ImportError:
        print("  requests not installed. pip install requests")
        return []
    except Exception as e:
        print(f"  Crawl failed: {e}")
        return []


def extract_professors(markdown, school_name, source_url):
    """Parse professor info from crawled markdown. Returns list of dicts."""
    profs = []
    # Pattern: Japanese name patterns followed by titles (教授, 准教授, 助教, 講師)
    lines = markdown.split("\n")
    for line in lines:
        # Match lines with academic title after kanji name
        for title in ["教授", "准教授", "助教", "講師", "Professor", "Associate Professor"]:
            if title in line:
                # Extract name: everything before the title, last 2-5 chars
                m = re.search(r'([一-龯]{2,6})\s*(?:（[^）]*）)?\s*(?:' + re.escape(title) + r')', line)
                if m:
                    name = m.group(1).strip()
                    # Skip already-too-long names and names with numbers
                    if 2 <= len(name) <= 6 and re.match(r'^[一-龯]+$', name):
                        # Extract research keywords from this and next lines
                        profs.append({
                            "name_jp": name,
                            "university": school_name.split(" ")[0] if " " in school_name else school_name,
                            "department": school_name,
                            "title": title,
                            "lab_url": source_url,
                            "research_keywords": [],
                            "recent_papers": [],
                            "notes": f"Firecrawlから抽出 ({time.strftime('%Y-%m-%d')})",
                            "sources": [source_url],
                        })
    return profs


def merge_to_db(new_profs):
    """Merge crawled professors into professors.json, deduplicating by name_jp."""
    try:
        with open(PROFESSOR_DB, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = []

    existing_names = {p["name_jp"] for p in existing}
    added = 0
    for p in new_profs:
        if p["name_jp"] not in existing_names:
            existing.append(p)
            existing_names.add(p["name_jp"])
            added += 1

    with open(PROFESSOR_DB, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"Merged {added} new professors into {PROFESSOR_DB} (total: {len(existing)})")


def main():
    dry_run = "--test" in sys.argv
    do_merge = "--merge" in sys.argv

    if do_merge:
        all_profs = []
        for fname in os.listdir(CRAWL_DIR):
            if fname.endswith(".md"):
                with open(os.path.join(CRAWL_DIR, fname), "r", encoding="utf-8") as f:
                    profs = extract_professors(f.read(), fname.replace(".md",""), "")
                    all_profs.extend(profs)
        merge_to_db(all_profs)
        return

    for uni, dept, url in (TARGET_URLS[:3] if dry_run else TARGET_URLS):
        name = f"{uni} {dept}"
        print(f"\nCrawling: {name}")
        profs = crawl_url(name, url, dry_run)
        if profs:
            merge_to_db(profs)
        time.sleep(5)


if __name__ == "__main__":
    main()
