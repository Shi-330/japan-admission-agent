"""Apply V2.2 migration to Supabase user_profiles table."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
print(f"URL: {url}")

supabase = create_client(url, key)

# Check existing columns
resp = supabase.table("user_profiles").select("*").limit(1).execute()
if resp.data:
    existing_cols = list(resp.data[0].keys())
    print(f"Existing columns ({len(existing_cols)}): {existing_cols}")
else:
    print("No rows found, table might be empty or not exist")
    existing_cols = []

# Columns to add
needed = {
    "target_degree": "text",
    "research_area": "text",
    "gpa_score": "float",
    "gpa_scale": "float",
    "facts": "jsonb",
    "events": "jsonb",
    "applications": "jsonb",
    "target_professors": "jsonb",
    "application_stage": "text",
    "field_sources": "jsonb",
}

missing = {k: v for k, v in needed.items() if k not in existing_cols}
print(f"\nMissing columns: {list(missing.keys())}" if missing else "\nAll columns present!")

if missing:
    # Use rpc to execute raw SQL
    # Alternatively try individual ALTER TABLE via REST
    for col, dtype in missing.items():
        default = {
            "jsonb": "'{}'::jsonb",
            "text": "''",
            "float": "0.0",
        }.get(dtype, "''")
        sql = f"ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS {col} {dtype} DEFAULT {default}"
        print(f"  Executing: {sql}")
        try:
            supabase.rpc("", {}).execute()  # This won't work for DDL
        except:
            pass

    print("\nCannot execute DDL via REST API.")
    print("Please run v2_migration.sql in Supabase SQL Editor:")
    print("  https://supabase.com/dashboard/project/fcyfiaihtifyfthcrdep/sql/new")
    print(f"\nSQL file: {Path(__file__).parent / 'v2_migration.sql'}")
