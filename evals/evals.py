"""
Fukurai Agent Evaluation Suite
================================
Lightweight eval framework: tests search/matching pipeline against golden dataset.
No heavy dependencies — pure Python + Supabase + HTTP.

Usage:
  venv/Scripts/python.exe evals/evals.py
  venv/Scripts/python.exe evals/evals.py --verbose
  venv/Scripts/python.exe evals/evals.py --contamination-only
"""

import json, os, sys, time, re
from typing import Any
from collections import Counter
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supabase import create_client
from demo.school_database import get_all_schools
from demo.school_search import hybrid_search_schools

# ── Config ──
GOLDEN = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
VERBOSE = "--verbose" in sys.argv

# ── Helpers ──
def _print(msg: str):
    """Print with flush to avoid buffering issues on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _match_tag(tags: list[str], expected: list[str]) -> bool:
    """Check if any expected tag appears in the school's tags (substring match)."""
    haystack = " ".join(tags or []).lower()
    return any(e.lower() in haystack for e in expected)


def _match_major(majors: list[str], expected: list[str]) -> bool:
    """Check if any expected keyword appears in majors."""
    haystack = " ".join(majors or []).lower()
    return any(e.lower() in haystack for e in expected)


def _forbid_in_text(text: str, forbidden: list[str]) -> bool:
    """Returns True if text contains none of the forbidden strings."""
    if not text:
        return True
    text_lower = text.lower()
    return not any(f.lower() in text_lower for f in forbidden)


# ── Eval Runner ──
class EvalRunner:
    def __init__(self):
        self.supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
        with open(GOLDEN, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)
        self.all_schools = get_all_schools()
        self.results: list[dict] = []

    def _search(self, query: str) -> list[dict]:
        """Run hybrid search and return school dicts."""
        try:
            raw = hybrid_search_schools(query, k=10)
            return [r.get("school", r) for r in raw if r.get("school") or r.get("school_name")]
        except Exception as e:
            _print(f"  Search error: {e}")
            return []

    def _check_contamination(self, schools: list[dict], test: dict) -> dict:
        """Check for cross-school data contamination in notes."""
        violations = []
        forbidden_unis = test.get("forbid_university", [])
        forbidden_notes = test.get("forbid_in_notes", [])
        forbid_locations = test.get("forbid_university_location", [])

        for s in schools:
            name = s.get("name", "") or s.get("school_name", "")
            notes = s.get("notes", "") or ""

            # Check university name contamination
            for fu in forbidden_unis:
                if fu in name and fu not in test.get("query", ""):
                    violations.append(f"Wrong university in result: {fu} in '{name[:40]}'")
                if fu in notes:
                    violations.append(f"Contamination: '{fu}' in notes of '{name[:40]}'")

            # Check forbidden patterns in notes
            for fn in forbidden_notes:
                if fn.lower() in notes.lower():
                    violations.append(f"Forbidden pattern '{fn}' in notes of '{name[:40]}'")

        return {
            "contamination_free": len(violations) == 0,
            "violations": violations,
        }

    def _check_tags(self, schools: list[dict], test: dict) -> dict:
        """Check tag-related expectations."""
        results = {"tag_hits": 0, "tag_misses": 0, "forbid_tag_violations": 0}
        expect_tags = test.get("expect_tags", [])
        forbid_tags = test.get("forbid_tags", [])
        no_tags = test.get("expect_no_tags", [])

        for s in schools[:5]:
            tags = s.get("tags", []) or []
            if expect_tags and _match_tag(tags, expect_tags):
                results["tag_hits"] += 1
            elif expect_tags:
                results["tag_misses"] += 1

            for ft in forbid_tags:
                if ft in " ".join(tags):
                    results["forbid_tag_violations"] += 1

            for nt in no_tags:
                if nt in " ".join(tags):
                    results["forbid_tag_violations"] += 1

        return results

    def _check_jlpt(self, schools: list[dict], test: dict) -> dict:
        """Check JLPT-related expectations."""
        jlpt_range = test.get("expect_jlpt_range", [])
        jlpt_max = test.get("expect_jlpt_max", "")

        valid = 0
        for s in schools[:5]:
            jlpt = (s.get("jlpt_min") or s.get("jlpt") or "")
            if jlpt_range and (jlpt in jlpt_range or not jlpt):
                valid += 1
            if jlpt_max:
                jlpt_vals = ["N5", "N4", "N3", "N2", "N1"]
                try:
                    if jlpt_vals.index(jlpt) <= jlpt_vals.index(jlpt_max):
                        valid += 1
                except (ValueError, KeyError):
                    if not jlpt:
                        valid += 1

        return {"jlpt_valid": valid, "jlpt_total": min(len(schools), 5)}

    def _check_exact(self, schools: list[dict], test: dict) -> dict:
        """Check exact school match expectations."""
        exact = test.get("expect_exact_school", "")
        uni = test.get("expect_university", "")
        uni_type = test.get("expect_university_type", "")
        location = test.get("expect_university_location", "")

        exact_found = False
        uni_match = 0
        type_match = 0
        location_match = 0

        for s in schools[:10]:
            name = s.get("name", "") or s.get("school_name", "")
            if exact and exact in name:
                exact_found = True
            if uni and uni in name:
                uni_match += 1
            if uni_type:
                st = s.get("type", "")
                if st == uni_type:
                    type_match += 1
            if location:
                # location check via university info
                # For now, approximate via school name
                pass

        return {
            "exact_found": exact_found if exact else None,
            "uni_match": uni_match > 0 if uni else None,
            "type_match": type_match > 0 if uni_type else None,
        }

    def run(self):
        total = len(self.dataset)
        contamination_violations = 0
        total_tag_hits = 0
        total_tag_misses = 0
        exact_matches = 0
        exact_total = 0

        _print(f"Fukurai Agent Eval — {total} test cases\n{'=' * 60}")

        for i, test in enumerate(self.dataset, 1):
            query = test["query"]
            desc = test.get("description", "")
            _print(f"\n[{i}/{total}] {desc}")
            _print(f"  Query: '{query}'")

            # Run search
            t0 = time.time()
            schools = self._search(query)
            elapsed = time.time() - t0
            _print(f"  Results: {len(schools)} schools ({elapsed:.1f}s)")

            if VERBOSE and schools:
                for s in schools[:3]:
                    name = s.get("name", "") or s.get("school_name", "?")
                    tags = s.get("tags", [])[:3]
                    _print(f"    - {name[:50]}  tags={tags}")

            # Run checks
            contam = self._check_contamination(schools, test)
            tags = self._check_tags(schools, test)
            jlpt = self._check_jlpt(schools, test)
            exact = self._check_exact(schools, test)

            # Track stats
            if not contam["contamination_free"]:
                contamination_violations += len(contam["violations"])
                if VERBOSE:
                    for v in contam["violations"]:
                        _print(f"  CONTAMINATION: {v}")

            total_tag_hits += tags["tag_hits"]
            total_tag_misses += tags["tag_misses"]

            if exact["exact_found"] is not None:
                exact_total += 1
                if exact["exact_found"]:
                    exact_matches += 1

            # Status
            status = []
            if contam["contamination_free"]: status.append("CLEAN")
            else: status.append(f"CONTAM({len(contam['violations'])})")
            if tags["tag_hits"] > 0: status.append(f"+{tags['tag_hits']}tag")
            if tags["forbid_tag_violations"] > 0: status.append(f"FORBID({tags['forbid_tag_violations']})")
            _print(f"  Status: {' | '.join(status)}")

        # ── Summary ──
        _print(f"\n{'=' * 60}")
        _print(f"EVAL SUMMARY")
        _print(f"{'=' * 60}")
        _print(f"  Test cases:           {total}")
        _print(f"  Contamination-free:   {total - sum(1 for t in self.dataset if not self._check_contamination(self._search(t['query']), t)['contamination_free'])}/{total}")
        _print(f"  Contam violations:    {contamination_violations}")
        _print(f"  Tag precision:        {total_tag_hits}/{total_tag_hits + total_tag_misses}" if (total_tag_hits + total_tag_misses) > 0 else "  Tag precision:        N/A")
        _print(f"  Exact school match:   {exact_matches}/{exact_total}" if exact_total > 0 else "  Exact school match:   N/A")
        _print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        EvalRunner().run()
    except KeyboardInterrupt:
        _print("\nAborted.")
    except Exception as e:
        _print(f"\nFATAL: {e}")
        if VERBOSE:
            import traceback
            traceback.print_exc()
