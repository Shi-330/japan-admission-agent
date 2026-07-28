"""
Post-enrichment audit: coverage, duplicates, data quality.
Usage: python tests/audit_schools.py
"""
import os, sys
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
from collections import Counter

s = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
r = s.table("schools").select("*").execute()
rows = r.data
print(f"Total schools: {len(rows)}")

# 1. Enrichment status
status = Counter(row["enrichment_status"] for row in rows)
print(f"\n--- Status ---")
for k, v in sorted(status.items()):
    print(f"  {k}: {v}")

# 2. Data quality
has_jlpt = sum(1 for r in rows if r.get("jlpt_min"))
has_english = sum(1 for r in rows if r.get("english_req") and r["english_req"].get("required"))
has_exam = sum(1 for r in rows if r.get("exam"))
has_notes = sum(1 for r in rows if r.get("notes"))
print(f"\n--- Fields ---")
print(f"  JLPT:    {has_jlpt}/{len(rows)}")
print(f"  English: {has_english}/{len(rows)}")
print(f"  Exam:    {has_exam}/{len(rows)}")
print(f"  Notes:   {has_notes}/{len(rows)}")

# 3. Duplicates
names = [r["name"] for r in rows]
dupes = {n: c for n, c in Counter(names).items() if c > 1}
if dupes:
    print(f"\n--- Duplicates ({len(dupes)}) ---")
    for n, c in dupes.items():
        print(f"  {n} x{c}")
else:
    print(f"\n--- Duplicates: 0 ---")

# 4. Skeleton/failed still left
remaining = [r for r in rows if r["enrichment_status"] in ("skeleton", "enriching", "failed")]
if remaining:
    print(f"\n--- Still pending ({len(remaining)}) ---")
    for r in remaining:
        print(f"  [{r['enrichment_status']}] {r['name']}")
else:
    print(f"\n--- All enriched! ---")
