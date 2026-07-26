"""
Seed script: Tokyo University seismology academic hierarchy.

Usage:
  python seed_academic.py          # seed 1 case
  python seed_academic.py --dry-run  # print SQL without executing

This populates the 4 tables (universities → graduate_schools → programs → documents)
for one complete path: 东京大学 → 理学系研究科 → 地球惑星科学専攻.

The flat "schools" table is rebuilt from programs as a search cache (backward compat).
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env")
    sys.exit(1)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Tokyo University Seismology ──────────────────────────────────────

UNIVERSITY = {
    "name": "东京大学",
    "name_jp": "東京大学",
    "type": "国立",
    "location": "东京都文京区",
    "website": "https://www.u-tokyo.ac.jp/ja/index.html",
}

GRAD_SCHOOL = {
    "name": "理学系研究科",
    "name_jp": "理学系研究科",
    "website": "https://www.s.u-tokyo.ac.jp/ja/",
    "exam_type": "外国人特别选拔",
    "english": {"type": "TOEFL", "min_score": 80, "requirement": "required",
                "note": "理学系研究科全専攻共通。TOEIC不可。免除：英語圏大学出身者",
                "source": "理学系研究科 修士課程 募集要項 2027"},
    "jlpt": None,   # 各専攻で異なるため、研究科レベルでは規定せず
    "notes": "理学系研究科全専攻共通でTOEFL必須。専攻別の専門科目筆記試験あり。地震学希望者は地震研究所（ERI）の教授も本研究科経由で受け入れ。",
}

PROGRAM = {
    "name": "地球惑星科学専攻",
    "name_jp": "地球惑星科学専攻",
    "degree": "修士",
    "capacity": 40,
    # null = inherit from graduate_school (TOEFL 80 required)
    "english": None,
    # override: this program specifically recommends N2
    "jlpt": {"level": "N2", "requirement": "recommended",
             "note": "日本語能力を有することが望ましい。N2未満でも教授内諾があれば入学許可例あり",
             "source": "理学系研究科 地球惑星科学専攻 入試情報 2027"},
    "research_areas": [
        "地震学", "火山学", "地球物理学", "地質学", "気象学",
        "地球化学", "宇宙惑星科学", "固体地球科学"
    ],
    "exam_periods": [
        {"name": "夏季入试", "month": 7, "note": "一般选拔"},
        {"name": "冬季入试", "month": 2, "note": "外国人特别选拔（推荐）"}
    ],
    "application_deadlines": [
        {"year": "2027", "type": "夏季出願", "date": "2026-06-15"},
        {"year": "2027", "type": "冬季出願", "date": "2026-11-15"},
    ],
    "url": "https://www.s.u-tokyo.ac.jp/ja/admission/",
    "notes": "地球惑星科学専攻是理学系研究科下最大的专攻之一，覆盖固体地球、大气海洋、宇宙行星三大方向。地震学方向推荐联系地震研究所教授。研究生制度（けんきゅうせい）也接受申请。",
}

DOCUMENTS = [
    {
        "doc_type": "募集要項",
        "year_tag": "2027",
        "title": "令和9年度 理学系研究科 修士課程 学生募集要項",
        "file_url": "https://www.s.u-tokyo.ac.jp/ja/admission/",
        "valid_from": "2026-04-01",
        "valid_until": "2027-03-31",
        "is_current": True,
    },
    {
        "doc_type": "募集要項",
        "year_tag": "2026",
        "title": "令和8年度 理学系研究科 修士課程 学生募集要項",
        "file_url": "https://www.s.u-tokyo.ac.jp/ja/admission/",
        "valid_from": "2025-04-01",
        "valid_until": "2026-03-31",
        "is_current": False,
    },
    {
        "doc_type": "入試日程",
        "year_tag": "2027",
        "title": "地球惑星科学専攻 修士課程 入試日程",
        "file_url": "https://www.eps.s.u-tokyo.ac.jp/admission/",
        "valid_from": "2026-05-01",
        "valid_until": "2027-03-31",
        "is_current": True,
    },
    {
        "doc_type": "過去問",
        "year_tag": "2023-2025",
        "title": "地球惑星科学専攻 大学院入試 過去問題（3年分）",
        "file_url": "https://www.eps.s.u-tokyo.ac.jp/admission/past-exams/",
        "valid_from": None,
        "valid_until": None,
        "is_current": True,
    },
]

# ── Execute ───────────────────────────────────────────────────────────

def run(dry_run=False):
    if dry_run:
        print("=== DRY RUN (no writes) ===\n")

    # 1. Run migration
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_academic_hierarchy.sql")
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()
    if dry_run:
        print(f"[SQL] Execute migration: {migration_path}")
    else:
        supabase.rpc("exec_sql", {"sql": sql}).execute()  # type: ignore
        print("Migration: tables created (if not exist)")

    # 2. Upsert university
    if dry_run:
        print(f"[UPSERT] universities: {UNIVERSITY['name']}")
    else:
        result = supabase.table("universities").upsert(UNIVERSITY, on_conflict="name").execute()
        uni_id = result.data[0]["id"]
        print(f"University: {UNIVERSITY['name']} (id={uni_id[:8]}...)")

    # 3. Upsert graduate school
    gs = {**GRAD_SCHOOL, "university_id": uni_id}
    if dry_run:
        print(f"[UPSERT] graduate_schools: {GRAD_SCHOOL['name']}")
    else:
        result = supabase.table("graduate_schools").upsert(gs, on_conflict="university_id,name").execute()
        gs_id = result.data[0]["id"]
        print(f"  Graduate School: {GRAD_SCHOOL['name']} (id={gs_id[:8]}...)")

    # 4. Upsert program
    prog = {**PROGRAM, "graduate_school_id": gs_id}
    # JSON fields need explicit serialization for Supabase
    for field in ("english", "jlpt", "research_areas", "exam_periods", "application_deadlines"):
        if isinstance(prog.get(field), (dict, list)):
            prog[field] = json.dumps(prog[field], ensure_ascii=False)
    if dry_run:
        print(f"[UPSERT] programs: {PROGRAM['name']}")
    else:
        result = supabase.table("programs").upsert(prog, on_conflict="graduate_school_id,name").execute()
        prog_id = result.data[0]["id"]
        print(f"    Program: {PROGRAM['name']} (id={prog_id[:8]}...)")

    # 5. Upsert documents
    for doc in DOCUMENTS:
        doc_data = {**doc, "program_id": prog_id}
        if dry_run:
            print(f"[UPSERT] documents: {doc['doc_type']} ({doc['year_tag']})")
        else:
            supabase.table("program_documents").upsert(
                doc_data, on_conflict="program_id,doc_type,year_tag"
            ).execute()
            print(f"      Doc: {doc['doc_type']} {doc['year_tag']} — {doc['title'][:40]}...")

    # 6. Rebuild flat schools cache for backward compat
    if not dry_run:
        print("\nRebuilding flat schools cache...")
        _sync_to_schools_table()
        print("Done.")

    if dry_run:
        print("\n=== Run without --dry-run to write ===")


def _sync_to_schools_table():
    """Rebuild the flat 'schools' table from the hierarchy for backward compat.

    Each program becomes one school row. Existing search endpoints read 'schools'.
    """
    print("  (clearing old schools...)")
    supabase.table("schools").delete().neq("name", "__RESERVED__").execute()

    pk = supabase.table("programs").select("*").execute()
    for p in pk.data:
        gs = supabase.table("graduate_schools").select("*, universities(*)").eq("id", p["graduate_school_id"]).execute()
        gs_data = gs.data[0] if gs.data else {}
        uni = gs_data.get("universities") or {}

        school_name = f"{uni.get('name', '')} {gs_data.get('name', '')}"
        school = {
            "name": school_name,
            "degree": p.get("degree", "修士"),
            "majors": json.loads(p.get("research_areas", "[]")) if isinstance(p.get("research_areas"), str) else (p.get("research_areas") or []),
            "tags": [p.get("name", ""), uni.get("type", ""), gs_data.get("exam_type", "")],
            "exam": json.dumps(p.get("exam_periods", []), ensure_ascii=False) if p.get("exam_periods") else "",
            "notes": p.get("notes", ""),
            "jlpt_min": (json.loads(p.get("jlpt")) if isinstance(p.get("jlpt"), str) else (p.get("jlpt") or {})).get("level", ""),
            "gpa_min": 0.0,
            "english_req": json.loads(p.get("english")) if isinstance(p.get("english"), str) else (p.get("english") or {}),
            "deadlines": json.loads(p.get("application_deadlines", "[]")) if isinstance(p.get("application_deadlines"), str) else (p.get("application_deadlines") or []),
            "source": "hierarchy",
            "verified": True,
        }
        supabase.table("schools").upsert(school, on_conflict="name").execute()
    print(f"  Synced {len(pk.data)} program(s) to schools cache.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
