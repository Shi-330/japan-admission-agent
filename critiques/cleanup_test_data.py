"""Clean eval-leftover test data from the test account (apps + dismissed test ids)."""
import os, requests
from dotenv import load_dotenv
load_dotenv("C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent/.env")
url = os.getenv('SUPABASE_URL'); key = os.getenv('SUPABASE_KEY')
r = requests.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": key, "Content-Type": "application/json"}, json={"email": "test@example.com", "password": "AgentV2_test!"}, timeout=15)
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
BASE = "http://localhost:8100"

stage = requests.get(f"{BASE}/v1/stage", headers=H, timeout=20).json()
schools = [a["school"] for a in stage.get("applications", [])]
print("current apps:", schools)

REAL = {"青山学院大学 理工学研究科", "东京科学大学 情報理工学院"}
for s in schools:
    if s not in REAL:
        res = requests.delete(f"{BASE}/v1/applications", headers=H, params={"school": s}, timeout=20)
        print(f"deleted test app '{s}':", res.status_code)

# ack-all then check reminders reflect only real data
requests.post(f"{BASE}/v1/reminders/ack", headers=H, json={"all": True}, timeout=20)
rem = requests.get(f"{BASE}/v1/reminders", headers=H, timeout=20).json()
print("reminders after cleanup+ackall:", rem.get("total"))
