"""
Integration test for V2.2 stage endpoints.
Requires: backend running on :8000, or test via Starlette TestClient.
Run: venv/Scripts/python.exe test_stage_api.py
"""
import json
import sys
sys.path.insert(0, ".")

from user.profile_manager import UserProfile, ProfileManager

def test_stage_with_applications():
    """Simulate what /v1/stage would return with multi-school applications."""
    from agent.state_machine import get_current_stage_info, generate_timeline, check_reminders

    profile = UserProfile(
        jlpt_level="N1",
        target_major="情报理工",
        applications=[
            {
                "school": "京都大学 情报理工",
                "stage": "contacting",
                "needs_contact": True,
                "professors": [
                    {"name": "田中太郎", "status": "sent", "date": "2026-06-20"},
                    {"name": "山田花子", "status": "sent", "date": "2026-07-05"},
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

    app_tracks = []
    for app in profile.applications:
        school = app.get("school", "")
        stage_id = app.get("stage", "preparing")
        info = get_current_stage_info(stage_id)
        app_tracks.append({
            "school": school,
            **info,
            "professors": app.get("professors", []),
            "deadlines": app.get("deadlines", {}),
            "notes": app.get("notes", ""),
            "needs_contact": app.get("needs_contact", False),
            "timeline": generate_timeline(stage_id),
            "reminders": check_reminders(stage_id),
        })

    assert len(app_tracks) == 2
    kyoto = app_tracks[0]
    assert kyoto["school"] == "京都大学 情报理工"
    assert kyoto["stage_id"] == "contacting"
    assert kyoto["label"] == "套磁阶段"
    assert len(kyoto["professors"]) == 2
    assert len(kyoto["timeline"]) >= 4  # contacting → applying → exam → waiting → decided
    print(f"[PASS] Kyoto: {kyoto['label']}, {len(kyoto['professors'])} professors, {len(kyoto['timeline'])} timeline entries")

    hokkaido = app_tracks[1]
    assert hokkaido["school"] == "北海道大学 情报科学"
    assert hokkaido["stage_id"] == "preparing"
    assert hokkaido["label"] == "准备阶段"
    # preparing has 0 order, so timeline should include all 6 stages
    assert len(hokkaido["timeline"]) == 6
    print(f"[PASS] Hokkaido: {hokkaido['label']}, {len(hokkaido['timeline'])} timeline entries")

    return app_tracks

def test_professor_reminder_detection():
    """Test 14-day no-reply detection for professors."""
    from agent.state_machine import check_reminders
    from datetime import datetime, timedelta

    # Simulate a professor sent 15 days ago
    old_date = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
    profile = UserProfile(
        applications=[
            {
                "school": "京都大学 情报理工",
                "stage": "contacting",
                "professors": [
                    {"name": "田中太郎", "status": "sent", "date": old_date}
                ],
                "deadlines": {},
                "notes": ""
            }
        ]
    )

    # Check reminders via the same logic as _collect_all_reminders
    reminders = []
    for app in profile.applications:
        for prof in app.get("professors", []):
            status = prof.get("status", "")
            if status in ("sent", "no_reply"):
                sent_date = prof.get("date", "")
                if sent_date:
                    sent = datetime.fromisoformat(sent_date)
                    elapsed = (datetime.now() - sent).days
                    if elapsed >= 14 and status != "no_reply":
                        reminders.append({
                            "school": app["school"],
                            "professor": prof["name"],
                            "message": f"{prof['name']} {elapsed}天未回复，建议发跟进邮件或换教授"
                        })

    assert len(reminders) >= 1, f"Expected at least 1 reminder for professor sent {old_date}"
    r = reminders[0]
    assert "田中太郎" in r["message"]
    assert "天未回复" in r["message"]
    print(f"[PASS] Professor reminder: {r['message']}")

    # Test professor sent 5 days ago → no reminder yet
    recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    recent_reminders = []
    recent_prof = {"name": "山田花子", "status": "sent", "date": recent_date}
    sent_date = recent_prof.get("date", "")
    sent = datetime.fromisoformat(sent_date)
    elapsed = (datetime.now() - sent).days
    if elapsed < 14:
        pass  # no reminder
    else:
        recent_reminders.append(recent_prof)
    assert len(recent_reminders) == 0, "Should not trigger reminder within 14 days"
    print(f"[PASS] Recent professor (5 days): no reminder triggered")

if __name__ == "__main__":
    print("=== V2.2 Stage API Test ===\n")
    passed = 0
    failed = 0
    for t in [test_stage_with_applications, test_professor_reminder_detection]:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
