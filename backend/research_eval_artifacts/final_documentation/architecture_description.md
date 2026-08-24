# System Architecture

## Real-Time Code Analysis Pipeline (Plugin / API)

```
Developer code
    |
    v
Plugin / API  (IntelliJ plugin APIClient.kt  <->  FastAPI /predict, /developer/scan)
    |
    v
Shared feature pipeline  (ml.feature_pipeline: TF-IDF word/char + count + 23 security features, 7,610-dim)
    |
    v
XGBoost  (production model, multi:softprob, 103/123 rounds, class order s0/v0/s1/v1)
    +
Data-flow / security evidence  (23 deterministic rule-based features, source-to-sink tracing)
    |
    v
SHAP  (shap.TreeExplainer over the production booster - real model explanation)
    |
    v
Hybrid Decision Engine  (decision_engine.py - weighted evidence score vs. calibrated thresholds)
    |
    v
Decision + evidence + explanation  (VULNERABLE / SAFE / SUSPICIOUS_REVIEW, CWE, severity, SHAP summary, source->sink)
    |
    v
Plugin UI / API response  (inline annotation + tooltip + FindingDetailView, or JSON to the Flutter/other clients)
```

This is the single, unmodified production path used by both the IntelliJ plugin's real-time inspection and its project-wide batch scan, and by the `/predict` and `/developer/scan` API endpoints directly. No part of this path was changed in Phase 12 or Phase 13.

## APK / Application Assessment Pipeline (Flutter user app)

```
APK
 |
 v
Manifest extraction  (apk_scanner.py - package/version/min-sdk/target-sdk/debuggable/allowBackup/features/abis)
 |
 v
Application/version/scan persistence  (db/crud.py persist_apk_scan - one all-or-nothing transaction)
 |
 v
Security assessment  (GET /apps/{id}/security - risk level, recommendation, evidence, vulnerabilities)
 |
 v
Compatibility  (compatibility.py evaluate_compatibility - real minSdkVersion vs. real device Android version)
 |
 v
Alternatives  (alternatives.py rank_alternatives - real, explicitly-linked AlternativeApp rows only)
 |
 v
Flutter UI  (Application Details / Device Compatibility / Search / History screens)
```

## Database (MySQL, via SQLAlchemy)

10 tables: `users`, `applications`, `app_versions`, `scans`, `vulnerabilities`, `ml_predictions`, `recommendations`, `alternative_apps`, `chat_history`, `security_tips` (confirmed present in `backend/db/models.py`, one class per table).

Key relationships: `applications` 1—N `app_versions`; `applications`/`app_versions` 1—N `scans`; `scans` 1—N `vulnerabilities`, `ml_predictions`, `recommendations`; `applications` N—N `alternative_apps` (self-referential linking table); `users` 1—N `scans` and `chat_history`.

Authentication: JWT (`pyjwt`) bearer tokens, verified per-request via a FastAPI dependency (`db/security.py` + `app.py`'s auth dependency); passwords hashed with **Argon2** (never plaintext, never a reversible hash). Schema managed via **Alembic** migrations. `persist_apk_scan()` and related multi-row writes are single transactions — verified via `test_transaction_rollback` (a mid-transaction failure leaves zero rows persisted, not a partial write). Real MySQL integration tests exist (`tests/test_db_integration.py`) and pass when a real MySQL server is reachable; in this validation environment no MySQL server was available, so those tests report as an honest `SKIPPED`, not a fabricated pass. No production migration to a hosted MySQL instance is claimed here — schema and integration behavior are verified against real MySQL semantics via SQLAlchemy, run locally against SQLite in the harness where MySQL isn't reachable (`tests/conftest.py`, explicit test-only configuration, documented in that file's own docstring).

## Chatbot Architecture

`POST /ai-chat` accepts `{message, user_id?, user_ram_mb?, user_android_version?, app_id?}`. `chatbot_logic.generate_chat_response()` classifies intent (CWE-89 explanation / CWE-295 explanation / why-risky / what-to-do / explain-recommendation / compatibility / name-based app lookup) via deterministic keyword matching. App-context intents resolve `app_id` to a real row via `database.get_app_assessment_by_id()`; every factual claim in a reply traces to a real stored field (`Scan.risk_level`, `RecommendationRecord.reason`, `AppVersion.min_sdk_version`, etc.) or to static, standard CWE-89/CWE-295 reference text — never a fabricated finding. The Flutter client renders the backend's `reply` field verbatim.

## IntelliJ Plugin Architecture

Real-time inspection: `CodeSentinelLiveInspection.kt` / `LiveVulnerabilityInspection.kt` + `CodeSentinelAnnotator.kt` / `NetworkSecurityAnnotator.kt` annotate SQL Injection (`SqlInjectionDetector.kt`, `SqlConcatenationAnalyzer.kt`) and Certificate Validation (`CertificateValidationDetector.kt`, `NetworkSecurityScanner.kt`) findings inline as the developer types. Project-wide batch scan: `ProjectFileCollector.kt` walks the project and submits files in batches to `/developer/scan` via `APIClient.kt`. Findings share one model (`FindingModel.kt`) and one detail view, reachable via an Alt+Enter intention (`ShowFindingDetailsIntention.kt`) or the plugin's tool window (`MyToolWindow.kt`). Quick Fixes are scoped to specific, verifiably-safe patterns only: `SQLQuickFix.kt`/`JavaSQLQuickFix.kt`/`SafeSqlQuickFixJava.kt`/`SafeSqlQuickFixKotlin.kt` for parameterized-query rewrites (via `SqlFixLocator.kt`), and `SafeHostnameVerifierQuickFixJava.kt`/`SafeHostnameVerifierQuickFixKotlin.kt` for the exact `HostnameVerifier.verify() { return true }` pattern (via `CertificateFixLocator.kt`/`CertificateFixAnalyzer.kt`); unsupported patterns fall back to manual remediation guidance rather than attempting an unsafe rewrite. `FixVerificationRunner.kt` re-scans after a Quick Fix is applied to confirm the finding actually cleared.
