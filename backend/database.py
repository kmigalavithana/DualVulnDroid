"""
Phase 7: this module is now a thin compatibility shim over the MySQL-
backed db/ package. Every function keeps its EXACT old name, signature,
and return shape from the SQLite-era implementation, so existing callers
(chatbot_logic.py, and any other code written against the old API)
require zero changes. Nothing here touches sqlite3 anymore - the actual
storage is MySQL via SQLAlchemy (see db/session.py, db/crud.py).

If DATABASE_URL isn't configured, calling any function here raises
db.session.DatabaseNotConfiguredError - it never silently falls back to
SQLite (see Part T).
"""

from db import crud
from db.session import SessionLocal, DatabaseNotConfiguredError


def _session():
    if SessionLocal is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not configured. Copy backend/.env.example to backend/.env "
            "and set DATABASE_URL to a real MySQL connection string."
        )
    return SessionLocal()


def create_user(email: str, password: str, name: str = "") -> bool:
    db = _session()
    try:
        user = crud.create_user(db, email, password, name)
        return user is not None
    finally:
        db.close()


def verify_user(email: str, password: str) -> dict:
    db = _session()
    try:
        user = crud.authenticate_user(db, email, password)
        if user is None:
            return None
        return {"id": user.id, "email": user.email, "name": user.name}
    finally:
        db.close()


def get_history(user_id: int) -> list:
    db = _session()
    try:
        rows = crud.get_user_history(db, user_id)
        return [
            {
                "app_name": r["app_name"],
                "security_score": r["security_score"],
                "risk_level": r["risk_level"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]
    finally:
        db.close()


def save_scan_result(user_id: int, app_name: str, overall_score: int, risk_level: str, recommendation: str):
    db = _session()
    try:
        application = crud.get_or_create_application(db, app_name=app_name, source="chat_lookup")
        crud.create_scan(
            db, user_id=user_id, application_id=application.id, app_version_id=None,
            scan_type="chat_lookup", security_score=overall_score, risk_level=risk_level,
            recommendation=recommendation, confidence=None,
        )
        db.commit()
    finally:
        db.close()


def save_chat_message(user_id: int, question: str, answer: str):
    db = _session()
    try:
        crud.save_chat_message(db, user_id, question, answer)
    finally:
        db.close()


def get_app_assessment(app_name: str) -> dict:
    """Same contract as the old SQLite version: None when the app has
    never actually been scanned - never a fabricated fallback."""
    db = _session()
    try:
        return _assessment_dict(db, crud.get_application_by_name(db, app_name))
    finally:
        db.close()


def get_app_assessment_by_id(app_id: int) -> dict:
    db = _session()
    try:
        return _assessment_dict(db, crud.get_application_by_id(db, app_id))
    finally:
        db.close()


def _assessment_dict(db, application) -> dict:
    if application is None:
        return None
    scan = crud.get_latest_scan_for_application(db, application.id)
    if scan is None:
        return None
    vulnerability_types = sorted({v.type for v in scan.vulnerabilities if v.type})
    scan_count = db.query(crud.models.Scan).filter(
        crud.models.Scan.application_id == application.id,
        crud.models.Scan.scan_status == "COMPLETED",
    ).count()
    # Same latest-recommendation tie-break as GET /apps/{id}/security (Phase
    # 10A) - kept identical so the chatbot never disagrees with the app
    # details screen about which recommendation is "current".
    latest_recommendation = max(scan.recommendations, key=lambda r: (r.created_at, r.id)) if scan.recommendations else None
    return {
        "app_id": application.id,
        "app_name": application.app_name,
        "package_name": application.package_name,
        "category": application.category,
        "security_score": scan.security_score,
        "risk_level": scan.risk_level,
        "vulnerability_types": vulnerability_types,
        "scan_count": scan_count,
        "last_scanned_at": scan.created_at.isoformat() if scan.created_at else None,
        # Additive fields (Phase 12 chatbot completion) - real stored data
        # only, never fabricated when absent. "recommendation_decision" is
        # scan.recommendation (the same field GET /apps/{id}/security
        # reads), not a field on the recommendations table itself.
        "recommendation_decision": scan.recommendation,
        "recommendation_reason": latest_recommendation.reason if latest_recommendation else None,
        "min_sdk_version": scan.app_version.min_sdk_version if scan.app_version else None,
        "target_sdk_version": scan.app_version.target_sdk_version if scan.app_version else None,
    }


def get_alternatives(category: str, exclude_app_name: str, limit: int = 3) -> list:
    """Old signature took a category string directly (no real curated-
    alternatives table existed yet). Real alternatives now come from
    AlternativeApp links (Part N) - this compatibility path has no
    application_id to look up links by by-category alone, so it honestly
    returns [] rather than guessing. Use GET /apps/{id}/alternatives for
    the real, linked-alternatives lookup."""
    return []


# search_applications()/get_application_by_id() were removed from this
# shim in Phase 7 - app.py's /apps/* routes now call db.crud directly
# (Depends(get_db)) for the richer Part K/L responses; nothing else in
# the codebase called the old shim versions.
