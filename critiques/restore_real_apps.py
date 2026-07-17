"""Restore the user's real applications + one realistic overdue professor for acceptance testing."""
import os, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv("C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent/.env")
url = os.getenv('SUPABASE_URL'); key = os.getenv('SUPABASE_KEY')
r = requests.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": key, "Content-Type": "application/json"}, json={"email": "test@example.com", "password": "AgentV2_test!"}, timeout=15)
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
BASE = "http://localhost:8100"

overdue_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
apps = [
    {"school": "青山学院大学 理工学研究科", "stage": "contacting",
     "professors": [{"name": "田中太郎", "status": "sent", "date": overdue_date}],
     "deadlines": {"秋入試出願": "2026-07-25"}},
    {"school": "东京科学大学 情報理工学院", "stage": "preparing"},
]
for a in apps:
    res = requests.post(f"{BASE}/v1/applications", headers=H, json=a, timeout=20)
    print(f"restored '{a['school']}':", res.status_code)

rem = requests.get(f"{BASE}/v1/reminders", headers=H, timeout=20).json()
print("reminders now:", rem.get("total"))
for x in rem.get("reminders", []):
    print(" -", x.get("type"), "|", x.get("message", "")[:60], "| action:", (x.get("action") or {}).get("type"))
