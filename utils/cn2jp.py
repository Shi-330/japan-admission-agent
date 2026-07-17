"""
CN->JP 搜索归一化模块。

提供 static 映射（即时、无依赖）和 LLM fallback（归一化）。
被 server.py 和 matching_engine.py 共同使用，单一实现。
"""
from typing import Optional

# ── Static CN→JP synonym map (instant, no LLM needed) ──
CN_JP_SYNONYMS = {
    "计算机": ["情報工学", "コンピュータ科学", "情報理工"],
    "人工智能": ["知能情報学", "人工知能", "AI"],
    "电子": ["電気電子", "電子情報学"],
    "机械": ["機械工学", "機械創造工学"],
    "数学": ["数理工学", "数理情報学", "数学"],
    "通信": ["情報通信", "通信情報システム"],
    "网络": ["情報ネットワーク", "メディアネットワーク"],
    "生命": ["生命人間情報科学", "バイオ情報工学"],
    "数据": ["データ科学", "データサイエンス"],
    "金融": ["社会情報学", "システム情報学"],
    "信息": ["情報理工", "情報工学", "情報科学"],
    "情报": ["情報理工", "情報工学", "情報科学"],
}


def normalize(term: str, chat_model=None) -> list[str]:
    """将中文搜索词归一化为日语搜索词列表。

    策略：
    1. 静态映射（即时）
    2. LLM fallback（如果 chat_model 提供且静态映射不够）
    3. 退化为原词

    返回搜索词列表（至少包含原词本身）。
    """
    terms = [term]

    # 1. Static synonym map
    for cn, jp_list in CN_JP_SYNONYMS.items():
        if cn in term:
            terms.extend(jp_list)

    # 2. LLM fallback: only if no static match AND chat_model is available
    if len(terms) == 1 and chat_model is not None:
        try:
            prompt = (
                f"将以下中文搜索词转换为日语汉字（用于搜索日本大学专业）。"
                f"返回2-3个最可能的日语写法，以逗号分隔。"
                f"只返回转换结果，不要解释。\n\n中文：{term}"
            )
            resp = chat_model.invoke(prompt)
            jp_text = resp.content if hasattr(resp, "content") else str(resp)
            jp_text = jp_text.strip()
            extra = [t.strip() for t in jp_text.split(",") if t.strip()]
            terms.extend(extra)
        except Exception:
            pass

    # Remove duplicates preserving order
    seen = set()
    deduped = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped
