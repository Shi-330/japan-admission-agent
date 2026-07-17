"""
学校数据库：从 Supabase 读写学校数据。
School 改为 Pydantic BaseModel，字段与 schools 表新 schema 一一对应。
"""
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
from utils.supabase_client import supabase
from utils.logger_handler import logger

TABLE = "schools"


class School(BaseModel):
    """学校数据模型 — V2 统一 schema"""
    name: str                                    # 唯一键（upsert on_conflict）
    degree: str = "修士"
    majors: list = Field(default_factory=list)   # 展示 + 搜索 + 匹配
    tags: list = Field(default_factory=list)     # 展示 + 搜索
    exam: str = ""                               # 考试形式
    notes: str = ""                              # 内部经验 / 备注

    # ── 匹配引擎硬字段 ──
    jlpt_min: str = ""                           # "N1"/"N2"/"N3"/""（空=不要求）
    gpa_min: float = 0.0                         # 4.0 制，0=不设线
    english_req: dict = Field(default_factory=lambda: {"required": False})  # jsonb

    # ── 结构化 deadlines ──
    deadlines: list = Field(default_factory=list)  # [{"name":"...","date":"..."}, ...]

    # ── 数据治理 ──
    source: str = "manual"                       # official / manual / crawled / imported
    verified: bool = False
    updated_at: str = ""


def _row_to_school(row: dict) -> Optional[School]:
    """将一行 DB 数据解析为 School 对象。缺失字段用默认值并 warning。"""
    try:
        # Filter to only known model fields, fill missing with defaults
        known_fields = set(School.model_fields.keys())
        filtered = {k: v for k, v in row.items() if k in known_fields}
        # Warn about missing critical fields
        for f in ("name",):
            if f not in filtered or not filtered[f]:
                logger.warning(f"行解析跳过: 缺少必要字段 {f}, row={row.get('name', '?')}")
                return None
        return School(**filtered)
    except Exception as e:
        logger.warning(f"行解析失败: {row.get('name', '?')} - {e}")
        return None


def get_all_schools() -> list[School]:
    """读取全部学校。失败返回空列表。"""
    try:
        res = supabase.table(TABLE).select("*").execute()
        schools = []
        for r in res.data:
            s = _row_to_school(r)
            if s:
                schools.append(s)
        logger.info(f"已加载 {len(schools)} 所学校 (共 {len(res.data)} 行)")
        return schools
    except Exception as e:
        logger.warning(f"读取学校数据失败 (可能表不存在): {e}")
        return []


def get_schools_by_major(major: str) -> list[School]:
    """按专业关键词模糊匹配（搜索 majors / name / tags）。"""
    schools = get_all_schools()
    if not major:
        return schools

    # Use cn2jp normalization for cross-language search
    try:
        from utils.cn2jp import normalize
        terms = normalize(major)
    except Exception:
        terms = [major]

    result = []
    for s in schools:
        haystack = " ".join([
            s.name,
            " ".join(s.majors),
            " ".join(s.tags),
        ]).lower()
        if any(t.lower() in haystack for t in terms):
            result.append(s)
    return result


def upsert_school(s: School):
    """写入/更新一所学校。on_conflict='name'，自动更新 updated_at。"""
    data = s.model_dump()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table(TABLE).upsert(data, on_conflict="name").execute()
        logger.info(f"已保存学校: {s.name}")
    except Exception as e:
        logger.error(f"保存失败 {s.name}: {e}")
        raise
