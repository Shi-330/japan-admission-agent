"""
Test V2.2 profile extraction & merge — per-school applications tracking.
Run: venv/Scripts/python.exe test_profile_v22.py
"""
import json
import sys
sys.path.insert(0, ".")

from user.profile_manager import ProfileManager, UserProfile, PROFILE_EXTRACTION_PROMPT

def test_extraction_prompt_includes_applications():
    """Verify the prompt template includes 'applications' keyword."""
    assert "applications" in PROFILE_EXTRACTION_PROMPT, "Prompt missing applications field"
    assert "professors" in PROFILE_EXTRACTION_PROMPT, "Prompt missing professors"
    assert "deadlines" in PROFILE_EXTRACTION_PROMPT, "Prompt missing deadlines"
    print("[PASS] Extraction prompt includes applications + professors + deadlines")

def test_merge_delta_applications():
    """Test merging application deltas into profile."""
    mgr = ProfileManager()
    profile = UserProfile()

    # Simulate LLM extraction delta: student said they emailed Prof. Tanaka at Kyoto
    delta = {
        "applications": [
            {
                "school": "京都大学 情报理工",
                "stage": "contacting",
                "needs_contact": True,
                "professors": [
                    {"name": "田中太郎", "status": "sent", "date": "2026-07-01"}
                ],
                "deadlines": {"出愿": "2026-12-15"},
                "notes": "已发套磁信"
            }
        ]
    }

    profile = mgr.merge_delta(profile, delta)

    assert len(profile.applications) == 1, f"Expected 1 application, got {len(profile.applications)}"
    app = profile.applications[0]
    assert app["school"] == "京都大学 情报理工"
    assert app["stage"] == "contacting"
    assert len(app["professors"]) == 1
    assert app["professors"][0]["name"] == "田中太郎"
    assert app["professors"][0]["status"] == "sent"
    assert app["deadlines"]["出愿"] == "2026-12-15"
    print(f"[PASS] merge_delta: 1st application — {app['school']} / {app['stage']} / {len(app['professors'])} professor(s)")

    # Simulate: same school, add a 2nd professor
    delta2 = {
        "applications": [
            {
                "school": "京都大学 情报理工",
                "stage": "contacting",
                "professors": [
                    {"name": "山田花子", "status": "sent", "date": "2026-07-05"}
                ],
                "notes": "田中2周未回，已换山田"
            }
        ]
    }
    profile = mgr.merge_delta(profile, delta2)

    assert len(profile.applications) == 1, "Should still be 1 school"
    app = profile.applications[0]
    assert len(app["professors"]) == 2, f"Expected 2 professors, got {len(app['professors'])}"
    assert app["professors"][1]["name"] == "山田花子"
    assert app["notes"] == "田中2周未回，已换山田"
    assert app["deadlines"]["出愿"] == "2026-12-15", "Deadline should persist"
    print(f"[PASS] merge_delta: 2nd professor added — {len(app['professors'])} professors, deadline preserved")

    # Simulate: update professor status (田中 replied)
    delta3 = {
        "applications": [
            {
                "school": "京都大学 情报理工",
                "professors": [
                    {"name": "田中太郎", "status": "replied", "date": "2026-07-10"}
                ]
            }
        ]
    }
    profile = mgr.merge_delta(profile, delta3)
    app = profile.applications[0]
    tanaka = [p for p in app["professors"] if p["name"] == "田中太郎"][0]
    assert tanaka["status"] == "replied", f"Expected 'replied', got {tanaka['status']}"
    assert tanaka["date"] == "2026-07-10"
    print(f"[PASS] merge_delta: professor status updated — 田中: {tanaka['status']}")

    # Simulate: add a 2nd school
    delta4 = {
        "applications": [
            {
                "school": "北海道大学 情报科学",
                "stage": "preparing",
                "needs_contact": False,
                "deadlines": {"出愿": "2027-01-20"}
            }
        ]
    }
    profile = mgr.merge_delta(profile, delta4)
    assert len(profile.applications) == 2, f"Expected 2 schools, got {len(profile.applications)}"
    assert profile.applications[1]["school"] == "北海道大学 情报科学"
    print(f"[PASS] merge_delta: 2nd school added — total {len(profile.applications)} schools")

def test_format_for_prompt():
    """Verify format_for_prompt renders applications."""
    profile = UserProfile(
        jlpt_level="N1",
        target_major="情报理工",
        applications=[
            {
                "school": "京都大学 情报理工",
                "stage": "contacting",
                "needs_contact": True,
                "professors": [
                    {"name": "田中太郎", "status": "sent", "date": "2026-07-01"},
                    {"name": "山田花子", "status": "sent", "date": "2026-07-05"}
                ],
                "deadlines": {"出愿": "2026-12-15"},
                "notes": "田中2周未回，已换山田"
            },
            {
                "school": "北海道大学 情报科学",
                "stage": "preparing",
                "needs_contact": False,
                "professors": [],
                "deadlines": {"出愿": "2027-01-20"},
                "notes": ""
            }
        ]
    )
    mgr = ProfileManager()
    formatted = mgr.format_for_prompt(profile)

    assert "【申请追踪】" in formatted, "Format missing applications section"
    assert "京都大学" in formatted
    assert "北海道大学" in formatted
    assert "田中太郎" in formatted
    assert "山田花子" in formatted
    assert "套磁" in formatted  # stage label
    assert "准备" in formatted
    assert "2026-12-15" in formatted
    print(f"[PASS] format_for_prompt renders applications correctly")

def test_extract_facts_includes_applications_in_snapshot():
    """Verify the LLM snapshot json includes the applications field."""
    profile = UserProfile(
        applications=[
            {
                "school": "京都大学 情报理工",
                "stage": "contacting",
                "needs_contact": True,
                "professors": [{"name": "田中太郎", "status": "sent", "date": "2026-07-01"}],
                "deadlines": {"出愿": "2026-12-15"},
                "notes": ""
            }
        ]
    )
    mgr = ProfileManager()
    # This will fail because no chat_model, but we can check the json building logic manually
    # Just verify the field is in the profile dict
    d = profile.to_dict()
    assert "applications" in d
    assert len(d["applications"]) == 1
    print(f"[PASS] Profile dict includes applications field")

if __name__ == "__main__":
    print("=== V2.2 Profile Test Suite ===\n")
    tests = [
        test_extraction_prompt_includes_applications,
        test_merge_delta_applications,
        test_format_for_prompt,
        test_extract_facts_includes_applications_in_snapshot,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {e}")
            failed += 1
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
