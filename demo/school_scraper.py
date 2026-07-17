"""
AI 辅助学校数据采集器。

不是传统爬虫（日本大学网站结构各异），而是：
1. 用 LLM 搜索并提取结构化数据
2. 导出 JSON → 人工验证 → 导入 Supabase

用法：
    python -m demo.school_scraper                    # 采集内置列表的全部学校
    python -m demo.school_scraper --school "东京大学 经济学研究科"  # 单所
    python -m demo.school_scraper --major 计算机       # 搜索某专业的学校
"""
import json, os, sys, argparse
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(v, None)
os.environ["NO_PROXY"] = "*"

from model.factory import chat_model
from demo.school_database import School

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "scraped_schools.json")

EXTRACT_PROMPT = """你是一个数据采集助手。请根据你对日本大学的了解，输出以下学校/专业的结构化信息。

学校：{school_name}

请输出一个 JSON 对象（不要 markdown 标记，直接输出 JSON）：

{{
  "name": "完整学校名 + 研究科名",
  "degree": "修士",
  "majors": ["专业1", "专业2"],
  "tags": ["标签1", "标签2"],
  "exam": "考试形式（如：筆記+面接 / 口頭試問+書類審査）",
  "notes": "补充说明（如：教授内諾必須、出願前に連絡必須 等）",
  "jlpt_min": "N1 或 N2（不要求留空）",
  "gpa_min": 数字(如3.0，0=不设线),
  "english_req": {{"type": "TOEFL/TOEIC/IELTS", "min": 80, "required": true}},
  "deadlines": [
    {{"name": "出願期間", "start": "2026-12-10", "end": "2027-01-09"}},
    {{"name": "試験日", "date": "2027-02-01"}},
    {{"name": "合格発表", "raw": "2027年2月下旬"}}
  ],
  "source_urls": ["官网入试要项URL1", "URL2"]
}}

重要说明：
- deadlines 数组：单日用 "date"，区间用 "start"+ "end"，无法确定精确日期时用 "raw"
- english_req.required=false 表示不要求英语
- source_urls 请提供真实的大学官网入试要项页面URL

请确保信息尽可能准确。不确定的字段填 "" 或 0，不要编造。"""

SEARCH_PROMPT = """请列出日本大学中与「{major}」相关的5-8个知名研究科（修士课程），每行一个完整的"学校名 研究科名"。
只输出学校名列表，不要其他内容。"""


def extract_school(school_name: str) -> dict:
    """用 LLM 提取单所学校的结构化数据"""
    prompt = EXTRACT_PROMPT.format(school_name=school_name)
    resp = chat_model.invoke(prompt)
    text = resp.content.strip()
    # Clean up markdown wrapping
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the text
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        print(f"  警告: 无法解析 {school_name} 的输出，原始文本:\n{text[:300]}")
        return None


def search_major(major: str) -> list[str]:
    """搜索某专业的知名学校"""
    prompt = SEARCH_PROMPT.format(major=major)
    resp = chat_model.invoke(prompt)
    schools = []
    for line in resp.content.strip().split("\n"):
        line = line.strip().strip("0123456789.。、- ")
        if line and len(line) > 5 and "大学" in line:
            schools.append(line)
    return schools


def scrape_schools(school_names: list[str], output_file: str = OUTPUT_FILE) -> list[dict]:
    """批量采集，保存到 JSON"""
    results = []
    existing = []
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_names = {s["name"] for s in existing}
        print(f"已有 {len(existing)} 条记录，跳过重复")

    for i, name in enumerate(school_names):
        if name in {s["name"] for s in existing}:
            print(f"[{i+1}/{len(school_names)}] 跳过 (已有): {name}")
            continue
        print(f"[{i+1}/{len(school_names)}] 采集: {name}")
        data = extract_school(name)
        if data:
            data["source"] = "ai_extracted"
            data["verified"] = False
            results.append(data)

    all_data = existing + results
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共 {len(all_data)} 所学校 → {output_file}")
    print("请人工验证后，使用 seed_schools_to_db.py 或 data_editor 导入 Supabase")
    return all_data


# ── 内置目标列表：可以手工扩充 ──
DEFAULT_SCHOOLS = [
    # 经济学
    "早稻田大学 经济学研究科",
    "庆应义塾大学 经济学研究科",
    "东京大学 经济学研究科",
    "一桥大学 经济学研究科",
    "京都大学 经济学研究科",
    "大阪大学 经济学研究科",
    "名古屋大学 经济学研究科",
    "东北大学 经济学研究科",
    "九州大学 经济学研究科",
    "神户大学 经济学研究科",
    # 计算机
    "东京工业大学 信息理工学研究科",
    "早稻田大学 基幹理工学研究科 信息理工专攻",
    "东京大学 信息理工学系研究科",
    "京都大学 信息学研究科",
    "大阪大学 信息科学研究科",
    # 社会学
    "东京大学 人文社会系研究科 社会学专攻",
    "一桥大学 社会学研究科",
    "早稻田大学 社会科学研究科",
    "京都大学 文学研究科 社会学专攻",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--school", help="采集单所学校")
    parser.add_argument("--major", help="搜索某专业的学校列表")
    parser.add_argument("--output", default=OUTPUT_FILE, help="输出文件路径")
    args = parser.parse_args()

    if args.school:
        schools = [args.school]
    elif args.major:
        print(f"搜索「{args.major}」相关学校...")
        schools = search_major(args.major)
        print(f"找到 {len(schools)} 所:\n" + "\n".join(f"  {s}" for s in schools))
        if input("\n继续采集? (y/n): ").lower() != "y":
            sys.exit(0)
    else:
        schools = DEFAULT_SCHOOLS
        print(f"将采集 {len(schools)} 所默认学校")

    scrape_schools(schools, args.output)
