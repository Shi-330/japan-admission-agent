"""
Generate missing RAG knowledge articles using LLM, then embed into pgvector.

Usage:
  python generate_knowledge.py              # generate + embed all topics
  python generate_knowledge.py --dry-run     # preview topics without writing
"""
import os, sys
from dotenv import load_dotenv; load_dotenv()
from model.factory import chat_model

MISSING_TOPICS = [
    {
        "filename": "学费与奖学金.txt",
        "topic": "日本大学院学费、奖学金、学费减免",
        "prompt": """写一篇800字的中文知识文章，主题：日本大学院（修士/博士）的学费、奖学金、学费减免制度。

包含：
1. 国立大学 vs 私立大学的学费对比（具体金额，日元和人民币）
2. 入学金和授业料的区别
3. 日本政府（MEXT）奖学金、JASSO奖学金、各大学自有奖学金
4. 学费减免制度的申请条件和流程
5. 生活费估算（东京 vs 地方城市）
6. 打工（资格外活动许可）的收入上限和实际可行性

信息要准确、具体，以2026年数据为准。用语专业但易懂。直接输出文章，不要标题头。""",
    },
    {
        "filename": "签证与在留资格.txt",
        "topic": "日本留学签证、在留资格认定",
        "prompt": """写一篇800字的中文知识文章，主题：日本留学签证和在留资格认定证明书（COE）申请流程。

包含：
1. 在留资格认定证明书（COE）是什么、谁申请、需要什么材料
2. 留学签证（在留资格「留学」）的申请流程和时间线
3. 从国内申请 vs 从日本境内变更的流程区别
4. 签证续签（在留期间更新）的手续和注意事项
5. 资格外活动许可（打工许可）的申请
6. 毕业后如果想留在日本工作的签证转换（特定活动→就劳签证）
7. 常见被拒原因和避坑指南

信息准确、流程清晰。直接输出文章。""",
    },
    {
        "filename": "日本生活指南.txt",
        "topic": "日本留学生活指南、租房、银行、手机",
        "prompt": """写一篇800字的中文知识文章，主题：日本大学院留学生的生活实务指南。

包含：
1. 租房：怎么找房（UR团地、民间、学生宿舍）、初期费用（礼金/敷金/中介费）、连带保证人怎么办
2. 银行开户：需要什么材料、哪家银行对外国人友好（ゆうちょ、三菱UFJ）
3. 手机和网络：格安SIM（LineMo、ahamo、UQ）vs 三大运营商、办网流程
4. 国民健康保险（国保）和学生减免
5. 交通：定期券、学生折扣
6. 垃圾分类和社区礼仪

实用、具体、有可操作性。直接输出文章。""",
    },
    {
        "filename": "大学院入试详解.txt",
        "topic": "日本大学院入试制度、考试类型、评分标准",
        "prompt": """写一篇800字的中文知识文章，主题：日本大学院（修士课程）入试制度详解。

包含：
1. 一般入试 vs 外国人留学生特别选拔 vs SGU英文项目的区别
2. 笔试科目（专业课、英语、数学）的一般形式和难度
3. 口试/面试的形式：关于研究计划书的提问、专业知识的追问
4. 出愿资格审查是什么、谁需要
5. 评分标准和合格判定（笔试+面试+书类的权重）
6. 夏季入试和冬季入试的时间线和区别
7. 研究生（けんきゅうせい）作为过渡路径的操作方式

信息准确、流程清晰。直接输出文章。""",
    },
    {
        "filename": "研究方向选择指南.txt",
        "topic": "日本大学院研究方向选择、教授匹配",
        "prompt": """写一篇800字的中文知识文章，主题：日本大学院申请中如何选择研究方向和匹配教授。

包含：
1. 如何从本科专业过渡到修士研究方向
2. 怎么读教授的research map和实验室主页——关键信息点
3. 跨专业申请的可行性和策略（理学→情报、机械→材料等常见跨法）
4. 研究计划书和教授研究方向的匹配度有多重要
5. 同时联系多个教授的礼仪和策略
6. 教授回复"没有名额""方向不同""欢迎报考"分别怎么应对
7. 研究室氛围怎么判断——看成员页面、毕业去向、研究经费

实用、有可操作性。直接输出文章。""",
    },
]


def generate_article(topic: dict) -> str:
    """Generate one knowledge article via LLM."""
    print(f"  Generating: {topic['filename']} ...")
    resp = chat_model.invoke(topic["prompt"])
    text = resp.content if hasattr(resp, "content") else str(resp)
    text = text.strip()
    # Remove markdown code blocks if LLM wrapped it
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    return text


def main(dry_run=False):
    data_dir = os.path.join(os.path.dirname(__file__), "data", "external")
    os.makedirs(data_dir, exist_ok=True)

    for topic in MISSING_TOPICS:
        path = os.path.join(data_dir, topic["filename"])
        if os.path.exists(path):
            print(f"  Skip (exists): {topic['filename']}")
            continue

        if dry_run:
            print(f"  [DRY] {topic['filename']}: {topic['topic']}")
            continue

        try:
            text = generate_article(topic)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"  Wrote: {topic['filename']} ({len(text)} chars)")
        except Exception as e:
            print(f"  FAIL: {topic['filename']} — {e}")

    if not dry_run:
        print("\nArticles generated. Now embed them:")
        print("  python ingest_knowledge.py")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
