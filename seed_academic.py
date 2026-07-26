"""
Seed academic hierarchy programs. Idempotent — safe to re-run.

Usage:
  python seed_academic.py           # seed all programs
  python seed_academic.py --dry-run  # preview
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env"); sys.exit(1)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _format_exam(periods) -> str:
    if isinstance(periods, str): periods = json.loads(periods)
    if not periods: return ""
    parts = [f"{p.get('name','')}({p.get('month','')}月)" if p.get('month') else p['name'] for p in periods]
    return " + ".join(parts)


ENTRIES = [
    # ═══ 東京大学 理学系研究科 地球惑星科学専攻 ═══
    {
        "university": "东京大学",
        "graduate_school": "理学系研究科",
        "gs": {
            "exam_type": "外国人特别选拔",
            "english": {"type": "TOEFL", "min_score": 80, "requirement": "required",
                        "note": "理学系研究科全専攻共通。TOEIC不可。",
                        "source": "理学系研究科 修士課程 募集要項 2027"},
            "jlpt": None,
            "notes": "地震研究所（ERI）教授也通过本研究科招收学生。",
        },
        "program": {
            "name": "地球惑星科学専攻", "name_jp": "地球惑星科学専攻",
            "degree": "修士", "capacity": 40,
            "english": None,  # inherit from GS
            "jlpt": {"level": "N2", "requirement": "recommended",
                     "note": "教授内諾あればN2未満でも可",
                     "source": "地球惑星科学専攻 入試情報 2027"},
            "research_areas": ["地震学", "火山学", "地球物理学", "地質学", "気象学",
                               "地球化学", "宇宙惑星科学", "固体地球科学"],
            "exam_periods": [{"name": "夏季入试", "month": 7}, {"name": "冬季入试", "month": 2}],
            "application_deadlines": [
                {"year": "2027", "type": "夏季出願", "date": "2026-06-15"},
                {"year": "2027", "type": "冬季出願", "date": "2026-11-15"}],
            "url": "https://www.s.u-tokyo.ac.jp/ja/admission/",
            "notes": "理学系研究科最大専攻之一。地震学方向推荐联系地震研究所教授。",
        },
        "documents": [
            {"doc_type": "募集要項", "year_tag": "2027",
             "title": "理学系研究科 修士課程 学生募集要項（令和9年度）",
             "file_url": "https://www.s.u-tokyo.ac.jp/ja/admission/",
             "valid_from": "2026-04-01", "valid_until": "2027-03-31", "is_current": True},
            {"doc_type": "入試日程", "year_tag": "2027",
             "title": "地球惑星科学専攻 修士課程 入試日程",
             "file_url": "https://www.eps.s.u-tokyo.ac.jp/admission/",
             "valid_from": "2026-05-01", "valid_until": "2027-03-31", "is_current": True},
        ],
    },

    # ═══ 京都大学 理学研究科 地球惑星科学専攻 ═══
    {
        "university": "京都大学",
        "graduate_school": "理学研究科",
        "gs": {
            "exam_type": "外国人特别选拔",
            "english": {"type": "TOEFL", "min_score": 79, "requirement": "required",
                        "source": "理学研究科 修士課程 募集要項 2027"},
            "jlpt": None,
        },
        "program": {
            "name": "地球惑星科学専攻", "name_jp": "地球惑星科学専攻",
            "degree": "修士", "capacity": 35,
            "english": None,
            "jlpt": {"level": "N2", "requirement": "recommended",
                     "note": "日本語能力を有することが望ましい",
                     "source": "理学研究科 入試情報"},
            "research_areas": ["地震学", "火山学", "地球物理学", "地質学", "気象学", "地球化学"],
            "exam_periods": [{"name": "夏季入试", "month": 8}, {"name": "冬季入试", "month": 2}],
            "application_deadlines": [
                {"year": "2027", "type": "夏季出願", "date": "2026-07-01"},
                {"year": "2027", "type": "冬季出願", "date": "2026-12-01"}],
            "url": "https://www.sci.kyoto-u.ac.jp/ja/admission/",
            "notes": "京大理学研究科。防災研究所（DPRI）教授也通过本研究科招收学生。",
        },
    },

    # ═══ 東北大学 理学研究科 地球物理学専攻 ═══
    {
        "university": "東北大学",
        "graduate_school": "理学研究科",
        "gs": {
            "exam_type": "外国人特别选拔",
            "english": {"type": "TOEFL", "min_score": 79, "requirement": "required",
                        "source": "理学研究科 募集要項 2027"},
            "jlpt": None,
        },
        "program": {
            "name": "地球物理学専攻", "name_jp": "地球物理学専攻",
            "degree": "修士", "capacity": 30,
            "english": None,
            "jlpt": {"level": "N2", "requirement": "recommended",
                     "source": "理学研究科 入試情報"},
            "research_areas": ["地震学", "地球物理学", "固体地球科学", "海洋物理学", "超高層物理学"],
            "exam_periods": [{"name": "夏季入试", "month": 8}, {"name": "冬季入试", "month": 2}],
            "application_deadlines": [
                {"year": "2027", "type": "夏季出願", "date": "2026-06-20"},
                {"year": "2027", "type": "冬季出願", "date": "2026-12-05"}],
            "url": "https://www.sci.tohoku.ac.jp/admission/",
            "notes": "東北大学是日本地震学研究重镇。2011年東日本大震災後研究资源大幅增加。",
        },
    },

    # ═══ 九州大学 理学府 地球惑星科学専攻 ═══
    {
        "university": "九州大学",
        "graduate_school": "理学府",
        "gs": {
            "exam_type": "外国人特别选拔",
            "english": {"type": "TOEFL", "min_score": 72, "requirement": "required",
                        "source": "理学府 募集要項 2027"},
            "jlpt": None,
        },
        "program": {
            "name": "地球惑星科学専攻", "name_jp": "地球惑星科学専攻",
            "degree": "修士", "capacity": 30,
            "english": None,
            "jlpt": {"level": "N2", "requirement": "recommended",
                     "source": "理学府 入試情報"},
            "research_areas": ["地震学", "火山学", "地球物理学", "地質学", "地球化学"],
            "exam_periods": [{"name": "夏季入试", "month": 8}, {"name": "冬季入试", "month": 2}],
            "application_deadlines": [
                {"year": "2027", "type": "夏季出願", "date": "2026-07-01"},
                {"year": "2027", "type": "冬季出願", "date": "2026-12-01"}],
            "url": "https://www.sci.kyushu-u.ac.jp/admission/",
            "notes": "九州地区最大理学研究据点。火山学研究日本领先（阿蘇・桜島近接）。",
        },
    },

    # ═══ 北海道大学 理学院 地球惑星科学専攻 ═══
    {
        "university": "北海道大学",
        "graduate_school": "理学院",
        "gs": {
            "exam_type": "外国人特别选拔",
            "english": {"type": "TOEFL", "min_score": 72, "requirement": "required",
                        "source": "理学院 募集要項 2027"},
            "jlpt": None,
        },
        "program": {
            "name": "地球惑星科学専攻", "name_jp": "地球惑星科学専攻",
            "degree": "修士", "capacity": 35,
            "english": None,
            "jlpt": {"level": "N2", "requirement": "recommended",
                     "source": "理学院 入試情報"},
            "research_areas": ["地震学", "火山学", "地球物理学", "気象学", "海洋科学"],
            "exam_periods": [{"name": "夏季入试", "month": 8}, {"name": "冬季入试", "month": 2}],
            "application_deadlines": [
                {"year": "2027", "type": "夏季出願", "date": "2026-07-10"},
                {"year": "2027", "type": "冬季出願", "date": "2026-12-10"}],
            "url": "https://www.sci.hokudai.ac.jp/admission/",
            "notes": "北海道大。有珠山・十勝岳等活火山近接，火山地震学野外研究便利。",
        },
    },

    # ═══ 名古屋大学 環境学研究科 地球環境科学専攻 ═══
    {
        "university": "名古屋大学",
        "graduate_school": "環境学研究科",
        "gs": {
            "exam_type": "外国人特别选拔",
            "english": {"type": "TOEFL", "min_score": 72, "requirement": "required",
                        "source": "環境学研究科 募集要項 2027"},
            "jlpt": None,
        },
        "program": {
            "name": "地球環境科学専攻", "name_jp": "地球環境科学専攻",
            "degree": "修士", "capacity": 25,
            "english": None,
            "jlpt": {"level": "N2", "requirement": "recommended",
                     "source": "環境学研究科 入試情報"},
            "research_areas": ["地震学", "地球物理学", "地質学", "気候変動", "自然災害科学"],
            "exam_periods": [{"name": "夏季入试", "month": 8}, {"name": "冬季入试", "month": 2}],
            "application_deadlines": [
                {"year": "2027", "type": "夏季出願", "date": "2026-07-10"},
                {"year": "2027", "type": "冬季出願", "date": "2026-12-10"}],
            "url": "https://www.env.nagoya-u.ac.jp/admission/",
            "notes": "环境学研究科。地震+灾害科学交叉方向，适合防灾研究兴趣的学生。",
        },
    },
]


def run(dry_run=False):
    for i, entry in enumerate(ENTRIES):
        uni_name = entry["university"]
        gs_name = entry["graduate_school"]
        print(f"\n--- [{i+1}/{len(ENTRIES)}] {uni_name} {gs_name} ---")

        # 1. Find university
        uni_r = supabase.table("universities").select("id,name").eq("name", uni_name).execute()
        if not uni_r.data:
            print(f"  SKIP: university '{uni_name}' not found — run seed_universities.py first")
            continue
        uni_id = uni_r.data[0]["id"]
        print(f"  Uni: {uni_name} ({uni_id[:8]}...)")

        # 2. Upsert graduate school
        gs_data = {**entry["gs"], "university_id": uni_id, "name": gs_name, "name_jp": gs_name}
        for f in ("english", "jlpt"):
            if isinstance(gs_data.get(f), dict):
                gs_data[f] = json.dumps(gs_data[f], ensure_ascii=False)
        gs_r = supabase.table("graduate_schools").upsert(gs_data, on_conflict="university_id,name").execute()
        gs_id = gs_r.data[0]["id"]
        print(f"  GS: {gs_name} ({gs_id[:8]}...)")

        # 3. Upsert program
        prog_data = {**entry["program"], "graduate_school_id": gs_id}
        for f in ("english", "jlpt", "exam_periods", "application_deadlines"):
            if isinstance(prog_data.get(f), dict):
                prog_data[f] = json.dumps(prog_data[f], ensure_ascii=False)
        prog_r = supabase.table("programs").upsert(prog_data, on_conflict="graduate_school_id,name").execute()
        prog_id = prog_r.data[0]["id"]
        print(f"  Program: {entry['program']['name']} ({prog_id[:8]}...)")

        # 4. Upsert documents
        for doc in entry.get("documents", []):
            doc_data = {**doc, "program_id": prog_id}
            try:
                supabase.table("program_documents").insert(doc_data).execute()
                print(f"    Doc: {doc['doc_type']} {doc['year_tag']}")
            except Exception as e:
                if "duplicate" in str(e).lower():
                    print(f"    Skip (exists): {doc['doc_type']} {doc['year_tag']}")
                else:
                    print(f"    FAIL: {e}")

    # 5. Sync to flat schools cache
    if not dry_run:
        print("\n--- Syncing schools cache ---")
        _sync_to_schools_table()
        print("Done.")


def _sync_to_schools_table():
    pk = supabase.table("programs").select("*").execute()
    for p in pk.data:
        gs = supabase.table("graduate_schools").select("*, universities(*)").eq("id", p["graduate_school_id"]).execute()
        gs_data = gs.data[0] if gs.data else {}
        uni = gs_data.get("universities") or {}

        school_name = f"{uni.get('name', '')} {gs_data.get('name', '')}"
        uni_type = uni.get("type", "")
        school = {
            "name": school_name,
            "degree": p.get("degree", "修士"),
            "type": uni_type,
            "majors": json.loads(p.get("research_areas", "[]")) if isinstance(p.get("research_areas"), str) else (p.get("research_areas") or []),
            "tags": [p.get("name", ""), uni_type, gs_data.get("exam_type", "")],
            "exam": _format_exam(p.get("exam_periods")) if p.get("exam_periods") else "",
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
