"""
三层升学顾问 Demo

1. 匹配引擎（确定性规则）-> 筛出可报/差多少/不能报
2. RAG 检索（语义搜索）-> 从私塾知识库找内部经验
3. LLM 合成（流式输出）-> 把结果编成人话

运行：python -m demo.run_demo
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Kill proxy + set HF mirror (must be before any HuggingFace import)
for _v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_v, None)
os.environ["NO_PROXY"] = "*"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from demo.matching_engine import StudentProfile, match_schools, generate_timeline, STATUS_LABELS
from rag.rag_service import RagSummarizeService
from model.factory import chat_model


def run(profile: StudentProfile, rag_query: str = None):
    print("=" * 60)
    print("[ 日本升学顾问 Demo")
    print("=" * 60)

    # First layer: matching engine
    print(f"\n{'─' * 40}")
    print("[ 学生画像")
    print(f"   JLPT: {profile.jlpt_level}  |  GPA: {profile.gpa}")
    print(f"   目标: {profile.target_major}  |  英语: {profile.english_score or '无'}")
    print(f"   出身校: {profile.undergraduate_school or '未知'}")

    print(f"\n{'─' * 40}")
    print("[ 第一层：确定性匹配（0 秒，无 LLM）")
    print(f"{'─' * 40}")
    matches = match_schools(profile)

    if not matches:
        print("  未找到匹配的院校。请检查目标专业或学校数据。")
        return

    for m in matches:
        print(f"\n  {STATUS_LABELS[m.status]}  {m.school_name}")
        for g in m.gaps:
            icon = "[O]" if g.met else "[X]"
            print(f"     {icon} {g.field}: 要求 {g.required} -> 你 {g.current}")
        print(f"     - 考试: {m.exam_info}")
        print(f"     [ 截止: {m.deadlines}")
        print(f"     > 内部: {m.notes}")

    print(f"\n{'─' * 40}")
    print("[ 时间线")
    print(f"{'─' * 40}")
    for event in generate_timeline(matches):
        print(f"  {event}")

    # Second layer: RAG
    ctx = ""
    if rag_query:
        print(f"\n{'─' * 40}")
        print("[ 第二层：RAG 知识库检索")
        print(f"{'─' * 40}")
        print(f"  查询: {rag_query}")
        try:
            rag = RagSummarizeService()
            ctx = rag.get_raw_vector_context(rag_query)
            print(f"  检索到 {len(ctx)} 字符的内部资料")
        except Exception as e:
            ctx = ""
            print(f"  RAG 不可用，跳过: {e}")

        # Third layer: LLM synthesis
        print(f"\n{'─' * 40}")
        print("[ 第三层：LLM 合成回答")
        print(f"{'─' * 40}")
        prompt = f"""你是一位日本升学顾问。请根据以下信息，给这位学生一个简洁的建议。

【学生条件】
JLPT {profile.jlpt_level}, GPA {profile.gpa}
目标：{profile.target_major}
英语：{profile.english_score or "无"}

【匹配结果】
{chr(10).join(f'{STATUS_LABELS[m.status]} {m.school_name}' for m in matches)}

【内部资料】
{ctx[:1000] if ctx else "(未检索)"}

请用 3-5 句话给出综合建议。用中文。"""

        print("  > ", end="", flush=True)
        try:
            resp = chat_model.invoke(prompt)
            print(resp.content)
        except Exception as e:
            print(f"(LLM 不可用: {e})")

    print(f"\n{'=' * 60}")
    print("Demo 结束。三层分工：匹配引擎筛学校 -> RAG 找经验 -> LLM 说人话")
    print("=" * 60)


if __name__ == "__main__":
    # 示例学生：中上水平，目标 情报理工
    student = StudentProfile(
        jlpt_level="N2",
        gpa=3.2,
        target_major="情報理工",
        english_score="TOEFL 80",
        undergraduate_school="上海外国语大学",
    )

    run(student, rag_query="早稻田大学 情报理工 面试 经验 研究计划书")
