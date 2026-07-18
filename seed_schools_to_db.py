"""Seed the schools table in Supabase with the new V2 schema.

幂等 upsert: 重跑行数不变，updated_at 更新。
"""
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from demo.school_database import School, upsert_school
from utils.logger_handler import logger

# ── Inline defaults — single source of truth ──
# Each entry matches the V2 schema:
# name, degree, majors, tags, exam, notes,
# jlpt_min, gpa_min, english_req,
# deadlines (structured array), source, verified
SCHOOLS = [
    {
        "name": "京都大学 情报学研究科",
        "degree": "修士",
        "majors": ["知能情報学", "社会情報学", "数理工学", "システム科学", "通信情報システム", "データ科学"],
        "tags": ["情報", "筆記", "面接", "英語必要", "国際プログラム"],
        "exam": "筆記+面接",
        "notes": "一般入試+国際プログラム。教授内諾不要。",
        "jlpt_min": "N1",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "出願期間", "start": "2026-12-10", "end": "2027-01-09", "round": "冬"},
            {"name": "試験日", "raw": "2027年2月"},
            {"name": "合格発表", "raw": "2027年2月下旬"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "东京科学大学 情報理工学院",
        "degree": "修士",
        "majors": ["情報工学", "数理計算科学"],
        "tags": ["情報", "筆記", "面接", "英語必要"],
        "exam": "筆記(数学+専門)+面接",
        "notes": "旧东京工业大学。A/B两轮入试。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "any", "required": True},
        "deadlines": [
            {"name": "A日程出願", "raw": "2026年6月"},
            {"name": "A日程試験", "raw": "2026年8月"},
            {"name": "B日程出願", "raw": "2026年11~12月"},
            {"name": "B日程試験", "raw": "2027年1~2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "筑波大学 システム情報工学研究群",
        "degree": "修士",
        "majors": ["情報理工", "知能機能システム", "エンパワーメント情報学"],
        "tags": ["情報", "書類選考", "面接", "英語必要", "筆記なし可能"],
        "exam": "書類+面接(筆記なしの場合も)",
        "notes": "8月+1-2月两轮。英語スコア必須。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "8月選考出願", "start": "2026-07-09", "end": "2026-07-22"},
            {"name": "8月試験", "start": "2026-08-19", "end": "2026-08-21"},
            {"name": "1-2月選考出願", "start": "2026-11-30", "end": "2026-12-10"},
            {"name": "1-2月試験", "start": "2027-01-26", "end": "2027-01-28"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "大阪大学 情報科学研究科",
        "degree": "修士",
        "majors": ["情報数理学", "コンピュータサイエンス", "情報システム工学", "情報ネットワーク学", "マルチメディア工学", "バイオ情報工学"],
        "tags": ["情報", "口頭試問", "書類選考", "英語必要", "英語コース"],
        "exam": "口頭試問+書類審査",
        "notes": "6専攻。受入教員の承認印必須。ITSCE英語コース有。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "一般出願", "start": "2026-05-21", "end": "2026-05-23"},
            {"name": "一般試験", "date": "2026-07-07"},
            {"name": "留学生夏出願", "start": "2026-06-23", "end": "2026-06-27"},
            {"name": "留学生冬出願", "start": "2026-10-27", "end": "2026-10-31"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "名古屋大学 情報学研究科",
        "degree": "修士",
        "majors": ["数理情報学", "複雑系科学", "社会情報学"],
        "tags": ["情報", "筆記", "面接", "英語必要", "事前連絡必須"],
        "exam": "筆記+面接(専攻による)",
        "notes": "年2回入試。出願前に志望教員に連絡必須。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "第1回出願", "start": "2026-06-26", "end": "2026-07-02"},
            {"name": "第1回試験", "date": "2026-08-05"},
            {"name": "第2回出願", "start": "2026-12-17", "end": "2026-12-23"},
            {"name": "第2回試験", "raw": "2027年2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "早稻田大学 基幹理工学研究科",
        "degree": "修士",
        "majors": ["情報理工", "情報通信"],
        "tags": ["情報", "筆記", "面接", "英語必要"],
        "exam": "筆記+面接",
        "notes": "情報理工学専攻。年2回入試。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "7月入試出願", "raw": "2026年5月"},
            {"name": "7月試験", "raw": "2026年7月"},
            {"name": "2月入試出願", "raw": "2026年12月"},
            {"name": "2月試験", "raw": "2027年2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "东北大学 情報科学研究科",
        "degree": "修士",
        "majors": ["情報基礎科学", "システム情報科学", "人間社会情報科学", "応用情報科学"],
        "tags": ["情報", "筆記", "口頭試問", "英語必要"],
        "exam": "筆記+口頭試問",
        "notes": "4専攻。教授事前連絡推奨。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "8月入試出願", "raw": "2026年7月"},
            {"name": "8月試験", "raw": "2026年8月"},
            {"name": "2月入試出願", "raw": "2026年12月"},
            {"name": "2月試験", "raw": "2027年2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "东京大学 情報理工学系研究科",
        "degree": "修士",
        "majors": ["コンピュータ科学", "数理情報学", "システム情報学", "電子情報学", "知能機械情報学", "創造情報学"],
        "tags": ["情報", "筆記", "面接", "英語必須", "教授内諾必須", "SGU"],
        "exam": "筆記(数学+専門)+面接",
        "notes": "2026年4月より英語授業化。電子情報学は冬入試廃止。教授内諾必須。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "min": 80, "required": True},
        "deadlines": [
            {"name": "夏入試出願", "start": "2026-05-29", "end": "2026-06-04"},
            {"name": "夏試験", "raw": "2026年8月"},
            {"name": "冬入試出願", "start": "2026-11-11", "end": "2026-11-17"},
            {"name": "冬試験", "raw": "2027年1~2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "九州大学 システム情報科学府",
        "degree": "修士",
        "majors": ["情報理工学", "電気電子工学"],
        "tags": ["情報", "筆記", "口頭試問", "英語必須", "PSD審査", "事前連絡必須"],
        "exam": "筆記(一般)+口述(特別)",
        "notes": "2026年度より外国人特別選抜廃止。海外大卒はPSD審査必須。複数教授同時連絡禁止。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "一般選抜出願", "start": "2025-07-07", "end": "2025-07-11"},
            {"name": "一般試験", "raw": "2025年8月"},
            {"name": "グローバル出願", "start": "2025-07-07", "end": "2025-07-11"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "北海道大学 情報科学研究院",
        "degree": "修士",
        "majors": ["情報理工学", "エレクトロニクス", "生命人間情報科学", "メディアネットワーク", "システム情報科学"],
        "tags": ["情報", "筆記", "面接", "英語必要", "教授内諾必須"],
        "exam": "筆記+面接(日英選択可)",
        "notes": "教授内諾必須(出願前に連絡)。日英いずれか選択して受験可。4月入学のみ。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "内諾期間", "start": "2025-10-01", "end": "2025-12-25"},
            {"name": "出願期間", "start": "2026-01-05", "end": "2026-01-09"},
            {"name": "試験", "raw": "2026年2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "明治大学 理工学研究科",
        "degree": "修士",
        "majors": ["情報科学", "電気工学", "機械工学", "応用化学"],
        "tags": ["情報", "筆記", "面接", "英語必要", "事前連絡推奨"],
        "exam": "筆記(専門+外国語)+面接",
        "notes": "年2回入試。研究計画書が最重要。事前連絡推奨。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "min": 85, "required": True},
        "deadlines": [
            {"name": "I期出願", "start": "2025-06-05", "end": "2025-06-10"},
            {"name": "I期試験", "date": "2025-07-19"},
            {"name": "II期出願", "start": "2025-12-01", "end": "2025-12-09"},
            {"name": "II期試験", "date": "2026-02-25"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "青山学院大学 理工学研究科",
        "degree": "修士",
        "majors": ["情報テクノロジー", "電気電子工学", "機械創造工学"],
        "tags": ["情報", "筆記", "面接", "英語必要", "SGU", "就職"],
        "exam": "筆記+面接",
        "notes": "東京渋谷。SGU英語プログラム有。就職に強い。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "秋入試出願", "raw": "2025年7月"},
            {"name": "秋試験", "raw": "2025年9月"},
            {"name": "春入試出願", "raw": "2026年1月"},
            {"name": "春試験", "raw": "2026年2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "立教大学 人工知能科学研究科",
        "degree": "修士",
        "majors": ["人工知能科学"],
        "tags": ["情報", "AI", "書類選考", "面接", "新設"],
        "exam": "書類+面接(夏)/筆記+面接(秋)",
        "notes": "2020年新設のAI専門研究科。池袋。募集63名。AI倫理/社会科学含む融合型カリキュラム。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"required": False},
        "deadlines": [
            {"name": "夏季推薦出願", "raw": "2025年6月下旬"},
            {"name": "夏季面接", "raw": "2025年7月"},
            {"name": "秋季一般出願", "raw": "2025年8月中旬"},
            {"name": "秋季試験", "raw": "2025年8~9月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "中央大学 理工学研究科",
        "degree": "修士",
        "majors": ["情報工学", "電気電子情報通信工学", "数学"],
        "tags": ["情報", "筆記", "面接", "英語必要"],
        "exam": "筆記(数学+専門)+面接",
        "notes": "2026年学部再編。後楽園キャンパス。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "夏季出願", "raw": "2025年7月"},
            {"name": "夏季試験", "raw": "2025年9月"},
            {"name": "冬季出願", "raw": "2026年1月"},
            {"name": "冬季試験", "raw": "2026年2月"}
        ],
        "source": "official",
        "verified": True,
    },
    {
        "name": "法政大学 情報科学研究科",
        "degree": "修士",
        "majors": ["情報科学", "システム工学", "応用情報技術"],
        "tags": ["情報", "書類選考", "面接", "産学連携"],
        "exam": "書類+面接",
        "notes": "小金井キャンパス。独立研究科。産学連携盛ん。面接重視の選抜有。",
        "jlpt_min": "N2",
        "gpa_min": 0.0,
        "english_req": {"type": "TOEFL", "required": True},
        "deadlines": [
            {"name": "秋季出願", "raw": "2025年8月"},
            {"name": "秋季試験", "raw": "2025年9~10月"},
            {"name": "春季出願", "raw": "2026年1月"},
            {"name": "春季試験", "raw": "2026年2月"}
        ],
        "source": "official",
        "verified": True,
    },
]


def main():
    print(f"Seeding {len(SCHOOLS)} schools (V2 schema)...")
    success = 0
    fail = 0
    for row in SCHOOLS:
        try:
            s = School(**row)
            upsert_school(s)
            print(f"  OK: {s.name}")
            success += 1
        except Exception as e:
            print(f"  FAIL: {row.get('name', '?')} - {e}")
            fail += 1

    print(f"\nDone. {success} OK, {fail} FAIL")

    # Index schools into vector store for hybrid search (V2.4)
    print("\nIndexing schools for hybrid search...")
    try:
        from demo.school_search import index_schools
        index_schools(clear_first=True)
    except Exception as e:
        print(f"  School indexing skipped: {e}")


if __name__ == "__main__":
    main()
