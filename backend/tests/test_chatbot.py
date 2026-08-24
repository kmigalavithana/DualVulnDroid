"""
Phase 12, Part F/8: tests for the chatbot's real-data-grounded intent
handling (CWE-89/CWE-295 explanations, why-risky, what-to-do, recommendation
explanation, compatibility) and for the app_id-based app-context lookup that
replaced the old, broken free-text prefix the Flutter client used to send.

Uses the same SessionLocal()/db.crud setup pattern as test_api.py to create
real Application/Scan/Vulnerability/RecommendationRecord rows against the
sqlite test database conftest.py configures, then drives chatbot_logic
directly and through the real /ai-chat endpoint via TestClient.
"""

from fastapi.testclient import TestClient

from app import app
from db.session import SessionLocal
from db import crud
import chatbot_logic

client = TestClient(app)


def _make_assessed_app(app_name, package_name, risk_level, recommendation, reason=None,
                        min_sdk_version=None, target_sdk_version=None, cwe=None):
    db = SessionLocal()
    try:
        application = crud.get_or_create_application(db, app_name=app_name, package_name=package_name)
        version = None
        if min_sdk_version is not None or target_sdk_version is not None:
            version = crud.get_or_create_app_version(
                db, application_id=application.id, version_name="1.0", version_code=1,
                min_sdk_version=min_sdk_version, target_sdk_version=target_sdk_version,
            )
        scan = crud.create_scan(
            db, user_id=None, application_id=application.id,
            app_version_id=version.id if version else None,
            scan_type="apk_upload", security_score=40 if risk_level == "HIGH" else 90,
            risk_level=risk_level, recommendation=recommendation, confidence=None,
        )
        if cwe:
            crud.add_vulnerability(
                db, scan_id=scan.id, cwe=cwe, type_="SQL Injection" if cwe == "CWE-89" else "Improper Certificate Validation",
                severity="HIGH", confidence=91, file_name="Example.java", line_number=1,
                source="getIntent", sink="rawQuery", description="test finding",
            )
        crud.add_recommendation(
            db, scan_id=scan.id, risk_level=risk_level, recommendation=recommendation,
            reason=reason, confidence=87,
        )
        db.commit()
        return application.id
    finally:
        db.close()


# ---------------------------------------------------------------------
# 1. CWE explanation intents - static reference text, no app needed.
# ---------------------------------------------------------------------
def test_cwe_89_explanation():
    reply = chatbot_logic.generate_chat_response("What is CWE-89?")
    assert "SQL Injection" in reply
    assert "parameterized" in reply.lower()


def test_cwe_295_explanation():
    reply = chatbot_logic.generate_chat_response("What is CWE-295?")
    assert "Certificate Validation" in reply
    assert "hostname" in reply.lower() or "trustmanager" in reply.lower()


def test_cwe_explanation_by_name_also_works():
    reply = chatbot_logic.generate_chat_response("Can you explain SQL injection?")
    assert "SQL Injection" in reply


# ---------------------------------------------------------------------
# 2. why_risky / what_to_do / explain_recommendation - real app_id lookup.
# ---------------------------------------------------------------------
def test_why_risky_uses_real_stored_findings():
    app_id = _make_assessed_app(
        "RiskyBank", "com.example.riskybank", "HIGH", "AVOID_INSTALLING",
        reason="Untrusted input reaches a raw SQL sink.", cwe="CWE-89",
    )
    reply = chatbot_logic.generate_chat_response("Why is this app risky?", app_id=app_id)
    assert "HIGH" in reply
    assert "SQL Injection" in reply
    assert "Untrusted input reaches a raw SQL sink." in reply


def test_why_risky_matches_the_flutter_apps_own_suggestion_chip_wording():
    # Phase 14B: found via real Android emulator testing - the Flutter
    # client's built-in suggestion chip literally reads "Why is this app
    # high risk?", which the intent classifier didn't originally match,
    # silently falling back to the generic greeting instead of a real,
    # grounded answer. Locks in the fix.
    app_id = _make_assessed_app(
        "RiskyBank", "com.example.riskybank", "HIGH", "AVOID_INSTALLING",
        reason="Untrusted input reaches a raw SQL sink.", cwe="CWE-89",
    )
    reply = chatbot_logic.generate_chat_response("Why is this app high risk?", app_id=app_id)
    assert "HIGH" in reply
    assert "SQL Injection" in reply
    assert "DualVulnDroid Security Bot" not in reply  # must not be the generic greeting


def test_why_risky_for_safe_app_says_not_risky():
    app_id = _make_assessed_app("SafeApp", "com.example.safeapp", "LOW", "SAFE_TO_INSTALL")
    reply = chatbot_logic.generate_chat_response("Why is this app risky?", app_id=app_id)
    assert "isn't currently flagged as risky" in reply


def test_what_to_do_matches_real_recommendation_decision():
    app_id = _make_assessed_app("CautionApp", "com.example.caution", "MEDIUM", "INSTALL_WITH_CAUTION")
    reply = chatbot_logic.generate_chat_response("What should I do about this vulnerability?", app_id=app_id)
    assert reply == chatbot_logic.RECOMMENDATION_EXPLANATIONS["INSTALL_WITH_CAUTION"]


def test_explain_recommendation_uses_real_decision_value():
    app_id = _make_assessed_app("AvoidApp", "com.example.avoid", "HIGH", "AVOID_INSTALLING")
    reply = chatbot_logic.generate_chat_response("What does this recommendation mean?", app_id=app_id)
    assert reply == chatbot_logic.RECOMMENDATION_EXPLANATIONS["AVOID_INSTALLING"]


def test_app_context_intent_with_unassessed_app_id_is_honest():
    db = SessionLocal()
    try:
        application = crud.get_or_create_application(db, app_name="NeverScanned", package_name="com.example.neverscanned")
        db.commit()
        app_id = application.id
    finally:
        db.close()

    reply = chatbot_logic.generate_chat_response("Why is this app risky?", app_id=app_id)
    assert "don't have a verified security assessment" in reply


def test_app_context_intent_with_unknown_app_id_is_honest():
    reply = chatbot_logic.generate_chat_response("Why is this app risky?", app_id=999999)
    assert "don't have a verified security assessment" in reply


# ---------------------------------------------------------------------
# 3. Compatibility - real min_sdk_version vs. real user_android_version.
# ---------------------------------------------------------------------
def test_compatibility_yes_when_device_meets_min_sdk():
    app_id = _make_assessed_app(
        "CompatApp", "com.example.compat", "LOW", "SAFE_TO_INSTALL", min_sdk_version=21,
    )
    reply = chatbot_logic.generate_chat_response("Is this app compatible with my device?", user_android_version=30, app_id=app_id)
    assert reply.startswith("Yes")
    assert "21" in reply and "30" in reply


def test_compatibility_no_when_device_below_min_sdk():
    app_id = _make_assessed_app(
        "NewApp", "com.example.newapp", "LOW", "SAFE_TO_INSTALL", min_sdk_version=31,
    )
    reply = chatbot_logic.generate_chat_response("Is this app compatible with my device?", user_android_version=21, app_id=app_id)
    assert reply.startswith("No")


def test_compatibility_honest_when_min_sdk_not_available():
    app_id = _make_assessed_app("UnknownSdkApp", "com.example.unknownsdk", "LOW", "SAFE_TO_INSTALL")
    reply = chatbot_logic.generate_chat_response("Is this app compatible with my device?", user_android_version=30, app_id=app_id)
    assert "wasn't available" in reply


def test_compatibility_without_app_id_asks_for_app():
    reply = chatbot_logic.generate_chat_response("Is this app compatible with my device?")
    assert "which app you mean" in reply


# ---------------------------------------------------------------------
# 4. Backward-compatible name-based lookup (no app_id supplied).
# ---------------------------------------------------------------------
def test_name_based_lookup_still_works_for_unassessed_app():
    reply = chatbot_logic.generate_chat_response("Is TotallyUnscannedApp safe?")
    assert "don't have a verified security assessment" in reply


def test_generic_message_with_no_app_returns_greeting():
    reply = chatbot_logic.generate_chat_response("hello there how are you")
    assert "DualVulnDroid Security Bot" in reply


# ---------------------------------------------------------------------
# 5. /ai-chat endpoint end-to-end - proves the app_id wiring (app.py ->
# chatbot_logic.generate_chat_response) actually works over real HTTP,
# not just as a direct function call.
# ---------------------------------------------------------------------
def test_ai_chat_endpoint_accepts_app_id_and_returns_grounded_reply():
    app_id = _make_assessed_app(
        "EndpointApp", "com.example.endpointapp", "HIGH", "AVOID_INSTALLING",
        reason="Certificate validation is bypassed.", cwe="CWE-295",
    )
    r = client.post("/ai-chat", json={"message": "Why is this app risky?", "app_id": app_id})
    assert r.status_code == 200
    body = r.json()
    assert "Certificate validation is bypassed." in body["reply"]
    assert "Improper Certificate Validation" in body["reply"]


def test_ai_chat_endpoint_without_app_id_still_works():
    r = client.post("/ai-chat", json={"message": "What is CWE-89?"})
    assert r.status_code == 200
    assert "SQL Injection" in r.json()["reply"]


def test_ai_chat_endpoint_empty_message_does_not_error():
    r = client.post("/ai-chat", json={"message": ""})
    assert r.status_code == 200
    assert "reply" in r.json()
