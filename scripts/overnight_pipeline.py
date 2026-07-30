"""
Overnight pipeline — runs sequentially:
1. Tag generation (complete remaining untagged schools)
2. PDF enrichment (find real PDF URLs via RAG search)
3. Merge feature branch, run evals

Usage: venv/Scripts/python.exe scripts/overnight_pipeline.py
"""
import os, sys, subprocess, time

STEPS = [
    ("Tag Generation", ["python", "scripts/tag_schools.py"]),
    ("PDF Enrichment", ["python", "scripts/enrich_pdfs.py"]),
    ("Git Merge Feature", ["git", "checkout", "master"]),
    ("Git Merge", ["git", "merge", "feature/ceramic-email-outreach", "--no-edit"]),
    ("Git Merge 2", ["git", "merge", "feature/ceramic-email-outreach"]),
    ("Eval Run", ["python", "evals/evals.py"]),
]

def run_step(name, cmd):
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print(f"CMD: {' '.join(cmd)}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=False, text=True, timeout=7200)
        elapsed = time.time() - t0
        if result.returncode == 0:
            print(f"  OK ({elapsed:.0f}s)")
        else:
            print(f"  FAILED (exit {result.returncode}, {elapsed:.0f}s)")
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT (>{7200}s)")
    except Exception as e:
        print(f"  ERROR: {e}")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for name, cmd in STEPS:
        run_step(name, cmd)
    print("\n🎌 Overnight pipeline complete.")
