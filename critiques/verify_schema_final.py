import os, requests, json, time
from dotenv import load_dotenv
load_dotenv("C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent/.env")
url = os.getenv('SUPABASE_URL'); key = os.getenv('SUPABASE_KEY')
r = requests.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": key, "Content-Type": "application/json"}, json={"email": "test@example.com", "password": "AgentV2_test!"}, timeout=15)
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# C1: schools API exposes new schema fields
s = requests.get("http://localhost:8000/v1/schools", headers=H, timeout=20).json()
first = s["schools"][0]
new_fields = [k for k in ("jlpt_min", "english_req", "deadlines_v2", "verified") if k in first]
print(f"C1 schools total={s['total']}, new fields present: {new_fields}")

# C2: match returns tiered results with english gaps
m = requests.post("http://localhost:8000/v1/match", headers=H, json={}, timeout=30).json()
results = m.get("matches", m if isinstance(m, list) else [])
statuses = {}
eng_gaps = 0
for x in results:
    st = x.get("status", "?")
    statuses[st] = statuses.get(st, 0) + 1
    for g in x.get("gaps", []):
        if g.get("field") in ("english", "英语") and not g.get("met", True):
            eng_gaps += 1
print(f"C2 match results={len(results)}, status tiers={statuses}, english gaps={eng_gaps}")

# C8: plaza CN search regression
c = requests.get("http://localhost:8000/v1/schools?major=计算机", headers=H, timeout=30).json()
print(f"C8 search 计算机: {c['total']} schools")
