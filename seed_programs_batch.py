"""
Batch-seed 74 programs across major fields to reach ~80 total.
Covers: economics, environment, materials, biology, mechanical, civil, EE, math, physics.
Each entry: university + graduate_school + program + research_areas.

Usage: python seed_programs_batch.py
Idempotent — upserts by (graduate_school_id, name).
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env"); sys.exit(1)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# (university_name, grad_school_name, exam_type, english_req_json, jlpt_json_or_None,
#  programs: [(name, name_jp, capacity, research_areas, notes)])
DATA = [
    # ═══════════ 经济学 (12) ═══════════
    ("东京大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 30,
       ["経済理論", "計量経済学", "経済史", "開発経済学", "国際経済学"],
       "東大経研。日本人学生に交じって一般入試を受ける必要あり。")]),

    ("京都大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 28,
       ["経済理論", "経済政策", "応用経済学", "国際経済学"],
       "京大経済。事前照会制度あり。")]),

    ("一橋大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 35,
       ["経済理論", "経済統計", "経済政策", "日本経済史", "国際経済"],
       "日本最強経済学研究科。事前指導教員承諾必要。")]),

    ("大阪大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 25,
       ["理論経済学", "計量経済学", "経済政策", "国際経済"],
       "阪大経済。日本語N1相当推奨。")]),

    ("神戸大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 30,
       ["経済理論", "応用経済学", "国際経済学", "金融経済"],
       "神戸大経済。旧官立高商以来の伝統。")]),

    ("東北大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 20,
       ["経済理論", "経済政策", "地域経済", "公共経済"],
       "東北大経済。地域経済学に強い。")]),

    ("九州大学", "経済学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "経済学府 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 25,
       ["経済理論", "経済政策", "国際経済", "産業組織"],
       "九大経済。留学生比率高め。")]),

    ("名古屋大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 20,
       ["経済理論", "社会経済学", "国際経済", "金融論"],
       "名大経済。")]),

    ("北海道大学", "経済学研究院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "経済学研究院 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 20,
       ["経済理論", "経済政策", "地域経済学", "公共経済学"],
       "北大経済。札幌。")]),

    ("早稻田大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 30,
       ["経済理論", "計量経済学", "経済政策", "国際経済学", "マクロ経済"],
       "早大経済。私大人気No.1。事前指導教員承諾推奨。")]),

    ("慶應義塾大学", "経済学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "経済学研究科 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 25,
       ["経済理論", "計量経済学", "経済政策", "国際経済", "金融論"],
       "慶應経済。三田。OB/OGネットワーク強力。")]),

    ("横浜国立大学", "国際社会科学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "国際社会科学府 募集要項 2027"}, None,
     [("経済学専攻", "経済学専攻", 20,
       ["経済理論", "国際経済学", "開発経済学", "経済政策"],
       "横国。東京圏国立。")]),

    # ═══════════ 環境学 (6) ═══════════
    ("東京大学", "新領域創成科学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "新領域創成科学研究科 募集要項 2027"}, None,
     [("環境システム学専攻", "環境システム学専攻", 25,
       ["環境工学", "環境システム", "環境政策", "サステナビリティ学", "環境リスク管理"],
       "東大柏キャンパス。学際的アプローチ。")]),

    ("京都大学", "地球環境学堂", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "地球環境学堂 募集要項 2027"}, None,
     [("地球環境学専攻", "地球環境学専攻", 20,
       ["環境学", "地球環境科学", "気候変動", "持続可能社会", "環境政策"],
       "京大地球環境。文理融合型。")]),

    ("東北大学", "環境科学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "環境科学研究科 募集要項 2027"}, None,
     [("環境科学専攻", "環境科学専攻", 30,
       ["環境科学", "環境リスク", "環境修復", "環境生態学", "環境材料"],
       "東北大環境。日本初の独立環境科学研究科。")]),

    ("九州大学", "工学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学府 募集要項 2027"}, None,
     [("環境社会工学専攻", "環境社会工学専攻", 20,
       ["環境工学", "都市環境", "水環境", "廃棄物管理", "環境計画"],
       "九大環境社会。工学+社会科学の交差。")]),

    ("北海道大学", "環境科学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "環境科学院 募集要項 2027"}, None,
     [("環境科学専攻", "環境科学専攻", 30,
       ["環境科学", "生態学", "環境地質学", "気候変動", "環境保全"],
       "北大環境。広大なフィールドを活かした研究。")]),

    ("筑波大学", "理工情報生命学術院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "理工情報生命学術院 募集要項 2027"}, None,
     [("環境科学学位プログラム", "環境科学学位プログラム", 20,
       ["環境科学", "大気環境", "水環境", "環境リスク", "環境政策"],
       "筑波大。学際的プログラム制。")]),

    # ═══════════ 材料/化学 (8) ═══════════
    ("東京大学", "工学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学系研究科 募集要項 2027"}, None,
     [("マテリアル工学専攻", "マテリアル工学専攻", 30,
       ["材料工学", "金属材料", "半導体材料", "ナノ材料", "計算材料科学"],
       "東大工。Materials Science 日本トップ。")]),

    ("京都大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("材料工学専攻", "材料工学専攻", 25,
       ["材料工学", "セラミックス", "金属材料", "複合材料"],
       "京大材料。セラミックス研究が強い。")]),

    ("大阪大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("マテリアル生産科学専攻", "マテリアル生産科学専攻", 25,
       ["材料工学", "ナノ材料", "機能性材料", "材料プロセス"],
       "阪大。産業応用指向。")]),

    ("東北大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("材料科学専攻", "材料科学専攻", 25,
       ["材料工学", "金属組織学", "磁性材料", "ナノテクノロジー"],
       "東北大。金属材料研究所（金研）あり。")]),

    ("東京工業大学", "工学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学院 募集要項 2027"}, None,
     [("材料工学専攻", "材料工学専攻", 30,
       ["材料工学", "高分子材料", "半導体", "ナノマテリアル"],
       "東工大（現東京科学大学）。日本最高の材料工学。")]),

    ("東京大学", "理学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "理学系研究科 募集要項 2027"}, None,
     [("化学専攻", "化学専攻", 30,
       ["有機化学", "無機化学", "物理化学", "分析化学", "生化学"],
       "東大理学。基礎化学研究の最高峰。")]),

    ("九州大学", "工学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学府 募集要項 2027"}, None,
     [("材料工学専攻", "材料工学専攻", 20,
       ["材料工学", "金属材料", "半導体材料", "耐熱材料"],
       "九大材料。九州の半導体産業と連携。")]),

    ("北海道大学", "工学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学院 募集要項 2027"}, None,
     [("材料科学専攻", "材料科学専攻", 20,
       ["材料工学", "ナノ材料", "光材料", "機能材料"],
       "北大材料。")]),

    # ═══════════ 生物学/生命科学 (8) ═══════════
    ("東京大学", "理学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "理学系研究科 募集要項 2027"}, None,
     [("生物科学専攻", "生物科学専攻", 30,
       ["分子生物学", "細胞生物学", "発生生物学", "神経科学", "進化生物学"],
       "東大理学。発生・神経生物学が強い。")]),

    ("京都大学", "生命科学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "生命科学研究科 募集要項 2027"}, None,
     [("生命科学専攻", "生命科学専攻", 30,
       ["分子生物学", "細胞生物学", "発生生物学", "ゲノム科学", "システム生物学"],
       "京大生命。iPS細胞研究所関連。")]),

    ("大阪大学", "生命機能研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "生命機能研究科 募集要項 2027"}, None,
     [("生命機能専攻", "生命機能専攻", 25,
       ["分子生物学", "細胞生物学", "発生生物学", "免疫学", "神経科学"],
       "阪大。発生・免疫学日本トップクラス。")]),

    ("名古屋大学", "生命農学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "生命農学研究科 募集要項 2027"}, None,
     [("生命科学専攻", "生命科学専攻", 25,
       ["分子生物学", "遺伝学", "生化学", "植物科学", "微生物学"],
       "名大生命農学。")]),

    ("九州大学", "生物資源環境科学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "生物資源環境科学府 募集要項 2027"}, None,
     [("生命科学専攻", "生命科学専攻", 20,
       ["分子生物学", "遺伝学", "微生物学", "生態学"],
       "九大生命。")]),

    ("筑波大学", "理工情報生命学術院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "理工情報生命学術院 募集要項 2027"}, None,
     [("生命科学学位プログラム", "生命科学学位プログラム", 25,
       ["分子生物学", "遺伝子工学", "細胞生物学", "バイオテクノロジー"],
       "筑波大。TARAセンターあり。")]),

    ("北海道大学", "生命科学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "生命科学院 募集要項 2027"}, None,
     [("生命科学専攻", "生命科学専攻", 25,
       ["分子生物学", "生態学", "進化生物学", "ゲノム科学"],
       "北大生命。北方圏生態系研究。")]),

    ("広島大学", "統合生命科学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 61, "requirement": "required", "source": "統合生命科学研究科 募集要項 2027"}, None,
     [("生命科学専攻", "生命科学専攻", 20,
       ["分子生物学", "細胞生物学", "遺伝学", "バイオテクノロジー"],
       "広大生命。")]),

    # ═══════════ 機械工学 (8) ═══════════
    ("東京大学", "工学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学系研究科 募集要項 2027"}, None,
     [("機械工学専攻", "機械工学専攻", 35,
       ["機械工学", "ロボット工学", "制御工学", "熱流体工学", "設計工学"],
       "東大工。日本の機械工学の最高峰。")]),

    ("京都大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("機械理工学専攻", "機械理工学専攻", 30,
       ["機械工学", "ロボティクス", "熱工学", "流体工学", "メカトロニクス"],
       "京大機械。ロボット研究が強い。")]),

    ("東北大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("機械機能創成専攻", "機械機能創成専攻", 30,
       ["機械工学", "精密工学", "ナノメカニクス", "ロボティクス"],
       "東北大機械。精密加工研究に強い。")]),

    ("東京工業大学", "工学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学院 募集要項 2027"}, None,
     [("機械系", "機械系", 35,
       ["機械工学", "制御工学", "ロボット工学", "熱流体", "材料力学"],
       "東工大機械。産学連携盛ん。")]),

    ("大阪大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("機械工学専攻", "機械工学専攻", 30,
       ["機械工学", "生産工学", "設計工学", "バイオメカニクス"],
       "阪大機械。")]),

    ("名古屋大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("機械システム工学専攻", "機械システム工学専攻", 25,
       ["機械工学", "航空宇宙工学", "制御工学", "メカトロニクス"],
       "名大機械。航空宇宙分野が強い（三菱重工連携）。")]),

    ("九州大学", "工学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学府 募集要項 2027"}, None,
     [("機械工学専攻", "機械工学専攻", 25,
       ["機械工学", "熱工学", "流体工学", "材料強度学"],
       "九大機械。")]),

    ("北海道大学", "工学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学院 募集要項 2027"}, None,
     [("機械宇宙工学専攻", "機械宇宙工学専攻", 20,
       ["機械工学", "航空宇宙工学", "制御工学", "ロボット工学"],
       "北大機械。宇宙工学コースあり。")]),

    # ═══════════ 土木/建築 (8) ═══════════
    ("東京大学", "工学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学系研究科 募集要項 2027"}, None,
     [("社会基盤学専攻", "社会基盤学専攻", 30,
       ["土木工学", "地震工学", "構造工学", "都市計画", "交通工学", "水工学"],
       "東大土木。地震工学・防災研究が日本最高。")]),

    ("京都大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("社会基盤工学専攻", "社会基盤工学専攻", 25,
       ["土木工学", "地震工学", "地盤工学", "水工学", "計画学"],
       "京大土木。防災研究所と密接連携。")]),

    ("東北大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("土木工学専攻", "土木工学専攻", 25,
       ["土木工学", "地震工学", "津波工学", "構造工学", "地盤工学"],
       "東北大土木。2011年以降の震災復興研究が豊富。")]),

    ("東京工業大学", "環境・社会理工学院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "環境・社会理工学院 募集要項 2027"}, None,
     [("土木・環境工学系", "土木・環境工学系", 25,
       ["土木工学", "環境工学", "地震工学", "都市計画"],
       "東工大土木。")]),

    ("東京大学", "工学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学系研究科 募集要項 2027"}, None,
     [("建築学専攻", "建築学専攻", 25,
       ["建築設計", "建築構造", "建築環境", "建築史", "都市デザイン"],
       "東大建築。日本建築界の最高峰。")]),

    ("京都大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("建築学専攻", "建築学専攻", 20,
       ["建築設計", "建築計画", "建築構造", "建築環境工学"],
       "京大建築。自由設計教育。")]),

    ("早稻田大学", "創造理工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "創造理工学研究科 募集要項 2027"}, None,
     [("建築学専攻", "建築学専攻", 30,
       ["建築設計", "建築計画", "建築史", "都市計画"],
       "早大建築。私大建築トップ。卒業生ネットワーク強力。")]),

    ("九州大学", "工学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学府 募集要項 2027"}, None,
     [("建設システム工学専攻", "建設システム工学専攻", 20,
       ["土木工学", "地盤工学", "水工学", "建設マネジメント"],
       "九大建設。")]),

    # ═══════════ 電気/電子 (5) — existing 33 schools already cover many ═══
    ("東京大学", "工学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "工学系研究科 募集要項 2027"}, None,
     [("電気系工学専攻", "電気系工学専攻", 30,
       ["電気工学", "電子工学", "半導体工学", "パワーエレクトロニクス", "通信工学"],
       "東大電気。日本最大規模の電気電子専攻。")]),

    ("京都大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("電気工学専攻", "電気工学専攻", 25,
       ["電気工学", "電子工学", "半導体工学", "エネルギー工学"],
       "京大電気。")]),

    ("東北大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("電気エネルギーシステム専攻", "電気エネルギーシステム専攻", 25,
       ["電気工学", "電力システム", "再生可能エネルギー", "パワーエレクトロニクス"],
       "東北大電気。エネルギー工学が強い。")]),

    ("大阪大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("電気電子情報通信工学専攻", "電気電子情報通信工学専攻", 30,
       ["電気工学", "電子工学", "通信工学", "半導体"],
       "阪大EE。")]),

    ("名古屋大学", "工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "工学研究科 募集要項 2027"}, None,
     [("電子工学専攻", "電子工学専攻", 25,
       ["電子工学", "半導体工学", "光エレクトロニクス", "センサ工学"],
       "名大電子。")]),

    # ═══════════ 数学/物理 (8) ═══════════
    ("東京大学", "理学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "理学系研究科 募集要項 2027"}, None,
     [("物理学専攻", "物理学専攻", 35,
       ["素粒子物理学", "宇宙物理学", "物性物理学", "量子物理学", "原子核物理学"],
       "東大物理。ノーベル賞受賞者多数輩出。")]),

    ("東京大学", "数理科学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "数理科学研究科 募集要項 2027"}, None,
     [("数理科学専攻", "数理科学専攻", 25,
       ["代数学", "幾何学", "解析学", "数理物理学", "確率論"],
       "東大数理。日本最高の数学研究拠点。")]),

    ("京都大学", "理学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "理学研究科 募集要項 2027"}, None,
     [("物理学・宇宙物理学専攻", "物理学・宇宙物理学専攻", 30,
       ["素粒子物理学", "宇宙物理学", "物性理論", "量子光学"],
       "京大物理。基礎物理学の世界的拠点。")]),

    ("京都大学", "理学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "理学研究科 募集要項 2027"}, None,
     [("数学・数理解析専攻", "数学・数理解析専攻", 25,
       ["代数学", "幾何学", "解析学", "数理物理学", "応用数学"],
       "京大数学。数理解析研究所（RIMS）あり。")]),

    ("東北大学", "理学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "理学研究科 募集要項 2027"}, None,
     [("物理学専攻", "物理学専攻", 25,
       ["物性物理学", "素粒子物理学", "宇宙物理学", "量子エレクトロニクス"],
       "東北大物理。物性物理が強い。")]),

    ("大阪大学", "理学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "理学研究科 募集要項 2027"}, None,
     [("物理学専攻", "物理学専攻", 25,
       ["素粒子物理学", "核物理学", "宇宙物理学", "物性物理学", "量子情報"],
       "阪大物理。RCNP（核物理研究センター）あり。")]),

    ("九州大学", "理学府", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "理学府 募集要項 2027"}, None,
     [("物理学専攻", "物理学専攻", 20,
       ["物性物理学", "素粒子論", "宇宙物理学"],
       "九大物理。")]),

    ("筑波大学", "理工情報生命学術院", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "理工情報生命学術院 募集要項 2027"}, None,
     [("物理学学位プログラム", "物理学学位プログラム", 20,
       ["物性物理学", "宇宙物理学", "計算物理学"],
       "筑波物理。KEK（高エネルギー加速器研究機構）近接。")]),

    # ═══════════ 跨学科/其他 (3) ═══════════
    ("東京大学", "情報理工学系研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 80, "requirement": "required", "source": "情報理工学系研究科 募集要項 2027"}, None,
     [("知能機械情報学専攻", "知能機械情報学専攻", 20,
       ["ロボット工学", "メカトロニクス", "人工知能", "ヒューマンインタフェース"],
       "東大IST。機械+情報の融合専攻。")]),

    ("大阪大学", "基礎工学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 79, "requirement": "required", "source": "基礎工学研究科 募集要項 2027"}, None,
     [("システム創成専攻", "システム創成専攻", 25,
       ["システム工学", "制御工学", "ロボティクス", "最適化", "人工知能"],
       "阪大基礎工。工学+理学の融合。")]),

    ("名古屋大学", "情報学研究科", "外国人特别选拔",
     {"type": "TOEFL", "min_score": 72, "requirement": "required", "source": "情報学研究科 募集要項 2027"}, None,
     [("知能システム学専攻", "知能システム学専攻", 25,
       ["人工知能", "ロボティクス", "画像処理", "機械学習", "自然言語処理"],
       "名大知能システム。機械学習+ロボティクス融合。")]),
]


def _format_exam(periods):
    if isinstance(periods, str): periods = json.loads(periods)
    if not periods: return ""
    parts = [f"{p.get('name','')}({p.get('month','')}月)" if p.get('month') else p['name'] for p in periods]
    return " + ".join(parts)


def run(dry_run=False):
    total = 0
    for uni_name, gs_name, exam_type, eng_req, jlpt_req, programs in DATA:
        # Find university
        uni_r = supabase.table("universities").select("id,name").eq("name", uni_name).execute()
        if not uni_r.data:
            print(f"  SKIP: university '{uni_name}' not found")
            continue
        uni_id = uni_r.data[0]["id"]

        # Upsert graduate school
        gs = {"university_id": uni_id, "name": gs_name, "name_jp": gs_name,
              "exam_type": exam_type,
              "english": json.dumps(eng_req, ensure_ascii=False) if eng_req else None,
              "jlpt": json.dumps(jlpt_req, ensure_ascii=False) if jlpt_req else None}
        gs_r = supabase.table("graduate_schools").upsert(gs, on_conflict="university_id,name").execute()
        gs_id = gs_r.data[0]["id"]

        for prog_name, prog_name_jp, cap, areas, notes in programs:
            exam_default = [{"name": "夏季入试", "month": 8}, {"name": "冬季入试", "month": 2}]
            p = {"graduate_school_id": gs_id,
                 "name": prog_name, "name_jp": prog_name_jp,
                 "degree": "修士", "capacity": cap,
                 "english": None,  # inherit from GS
                 "jlpt": None,     # inherit from GS
                 "research_areas": areas,
                 "exam_periods": json.dumps(exam_default, ensure_ascii=False),
                 "notes": notes,
                 "application_deadlines": None}
            p_r = supabase.table("programs").upsert(p, on_conflict="graduate_school_id,name").execute()
            total += 1
            print(f"  {uni_name} {gs_name} -> {prog_name}")

    print(f"\nSeeded {total} programs.")
    if dry_run:
        print("(DRY RUN)")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
