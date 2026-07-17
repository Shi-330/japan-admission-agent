"""Run additive-only schema migration against Supabase schools table.

Adds 6 structured columns + deadlines_v2 (NEW column so the old `deadlines`
dict stays untouched — production code keeps working until it is redeployed).
"""
import os
from dotenv import load_dotenv
load_dotenv("C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent/.env")
from supabase.client import create_client

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

STATEMENTS = [
    "ALTER TABLE schools ADD COLUMN IF NOT EXISTS jlpt_min text DEFAULT ''",
    "ALTER TABLE schools ADD COLUMN IF NOT EXISTS gpa_min float8 DEFAULT 0.0",
    """ALTER TABLE schools ADD COLUMN IF NOT EXISTS english_req jsonb DEFAULT '{"required": false}'::jsonb""",
    "ALTER TABLE schools ADD COLUMN IF NOT EXISTS source text DEFAULT 'manual'",
    "ALTER TABLE schools ADD COLUMN IF NOT EXISTS verified bool DEFAULT false",
    "ALTER TABLE schools ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now()",
    # NEW column for structured deadlines; old `deadlines` dict column stays as-is
    "ALTER TABLE schools ADD COLUMN IF NOT EXISTS deadlines_v2 jsonb DEFAULT NULL",
]

for stmt in STATEMENTS:
    try:
        sb.rpc("exec_sql", {"sql": stmt}).execute()
        print("OK:", stmt[:70])
    except Exception as e:
        print("FAIL:", stmt[:70], "->", e)
        raise SystemExit(1)

# Verify columns exist by selecting one row with new fields
res = sb.table("schools").select("name, jlpt_min, gpa_min, english_req, source, verified, updated_at, deadlines_v2").limit(1).execute()
print("verify select OK:", list(res.data[0].keys()) if res.data else "no rows")
