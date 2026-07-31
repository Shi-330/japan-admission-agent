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
    """Crawl one URL with requests + BeautifulSoup. Zero-cost, no API key needed."""
    if dry_run:
        print(f"  [DRY RUN] Would crawl: {name_jp} -> {url}")
        return []

    try:
        import requests as req
        resp = req.get(url, headers={"User-Agent": "JapanAdmissionAgent/1.0"}, timeout=30)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return []

        # Simple HTML extraction — look for professor patterns
        text = resp.text
        profs = extract_professors_from_html(text, name_jp, url)

        # Save raw HTML for inspection
        os.makedirs(CRAWL_DIR, exist_ok=True)
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', name_jp)[:40]
        with open(os.path.join(CRAWL_DIR, f"{safe_name}.html"), "w", encoding="utf-8") as f:
            f.write(text)

        print(f"  Crawled {name_jp}: {len(text)} bytes, {len(profs)} professors found")
        return profs

    except Exception as e:
        print(f"  Crawl failed: {e}")
        return []


def extract_professors_from_html(html, school_name, source_url):
    """Parse professor info from raw HTML. Returns list of dicts."""
    from html.parser import HTMLParser
    profs = []
    titles = ["教授", "准教授", "助教", "講師", "Professor", "Associate Professor",
              "名誉教授", "特任教授", "客員教授"]
    # Strip HTML tags for text extraction
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        for title in titles:
            if title in line:
                m = re.search(r'([一-龯]{2,8})\s*(?:（[^）]*）)?\s*' + re.escape(title), line)
                if m:
                    name = m.group(1).strip()
                    if 2 <= len(name) <= 8 and re.match(r'^[一-龯]+$', name):
                        profs.append({
                            "name_jp": name,
                            "university": school_name.split(" ")[0] if " " in school_name else school_name,
                            "department": school_name,
                            "title": title,
                            "lab_url": source_url,
                            "research_keywords": [],
                            "recent_papers": [],
                            "notes": f"Web crawl ({time.strftime('%Y-%m-%d')})",
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
