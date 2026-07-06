"""Add 5 schools via local API (urllib, no httpx dependency)."""
import json, urllib.request, os, sys
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def api(method, path, body=None, timeout=30):
    req = urllib.request.Request(
        f"http://localhost:8000{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

# Step 1: Login
req = urllib.request.Request(
    f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
    data=json.dumps({"email":"test@example.com","password":"AgentV2_test!"}).encode(),
    headers={"Content-Type":"application/json","apikey":SUPABASE_KEY},
)
with urllib.request.urlopen(req, timeout=10) as resp:
    TOKEN = json.loads(resp.read())["access_token"]
print(f"Logged in: {TOKEN[:20]}...")

# Step 2: Add schools one by one
schools = [
    {
        "school": "京都大学 情报理工",
        "stage": "preparing",
        "needs_contact": True,
        "deadlines": {"出願期間":"2026-12-10 ~ 2027-01-09","試験日":"2027年2月","合格発表":"2027年2月下旬","検定料":"30000円"},
        "notes": "知能情報学/社会情報学/数理工学/システム科学/通信情報/データ科学。一般+国際プログラム。"
    },
    {
        "school": "东京科学大学 情报理工",
        "stage": "preparing",
        "needs_contact": True,
        "deadlines": {"出願(A日程)":"2026年6月","試験(A)":"2026年8月","出願(B日程)":"2026年11~12月","試験(B)":"2027年1~2月"},
        "notes": "旧东京工业大学。情報理工学院。笔記(数学+専門)+面接。"
    },
    {
        "school": "筑波大学 情报理工",
        "stage": "preparing",
        "needs_contact": True,
        "deadlines": {"出願(8月)":"2026-07-09~07-22","試験(8月)":"2026-08-19~21","出願(1-2月)":"2026-11-30~12-10","試験(1-2月)":"2027-01-26~28"},
        "notes": "システム情報工学研究群。書類+面接。英語スコア要。"
    },
    {
        "school": "大阪大学 情报科学",
        "stage": "preparing",
        "needs_contact": True,
        "deadlines": {"出願(一般)":"2026-05-21~23","試験(一般)":"2026-07-07","出願(留学生夏)":"2026-06-23~27","出願(留学生冬)":"2026-10-27~31"},
        "notes": "情報科学研究科。要TOEIC/TOEFL。受入教員の承認印必須。"
    },
    {
        "school": "名古屋大学 情报学",
        "stage": "preparing",
        "needs_contact": True,
        "deadlines": {"出願(第1回)":"2026-06-26~07-02","試験(第1回)":"2026-08-05~06","出願(第2回)":"2026-12-17~23","試験(第2回)":"2027年2月"},
        "notes": "情報学研究科。数理情報学/複雑系科学/社会情報学。志望教員に事前連絡必須。"
    },
]

for s in schools:
    try:
        r = api("POST", "/v1/applications", s, timeout=30)
        print(f"OK: {s['school']}")
    except Exception as e:
        print(f"FAIL: {s['school']} - {e}")

# Step 3: Verify
try:
    r = api("GET", "/v1/stage", timeout=10)
    apps = r.get("applications", [])
    print(f"\nTotal: {len(apps)} schools tracked")
    for a in apps:
        print(f"  {a['school']} [{a['label']}]")
        for k, v in a.get("deadlines", {}).items():
            print(f"    {k}: {v}")
except Exception as e:
    print(f"Verify failed: {e}")
