#!/bin/bash
cd /c/Users/86158/Documents/PythonProject/Japan-Admission-Agent
echo "=== PHASE 1: Tag Generation ==="
venv/Scripts/python.exe scripts/tag_schools.py
echo "=== PHASE 2: PDF Enrichment ==="
venv/Scripts/python.exe scripts/enrich_pdfs.py
echo "=== PHASE 3: Merge feature branch ==="
git checkout master
git merge feature/ceramic-email-outreach --no-edit
echo "=== PHASE 4: Final Eval ==="
venv/Scripts/python.exe evals/evals.py
echo "=== DONE ==="
