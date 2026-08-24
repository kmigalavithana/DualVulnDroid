"""
Phase 7, Part V: real MySQL database integration tests for db/crud.py.

These tests use their OWN engine/session bound directly to
TEST_DATABASE_URL (falling back to DATABASE_URL if that's the only thing
set) - they never touch the app's shared db.session.SessionLocal, and
never run against SQLite. If neither variable points at a reachable
mysql+pymysql:// server, every test in this module is SKIPPED, not
faked: this sandbox has no MySQL server available (documented in the
Phase 7 report), so in this environment they are expected to show as
skipped, and that is the honest result.

Run for real against an actual MySQL test database:

    TEST_DATABASE_URL=mysql+pymysql://user:pass@host:3306/dualvulndroid_test \\
        python -m pytest tests/test_db_integration.py -v

Do NOT point this at a production database - see backend/.env.example
("do not use the production database for tests"). Each test drops and
recreates the whole schema first, so nothing here is safe to run
against real user data.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from db.session import Base
from db import crud

_CANDIDATE_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


def _is_real_mysql_url(url) -> bool:
    return bool(url) and url.startswith("mysql")


def _reachable(url) -> tuple:
    """Returns (ok, message) - never raises, so collection can't crash."""
    if not _is_real_mysql_url(url):
        return False, (
            "TEST_DATABASE_URL (or DATABASE_URL) is not set to a real "
            "mysql+pymysql:// connection string - skipping Part V "
            "integration tests. See backend/.env.example."
        )
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect():
            pass
        engine.dispose()
        return True, "ok"
    except OperationalError as e:
        return False, f"TEST_DATABASE_URL is set but MySQL is unreachable: {e}"


_OK, _REASON = _reachable(_CANDIDATE_URL)
pytestmark = pytest.mark.skipif(not _OK, reason=_REASON)


@pytest.fixture()
def db():
    """Fresh schema per test - drop_all then create_all against the real
    MySQL test database, so no test depends on another's leftover rows."""
    engine = create_engine(_CANDIDATE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------
# 1. Create user
# ---------------------------------------------------------------------
def test_create_user(db):
    user = crud.create_user(db, email="alice@example.com", password="correct horse battery staple", name="Alice")
    assert user is not None
    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.password_hash.startswith("$argon2")  # never plaintext/SHA-256 for new accounts


# ---------------------------------------------------------------------
# 2. Login
# ---------------------------------------------------------------------
def test_login(db):
    crud.create_user(db, email="bob@example.com", password="s3cret-pass", name="Bob")
    user = crud.authenticate_user(db, email="bob@example.com", password="s3cret-pass")
    assert user is not None
    assert user.email == "bob@example.com"

    wrong = crud.authenticate_user(db, email="bob@example.com", password="wrong-password")
    assert wrong is None


# ---------------------------------------------------------------------
# 3. Create application
# ---------------------------------------------------------------------
def test_create_application(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app", source="apk_upload")
    assert app.id is not None
    assert app.app_name == "RealBank"
    assert app.package_name == "com.realbank.app"


# ---------------------------------------------------------------------
# 4. Create app version
# ---------------------------------------------------------------------
def test_create_app_version(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    version = crud.get_or_create_app_version(db, application_id=app.id, version_name="2.1.0", version_code=21)
    assert version is not None
    assert version.application_id == app.id
    assert version.version_name == "2.1.0"

    # Neither version_name nor version_code known -> honest None, no row.
    unknown = crud.get_or_create_app_version(db, application_id=app.id, version_name=None, version_code=None)
    assert unknown is None


# ---------------------------------------------------------------------
# 5. Create scan
# ---------------------------------------------------------------------
def test_create_scan(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    scan = crud.create_scan(
        db, user_id=None, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=72, risk_level="MEDIUM", recommendation="INSTALL_WITH_CAUTION", confidence=None,
    )
    db.commit()
    assert scan.id is not None
    assert scan.application_id == app.id
    assert scan.security_score == 72


# ---------------------------------------------------------------------
# 6. Store vulnerability
# ---------------------------------------------------------------------
def test_store_vulnerability(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    scan = crud.create_scan(
        db, user_id=None, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=40, risk_level="HIGH", recommendation="AVOID_INSTALLING", confidence=None,
    )
    vuln = crud.add_vulnerability(
        db, scan_id=scan.id, cwe="CWE-89", type_="SQL Injection", severity="HIGH", confidence=91,
        file_name="LoginActivity.java", line_number=42, source="getIntent().getStringExtra",
        sink="rawQuery", description="Unsanitized string concatenation into rawQuery().",
    )
    db.commit()
    assert vuln.id is not None
    assert vuln.scan_id == scan.id
    assert vuln.cwe == "CWE-89"


# ---------------------------------------------------------------------
# 7. Store ML prediction
# ---------------------------------------------------------------------
def test_store_ml_prediction(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    scan = crud.create_scan(
        db, user_id=None, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=40, risk_level="HIGH", recommendation="AVOID_INSTALLING", confidence=None,
    )
    pred = crud.add_ml_prediction(
        db, scan_id=scan.id, model_name="xgboost_hybrid", model_version="1.0",
        predicted_class="CWE-89", confidence=87, shap_summary=[{"feature": "string_concat_in_sink", "value": 0.42}],
    )
    db.commit()
    assert pred.id is not None
    assert pred.scan_id == scan.id
    assert pred.shap_summary[0]["feature"] == "string_concat_in_sink"


# ---------------------------------------------------------------------
# 8. Store recommendation
# ---------------------------------------------------------------------
def test_store_recommendation(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    scan = crud.create_scan(
        db, user_id=None, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=40, risk_level="HIGH", recommendation="AVOID_INSTALLING", confidence=None,
    )
    rec = crud.add_recommendation(
        db, scan_id=scan.id, risk_level="HIGH", recommendation="AVOID_INSTALLING",
        reason="Untrusted input reaches a raw SQL sink.", confidence=87,
    )
    db.commit()
    assert rec.id is not None
    assert rec.scan_id == scan.id
    assert rec.recommendation == "AVOID_INSTALLING"


# ---------------------------------------------------------------------
# 9. Search application
# ---------------------------------------------------------------------
def test_search_application(db):
    crud.get_or_create_application(db, app_name="RealBank Mobile", package_name="com.realbank.app")
    crud.get_or_create_application(db, app_name="Totally Unrelated Weather App", package_name="com.weather.app")

    results = crud.search_applications(db, query="realbank")
    assert len(results) == 1
    assert results[0]["app_name"] == "RealBank Mobile"

    no_match = crud.search_applications(db, query="nonexistent-app-xyz")
    assert no_match == []


# ---------------------------------------------------------------------
# 10. Get security assessment
# ---------------------------------------------------------------------
def test_get_security_assessment(db):
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    scan = crud.create_scan(
        db, user_id=None, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=40, risk_level="HIGH", recommendation="AVOID_INSTALLING", confidence=None,
    )
    crud.add_vulnerability(
        db, scan_id=scan.id, cwe="CWE-89", type_="SQL Injection", severity="HIGH", confidence=91,
        file_name="LoginActivity.java", line_number=42, source="getIntent", sink="rawQuery", description="...",
    )
    db.commit()

    latest = crud.get_latest_scan_for_application(db, app.id)
    assert latest is not None
    assert latest.id == scan.id
    assert latest.risk_level == "HIGH"
    assert len(latest.vulnerabilities) == 1
    assert latest.vulnerabilities[0].cwe == "CWE-89"


# ---------------------------------------------------------------------
# 11. User history isolation
# ---------------------------------------------------------------------
def test_user_history_isolation(db):
    alice = crud.create_user(db, email="alice2@example.com", password="pw-alice-123", name="Alice")
    carol = crud.create_user(db, email="carol@example.com", password="pw-carol-456", name="Carol")
    app = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")

    crud.create_scan(
        db, user_id=alice.id, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=90, risk_level="LOW", recommendation="SAFE_TO_INSTALL", confidence=None,
    )
    crud.create_scan(
        db, user_id=carol.id, application_id=app.id, app_version_id=None, scan_type="apk_upload",
        security_score=20, risk_level="HIGH", recommendation="AVOID_INSTALLING", confidence=None,
    )
    db.commit()

    alice_history = crud.get_user_history(db, alice.id)
    carol_history = crud.get_user_history(db, carol.id)

    assert len(alice_history) == 1
    assert len(carol_history) == 1
    assert alice_history[0]["security_score"] == 90
    assert carol_history[0]["security_score"] == 20


# ---------------------------------------------------------------------
# 12. Unknown application
# ---------------------------------------------------------------------
def test_unknown_application(db):
    assert crud.get_application_by_id(db, 999999) is None
    assert crud.get_latest_scan_for_application(db, 999999) is None
    assert crud.get_alternatives(db, 999999) == []  # never a guessed alternative


# ---------------------------------------------------------------------
# 13. Transaction rollback
# ---------------------------------------------------------------------
def test_transaction_rollback(db, monkeypatch):
    app_count_before = db.query(crud.models.Application).count()
    scan_count_before = db.query(crud.models.Scan).count()

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure mid-transaction")

    monkeypatch.setattr(crud, "add_recommendation", _boom)

    scan_report = {
        "app_name": "RollbackTestApp",
        "risk_level": "high",
        "security_score": 10,
        "detections": [{"type": "Dangerous Permission", "code": "READ_SMS"}],
        "malicious_urls": [],
        "explanation": "test",
    }
    with pytest.raises(RuntimeError):
        crud.persist_apk_scan(db, user_id=None, scan_report=scan_report)

    # Nothing from the failed transaction should have been persisted.
    assert db.query(crud.models.Application).count() == app_count_before
    assert db.query(crud.models.Scan).count() == scan_count_before


# ---------------------------------------------------------------------
# 14. Duplicate package/version handling
# ---------------------------------------------------------------------
def test_duplicate_package_and_version_handling(db):
    app1 = crud.get_or_create_application(db, app_name="RealBank", package_name="com.realbank.app")
    app2 = crud.get_or_create_application(db, app_name="RealBank (renamed listing)", package_name="com.realbank.app")
    assert app1.id == app2.id  # same package_name -> same row, not a duplicate

    v1 = crud.get_or_create_app_version(db, application_id=app1.id, version_name="3.0.0", version_code=30)
    v2 = crud.get_or_create_app_version(db, application_id=app1.id, version_name="3.0.0", version_code=30)
    assert v1.id == v2.id  # same (application_id, version_name, version_code) -> same row

    total_apps = db.query(crud.models.Application).filter(crud.models.Application.package_name == "com.realbank.app").count()
    total_versions = db.query(crud.models.AppVersion).filter(crud.models.AppVersion.application_id == app1.id).count()
    assert total_apps == 1
    assert total_versions == 1


# ---------------------------------------------------------------------
# Phase 8A: version-aware APK persistence, driven end-to-end through
# crud.persist_apk_scan() with a scan_report shaped exactly like what
# apk_scanner.scan_apk_file() now produces (package_name/version_name/
# version_code/application_label from a real manifest parse). These
# scan_report dicts are hand-built test fixtures standing in for that
# real parse output - they are not claims about any actual APK.
# ---------------------------------------------------------------------

def _apk_scan_report(package_name, version_name, version_code, app_label,
                      risk_level="low", security_score=90, min_sdk_version=None,
                      target_sdk_version=None, debuggable=None, allow_backup=None,
                      features=None, abis=None):
    return {
        "app_name": "irrelevant-temp-upload-name.apk",
        "package_name": package_name,
        "version_name": version_name,
        "version_code": version_code,
        "application_label": app_label,
        "min_sdk_version": min_sdk_version,
        "target_sdk_version": target_sdk_version,
        "debuggable": debuggable,
        "allow_backup": allow_backup,
        "features": features,
        "abis": abis,
        "risk_level": risk_level,
        "security_score": security_score,
        "detections": [],
        "malicious_urls": [],
        "explanation": "test",
    }


def test_apk_scan_new_application_and_version_persistence(db):
    scan = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.realapp", "1.0", 10, "Real App"),
    )

    application = db.query(crud.models.Application).filter(
        crud.models.Application.package_name == "com.example.realapp"
    ).first()
    assert application is not None
    assert application.app_name == "Real App"  # real label preferred over the upload filename

    version = db.query(crud.models.AppVersion).filter(
        crud.models.AppVersion.application_id == application.id
    ).first()
    assert version is not None
    assert version.version_name == "1.0"
    assert version.version_code == 10

    assert scan.application_id == application.id
    assert scan.app_version_id == version.id


def test_apk_scan_same_application_new_version_does_not_overwrite_old_scan(db):
    scan_v1 = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.versioned", "1.0", 10, "Versioned App", "high", 20),
    )
    scan_v2 = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.versioned", "1.1", 11, "Versioned App", "low", 90),
    )

    # Same application, not duplicated.
    assert scan_v1.application_id == scan_v2.application_id
    applications = db.query(crud.models.Application).filter(
        crud.models.Application.package_name == "com.example.versioned"
    ).all()
    assert len(applications) == 1

    # Two distinct version rows, two distinct scans - the earlier
    # assessment is never overwritten.
    assert scan_v1.app_version_id != scan_v2.app_version_id
    assert scan_v1.id != scan_v2.id
    assert scan_v1.risk_level == "HIGH"
    assert scan_v2.risk_level == "LOW"

    versions = db.query(crud.models.AppVersion).filter(
        crud.models.AppVersion.application_id == scan_v1.application_id
    ).all()
    assert len(versions) == 2

    both_scans = db.query(crud.models.Scan).filter(
        crud.models.Scan.application_id == scan_v1.application_id
    ).all()
    assert len(both_scans) == 2


def test_apk_scan_links_each_scan_to_the_version_it_actually_scanned(db):
    scan_v1 = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.linktest", "1.0", 10, "Link Test App"),
    )
    scan_v2 = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.linktest", "2.0", 20, "Link Test App"),
    )

    version_for_scan_v1 = db.get(crud.models.AppVersion, scan_v1.app_version_id)
    version_for_scan_v2 = db.get(crud.models.AppVersion, scan_v2.app_version_id)

    assert version_for_scan_v1.version_name == "1.0"
    assert version_for_scan_v2.version_name == "2.0"


def test_apk_scan_same_application_same_version_reuses_version_row(db):
    scan_a = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.reupload", "2.0", 20, "Reupload App"),
    )
    scan_b = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.reupload", "2.0", 20, "Reupload App"),
    )

    # Re-scanning the identical version reuses the same AppVersion row -
    # not a blindly-created duplicate.
    versions = db.query(crud.models.AppVersion).filter(
        crud.models.AppVersion.application_id == scan_a.application_id
    ).all()
    assert len(versions) == 1
    assert scan_a.app_version_id == scan_b.app_version_id

    # But each upload is still recorded as its own Scan - re-scanning
    # doesn't erase the previous assessment.
    assert scan_a.id != scan_b.id
    both_scans = db.query(crud.models.Scan).filter(
        crud.models.Scan.application_id == scan_a.application_id
    ).all()
    assert len(both_scans) == 2


# ---------------------------------------------------------------------
# Phase 8B: min_sdk_version / target_sdk_version / debuggable /
# allow_backup persistence, against real MySQL.
# ---------------------------------------------------------------------

def test_apk_scan_persists_android_metadata_on_app_version(db):
    scan = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report(
            "com.example.androidmeta", "1.0", 10, "Android Meta App",
            min_sdk_version=24, target_sdk_version=34, debuggable=False, allow_backup=True,
        ),
    )
    version = db.get(crud.models.AppVersion, scan.app_version_id)
    assert version.min_sdk_version == 24
    assert version.target_sdk_version == 34
    assert version.debuggable is False
    assert version.allow_backup is True


def test_apk_scan_stores_none_for_missing_android_metadata_not_guessed(db):
    scan = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.nometa", "1.0", 10, "No Meta App"),
    )
    version = db.get(crud.models.AppVersion, scan.app_version_id)
    assert version.min_sdk_version is None
    assert version.target_sdk_version is None
    assert version.debuggable is None
    assert version.allow_backup is None


def test_apk_rescan_fills_in_previously_missing_android_metadata(db):
    # First scan of this version had a manifest parse that couldn't
    # determine min_sdk_version (e.g. a malformed attribute); a later
    # re-scan of the SAME version parses cleanly - the version row should
    # pick up the real value without erasing anything, and without
    # creating a duplicate AppVersion row.
    scan_a = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.fillgap", "1.0", 10, "Fill Gap App", debuggable=True),
    )
    scan_b = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report(
            "com.example.fillgap", "1.0", 10, "Fill Gap App",
            min_sdk_version=26, debuggable=False,  # a different value - must NOT overwrite the real one already stored
        ),
    )
    assert scan_a.app_version_id == scan_b.app_version_id  # still the same version row

    version = db.get(crud.models.AppVersion, scan_a.app_version_id)
    assert version.min_sdk_version == 26  # filled in - was genuinely missing before
    assert version.debuggable is True  # NOT overwritten - a real value was already stored


# ---------------------------------------------------------------------
# Phase 8C: features_json / abis_json persistence, against real MySQL.
# ---------------------------------------------------------------------

def test_apk_scan_persists_features_and_abis_on_app_version(db):
    features = [
        {"feature_name": "android.hardware.camera", "required": True, "required_explicit": True, "gl_es_version": None},
        {"feature_name": "android.hardware.nfc", "required": False, "required_explicit": True, "gl_es_version": None},
    ]
    scan = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report(
            "com.example.featuretest", "1.0", 10, "Feature Test App",
            features=features, abis=["arm64-v8a", "armeabi-v7a"],
        ),
    )
    version = db.get(crud.models.AppVersion, scan.app_version_id)
    assert version.features_json == features
    assert version.abis_json == ["arm64-v8a", "armeabi-v7a"]


def test_apk_scan_stores_empty_lists_not_null_when_none_declared(db):
    # apk_scanner.py always returns [] (never None) when no features/ABIs
    # were found - empty is a real, verified fact ("this build declares
    # none"), distinct from "not yet analyzed".
    scan = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report(
            "com.example.nofeatures", "1.0", 10, "No Features App",
            features=[], abis=[],
        ),
    )
    version = db.get(crud.models.AppVersion, scan.app_version_id)
    assert version.features_json == []
    assert version.abis_json == []


def test_apk_rescan_replaces_features_and_abis_not_gap_filled(db):
    # Unlike the scalar SDK/debuggable/allowBackup fields, features/abis
    # are lists - every scan's real findings fully replace what was
    # stored before (see get_or_create_app_version's docstring).
    scan_a = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.rescanfeatures", "1.0", 10, "Rescan Features App",
                                      features=[{"feature_name": "android.hardware.camera", "required": True,
                                                 "required_explicit": True, "gl_es_version": None}],
                                      abis=["armeabi-v7a"]),
    )
    scan_b = crud.persist_apk_scan(
        db, user_id=None,
        scan_report=_apk_scan_report("com.example.rescanfeatures", "1.0", 10, "Rescan Features App",
                                      features=[], abis=["arm64-v8a", "armeabi-v7a"]),
    )
    assert scan_a.app_version_id == scan_b.app_version_id
    version = db.get(crud.models.AppVersion, scan_a.app_version_id)
    assert version.features_json == []
    assert version.abis_json == ["arm64-v8a", "armeabi-v7a"]


def test_get_candidate_applications_for_ranking_excludes_target_and_returns_real_data(db):
    target = crud.get_or_create_application(db, app_name="Target App", package_name="com.example.target", category="Finance")
    db.commit()
    scan_a = crud.persist_apk_scan(db, user_id=None, scan_report=_apk_scan_report(
        "com.example.alt1", "1.0", 1, "Alt One", risk_level="low", security_score=90))

    candidates = crud.get_candidate_applications_for_ranking(db, exclude_application_id=target.id)
    candidate_ids = [c["application"].id for c in candidates]
    assert target.id not in candidate_ids
    assert scan_a.application_id in candidate_ids
    match = next(c for c in candidates if c["application"].id == scan_a.application_id)
    assert match["risk_level"] == "LOW"
    assert match["security_score"] == 90
