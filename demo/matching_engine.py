"""
确定性院校匹配引擎。

输入：学生画像（JLPT、EJU、GPA、目标专业、英语成绩）
输出：每所学校的三档分类（✅可报 / ⚠️条件不足 / ❌差距较大）+ 差距详情

不使用 LLM。所有判断基于结构化规则。
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
from .school_data import SCHOOLS, JLPT_RANK


@dataclass
class StudentProfile:
    jlpt_level: str      # "N1" / "N2" / "N3" / ...
    eju_score: int        # 留考总分
    gpa: float            # 4.0 制
    target_major: str     # "经济学" / "社会学" / ...
    english_score: str = ""      # "TOEFL 80" / "TOEIC 750" / ...
    undergraduate_school: str = ""


@dataclass
class GapDetail:
    field: str            # "JLPT" / "EJU" / "GPA" / "英语"
    required: str
    current: str
    met: bool


@dataclass
class MatchResult:
    school_name: str
    status: str           # "match" / "warning" / "reject"
    status_label: str     # "✅ 可报考" / "⚠️ 条件不足" / "❌ 差距较大"
    gaps: List[GapDetail] = field(default_factory=list)
    deadlines: dict = field(default_factory=dict)
    exam_info: str = ""
    notes: str = ""
    capacity: str = ""


def _jlpt_met(required: str, actual: str) -> bool:
    """N1 > N2 > N3, 高级别覆盖低级别"""
    req_rank = JLPT_RANK.get(required, 0)
    act_rank = JLPT_RANK.get(actual, 0)
    return act_rank >= req_rank


def _english_met(required_note: str, actual: str) -> bool:
    """简单解析英语成绩。粗匹配，可扩展。"""
    # 学校不强制要求 → 直接通过
    if "不强制" in required_note or "建议" in required_note:
        return True
    # 学校要求英语但学生没成绩
    if not actual or actual == "无":
        return False
    # 尝试提取分数做数值比较
    import re
    req_match = re.search(r'(\d+)', required_note)
    act_match = re.search(r'(\d+)', actual)
    if req_match and act_match:
        return int(act_match.group(1)) >= int(req_match.group(1))
    return True  # 无法解析时不阻断


def match_schools(profile: StudentProfile) -> List[MatchResult]:
    """对全部学校做匹配，返回排序后的结果（match > warning > reject）"""
    results = []
    for school in SCHOOLS:
        if profile.target_major not in school["name"]:
            continue  # 专业不匹配，跳过

        gaps = []

        # JLPT 检查
        jlpt_ok = _jlpt_met(school["jlpt_min"], profile.jlpt_level)
        gaps.append(GapDetail("JLPT", school["jlpt_min"],
                              profile.jlpt_level, jlpt_ok))

        # EJU 检查
        eju_ok = profile.eju_score >= school["eju_min"]
        gaps.append(GapDetail("EJU", str(school["eju_min"]),
                              str(profile.eju_score), eju_ok))

        # GPA 检查
        gpa_ok = profile.gpa >= school["gpa_min"]
        gaps.append(GapDetail("GPA", str(school["gpa_min"]),
                              str(profile.gpa), gpa_ok))

        # 英语检查
        eng_ok = _english_met(school["english_note"], profile.english_score)
        gaps.append(GapDetail("英语", school["english_note"],
                              profile.english_score or "无", eng_ok))

        # 综合判定
        all_ok = all(g.met for g in gaps)
        hard_fails = [g for g in gaps if not g.met and g.field in ("JLPT", "EJU")]
        if all_ok:
            status = "match"
            status_label = "✅ 可报考"
        elif len(hard_fails) >= 2 or abs(profile.eju_score - school["eju_min"]) > 60:
            status = "reject"
            status_label = "❌ 差距较大"
        else:
            status = "warning"
            status_label = "⚠️ 条件不足"

        results.append(MatchResult(
            school_name=school["name"],
            status=status,
            status_label=status_label,
            gaps=gaps,
            deadlines=school.get("deadlines", {}),
            exam_info=school.get("exam", ""),
            notes=school.get("notes", ""),
            capacity=school.get("capacity", ""),
        ))

    # 排序：match > warning > reject
    order = {"match": 0, "warning": 1, "reject": 2}
    results.sort(key=lambda r: order[r.status])
    return results


def generate_timeline(matches: List[MatchResult]) -> List[str]:
    """根据匹配结果生成倒推时间线"""
    now = datetime.now()
    events = []

    # 通用节点
    events.append(f"{now.strftime('%Y-%m')} | 现在：开始准备")
    events.append(f"{(now + timedelta(days=30)).strftime('%Y-%m')} | 确定目标院校（{len([m for m in matches if m.status != 'reject'])}所）")
    events.append(f"{(now + timedelta(days=60)).strftime('%Y-%m')} | 完成研究计划书初稿")
    events.append(f"{(now + timedelta(days=90)).strftime('%Y-%m')} | 联系教授（如有需要）")

    for m in matches:
        if m.status == "reject":
            continue
        # 从最早截止日倒推
        for intake, deadline_str in m.deadlines.items():
            events.append(f"{deadline_str} | {m.school_name} {intake} 出愿截止")

    events.append("考前2个月 | 集中复习校内考科目")
    events.append("考前1周 | 确认出愿材料完整性")

    return events
