"""
V2.2 申请阶段状态机 — 修士 (Master's) 申请流程

Deterministic stage definitions + transition rules.
LLM only fills content WITHIN each stage; the stage itself is NOT an LLM decision.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ── Stage definitions ──
STAGES: Dict[str, dict] = {
    "browsing": {
        "order": -1,
        "label": "关注中",
        "description": "浏览学校信息，尚未开始正式准备",
        "conditions": [],
        "actions": [
            "查看募集要项，了解出愿要求和考试科目",
            "浏览教授研究方向，初步筛选感兴趣的方向",
            "确认是否需要联系教授（内诺制/事前連絡）",
        ],
        "typical_duration_days": 0,
        "next_stages": ["preparing"],
        "prev_stages": [],
    },
    "preparing": {
        "order": 0,
        "label": "准备阶段",
        "description": "考语言、定方向、选教授、读论文",
        "conditions": [
            "JLPT N2 以上（建议 N1）",
            "英语 TOEFL 80+ / TOEIC 750+ / IELTS 6.0+",
            "确定 2-3 个研究方向关键词",
            "筛选 5-10 位目标教授",
        ],
        "actions": [
            "确定研究方向并精读 3-5 篇核心论文",
            "整理目标教授的研究方向和近期论文",
            "准备研究计划书初稿（2000 字左右）",
            "联系本科导师准备推荐信",
        ],
        "typical_duration_days": 90,
        "next_stages": ["contacting"],
        "prev_stages": [],
    },
    "contacting": {
        "order": 1,
        "label": "套磁阶段",
        "description": "发送套磁信、等待回复、跟进或更换教授",
        "conditions": [
            "研究计划书初稿完成",
            "目标教授列表已整理",
            "套磁信模板已准备",
        ],
        "actions": [
            "每周发出 1-2 封套磁信（不要同时群发同校教授）",
            "记录每位教授的回复状态（已读/有意/婉拒/无回复）",
            "两周无回复可发一次跟进邮件",
            "收到积极回复后深度研究该教授近期方向",
        ],
        "typical_duration_days": 60,
        "next_stages": ["applying"],
        "prev_stages": ["preparing"],
        "reminders": [
            {"days": 14, "message": "教授 14 天未回复，建议发一封跟进邮件"},
            {"days": 30, "message": "教授 30 天未回复，建议转向其他教授"},
        ],
    },
    "applying": {
        "order": 2,
        "label": "出愿阶段",
        "description": "准备出愿书类、提交申请、缴纳入学检定料",
        "conditions": [
            "至少 1 位教授给内诺或积极回复",
            "研究计划书终稿完成",
            "成绩单、毕业证明、推荐信等书类齐备",
        ],
        "actions": [
            "确认出愿截止日期（4 月入学通常在 前年 10-12 月，9 月入学在 当年 4-6 月）",
            "按募集要项逐项检查书类清单",
            "研究计划书最终修改并请教授/学长审阅",
            "缴纳入学检定料（约 30,000 日元）",
            "邮寄或在线提交出愿材料",
        ],
        "typical_duration_days": 45,
        "next_stages": ["exam", "waiting"],
        "prev_stages": ["contacting"],
        "deadlines": [
            {"label": "4 月入学出愿", "months": [10, 11, 12]},
            {"label": "9 月入学出愿", "months": [4, 5, 6]},
        ],
    },
    "exam": {
        "order": 3,
        "label": "考试阶段",
        "description": "笔试（专业课）+ 面试（研究计划书答辩）",
        "conditions": [
            "出愿材料已提交并通过书类审查",
            "准考证（受験票）已收到",
        ],
        "actions": [
            "复习专业课核心知识（参考过去问）",
            "准备面试：研究计划书 5 分钟概述 + 研究动机 + 方法论",
            "模拟面试 2-3 次",
            "确认考试地点、时间、交通",
        ],
        "typical_duration_days": 30,
        "next_stages": ["waiting"],
        "prev_stages": ["applying"],
    },
    "waiting": {
        "order": 4,
        "label": "等待结果",
        "description": "等待合格通知、办理在留、找房",
        "conditions": [
            "笔试和面试已参加",
        ],
        "actions": [
            "等待合格通知（通常考后 2-4 周）",
            "合格后：办理在留资格认定证明书（COE）",
            "找房、申请宿舍",
            "准备签证材料",
        ],
        "typical_duration_days": 60,
        "next_stages": ["decided"],
        "prev_stages": ["exam"],
    },
    "decided": {
        "order": 5,
        "label": "确定去向",
        "description": "收到结果、办理入学手续",
        "conditions": [],
        "actions": [
            "合格：办理入学手续、缴纳入学金",
            "不合格：回顾申请过程、考虑其他学校或下一期",
        ],
        "typical_duration_days": 0,
        "next_stages": [],
        "prev_stages": ["waiting"],
    },
}


def get_stage(stage_id: str) -> Optional[dict]:
    """Get stage definition by id."""
    return STAGES.get(stage_id)


def get_current_stage_info(application_stage: str) -> dict:
    """Get full stage info for the student's current stage."""
    stage = STAGES.get(application_stage)
    if not stage:
        return {
            "stage": application_stage or "preparing",
            "label": "未开始",
            "progress": 0,
            "actions": ["填写学生背景信息，确定申请目标"],
            "conditions": [],
        }
    total = len(STAGES)
    return {
        **stage,
        "stage_id": application_stage,
        "progress": stage["order"] / max(total - 1, 1),
        "next_stages": stage.get("next_stages", []),
    }


def get_next_actions(application_stage: str) -> List[str]:
    """Get suggested next actions for current stage."""
    info = get_current_stage_info(application_stage)
    return info.get("actions", [])


def advance_stage(current_stage: str, target_stage: str) -> bool:
    """Check if forward transition is valid."""
    stage = STAGES.get(current_stage, {})
    return target_stage in stage.get("next_stages", [])


def can_transition(current_stage: str, target_stage: str) -> bool:
    """Check if any transition (forward or backward) is valid."""
    stage = STAGES.get(current_stage, {})
    return target_stage in stage.get("next_stages", []) or target_stage in stage.get("prev_stages", [])


def get_allowed_stages(current_stage: str) -> dict:
    """Get {next: [...], prev: [...]} allowed transitions from current stage."""
    stage = STAGES.get(current_stage, {})
    return {
        "next": stage.get("next_stages", []),
        "prev": stage.get("prev_stages", []),
    }


def stage_context_for_prompt(application_stage: str) -> str:
    """Generate a context snippet for the LLM system prompt based on stage."""
    info = get_current_stage_info(application_stage)
    if not info.get("stage_id"):
        return ""

    lines = [
        f"\n【申请阶段：{info['label']}】（进度 {info['progress']*100:.0f}%）",
        f"描述：{info.get('description', '')}",
    ]

    conditions = info.get("conditions", [])
    if conditions:
        lines.append("当前阶段条件：")
        for c in conditions:
            lines.append(f"  - {c}")

    actions = info.get("actions", [])
    if actions:
        lines.append("建议行动：")
        for a in actions:
            lines.append(f"  - {a}")

    return "\n".join(lines)


def check_reminders(application_stage: str, stage_started_at: Optional[str] = None) -> List[str]:
    """Check if any reminders are due based on stage and start date."""
    if not stage_started_at:
        return []
    stage = STAGES.get(application_stage, {})
    reminders = stage.get("reminders", [])
    if not reminders:
        return []

    try:
        start = datetime.fromisoformat(stage_started_at)
        elapsed = (datetime.now() - start).days
    except (ValueError, TypeError):
        return []

    due = []
    for r in reminders:
        if elapsed >= r["days"]:
            due.append(r["message"])
    return due


def generate_timeline(stage_id: str, start_date: Optional[str] = None,
                      deadlines: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """Generate a projected timeline. Uses real deadline dates when available."""
    now = datetime.now()

    # ── Try real-date timeline from deadlines ──
    if deadlines:
        # Map deadline keywords to stages
        keyword_stage = {
            "出願": "applying", "出願期間": "applying", "願書": "applying",
            "試験": "exam", "試験日": "exam", "入試": "exam", "筆記": "exam",
            "口述": "exam", "面接": "exam",
            "合格": "waiting", "合格発表": "waiting",
            "入学": "decided", "入学手続": "decided", "手続": "decided",
        }
        # Collect dates per stage
        stage_dates = {}
        items = deadlines.items() if isinstance(deadlines, dict) else ((d.get("name", ""), d.get("date", "")) for d in (deadlines or []))
        for key, val in items:
            for kw, stage in keyword_stage.items():
                if kw in key:
                    # Parse date — try various formats
                    ds = val.strip()
                    try:
                        # "2026-12-15" or "2026-12-10 ~ 2027-01-09"
                        ds = ds.split("~")[0].split("～")[0].strip()
                        ds = ds.replace("年","-").replace("月","-").replace("日","")
                        d = datetime.fromisoformat(ds[:10]) if len(ds) >= 10 else None
                        if d:
                            if stage not in stage_dates or d < stage_dates[stage]:
                                stage_dates[stage] = d
                    except (ValueError, TypeError):
                        continue
                    break

        if stage_dates:
            # Build timeline from real dates
            timeline = []
            ordered = ["preparing", "contacting", "applying", "exam", "waiting", "decided"]
            prev_date = now
            for sid in ordered:
                stage = STAGES.get(sid, {})
                label = stage.get("label", sid)
                if sid in stage_dates:
                    d = stage_dates[sid]
                    timeline.append({
                        "stage": sid, "label": label,
                        "start": prev_date.strftime("%Y-%m-%d"),
                        "end": d.strftime("%Y-%m-%d"),
                        "is_real": True,
                    })
                    prev_date = d
                else:
                    timeline.append({
                        "stage": sid, "label": label,
                        "start": prev_date.strftime("%Y-%m-%d"),
                        "end": "",
                        "is_real": False,
                    })
            return timeline

    # ── Fallback: generic duration-based timeline ──
    if not start_date:
        start_date = now.isoformat()

    try:
        base = datetime.fromisoformat(start_date)
    except (ValueError, TypeError):
        base = now

    timeline = []
    current = base
    for sid, stage in sorted(STAGES.items(), key=lambda x: x[1]["order"]):
        if stage["order"] < STAGES.get(stage_id, {}).get("order", 0):
            continue
        if stage["order"] < 0:  # skip browsing
            continue
        days = stage.get("typical_duration_days", 30)
        end = current + timedelta(days=days)
        timeline.append({
            "stage": sid,
            "label": stage["label"],
            "start": current.strftime("%Y-%m"),
            "end": end.strftime("%Y-%m"),
            "duration_days": days,
        })
        current = end

    return timeline
