"""Seed the schools table in Supabase with 15 default schools."""
import json, os
from dotenv import load_dotenv
load_dotenv()

from supabase.client import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY not found")
    exit(1)

supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Check existing
existing = supabase_admin.table("schools").select("count", count="exact").execute()
if existing.count > 0:
    print(f"Already {existing.count} schools in DB.")
    resp = input("Clear and re-seed? [y/N] ")
    if resp.lower() != 'y':
        print("Aborted."); exit(0)
    supabase_admin.table("schools").delete().neq("id", 0).execute()

# Inline defaults — single source of truth
SCHOOLS = [
    {"name":"京都大学 情报学研究科","majors":["知能情報学","社会情報学","数理工学","システム科学","通信情報システム","データ科学"],"degree":"修士","jlpt":"N1","english":"TOEFL/TOEIC","exam":"筆記+面接","deadlines":{"出願期間":"2026-12-10 ~ 2027-01-09","試験日":"2027年2月","合格発表":"2027年2月下旬"},"notes":"一般入試+国際プログラム。教授内諾不要。","tags":["情報","筆記","面接","英語必要","国際プログラム"]},
    {"name":"东京科学大学 情報理工学院","majors":["情報工学","数理計算科学"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"筆記(数学+専門)+面接","deadlines":{"A日程出願":"2026年6月","A日程試験":"2026年8月","B日程出願":"2026年11~12月","B日程試験":"2027年1~2月"},"notes":"旧东京工业大学。A/B两轮入试。","tags":["情報","筆記","面接","英語必要"]},
    {"name":"筑波大学 システム情報工学研究群","majors":["情報理工","知能機能システム","エンパワーメント情報学"],"degree":"修士","jlpt":"N2以上","english":"TOEIC/TOEFL/IELTS","exam":"書類+面接(筆記なしの場合も)","deadlines":{"8月選考出願":"2026-07-09~22","8月試験":"2026-08-19~21","1-2月選考出願":"2026-11-30~12-10","1-2月試験":"2027-01-26~28"},"notes":"8月+1-2月两轮。英語スコア必須。","tags":["情報","書類選考","面接","英語必要","筆記なし可能"]},
    {"name":"大阪大学 情報科学研究科","majors":["情報数理学","コンピュータサイエンス","情報システム工学","情報ネットワーク学","マルチメディア工学","バイオ情報工学"],"degree":"修士","jlpt":"N2以上","english":"TOEIC/TOEFL必須","exam":"口頭試問+書類審査","deadlines":{"一般出願":"2026-05-21~23","一般試験":"2026-07-07","留学生夏出願":"2026-06-23~27","留学生冬出願":"2026-10-27~31"},"notes":"6専攻。受入教員の承認印必須。ITSCE英語コース有。","tags":["情報","口頭試問","書類選考","英語必要","英語コース"]},
    {"name":"名古屋大学 情報学研究科","majors":["数理情報学","複雑系科学","社会情報学"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"筆記+面接(専攻による)","deadlines":{"第1回出願":"2026-06-26~07-02","第1回試験":"2026-08-05~06","第2回出願":"2026-12-17~23","第2回試験":"2027年2月"},"notes":"年2回入試。出願前に志望教員に連絡必須。","tags":["情報","筆記","面接","英語必要","事前連絡必須"]},
    {"name":"早稻田大学 基幹理工学研究科","majors":["情報理工","情報通信"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"筆記+面接","deadlines":{"7月入試出願":"2026年5月","7月試験":"2026年7月","2月入試出願":"2026年12月","2月試験":"2027年2月"},"notes":"情報理工学専攻。年2回入試。","tags":["情報","筆記","面接","英語必要"]},
    {"name":"东北大学 情報科学研究科","majors":["情報基礎科学","システム情報科学","人間社会情報科学","応用情報科学"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"筆記+口頭試問","deadlines":{"8月入試出願":"2026年7月","8月試験":"2026年8月","2月入試出願":"2026年12月","2月試験":"2027年2月"},"notes":"4専攻。教授事前連絡推奨。","tags":["情報","筆記","口頭試問","英語必要"]},
    {"name":"东京大学 情報理工学系研究科","majors":["コンピュータ科学","数理情報学","システム情報学","電子情報学","知能機械情報学","創造情報学"],"degree":"修士","jlpt":"N2以上推奨","english":"TOEFL必須(ETS直送)","exam":"筆記(数学+専門)+面接","deadlines":{"夏入試出願":"2026-05-29~06-04","夏試験":"2026年8月","冬入試出願":"2026-11-11~17","冬試験":"2027年1~2月"},"notes":"2026年4月より英語授業化。電子情報学は冬入試廃止。教授内諾必須。","tags":["情報","筆記","面接","英語必須","教授内諾必須","SGU"]},
    {"name":"九州大学 システム情報科学府","majors":["情報理工学","電気電子工学"],"degree":"修士","jlpt":"N2以上推奨","english":"TOEFL/TOEIC/IELTS必須","exam":"筆記(一般)+口述(特別)","deadlines":{"一般選抜出願":"2025-07-07~11","一般試験":"2025年8月","グローバル出願":"2025-07-07~11"},"notes":"2026年度より外国人特別選抜廃止。海外大卒はPSD審査必須。複数教授同時連絡禁止。","tags":["情報","筆記","口頭試問","英語必須","PSD審査","事前連絡必須"]},
    {"name":"北海道大学 情報科学研究院","majors":["情報理工学","エレクトロニクス","生命人間情報科学","メディアネットワーク","システム情報科学"],"degree":"修士","jlpt":"N2以上(日本語選択時)","english":"TOEFL/TOEIC(英語選択時)","exam":"筆記+面接(日英選択可)","deadlines":{"内諾期間":"2025-10-01~12-25","出願期間":"2026-01-05~09","試験":"2026年2月"},"notes":"教授内諾必須(出願前に連絡)。日英いずれか選択して受験可。4月入学のみ。","tags":["情報","筆記","面接","英語必要","教授内諾必須"]},
    {"name":"明治大学 理工学研究科","majors":["情報科学","電気工学","機械工学","応用化学"],"degree":"修士","jlpt":"N2以上","english":"TOEFL 85+/TOEIC 800+","exam":"筆記(専門+外国語)+面接","deadlines":{"I期出願":"2025-06-05~10","I期試験":"2025-07-19","II期出願":"2025-12-01~09","II期試験":"2026-02-25"},"notes":"年2回入試。研究計画書が最重要。事前連絡推奨。","tags":["情報","筆記","面接","英語必要","事前連絡推奨"]},
    {"name":"青山学院大学 理工学研究科","majors":["情報テクノロジー","電気電子工学","機械創造工学"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"筆記+面接","deadlines":{"秋入試出願":"2025年7月","秋試験":"2025年9月","春入試出願":"2026年1月","春試験":"2026年2月"},"notes":"東京渋谷。SGU英語プログラム有。就職に強い。","tags":["情報","筆記","面接","英語必要","SGU","就職"]},
    {"name":"立教大学 人工知能科学研究科","majors":["人工知能科学"],"degree":"修士","jlpt":"N2以上(面接は日本語)","english":"TOEFL/IELTS推奨","exam":"書類+面接(夏)/筆記+面接(秋)","deadlines":{"夏季推薦出願":"2025年6月下旬","夏季面接":"2025年7月","秋季一般出願":"2025年8月中旬","秋季試験":"2025年8~9月"},"notes":"2020年新設のAI専門研究科。池袋。募集63名。AI倫理/社会科学含む融合型カリキュラム。","tags":["情報","AI","書類選考","面接","新設"]},
    {"name":"中央大学 理工学研究科","majors":["情報工学","電気電子情報通信工学","数学"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"筆記(数学+専門)+面接","deadlines":{"夏季出願":"2025年7月","夏季試験":"2025年9月","冬季出願":"2026年1月","冬季試験":"2026年2月"},"notes":"2026年学部再編。後楽園キャンパス。","tags":["情報","筆記","面接","英語必要"]},
    {"name":"法政大学 情報科学研究科","majors":["情報科学","システム工学","応用情報技術"],"degree":"修士","jlpt":"N2以上","english":"TOEFL/TOEIC","exam":"書類+面接","deadlines":{"秋季出願":"2025年8月","秋季試験":"2025年9~10月","春季出願":"2026年1月","春季試験":"2026年2月"},"notes":"小金井キャンパス。独立研究科。産学連携盛ん。面接重視の選抜有。","tags":["情報","書類選考","面接","産学連携"]},
]

print(f"Seeding {len(SCHOOLS)} schools...")
for s in SCHOOLS:
    try:
        row = {"name":s["name"],"majors":s.get("majors",[]),"degree":s.get("degree","修士"),
               "jlpt":s.get("jlpt",""),"english":s.get("english",""),"exam":s.get("exam",""),
               "deadlines":s.get("deadlines",{}),"notes":s.get("notes",""),"tags":s.get("tags",[])}
        supabase_admin.table("schools").insert(row).execute()
        print(f"  OK: {s['name']}")
    except Exception as e:
        print(f"  FAIL: {s['name']} - {e}")

res = supabase_admin.table("schools").select("count", count="exact").execute()
print(f"\nDone. {res.count} schools in DB.")
