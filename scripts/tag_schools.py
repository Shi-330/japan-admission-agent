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

# ── Tag taxonomy (academic focus only — admin tags already known) ──
ACADEMIC_TAGS = [
    # 理学
    "数学", "物理学", "化学", "生物学", "地球科学", "天文学",
    "素粒子物理", "宇宙物理", "物性物理", "量子力学", "原子核物理",
    "有機化学", "無機化学", "高分子化学", "生物化学",
    "分子生物学", "細胞生物学", "遺伝学", "ゲノム科学", "生態学", "進化生物学", "微生物学",
    "地震学", "地球物理学", "気象学", "海洋学", "地質学", "火山学", "地球化学",
    # 工学
    "機械工学", "電気電子工学", "情報工学", "土木工学", "建築学", "材料工学",
    "化学工学", "航空宇宙工学", "原子力工学", "船舶海洋工学",
    "AI", "機械学習", "深層学習", "自然言語処理", "コンピュータビジョン", "ロボティクス",
    "データサイエンス", "情報理論", "暗号理論", "セキュリティ",
    "制御工学", "信号処理", "画像処理", "音声処理",
    "半導体", "光エレクトロニクス", "通信工学", "マイクロ波",
    "地盤工学", "水工学", "環境工学", "都市計画",
    # 農学・生命
    "農学", "畜産学", "水産学", "林学", "食品科学", "栄養学",
    "植物病理学", "昆虫学", "土壌学",
    # 医歯薬
    "内科学", "外科学", "病理学", "薬理学", "公衆衛生学", "免疫学",
    "脳科学", "神経科学", "再生医学", "腫瘍学",
    # 人文社会
    "哲学", "倫理学", "美学", "宗教学",
    "歴史学", "考古学", "文化人類学", "民俗学",
    "文学", "言語学", "日本語学", "英語学",
    "法学", "政治学", "行政学", "国際関係論",
    "経済学", "経営学", "会計学", "金融論",
    "社会学", "心理学", "教育学", "社会福祉学",
    "地理学", "人口学", "統計学",
    # 芸術
    "美術", "音楽", "デザイン", "演劇", "映像",
    # 学際
    "環境科学", "情報学", "生命科学", "認知科学", "複雑系科学",
    "災害科学", "地域研究", "ジェンダー論",
]

SYSTEM_PROMPT = f"""あなたは日本の大学院研究科の専門分野タグ付けの専門家です。
研究科名と備考から、この研究科が**実際に研究している学術分野**を抽出してください。

抽出ルール：
1. 以下の許可リストから該当する全てのタグを選んでください
2. 研究科名に含まれる語から直接判断する（例：「理学研究科」→ 物理学, 化学, 生物学...）
3. 備考（notes）に具体的な研究分野の記述があればそれも活用する
4. 不確かな場合は無理に付けない（空のリストも可）
5. 必ず許可リストの語をそのまま使う（表記ゆれ禁止）

許可リスト（この中からのみ選ぶこと）：
{', '.join(ACADEMIC_TAGS)}

出力形式：{{"tags": ["タグ1", "タグ2", ...]}}
JSONのみを返してください。説明は不要です。"""

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
            valid = [t for t in tags if t in set(ACADEMIC_TAGS)]
            return valid
    except Exception as e:
        print(f"  LLM error: {e}")
    return []


def main():
    # Force UTF-8 inside function body too (Windows GBK workaround)
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
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
