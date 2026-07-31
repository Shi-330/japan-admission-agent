"""
KAKEN professor name validation.
Cross-checks professor names against Japan's national research database (KAKEN).

Usage:
  venv/Scripts/python.exe scripts/validate_professor.py --name "辻健"
  venv/Scripts/python.exe scripts/validate_professor.py --name "清野纯一"
  venv/Scripts/python.exe scripts/validate_professor.py --batch  # validate all in professors.json

KAKEN search URL: https://kaken.nii.ac.jp/search/?q={name}
"""
import os, sys, json, time, io, re
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import requests
from dotenv import load_dotenv
load_dotenv()

# ORCID Public API — free, REST-based, global coverage
# https://info.orcid.org/documentation/api-tutorials/api-tutorial-searching-the-orcid-registry/
ORCID_SEARCH = "https://pub.orcid.org/v3.0/search/"
ORCID_HEADERS = {"Accept": "application/json"}
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "kaken_cache.json")
PROFESSOR_DB = os.path.join(os.path.dirname(__file__), "..", "data", "professors.json")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "JapanAdmissionAgent/1.0 (academic research; contact@agent.shi330.xyz)"
})


def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def search_orcid(name: str) -> dict | None:
    """Search ORCID for a professor by name. Returns {found, orcid_id, name, url, keywords} or None."""
    cache = load_cache()
    if name in cache:
        return cache[name]

    try:
        # Build ORCID query from name parts
        parts = name.strip().split()
        query_parts = []
        if len(parts) >= 2:
            query_parts.append(f"family-name:{parts[0]}")
            query_parts.append(f"given-names:{parts[1]}")
        else:
            query_parts.append(f"family-name:{name}")
        query = " AND ".join(query_parts)
        url = f"{ORCID_SEARCH}?q={requests.utils.quote(query)}&rows=3"
        r = SESSION.get(url, headers=ORCID_HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()
        results = data.get("result", [])
        if results:
            first = results[0]
            orcid_id = first.get("orcid-identifier", {}).get("path", "")
            result = {
                "found": True,
                "orcid_id": orcid_id,
                "name_jp": name,
                "url": f"https://orcid.org{orcid_id}" if orcid_id else "",
                "source": "ORCID",
            }
        else:
            result = {"found": False, "name_jp": name, "source": "ORCID"}

        cache[name] = result
        save_cache(cache)
        return result

    except Exception as e:
        return {"found": False, "error": str(e)}


def check_url(url: str) -> bool:
    """Send HEAD request. Returns True if URL is alive (200 OK)."""
    if not url: return False
    try:
        r = SESSION.head(url, timeout=10, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def get_kaken_link(name_jp: str) -> str | None:
    """Build a KAKEN researcher page URL from name. Returns URL or None."""
    # KAKEN search URL for Japanese names
    return f"https://kaken.nii.ac.jp/ja/search/?q={requests.utils.quote(name_jp)}"


def validate_professors_batch():
    """Validate all professors in professors.json against KAKEN."""
    with open(PROFESSOR_DB, "r", encoding="utf-8") as f:
        profs = json.load(f)

    for p in profs:
        name = p["name_jp"]
        # ORCID validation
        result = search_orcid(name)
        p["orcid_validated"] = result["found"] if result else False
        p["orcid_id"] = result.get("orcid_id", "") if result else ""
        p["orcid_url"] = result.get("url", "") if result else ""

        # URL liveness check
        lab_url = p.get("lab_url", "")
        url_alive = check_url(lab_url) if lab_url else False

        # Build sources: permanent IDs first, lab_url last
        sources = []
        if p.get("orcid_url"): sources.append(p["orcid_url"])
        sources.append(get_kaken_link(name))
        if url_alive and lab_url: sources.append(lab_url)
        p["sources"] = [s for s in sources if s]

        # Confidence
        if p["orcid_validated"] and url_alive:
            p["confidence"] = "verified"
        elif p["orcid_validated"]:
            p["confidence"] = "orcid_only"
        else:
            p["confidence"] = "unverified"

        status = "verified" if p["orcid_validated"] else "not_found"
        print(f"  {name:20s} -> {status} | URL: {'alive' if url_alive else 'dead'} | confidence: {p['confidence']}")

    with open(PROFESSOR_DB, "w", encoding="utf-8") as f:
        json.dump(profs, f, ensure_ascii=False, indent=2)
    print(f"\nValidated {len(profs)} professors. Updated professors.json.")


if __name__ == "__main__":
    if "--batch" in sys.argv:
        validate_professors_batch()
    elif "--name" in sys.argv:
        idx = sys.argv.index("--name")
        name = sys.argv[idx + 1]
        result = search_orcid(name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(__doc__)
