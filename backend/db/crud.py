"""
Phase 7: all database operations for the MySQL-backed layer. Every
function here operates on real, caller-supplied data - none of them
invent a score, risk level, or compatibility fact that wasn't actually
computed elsewhere (predictor.py's decision engine, apk_scanner.py's
real static analysis).
"""

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .security import hash_password, verify_password


# =====================================================
# Users (Part D)
# =====================================================

def create_user(db: Session, email: str, password: str, name: str = "") -> Optional[models.User]:
    user = models.User(email=email, password_hash=hash_password(password), name=name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        return None
    matches, needs_upgrade = verify_password(password, user.password_hash)
    if not matches:
        return None
    if needs_upgrade:
        # Safe rolling migration off the old SHA-256 scheme (Part D) -
        # only possible at the moment of a successful login, since a
        # one-way hash can't be batch-converted without the plaintext.
        user.password_hash = hash_password(password)
        db.commit()
        db.refresh(user)
    return user


# =====================================================
# Applications / versions (Part E/F)
# =====================================================

def get_or_create_application(db: Session, app_name: str, package_name: str = None,
                               developer: str = None, category: str = None,
                               icon_url: str = None, source: str = None) -> models.Application:
    query = db.query(models.Application)
    app = None
    if package_name:
        app = query.filter(models.Application.package_name == package_name).first()
    if app is None:
        app = query.filter(models.Application.app_name == app_name).first()

    if app is not None:
        # Fill in any real details we didn't have before; never overwrite
        # a real value with a blank one.
        if category and not app.category:
            app.category = category
        if developer and not app.developer:
            app.developer = developer
        if icon_url and not app.icon_url:
            app.icon_url = icon_url
        # flush, not commit: this function is composed into larger
        # transactions (persist_apk_scan) that must stay all-or-nothing -
        # committing here would leave this row behind even if a later
        # step in the same request fails. Callers own the final commit.
        db.flush()
        return app

    app = models.Application(
        app_name=app_name, package_name=package_name, developer=developer,
        category=category, icon_url=icon_url, source=source
    )
    db.add(app)
    db.flush()
    return app


def get_or_create_app_version(db: Session, application_id: int, version_name: str = None,
                               version_code: int = None, min_sdk_version: int = None,
                               target_sdk_version: int = None, debuggable: bool = None,
                               allow_backup: bool = None, features: list = None,
                               abis: list = None) -> Optional[models.AppVersion]:
    """Returns None (not a guess) when neither version_name nor
    version_code is actually known (Part F: allow NULL where necessary,
    never assume version info).

    min_sdk_version/target_sdk_version/debuggable/allow_backup (Phase 8B)
    are real AndroidManifest.xml facts about this exact build - None
    means the manifest genuinely didn't yield that value. Re-scanning the
    same version fills in any of these that were missing before, the
    same "never overwrite a real value with a blank one" pattern used in
    get_or_create_application - it never clobbers a value this version
    already has with a fresher None.

    features/abis (Phase 8C) are lists, not scalars, so they use
    different semantics: apk_scanner.py always returns a real list
    (possibly empty - empty genuinely means "this build declares none",
    not "unknown"), so every scan's features_json/abis_json fully
    replaces whatever was stored before rather than gap-filling. A
    caller that never passes features/abis (None, the default) leaves
    whatever is already stored untouched.
    """
    if version_name is None and version_code is None:
        return None

    version = db.query(models.AppVersion).filter(
        models.AppVersion.application_id == application_id,
        models.AppVersion.version_name == version_name,
        models.AppVersion.version_code == version_code,
    ).first()
    if version is not None:
        if version.min_sdk_version is None and min_sdk_version is not None:
            version.min_sdk_version = min_sdk_version
        if version.target_sdk_version is None and target_sdk_version is not None:
            version.target_sdk_version = target_sdk_version
        if version.debuggable is None and debuggable is not None:
            version.debuggable = debuggable
        if version.allow_backup is None and allow_backup is not None:
            version.allow_backup = allow_backup
        if features is not None:
            version.features_json = features
        if abis is not None:
            version.abis_json = abis
        db.flush()
        return version

    version = models.AppVersion(
        application_id=application_id, version_name=version_name, version_code=version_code,
        min_sdk_version=min_sdk_version, target_sdk_version=target_sdk_version,
        debuggable=debuggable, allow_backup=allow_backup,
        features_json=features if features is not None else [],
        abis_json=abis if abis is not None else [],
    )
    db.add(version)
    # flush, not commit - see get_or_create_application for why.
    db.flush()
    return version


def search_applications(db: Session, query: str, limit: int = 10) -> list:
    rows = (
        db.query(models.Application)
        .filter(models.Application.app_name.ilike(f"%{query}%"))
        .order_by(models.Application.app_name)
        .limit(limit)
        .all()
    )
    return [{"id": a.id, "app_name": a.app_name, "package_name": a.package_name, "category": a.category} for a in rows]


def get_application_by_id(db: Session, app_id: int) -> Optional[models.Application]:
    return db.query(models.Application).filter(models.Application.id == app_id).first()


def get_application_by_name(db: Session, app_name: str) -> Optional[models.Application]:
    return db.query(models.Application).filter(models.Application.app_name.ilike(app_name)).first()


def get_latest_scan_for_application(db: Session, application_id: int) -> Optional[models.Scan]:
    return (
        db.query(models.Scan)
        .filter(models.Scan.application_id == application_id, models.Scan.scan_status == "COMPLETED")
        .order_by(models.Scan.created_at.desc())
        .first()
    )


def get_alternatives(db: Session, application_id: int, limit: int = 5) -> list:
    """Only ever returns REAL, explicitly-linked alternative applications
    (Part N) - empty list when none have been curated yet, never a guess."""
    links = (
        db.query(models.AlternativeApp)
        .filter(models.AlternativeApp.application_id == application_id)
        .limit(limit)
        .all()
    )
    result = []
    for link in links:
        alt_app = get_application_by_id(db, link.alternative_application_id)
        if alt_app is None:
            continue
        latest_scan = get_latest_scan_for_application(db, alt_app.id)
        result.append({
            "id": alt_app.id,
            "app_name": alt_app.app_name,
            "package_name": alt_app.package_name,
            "security_score": latest_scan.security_score if latest_scan else None,
            "risk_level": latest_scan.risk_level if latest_scan else None,
        })
    return result


# =====================================================
# Scans / vulnerabilities / predictions / recommendations (Part G-J)
# =====================================================

def create_scan(db: Session, user_id: Optional[int], application_id: Optional[int],
                 app_version_id: Optional[int], scan_type: str,
                 security_score: Optional[int], risk_level: Optional[str],
                 recommendation: Optional[str], confidence: Optional[int],
                 scan_status: str = "COMPLETED") -> models.Scan:
    scan = models.Scan(
        user_id=user_id, application_id=application_id, app_version_id=app_version_id,
        scan_type=scan_type, scan_status=scan_status, security_score=security_score,
        risk_level=risk_level, recommendation=recommendation, confidence=confidence,
    )
    db.add(scan)
    db.flush()  # assigns scan.id without committing yet - part of the caller's transaction
    return scan


def add_vulnerability(db: Session, scan_id: int, cwe: Optional[str], type_: Optional[str],
                       severity: Optional[str], confidence: Optional[int], file_name: Optional[str],
                       line_number: Optional[int], source: Optional[str], sink: Optional[str],
                       description: Optional[str], status: str = models.VulnerabilityStatus.OPEN.value) -> models.Vulnerability:
    vuln = models.Vulnerability(
        scan_id=scan_id, cwe=cwe, type=type_, severity=severity, confidence=confidence,
        file_name=file_name, line_number=line_number, source=source, sink=sink,
        description=description, status=status,
    )
    db.add(vuln)
    db.flush()
    return vuln


def add_ml_prediction(db: Session, scan_id: int, model_name: Optional[str], model_version: Optional[str],
                       predicted_class: Optional[str], confidence: Optional[int],
                       shap_summary: Optional[list] = None) -> models.MLPrediction:
    pred = models.MLPrediction(
        scan_id=scan_id, model_name=model_name, model_version=model_version,
        predicted_class=predicted_class, confidence=confidence, shap_summary=shap_summary,
    )
    db.add(pred)
    db.flush()
    return pred


def add_recommendation(db: Session, scan_id: int, risk_level: Optional[str], recommendation: Optional[str],
                        reason: Optional[str], confidence: Optional[int]) -> models.RecommendationRecord:
    rec = models.RecommendationRecord(
        scan_id=scan_id, risk_level=risk_level, recommendation=recommendation,
        reason=reason, confidence=confidence,
    )
    db.add(rec)
    db.flush()
    return rec


# =====================================================
# APK upload persistence (Part P/Q) - one transaction, all-or-nothing.
# =====================================================

# Real static-analysis risk -> the same 4-tier decision vocabulary used
# throughout the rest of the system, never a fabricated score/tier.
_RISK_TO_RECOMMENDATION = {
    "high": models.RecommendationDecision.AVOID_INSTALLING.value,
    "medium": models.RecommendationDecision.INSTALL_WITH_CAUTION.value,
    "low": models.RecommendationDecision.SAFE_TO_INSTALL.value,
}


def persist_apk_scan(db: Session, user_id: Optional[int], scan_report: dict) -> models.Scan:
    """
    Persists a REAL apk_scanner.scan_apk_file() report across
    application / app_version / scan / vulnerabilities / ml_prediction /
    recommendation in a single transaction (Part Q) - commits once at the
    end, rolls back entirely on any failure so no half-created scan is
    ever left behind.

    Nothing here invents data the scanner didn't actually report:
    security_score is only set if scan_report provided one; vulnerability
    rows are only created for real detections[]; package_name/version_name/
    version_code/application_label/min_sdk_version/target_sdk_version/
    debuggable/allow_backup (Phase 8A/8B) come from apk_scanner.py's real
    AndroidManifest.xml parse and stay NULL when that parse couldn't
    genuinely determine them - never guessed, never derived from the
    upload's filename.
    """
    try:
        # Prefer the real manifest application label; fall back to the
        # real uploaded filename (an existing, documented Phase 7
        # behavior - app.py sets scan_report["app_name"] to file.filename)
        # only when the manifest didn't yield a usable label.
        app_name = scan_report.get("application_label") or scan_report.get("app_name") or "unknown"
        package_name = scan_report.get("package_name")
        application = get_or_create_application(
            db, app_name=app_name, package_name=package_name, source="apk_upload"
        )

        version_name = scan_report.get("version_name")
        version_code = scan_report.get("version_code")
        app_version = get_or_create_app_version(
            db, application.id, version_name, version_code,
            min_sdk_version=scan_report.get("min_sdk_version"),
            target_sdk_version=scan_report.get("target_sdk_version"),
            debuggable=scan_report.get("debuggable"),
            allow_backup=scan_report.get("allow_backup"),
            features=scan_report.get("features"),
            abis=scan_report.get("abis"),
        )

        risk_level = (scan_report.get("risk_level") or "unknown").upper()
        recommendation = _RISK_TO_RECOMMENDATION.get(scan_report.get("risk_level"), models.RecommendationDecision.MANUAL_REVIEW.value)
        security_score = scan_report.get("security_score")  # already None-safe from apk_scanner

        scan = create_scan(
            db, user_id=user_id, application_id=application.id,
            app_version_id=app_version.id if app_version else None,
            scan_type="apk_upload", security_score=security_score,
            risk_level=risk_level if risk_level != "UNKNOWN" else None,
            recommendation=recommendation, confidence=None,
        )

        for detection in scan_report.get("detections", []):
            add_vulnerability(
                db, scan_id=scan.id,
                cwe=None,  # apk_scanner's manifest/permission findings aren't CWE-89/295 code findings
                type_=detection.get("type"), severity=risk_level if risk_level != "UNKNOWN" else None,
                confidence=None, file_name="AndroidManifest.xml", line_number=None,
                source=None, sink=None, description=detection.get("code"),
                status=models.VulnerabilityStatus.OPEN.value,
            )

        for url_report in scan_report.get("malicious_urls", []):
            add_vulnerability(
                db, scan_id=scan.id, cwe=None, type_="Malicious URL", severity="HIGH",
                confidence=None, file_name=None, line_number=None, source=None, sink=None,
                description=f"{url_report.get('url')}: {url_report.get('reason')}",
                status=models.VulnerabilityStatus.OPEN.value,
            )

        # Flutter APK Scan implementation phase: real CWE-89/CWE-295
        # findings from decompiled DEX code (apk_code_scanner.py), run
        # through the same predictor.py/dataflow.py pipeline as the IDE
        # plugin. Unlike the manifest/permission/URL findings above, these
        # DO carry a real cwe value - they are genuine source-level
        # findings, not a manifest heuristic.
        for finding in scan_report.get("codeAnalysis", {}).get("findings", []):
            explanation = finding.get("explanation")
            description = " ".join(explanation) if isinstance(explanation, list) else explanation
            add_vulnerability(
                db, scan_id=scan.id, cwe=finding.get("cwe"), type_=finding.get("type"),
                severity=finding.get("severity"),
                confidence=int(round(finding["confidence"])) if finding.get("confidence") is not None else None,
                file_name=finding.get("file"), line_number=finding.get("line"),
                source=None, sink=None, description=description,
                status=models.VulnerabilityStatus.OPEN.value,
            )

        add_recommendation(
            db, scan_id=scan.id, risk_level=scan.risk_level, recommendation=recommendation,
            reason=scan_report.get("explanation"), confidence=None,
        )

        db.commit()
        db.refresh(scan)

        # Step 7 (Part P): make the application searchable regardless of
        # whether this was a logged-in or guest scan.
        return scan
    except Exception:
        db.rollback()
        raise


# =====================================================
# Alternative-ranking candidate data (Phase 8C, Part K) - real Application
# rows paired with their real latest-scan assessment, for
# alternatives.rank_alternatives() to filter/rank. No filtering happens
# here - that's alternatives.py's job, kept separate from data access.
# =====================================================

def get_candidate_applications_for_ranking(db: Session, exclude_application_id: int, limit: int = 50) -> list:
    applications = (
        db.query(models.Application)
        .filter(models.Application.id != exclude_application_id)
        .limit(limit)
        .all()
    )
    candidates = []
    for app in applications:
        scan = get_latest_scan_for_application(db, app.id)
        candidates.append({
            "application": app,
            "risk_level": scan.risk_level if scan else None,
            "security_score": scan.security_score if scan else None,
            "confidence": scan.confidence if scan else None,
        })
    return candidates


# =====================================================
# User history (Part M) - only ever the authenticated user's own scans.
# =====================================================

def get_user_history(db: Session, user_id: int, limit: int = 50) -> list:
    scans = (
        db.query(models.Scan)
        .filter(models.Scan.user_id == user_id)
        .order_by(models.Scan.created_at.desc())
        .limit(limit)
        .all()
    )
    history = []
    for scan in scans:
        app = scan.application
        history.append({
            "scan_id": scan.id,
            # Phase 9: added so a Flutter client can navigate straight to
            # this application's own detail/security view from a history
            # entry, without re-searching by name - a real, already-
            # available field (scan.application_id), not a new lookup.
            "application_id": app.id if app else None,
            "app_name": app.app_name if app else None,
            "package_name": app.package_name if app else None,
            "security_score": scan.security_score,
            "risk_level": scan.risk_level,
            "recommendation": scan.recommendation,
            "timestamp": scan.created_at.isoformat() if scan.created_at else None,
        })
    return history


# =====================================================
# Chat history (unchanged behavior, new backend)
# =====================================================

def save_chat_message(db: Session, user_id: Optional[int], question: str, answer: str) -> models.ChatHistory:
    entry = models.ChatHistory(user_id=user_id, question=question, answer=answer)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_user_chat_history(db: Session, user_id: int, limit: int = 200) -> list:
    """The read side of chat history (Phase 14C) - had no counterpart
    until now, so save_chat_message() was write-only. Chronological
    (oldest first), unlike get_user_history()'s newest-first scan list,
    since this is read as a conversation transcript, not an event log."""
    entries = (
        db.query(models.ChatHistory)
        .filter(models.ChatHistory.user_id == user_id)
        .order_by(models.ChatHistory.created_at.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": entry.id,
            "question": entry.question,
            "answer": entry.answer,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]
