import os, json
from dotenv import load_dotenv
load_dotenv("C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent/.env")
from supabase.client import create_client
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

rows = sb.table("schools").select("name, jlpt, jlpt_min, english_req, deadlines, deadlines_v2, verified").limit(3).execute().data
for r in rows:
    print("school:", r["name"][:20])
    print("  jlpt(old):", r["jlpt"], "| jlpt_min(new):", repr(r["jlpt_min"]))
    print("  english_req:", r["english_req"])
    print("  deadlines(old,should be dict):", type(r["deadlines"]).__name__, str(r["deadlines"])[:60])
    print("  deadlines_v2(new,should be list):", type(r["deadlines_v2"]).__name__, str(r["deadlines_v2"])[:80])

n_v2 = sb.table("schools").select("count", count="exact").not_.is_("deadlines_v2", "null").execute().count
n_jlpt = sb.table("schools").select("count", count="exact").neq("jlpt_min", "").execute().count
print(f"\nrows with deadlines_v2: {n_v2}/33, rows with jlpt_min: {n_jlpt}/33")
