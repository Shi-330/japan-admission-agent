"""
Batch tag generation for graduate schools lacking structured tags.
Offline script — calls LLM to extract structured tags from school name + notes.

Usage:
  venv/Scripts/python.exe scripts/tag_schools.py          # process all untagged
  venv/Scripts/python.exe scripts/tag_schools.py --dry-run  # preview only
  venv/Scripts/python.exe scripts/tag_schools.py --limit 20  # test first 20
"""
import os, sys, json, time
# Force UTF-8 on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supabase import create_client
from model.factory import chat_model

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── Tag taxonomy ──
TAG_CATEGORIES = {
    "exam": ["筆記", "面接", "口頭試問", "書類選考", "筆記なし可能", "口述試験"],
    "english": ["英語必要", "英語不要", "TOEFL", "TOEIC", "IELTS", "SGU", "英語コース", "国際プログラム"],
    "japanese": ["N1必須", "N2必須", "日本語不要"],
    "contact": ["教授内諾必須", "事前連絡必須", "事前連絡推奨", "教授内諾不要"],
    "focus": ["AI", "データサイエンス", "ロボティクス", "環境", "医療", "法律", "経済", "経営",
              "建築", "土木", "化学", "物理", "生物", "数学", "文学", "歴史", "哲学",
              "社会学", "教育学", "心理学", "芸術", "音楽", "デザイン", "農学",
              "情報", "知能情報", "機械学習", "画像処理", "自然言語処理", "セキュリティ"],
    "type": ["国立", "公立", "私立", "外国人特别选拔", "社会人入試"],
}

SYSTEM_PROMPT = f"""你是日本大学院标签专家。根据研究科名称和备注，提取以下维度的标签。
可用标签列表：
- 考试形式: {', '.join(TAG_CATEGORIES['exam'])}
- 英语要求: {', '.join(TAG_CATEGORIES['english'])}
- 日语要求: {', '.join(TAG_CATEGORIES['japanese'])}
- 联系教授: {', '.join(TAG_CATEGORIES['contact'])}
- 专业领域: {', '.join(TAG_CATEGORIES['focus'])}
- 学校类型: {', '.join(TAG_CATEGORIES['type'])}

规则：
1. 只从上述列表中选择，不要编造新标签
2. 根据学校名和备注判断，不确定的不标
3. 每个维度最多选3个最匹配的标签
4. 返回JSON: {{"tags": ["tag1", "tag2", ...]}}
5. 只返回JSON，不要解释"""

def tag_school(school: dict) -> list[str]:
    """Call LLM to generate tags for one school."""
    name = school.get("name_jp", "")
    notes = (school.get("notes") or "")[:300]
    prompt = f"研究科: {name}\n备注: {notes}\n\n{SYSTEM_PROMPT}"
    try:
        resp = chat_model.invoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        # Parse JSON
        m = __import__("re").search(r'\{.*\}', text, __import__("re").DOTALL)
        if m:
            data = json.loads(m.group(0))
            tags = data.get("tags", [])
            # Validate against known tags
            all_tags = set()
            for cat in TAG_CATEGORIES.values():
                all_tags.update(cat)
            valid = [t for t in tags if t in all_tags]
            return valid
    except Exception as e:
        print(f"  LLM error: {e}")
    return []


def main():
    dry_run = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

    # Fetch schools without tags (or with empty tags)
    r = supabase.table("graduate_schools").select("id,name_jp,notes,tags").execute()
    untagged = [s for s in r.data if not s.get("tags") or len(s.get("tags", [])) == 0]
    print(f"Total schools: {len(r.data)}, untagged: {len(untagged)}")

    if limit:
        untagged = untagged[:limit]

    ok = 0
    for i, s in enumerate(untagged):
        name = s["name_jp"]
        print(f"\n[{i+1}/{len(untagged)}] {name[:50]}")

        if dry_run:
            tags = tag_school(s)
            print(f"  -> {tags}")
            continue

        # Check if already tagged (race condition safety)
        check = supabase.table("graduate_schools").select("tags").eq("id", s["id"]).execute()
        if check.data and check.data[0].get("tags") and len(check.data[0]["tags"]) > 0:
            print("  Already tagged, skip")
            ok += 1
            continue

        tags = tag_school(s)
        if tags:
            try:
                supabase.table("graduate_schools").update({"tags": tags}).eq("id", s["id"]).execute()
                print(f"  -> {tags}")
                ok += 1
            except Exception as e:
                print(f"  DB error: {e}")
        else:
            print("  -> No tags extracted")

        time.sleep(1.5)  # Rate limit for LLM API

        if (i + 1) % 50 == 0:
            print(f"\n--- Progress: {ok}/{i+1} tagged ---")

    print(f"\nDone: {ok}/{len(untagged)} tagged")


if __name__ == "__main__":
    main()
