"""
学校数据库：从 Supabase 读写学校数据（graduate_schools 表）。
School Pydantic BaseModel —— 字段映射 graduate_schools 列（含 enrichment 扩展列）。
继承结构：universities → graduate_schools（单表承载全部入学运营数据）
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
from utils.supabase_client import supabase
from utils.logger_handler import logger

TABLE = "graduate_schools"


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


def _to_iso_date(s: str) -> str | None:
    """Convert date string to YYYY-MM-DD. Returns None on failure."""
    if not s:
        return None
    s = s.strip().replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
    if s.count("-") < 1:
        return None
    parts = s.split("-")
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 and parts[1] else 1
        d = int(parts[2]) if len(parts) > 2 and parts[2] else 1
        return f"{y:04d}-{m:02d}-{d:02d}"
    except (ValueError, IndexError):
        return None


def _row_to_school(row: dict) -> Optional[School]:
    """将一行 DB 数据解析为 School 对象。缺失字段用默认值并 warning。

    Pydantic v2 拒绝 str/float/bool/list/dict 字段的 None 值，
    因此需要预先将 DB 中可能为 Null 的字段转化为默认值。
    JSONB 列 (deadlines, english_req) 在 Supabase 返回时可能为 str 而非 list/dict，
    也需要反序列化。
    """
    try:
        # Column mapping: graduate_schools → School model fields
        row = dict(row)
        # name: prefer name_jp (Japanese name is canonical for grad schools)
        if row.get("name_jp"):
            row.setdefault("name", row["name_jp"])
        # exam_type → exam
        if row.get("exam_type") and not row.get("exam"):
            row["exam"] = row["exam_type"]
        # deadlines: already structured JSONB column
        if row.get("deadlines") and isinstance(row.get("deadlines"), list):
            pass  # already structured, no conversion needed

        # Filter to only known model fields, fill missing with defaults
        known_fields = set(School.model_fields.keys())
        filtered = {k: v for k, v in row.items() if k in known_fields}

        # Coerce None to defaults for all optional fields (Pydantic v2 strict)
        for key in list(filtered.keys()):
            val = filtered[key]
            if val is not None:
                continue
            if key == "name":
                # name is required; skip this row
                logger.warning(f"行解析跳过: name 为 None, row={row.get('name', '?')}")
                return None
            # Map each optional field to its Pydantic default
            filtered[key] = {
                "degree": "修士",
                "exam": "",
                "notes": "",
                "source": "manual",
                "updated_at": "",
                "jlpt_min": "",
                "gpa_min": 0.0,
                "verified": False,
                "majors": [],
                "tags": [],
                "deadlines": [],
                "english_req": {"required": False},
            }.get(key, "")

        # Handle JSONB columns that might be stored as JSON strings
        if isinstance(filtered.get("deadlines"), str):
            try:
                filtered["deadlines"] = json.loads(filtered["deadlines"])
            except (json.JSONDecodeError, TypeError):
                filtered["deadlines"] = []

        # Handle old-format deadlines dict -> structured array
        # e.g. {"出願期間":"2026-12-10 ~ 2027-01-09","試験日":"2027年2月"}
        # -> [{"name":"出願期間","start":"2026-12-10","end":"2027-01-09"}, ...]
        if isinstance(filtered.get("deadlines"), dict):
            new_dls = []
            for k, v in filtered["deadlines"].items():
                if not isinstance(v, str) or not v.strip():
                    continue
                v = v.strip()
                entry = {"name": k}
                # Detect range: YYYY-MM-DD ~ YYYY-MM-DD
                range_m = re.match(
                    r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})?\s*[~～]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
                    v
                )
                if range_m:
                    start_raw = range_m.group(1) or range_m.group(2)
                    end_raw = range_m.group(2)
                    start_iso = _to_iso_date(start_raw)
                    end_iso = _to_iso_date(end_raw)
                    if start_iso and end_iso:
                        entry["start"] = start_iso
                        entry["end"] = end_iso
                        new_dls.append(entry)
                        continue
                # Detect single date: YYYY-MM-DD or YYYY年M月D日
                single_m = re.match(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', v)
                if single_m:
                    entry["date"] = f"{int(single_m.group(1)):04d}-{int(single_m.group(2)):02d}-{int(single_m.group(3)):02d}"
                    new_dls.append(entry)
                    continue
                # Fallback: keep raw
                entry["raw"] = v
                new_dls.append(entry)
            filtered["deadlines"] = new_dls

        if isinstance(filtered.get("english_req"), str):
            try:
                filtered["english_req"] = json.loads(filtered["english_req"])
            except (json.JSONDecodeError, TypeError):
                filtered["english_req"] = {"required": False}

        # ── Old -> new field fallback (when DB has not been migrated) ──
        # jlpt (text) -> jlpt_min
        if not filtered.get("jlpt_min"):
            raw_jlpt = row.get("jlpt", "") or ""
            m = re.search(r'N[1-5]', str(raw_jlpt))
            if m:
                filtered["jlpt_min"] = m.group(0)

        # english (text) -> english_req
        if not filtered.get("english_req", {}).get("required"):
            raw_english = row.get("english", "") or ""
            if raw_english:
                text = str(raw_english).strip()
                optional_keywords = ["推奨", "不强制", "不強制", "任意", "不要", "建议"]
                if not any(kw in text for kw in optional_keywords):
                    exam_types = {"TOEFL": r'TOEFL|托福', "TOEIC": r'TOEIC|托业|托業', "IELTS": r'IELTS|雅思'}
                    found = []
                    for ex_name, ex_pat in exam_types.items():
                        if re.search(ex_pat, text, re.IGNORECASE):
                            num_m = re.search(
                                r'(?:' + ex_pat + r')[\s\S]{0,10}?(\d{2,3})', text, re.IGNORECASE
                            )
                            found.append((ex_name, int(num_m.group(1)) if num_m else 0))
                    if found:
                        best = max(found, key=lambda x: x[1])
                        req = {"type": best[0], "required": True}
                        if best[1] > 0:
                            req["min"] = best[1]
                        filtered["english_req"] = req
                    elif re.search(r'TOEFL|TOEIC|IELTS|英語', text, re.IGNORECASE):
                        filtered["english_req"] = {"type": "any", "required": True}

        # gpa (numeric) -> gpa_min
        row_gpa = row.get("gpa")
        if filtered.get("gpa_min", 0.0) == 0.0 and row_gpa:
            try:
                filtered["gpa_min"] = float(row_gpa)
            except (ValueError, TypeError):
                pass

        # Warn about missing required fields
        if not filtered.get("name"):
            logger.warning(f"行解析跳过: 缺少必要字段 name, row={row.get('name', '?')}")
            return None

        return School(**filtered)
    except Exception as e:
        logger.warning(f"行解析失败: {row.get('name', '?')} - {e}")
        return None


_school_cache: list[School] | None = None
_university_cache: dict[str, str] | None = None  # {id: name_jp}


def invalidate_school_cache():
    """Clear cached school data (call after writes)."""
    global _school_cache, _university_cache
    _school_cache = None
    _university_cache = None


def get_all_schools(enriched_only: bool = False) -> list[School]:
    """读取全部学校（缓存），自动拼接大学名 → 研究科名。

    Args:
        enriched_only: 只返回有实质数据的研究科（过滤空壳目录）。
    """
    global _school_cache, _university_cache
    if _school_cache is not None:
        schools = _school_cache
    else:
        try:
            # Batch-load universities for name prefix (also cached)
            if _university_cache is None:
                uni_res = supabase.table("universities").select("id,name_jp").execute()
                _university_cache = {u["id"]: u["name_jp"] for u in uni_res.data}

            res = supabase.table(TABLE).select("*").execute()
            schools = []
            for r in res.data:
                r = dict(r)
                uni_name = _university_cache.get(r.get("university_id", ""), "")
                gs_name = r.get("name_jp") or r.get("name", "")
                if uni_name and gs_name and not gs_name.startswith(uni_name):
                    r["name"] = f"{uni_name} {gs_name}"
                else:
                    r["name"] = gs_name or uni_name

                s = _row_to_school(r)
                if s:
                    schools.append(s)
            _school_cache = schools
            logger.info(f"已加载 {len(schools)} 所学校 (共 {len(res.data)} 行)")
        except Exception as e:
            logger.warning(f"读取学校数据失败 (可能表不存在): {e}")
            return []

    if enriched_only:
        return [s for s in (_school_cache or []) if (
            (s.majors and len(s.majors) > 0) or s.exam or s.notes or s.jlpt_min
        )]
    return _school_cache or []


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
    """Upsert a school into graduate_schools. Maps School fields to DB column names."""
    data = s.model_dump()
    # Map School.exam → DB column exam_type
    if "exam" in data:
        data["exam_type"] = data.pop("exam")
    # updated_at doesn't exist on graduate_schools, use created_at as marker
    # Instead, just upsert by name (graduate_schools has unique constraint on name)
    try:
        # Check if exists
        existing = supabase.table(TABLE).select("id").eq("name_jp", s.name).execute()
        if existing.data:
            supabase.table(TABLE).update(data).eq("id", existing.data[0]["id"]).execute()
            logger.info(f"已更新学校: {s.name}")
        else:
            supabase.table(TABLE).insert(data).execute()
            logger.info(f"已插入学校: {s.name}")
        invalidate_school_cache()
    except Exception as e:
        logger.error(f"保存失败 {s.name}: {e}")
        raise
