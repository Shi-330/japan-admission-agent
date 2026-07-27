"""
确定性院校匹配引擎 V2.

输入：学生画像（JLPT、GPA、目标专业、英语成绩）
输出：每所学校的三档分类（可报考 / 条件不足 / 差距较大）+ 差距详情

不使用 LLM。所有判断基于结构化规则。
不使用 EJU（修士匹配不适用）。
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
from utils.logger_handler import logger

# JLPT rank ordering for comparison
JLPT_RANK = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}


@dataclass
class StudentProfile:
    jlpt_level: str           # "N1" / "N2" / "N3" / "无"
    gpa: float                 # 4.0 制（0=未填写）
    target_major: str          # "情报理工" / "计算机" / ...
    english_score: str = ""    # "TOEFL 80" / "TOEIC 750" / ...
    undergraduate_school: str = ""


@dataclass
class GapDetail:
    field: str                 # "JLPT" / "GPA" / "英语"
    required: str
    current: str
    met: bool


STATUS_LABELS = {"match": "[可报考]", "warning": "[条件不足]", "reject": "[差距较大]"}

@dataclass
class MatchResult:
    school_name: str
    status: str                # "match" / "warning" / "reject"
    gaps: List[GapDetail] = field(default_factory=list)
    deadlines: list = field(default_factory=list)   # structured deadline array
    exam_info: str = ""
    notes: str = ""


def _jlpt_rank(level: str) -> int:
    """Convert JLPT level string to numeric rank. Unknown = 0."""
    return JLPT_RANK.get(level.strip().upper(), 0)


def _jlpt_met(required: str, actual: str) -> tuple[bool, int]:
    """Check JLPT requirement. Returns (met, gap_levels).
    N1 > N2 > N3, higher rank covers lower.
    If required is empty, requirement is waived.
    """
    if not required:
        return True, 0
    req_rank = _jlpt_rank(required)
    act_rank = _jlpt_rank(actual)
    return act_rank >= req_rank, req_rank - act_rank


def _parse_english_score(raw: str) -> dict:
    """Parse student's english_score string into {type, score}.
    Returns {} if unparseable.
    """
    if not raw or raw in ("无", "未参加", "未提供"):
        return {}
    raw = raw.strip().upper()
    for exam in ("TOEFL", "TOEIC", "IELTS", "托福", "托业", "雅思"):
        if exam in raw:
            nums = re.findall(r'\d+', raw)
            return {"type": exam, "score": int(nums[0]) if nums else 0}
    return {}


def _english_met(english_req: dict, actual: str) -> tuple[bool, str]:
    """Check English requirement against student's actual score.

    english_req: {"required": false} → always pass
                 {"type": "any", "required": true} → pass if student has any score
                 {"type": "TOEFL", "min": 80, "required": true} → numeric comparison
    Returns (met, detail_string)
    """
    if not english_req or not english_req.get("required", False):
        return True, "不要求"

    # Student has no score
    student = _parse_english_score(actual)
    if not student:
        return False, "无英语成绩"

    req_type = english_req.get("type", "")

    # "any" means any English test score is acceptable
    if req_type == "any" or not req_type:
        return True, f"有成绩: {actual}"

    # Specific exam type with optional minimum
    req_min = english_req.get("min", 0)
    student_score = student.get("score", 0)

    if req_min > 0 and student_score > 0:
        return student_score >= req_min, f"{actual} (要求 {req_type} {req_min})"

    # Has required exam type, no minimum specified
    if student.get("type") and req_type in ("TOEFL", "TOEIC", "IELTS", "托福", "托业", "雅思"):
        return True, f"有成绩: {actual}"

    return False, f"缺少 {req_type}"


def _schools_from_db() -> list[dict]:
    """Load schools from Supabase. Returns empty list on failure (no fallback)."""
    try:
        from .school_database import get_all_schools
        db_schools = get_all_schools()
        if db_schools:
            return [s.model_dump() for s in db_schools]
    except Exception as e:
        logger.warning(f"从数据库加载学校失败: {e}")
    return []


def match_schools(profile: StudentProfile, chat_model=None) -> List[MatchResult]:
    """对全部学校做匹配。chat_model 用于 cn2jp LLM fallback。"""
    results = []
    schools = _schools_from_db()

    if not schools:
        logger.warning("学校数据加载失败，无法执行匹配")
        return results  # empty — caller should handle with error message

    # Use cn2jp for major normalization (LLM enrichment when available)
    target_terms = [profile.target_major] if profile.target_major else []
    if profile.target_major:
        try:
            from utils.cn2jp import normalize
            target_terms = normalize(profile.target_major, chat_model=chat_model)
        except Exception:
            pass

    for school in schools:
        # Professional filter: term must hit majors, name, or tags
        if profile.target_major and target_terms:
            haystack = " ".join([
                school.get("name", ""),
                " ".join(school.get("majors", [])),
                " ".join(school.get("tags", [])),
            ]).lower()
            if not any(t.lower() in haystack for t in target_terms):
                continue

        gaps = []

        # ── JLPT check ──
        jlpt_ok, jlpt_gap = _jlpt_met(school.get("jlpt_min", ""), profile.jlpt_level)
        gaps.append(GapDetail("JLPT", school.get("jlpt_min", "无要求"),
                              profile.jlpt_level, jlpt_ok))

        # ── GPA check ──
        gpa_min = school.get("gpa_min", 0.0) or 0.0
        if gpa_min == 0.0:
            gpa_ok = True
        elif profile.gpa == 0.0:
            # Student GPA not filled — pass with warning note
            gpa_ok = True
        else:
            gpa_ok = profile.gpa >= gpa_min
        gaps.append(GapDetail("GPA", f"{gpa_min:.1f}" if gpa_min > 0 else "无要求",
                              f"{profile.gpa:.2f}" if profile.gpa > 0 else "未填写", gpa_ok))

        # ── English check ──
        eng_ok, eng_detail = _english_met(school.get("english_req", {}), profile.english_score)
        gaps.append(GapDetail("英语", eng_detail, profile.english_score or "无", eng_ok))

        # ── Status determination ──
        fails = [g for g in gaps if not g.met]
        fail_count = len(fails)

        if fail_count == 0:
            status = "match"
        elif fail_count >= 2:
            status = "reject"
        else:
            # Exactly 1 fail — check if it's JLPT with >=2 level gap
            jlpt_fail = next((g for g in fails if g.field == "JLPT"), None)
            if jlpt_fail:
                _, gap_levels = _jlpt_met(school.get("jlpt_min", ""), profile.jlpt_level)
                if gap_levels >= 2:
                    status = "reject"
                else:
                    status = "warning"
            else:
                status = "warning"

        results.append(MatchResult(
            school_name=school["name"],
            status=status,
            gaps=gaps,
            deadlines=school.get("deadlines", []),
            exam_info=school.get("exam", ""),
            notes=school.get("notes", ""),
        ))

    # Sort: match > warning > reject
    order = {"match": 0, "warning": 1, "reject": 2}
    results.sort(key=lambda r: order[r.status])
    return results


def generate_timeline(matches: List[MatchResult]) -> List[str]:
    """根据匹配结果生成倒推时间线（消费结构化 deadlines 中有 date/start 的条目）。"""
    now = datetime.now()
    events = []

    events.append(f"{now.strftime('%Y-%m')} | 现在：开始准备")
    events.append(f"{(now + timedelta(days=30)).strftime('%Y-%m')} | 确定目标院校（{len([m for m in matches if m.status != 'reject'])}所）")
    events.append(f"{(now + timedelta(days=60)).strftime('%Y-%m')} | 完成研究计划书初稿")
    events.append(f"{(now + timedelta(days=90)).strftime('%Y-%m')} | 联系教授（如有需要）")

    for m in matches:
        if m.status == "reject":
            continue
        for dl in m.deadlines:
            if not isinstance(dl, dict):
                continue
            dl_name = dl.get("name", "")
            # Only use entries with date or start (parsable)
            date_str = dl.get("date") or dl.get("start")
            if date_str:
                events.append(f"{date_str[:10]} | {m.school_name} {dl_name}")
            elif dl.get("raw"):
                events.append(f"{dl['raw']} | {m.school_name} {dl_name}")

    events.append("考前2个月 | 集中复习校内考科目")
    events.append("考前1周 | 确认出愿材料完整性")

    return events
