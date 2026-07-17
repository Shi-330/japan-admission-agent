"""
migrate_schools_v2.py — 存量数据转换脚本（一次性，幂等可重跑）。

把 Sprint 3 落库的旧格式行（jlpt/english 文本、deadlines dict）转换为新 schema
（jlpt_min/gpa_min/english_req jsonb、deadlines 数组）。

运行方式：
  1. 先在 Supabase SQL Editor 执行 migrations/schools_v2.sql
  2. venv/Scripts/python.exe migrate_schools_v2.py

幂等：已经转换的行（deadlines 是数组而非 dict）跳过转换字段，仅校验后更新 upated_at。
"""
import json
import re
import os
import sys
from datetime import datetime, timezone, date
from dotenv import load_dotenv

load_dotenv()

# ── Ensure we can import sibling modules ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger_handler import logger
from demo.school_database import School, TABLE

# 写库必须用 service key：anon key 会被 RLS 静默拦截（update 0 行且不报错）
from supabase.client import create_client
_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
if not _service_key:
    print("ERROR: SUPABASE_SERVICE_KEY not found — 迁移需要写权限")
    sys.exit(1)
supabase = create_client(os.environ.get("SUPABASE_URL"), _service_key)

# ── Helpers ──

def _extract_jlpt_min(raw_jlpt: str) -> str:
    """从 jlpt 文本中提取 N1/N2/N3，提取失败返回 ''"""
    if not raw_jlpt:
        return ""
    m = re.search(r'N[1-5]', raw_jlpt)
    return m.group(0) if m else ""


def _extract_english_req(raw_english: str) -> dict:
    """从 english 文本提取 structured english_req。

    规则：
    - 含"推奨/不強制/任意/不要"等 → required: false
    - 纯列举考试类型 → {"type":"any","required":true}
    - 有分数线的提取考试+分数线
    """
    if not raw_english:
        return {"required": False}

    text = raw_english.strip()

    # 不要求
    optional_keywords = ["推奨", "不强制", "不強制", "任意", "不要", "建议"]
    if any(kw in text for kw in optional_keywords):
        return {"required": False}

    # 尝试提取考试类型和分数线
    exam_types = {
        "TOEFL": r'(?:TOEFL|托福)(?:\s*iBT)?',
        "TOEIC": r'(?:TOEIC|托业|托業)',
        "IELTS": r'(?:IELTS|雅思)',
    }
    scores = {}
    for ex_name, ex_pattern in exam_types.items():
        if re.search(ex_pattern, text, re.IGNORECASE):
            # 提取数字
            num_m = re.search(r'(?:' + ex_pattern + r')[\s\S]{0,10}?(\d{2,3})', text, re.IGNORECASE)
            if num_m:
                scores[ex_name] = int(num_m.group(1))
            else:
                scores[ex_name] = 0  # 有考试类型但无具体分数

    if scores:
        # 取分数要求最高的
        max_type = max(scores, key=lambda k: scores[k])
        result = {
            "type": max_type,
            "required": True,
        }
        if scores[max_type] > 0:
            result["min"] = scores[max_type]
        return result

    # 纯列举（"TOEFL/TOEIC"等无分无推奨）→ type:"any"
    if re.search(r'TOEFL|TOEIC|IELTS|英語', text, re.IGNORECASE):
        return {"type": "any", "required": True}

    return {"required": False}


def _parse_deadlines_dict_to_list(old_deadlines) -> list:
    """将旧格式 deadlines dict 转换为结构化数组。

    旧格式: {"出願期間":"2026-12-10 ~ 2027-01-09","試験日":"2027年2月"}
    新格式: [{"name":"出願期間","start":"2026-12-10","end":"2026-12-15"}, ...]
    """
    if isinstance(old_deadlines, list):
        # 已经转换过
        return old_deadlines

    if not isinstance(old_deadlines, dict):
        return []

    result = []
    for name, raw_value in old_deadlines.items():
        if not raw_value or not isinstance(raw_value, str):
            continue
        raw_value = raw_value.strip()
        entry = {"name": name}

        # 尝试解析区间: YYYY-MM-DD ~ YYYY-MM-DD 或 YYYY-MM-DD~YYYY-MM-DD
        range_m = re.match(
            r'(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}?)?\s*[~～]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}?)',
            raw_value
        )
        if range_m:
            start_raw = range_m.group(1) or range_m.group(2)
            end_raw = range_m.group(2)
            start_iso = _to_iso_date(start_raw)
            end_iso = _to_iso_date(end_raw)
            if start_iso and end_iso:
                entry["start"] = start_iso
                entry["end"] = end_iso
                result.append(entry)
                continue

        # 解析单日: YYYY-MM-DD 或 YYYY年M月D日
        single_m = re.match(r'(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?', raw_value)
        if single_m:
            y, m, d = single_m.group(1), single_m.group(2), single_m.group(3)
            entry["date"] = f"{y}-{int(m):02d}-{int(d):02d}"
            result.append(entry)
            continue

        # 解析 YYYY-MM 或 YYYY年M月（→ raw）
        month_m = re.match(r'(\d{4})[-/.年](\d{1,2})月?', raw_value)
        if month_m:
            y, m = month_m.group(1), month_m.group(2)
            entry["date"] = f"{y}-{int(m):02d}-01"
            # 带有"月"等模糊指示，也保留 raw
            entry["raw"] = raw_value
            result.append(entry)
            continue

        # 纯文字（"前年10月"、"当年4月" 等）→ raw
        entry["raw"] = raw_value
        result.append(entry)

    return result


def _to_iso_date(s: str) -> str | None:
    """尝试将各种格式转为 YYYY-MM-DD，失败返回 None。"""
    if not s:
        return None
    s = s.strip().replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
    # 如果只有年份，忽略
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


def _is_expired(entry: dict, today: date) -> bool:
    """检查 deadline 条目是否已过期（date 或 end < 今天）。"""
    for key in ("end", "date"):
        val = entry.get(key)
        if val:
            try:
                dt = datetime.strptime(val[:10], "%Y-%m-%d").date()
                if dt < today:
                    return True
            except (ValueError, IndexError):
                pass
    return False


# ── Main migration ──

def migrate():
    """主迁移逻辑。"""
    today = date.today()
    stats = {"total": 0, "skipped_already": 0, "converted": 0, "raw_fallback": 0, "expired_warn": 0, "errors": 0, "skipped_rows": []}

    try:
        res = supabase.table(TABLE).select("*").execute()
    except Exception as e:
        logger.error(f"读取 schools 表失败: {e}")
        sys.exit(1)

    rows = res.data
    stats["total"] = len(rows)
    logger.info(f"共读取 {len(rows)} 行数据")

    for row in rows:
        name = row.get("name", "?")
        try:
            # 生产兼容：结构化数组写入 deadlines_v2 新列，老 deadlines dict 列原样保留
            # （生产老代码继续读老列；新代码优先读 deadlines_v2）
            if row.get("deadlines_v2"):
                stats["skipped_already"] += 1
                try:
                    School(**row)
                except Exception as ve:
                    logger.warning(f"校验失败 {name}: {ve}")
                continue

            deadlines_raw = row.get("deadlines", {})

            # 转换 deadline 格式
            new_deadlines = _parse_deadlines_dict_to_list(deadlines_raw)

            # 统计过期条目
            expired_entries = [e for e in new_deadlines if _is_expired(e, today)]
            if expired_entries:
                stats["expired_warn"] += len(expired_entries)
                logger.warning(f"过期 deadline: {name} -> {[e['name'] for e in expired_entries]}")

            # 统计 raw 兜底
            raw_entries = [e for e in new_deadlines if "raw" in e and "date" not in e and "start" not in e]
            if raw_entries:
                stats["raw_fallback"] += len(raw_entries)

            # 转换 jlpt
            jlpt_min = _extract_jlpt_min(row.get("jlpt", ""))

            # 转换 english
            english_req = _extract_english_req(row.get("english", ""))

            # 构造更新数据 —— 注意：不碰老 deadlines 列，结构化数组进 deadlines_v2
            updated = {
                "name": name,
                "deadlines_v2": new_deadlines,
                "jlpt_min": jlpt_min,
                "gpa_min": row.get("gpa_min", row.get("gpa", 0.0)) or 0.0,
                "english_req": english_req,
                "source": row.get("source") or "imported",
                "verified": row.get("verified") or False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            # 校验（School 模型按 deadlines 字段校验，这里用转换结果代入）
            try:
                School(**{**row, **updated, "deadlines": new_deadlines})
            except Exception as ve:
                logger.warning(f"校验失败后跳过 {name}: {ve}")
                stats["errors"] += 1
                stats["skipped_rows"].append(name)
                continue

            # 更新到 DB —— schools.name 无 UNIQUE 约束，upsert(on_conflict) 会 42P10，
            # 这里按主键 id 精确 update（行已存在，纯字段更新）
            updated.pop("name", None)
            upd_res = supabase.table(TABLE).update(updated).eq("id", row["id"]).execute()
            if not upd_res.data:
                raise RuntimeError("update 影响 0 行（检查 RLS / service key）")
            stats["converted"] += 1
            logger.info(f"已转换: {name}")

        except Exception as e:
            logger.error(f"转换异常 {name}: {e}")
            stats["errors"] += 1
            stats["skipped_rows"].append(name)

    # 打印统计
    print()
    print("=" * 60)
    print("迁移完成")
    print(f"  总行数:          {stats['total']}")
    print(f"  跳过(已转换):    {stats['skipped_already']}")
    print(f"  新转换:          {stats['converted']}")
    print(f"  raw 兜底条目数:  {stats['raw_fallback']}")
    print(f"  过期条目数:      {stats['expired_warn']}")
    print(f"  错误:            {stats['errors']}")
    if stats["skipped_rows"]:
        print(f"  跳过的学校:      {', '.join(stats['skipped_rows'])}")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
