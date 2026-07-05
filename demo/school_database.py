"""
学校数据库：替换硬编码 school_data.py，从 Supabase 读写。
每所学校的数据是真实采集的（手工录入或爬虫），不是 LLM 编的。
"""
from dataclasses import dataclass, asdict
from typing import Optional
from utils.supabase_client import supabase
from utils.logger_handler import logger

TABLE = "schools"


@dataclass
class School:
    name: str                    # "早稻田大学 经济学研究科"
    degree: str = "修士"          # 修士 / 学部 / 博士
    jlpt_min: str = "N2"
    eju_min: int = 0
    eju_subjects: str = ""       # 逗号分隔："日语,数学1"
    gpa_min: float = 0.0
    english_note: str = ""       # "TOEFL iBT 80+"
    deadline_april: str = ""     # "前年10月"
    deadline_september: str = ""
    exam: str = ""               # 考试形式
    capacity: str = ""           # 定员
    notes: str = ""              # 内部经验
    source: str = ""             # 数据来源："crawled" / "manual" / "official"
    target_major: str = ""       # 目标专业关键词："经济学/计算机/社会学"
    verified: bool = False       # 是否已验证


def _row_to_school(row: dict) -> School:
    return School(**{k: v for k, v in row.items() if k in School.__dataclass_fields__})


def get_all_schools() -> list[School]:
    try:
        res = supabase.table(TABLE).select("*").execute()
        return [_row_to_school(r) for r in res.data]
    except Exception as e:
        logger.warning(f"读取学校数据失败 (可能表不存在): {e}")
        return []


def get_schools_by_major(major: str) -> list[School]:
    """按专业关键词模糊匹配"""
    schools = get_all_schools()
    if not major:
        return schools
    # 模糊匹配：专业关键词出现在 school.target_major 或 school.name 中
    result = []
    for s in schools:
        if major in s.target_major or major in s.name:
            result.append(s)
    return result or schools  # fallback: 全返回


def upsert_school(s: School):
    data = asdict(s)
    data.pop("id", None)
    supabase.table(TABLE).upsert(data, on_conflict="name").execute()
    logger.info(f"已保存学校: {s.name}")


def import_from_hardcoded(schools_list: list[dict]):
    """从旧的 school_data.py 硬编码数据批量导入"""
    for raw in schools_list:
        s = School(
            name=raw["name"],
            degree=raw.get("degree", "修士"),
            jlpt_min=raw.get("jlpt_min", "N2"),
            eju_min=raw.get("eju_min", 0),
            eju_subjects=",".join(raw.get("eju_subjects", [])),
            gpa_min=raw.get("gpa_min", 0.0),
            english_note=raw.get("english_note", ""),
            deadline_april=raw.get("deadlines", {}).get("4月入学", ""),
            deadline_september=raw.get("deadlines", {}).get("9月入学", ""),
            exam=raw.get("exam", ""),
            capacity=raw.get("capacity", ""),
            notes=raw.get("notes", ""),
            source="imported",
            target_major=raw.get("name", "").split(" ")[-1].replace("研究科", ""),
            verified=False,
        )
        upsert_school(s)
