"""
RAG evaluation: Golden set of 20 annotated queries → Recall@k / MRR / Hit Rate.

Usage:
  python tests/rag_eval.py              # run all 20 queries
  python tests/rag_eval.py --k 3        # custom k (default=5)
  python tests/rag_eval.py --json       # output as JSON for CI

Each test case: query → expected knowledge source file(s).
A "hit" = the retrieved document's source file matches one of the expected files.
"""
import os, sys, json, time
from typing import List, Dict

# ── Golden set: 20 queries annotated with expected knowledge sources ──
# source = filename prefix that should appear in retrieved documents
GOLDEN_SET = [
    # ---- 申请流程 (4) ----
    {"query": "研究生制度和修士有什么区别", "sources": ["研究生制度"], "desc": "研究生 vs 修士"},
    {"query": "出愿需要准备什么材料", "sources": ["出愿流程指南"], "desc": "出愿材料"},
    {"query": "日本大学院申请时间线", "sources": ["出愿流程指南", "申请流程概述"], "desc": "申请时间线"},
    {"query": "如何联系日本教授", "sources": ["套磁邮件指南"], "desc": "联系教授"},

    # ---- 语言要求 (4) ----
    {"query": "考东京大学需要日语N几", "sources": ["语言要求详解"], "desc": "日语要求"},
    {"query": "托福80分够不够申日本大学院", "sources": ["语言要求详解"], "desc": "托福要求"},
    {"query": "日本SGU英文项目需要日语吗", "sources": ["语言要求详解"], "desc": "SGU日语"},
    {"query": "托业和托福哪个在日本更认可", "sources": ["语言要求详解"], "desc": "托业vs托福"},

    # ---- 考试/面试 (4) ----
    {"query": "修士入学考试考什么科目", "sources": ["入试笔试面试"], "desc": "考试科目"},
    {"query": "面试会被问到什么问题", "sources": ["入试笔试面试"], "desc": "面试问题"},
    {"query": "怎么准备研究计划书", "sources": ["研究计划书写作"], "desc": "计划书"},
    {"query": "过去问在哪里可以找到", "sources": ["入试笔试面试", "出愿流程指南"], "desc": "过去问"},

    # ---- 经验/案例 (4) ----
    {"query": "前辈申请经验分享", "sources": ["前辈经验案例"], "desc": "经验分享"},
    {"query": "双非背景能考上东大吗", "sources": ["前辈经验案例"], "desc": "双非东大"},
    {"query": "套磁邮件怎么写回复率高", "sources": ["套磁邮件指南"], "desc": "套磁模板"},
    {"query": "没有N1可以申请研究生吗", "sources": ["语言要求详解", "研究生制度"], "desc": "N1研究生"},

    # ---- 冷门/边界 (4) ----
    {"query": "日本大学院学费多少钱", "sources": [], "desc": "学费(无直接来源)"},
    {"query": "地震学哪个教授比较好", "sources": [], "desc": "地震学教授(无直接来源)"},
    {"query": "在东京一个月生活费多少", "sources": [], "desc": "生活费(无直接来源)"},
    {"query": "签证怎么办理", "sources": [], "desc": "签证(无直接来源)"},
]


def run_eval(k: int = 5) -> Dict:
    """Run all 20 queries through RAG and compute metrics."""
    from rag.rag_service import RagSummarizeService
    rag = RagSummarizeService()

    results = []
    recall_sum = 0.0
    mrr_sum = 0.0
    hits = 0

    print(f"{'='*60}")
    print(f"RAG Eval: {len(GOLDEN_SET)} queries, Recall@{k} + MRR")
    print(f"{'='*60}")

    for i, case in enumerate(GOLDEN_SET):
        query = case["query"]
        expected = set(case.get("sources", []))
        desc = case.get("desc", "")

        # Run retrieval
        start = time.time()
        docs = rag.retriever_docs(query)[:k]
        elapsed = time.time() - start

        # Extract source filenames from retrieved documents
        # Metadata source contains full paths like "data/external/套磁邮件指南.txt"
        # Normalize to match GOLDEN_SET keys (substring match against known sources)
        retrieved_sources = []
        for doc in docs:
            src = doc.metadata.get("source", "")
            if not src:
                # Fallback: check page_content for source markers
                content = doc.page_content
                if "套磁" in content: retrieved_sources.append("套磁邮件指南")
                if "研究计划" in content: retrieved_sources.append("研究计划书写作")
                if "面试" in content or "笔试" in content or "入试" in content: retrieved_sources.append("入试笔试面试")
                if "语言" in content or "JLPT" in content or "TOEFL" in content: retrieved_sources.append("语言要求详解")
                if "前辈" in content or "案例" in content: retrieved_sources.append("前辈经验案例")
                if "研究生" in content and "制度" in content: retrieved_sources.append("研究生制度")
                if "出愿" in content or "申请流程" in content: retrieved_sources.append("出愿流程指南")
                continue
            fname = os.path.basename(src).rsplit(".", 1)[0]
            retrieved_sources.append(fname)
            # Also add normalized short names
            if "套磁" in fname: retrieved_sources.append("套磁邮件指南")
            if "研究计划" in fname: retrieved_sources.append("研究计划书写作")
            if "面试" in fname or "笔试" in fname or "入试" in fname: retrieved_sources.append("入试笔试面试")
            if "语言" in fname or "JLPT" in fname or "TOEFL" in fname: retrieved_sources.append("语言要求详解")
            if "前辈" in fname or "案例" in fname: retrieved_sources.append("前辈经验案例")
            if "研究生" in fname and "制度" in fname: retrieved_sources.append("研究生制度")
            if "出愿" in fname or "申请流程" in fname: retrieved_sources.append("出愿流程指南")

        # Compute metrics
        retrieved_set = set(retrieved_sources)
        matched = expected & retrieved_set if expected else set()

        # Recall@k = |relevant ∩ retrieved| / |relevant|
        recall = len(matched) / len(expected) if expected else 1.0  # edge: no expected source = auto 1.0

        # MRR = 1 / rank of first relevant result
        mrr = 0.0
        for rank, src in enumerate(retrieved_sources, 1):
            if src in expected:
                mrr = 1.0 / rank
                break
        if not expected:
            mrr = 1.0  # no expected = perfect

        hit = len(matched) > 0
        if hit: hits += 1
        recall_sum += recall
        mrr_sum += mrr

        status = "HIT" if hit else "MISS"
        print(f"  [{status}] #{i+1:02d} {desc}")
        print(f"         Expected: {expected or '(none — cold query)'}")
        print(f"         Got:      {retrieved_sources[:5]}")
        print(f"         Recall@{k}={recall:.2f}  MRR={mrr:.2f}  ({elapsed*1000:.0f}ms)")

        results.append({
            "id": i + 1, "query": query, "desc": desc,
            "expected": list(expected), "retrieved": retrieved_sources[:k],
            "recall": round(recall, 3), "mrr": round(mrr, 3),
            "hit": hit, "elapsed_ms": round(elapsed * 1000),
        })

    n = len(GOLDEN_SET)
    summary = {
        "total_queries": n,
        "k": k,
        "mean_recall": round(recall_sum / n, 3),
        "mean_mrr": round(mrr_sum / n, 3),
        "hit_rate": round(hits / n, 3),
        "total_hits": hits,
        "results": results,
    }

    print(f"{'='*60}")
    print(f"Summary: Recall@{k}={summary['mean_recall']}  MRR={summary['mean_mrr']}  HitRate={summary['hit_rate']} ({hits}/{n})")
    print(f"{'='*60}")
    return summary


if __name__ == "__main__":
    k = 5
    output_json = False
    for arg in sys.argv[1:]:
        if arg.startswith("--k="): k = int(arg.split("=")[1])
        if arg == "--json": output_json = True

    result = run_eval(k=k)
    if output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
