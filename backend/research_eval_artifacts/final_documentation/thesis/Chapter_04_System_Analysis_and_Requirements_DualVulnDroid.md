K M IGLAVITHANA
DUAL-VULNERABILITY DETECTION IN ANDROID CODE: REAL-TIME SQL INJECTION AND CERTIFICATE VALIDATION DETECTION
CHAPTER 04 – SYSTEM ANALYSIS AND REQUIREMENTS

## 4.1 Introduction

Chapter 2 established, from the reviewed literature, that existing Android vulnerability-detection research rarely combines machine-learning prediction, static/data-flow evidence, real-time developer feedback, and joint CWE-89/CWE-295 coverage within one workflow. Chapter 3 described the research methodology used to close that gap: dataset preparation, feature engineering, model comparison, and the design of a Hybrid Decision Engine. This chapter translates that research problem into a systems-engineering statement. It analyses the practical shortcomings of the workflows available to a developer and to an end user in the absence of a system such as DualVulnDroid; defines the stakeholders, functional and non-functional requirements, constraints, and use cases the implemented system was built to satisfy; and traces each research objective stated in Chapter 1 to a concrete, verified requirement. Every requirement, use case, and system description in this chapter is drawn directly from the DualVulnDroid source code and from the automated and live-device validation evidence produced across Phases 14A–14D of this research; no functionality is described on the basis that it would be useful or is common in comparable tools, and no validation result is reported as more complete than the evidence actually supports.

## 4.2 Analysis of the Existing Problem

In the absence of a system such as DualVulnDroid, a developer identifies CWE-89 and CWE-295 vulnerabilities through one of three practical means, each carrying the specific limitations established in Chapter 2. Manual code review depends entirely on the reviewer's attention and familiarity with the two vulnerable patterns and does not scale to large or fast-moving codebases. A general-purpose static-analysis or SAST tool, where one is used, typically runs as a separate, manually triggered step rather than during editing, and, as the literature reviewed in Section 2.11 established, is not documented as combining a machine-learning prediction with an explicit source-to-sink trace and a separated, model-level explanation within a single finding. A developer working without any automated support has no in-editor signal at all until a vulnerability is later caught in testing, code review, or, in the worst case, after release.

From the perspective of a person deciding whether to install or continue using an already-published Android application, the equivalent gap is user-facing rather than developer-facing. General app-store listings and permission dialogs, as Felt et al.'s findings reviewed in Section 2.13 established, are poorly attended to and poorly understood by most users, and provide no application-specific explanation of why a given risk level was assigned, no explicit statement of whether the application is compatible with the user's own device, and no transparent, evidence-based suggestion of a safer alternative. Developer-facing and user-facing security information are, in the reviewed literature, treated as largely separate concerns, addressed by separate tools built on separate, unrelated detection pipelines. No system identified in the literature review was found to provide real-time, explainable, dual-CWE detection to a developer while also providing an end user with an equivalent, understandable security assessment grounded in the same underlying detection pipeline.

## 4.3 Proposed DualVulnDroid System

DualVulnDroid addresses the gap analysed above with three integrated components sharing one backend detection pipeline. The **IntelliJ/Android Studio plugin** (Kotlin) provides real-time, in-editor annotation of CWE-89 and CWE-295 findings as a developer writes code, a project-wide "Scan Project" batch-scanning action, a shared finding-detail view reachable via an Alt+Enter intention, and Quick Fix remediation for a small set of verified, narrowly-scoped patterns. The **FastAPI backend** exposes this same detection pipeline — the 7,610-dimensional hybrid feature representation, the production XGBoost classifier, SHAP explanation, and the Hybrid Decision Engine — over a versioned HTTP API, and persists application, scan, user, and chat data in a MySQL database. The **Flutter application** is the end-user-facing component: it allows a person to register/log in, search for an already-assessed application, review its security assessment and the evidence behind it, check its compatibility with their device, review safer alternatives where available, and ask a security-focused chatbot grounded in that same real, stored data. The system architecture is summarised as:

```
Android/IDE or Flutter UI
        |
        v
Backend API
        |
        v
Hybrid feature pipeline
        |
        v
XGBoost production model
        |
        v
SHAP
        |
        v
Hybrid Decision Engine
        |
        v
Developer/User result
```

This architecture is unchanged from the one described in Chapter 3 and validated across Phases 11–14 of this research; this chapter analyses the requirements it satisfies, not a new or reconsidered design.

## 4.4 Stakeholder and User Analysis

Three stakeholder groups were identified from the system's actual interfaces and usage patterns, and their requirements differ in kind, not only in interface.

A **developer** uses the IntelliJ/Android Studio plugin and requires: immediate, in-editor awareness of a CWE-89/CWE-295 finding as code is written; enough evidence (severity, confidence, source-to-sink trace, SHAP factors) to judge whether a finding merits action without leaving the editor; a safe, narrowly-scoped automatic fix where one genuinely exists, and an honest "manual remediation" message otherwise; and a project-wide scan for reviewing an existing codebase in one pass.

A **security analyst or researcher** is a secondary stakeholder who uses the same plugin interface as the developer, but with a different objective: auditing an existing codebase for CWE-89/CWE-295 exposure (via Scan Project) and inspecting the evidentiary basis of a finding (SHAP contributions, source-to-sink trace, Decision Engine reasoning) rather than necessarily applying a fix. No separate interface or role-based access control exists for this stakeholder in the current implementation; their requirements are satisfied by the same real-time and Scan Project functionality analysed in Section 4.10, used analytically rather than remediation-first.

An **application user** uses the Flutter application and requires: the ability to search for an application by name without needing to already know its package identifier; a security assessment expressed in terms of risk and a concrete recommendation, not a raw classifier label; an honest statement of whether the application will run on their specific device; a transparent, evidence-based alternative when an application is assessed as high risk; and a way to ask a follow-up question in natural language and receive an answer grounded in the same real data the rest of the application shows them, including their own real, previous chat exchanges on request, rather than a separately invented explanation.

## 4.5 Functional Requirements

Table 4.1 lists the functional requirements of DualVulnDroid. Each requirement's verification status uses the precise language established for this chapter: **Validated** where the described behaviour was genuinely exercised and observed (automated test, headless IntelliJ Platform integration test, or a live Android emulator session); **"Implementation and automated testing were validated; live Android UI validation remained outstanding"** where the backend/Flutter code and its automated tests pass but no on-device UI observation exists; and **Not applicable / not implemented** where no such feature exists in the current system.

**Table 4.1. Functional requirements.**

| ID | Requirement | Rationale | System Component | Verification/Evidence |
|---|---|---|---|---|
| FR-01 | The system shall analyse Android Java/Kotlin source code for CWE-89 and CWE-295 vulnerabilities, as a single file (real-time) and as a project-wide batch. | Directly addresses the dual-CWE, real-time detection gap identified in Chapter 2. | `predictor.py`, `security_features.py`, `dataflow.py`; `CodeSentinelAnnotator.kt`, `ProjectFileCollector.kt` | Validated — 46/55 Kotlin plugin tests incl. 9 headless IntelliJ Platform integration tests (Phase 14A) |
| FR-02 | The system shall classify a finding into one of four labels (s0/v0/s1/v1) and report a confidence value and severity. | A bare detection is insufficient for a developer or user to act on; a graded, labelled output is required. | `predictor.py` (`LABELS_ORDER`, `_severity_from_decision`) | Validated — Chapter 6 test-set evaluation; backend `pytest` suite |
| FR-03 | The system shall combine the ML prediction with static/data-flow evidence through a Hybrid Decision Engine, producing VULNERABLE, SAFE, or SUSPICIOUS_REVIEW. | Addresses the integration gap (Section 2.15): a model prediction alone is not treated as sufficient for a security decision. | `decision_engine.py` | Validated — Chapter 7 coverage/FNR/FPR analysis |
| FR-04 | The system shall provide a developer-oriented explanation for each finding, comprising SHAP feature contributions and separately-labelled static/data-flow evidence. | Addresses the explainability gap (Section 2.15); the two forms of evidence are kept distinct per Section 2.14's Pattern 5 finding. | `predictor.py` (`shapTopFeatures`), `decision_engine.py` (`decisionEvidence`), `CodeSentinelAnnotator.kt` tooltip | Validated — headless IDE test (Phase 14A) confirms real tooltip content |
| FR-05 | The IDE plugin shall annotate a VULNERABLE finding inline with severity, type, and confidence, and shall provide a full detail view via an Alt+Enter intention. | Real-time, in-editor feedback rather than a separate scanning step (Section 2.11/2.12). | `CodeSentinelAnnotator.kt`, `ShowFindingDetailsIntention.kt`, `MyToolWindow.kt` | Implementation and automated testing were validated (headless IDE test); live Android/IDE UI validation remained outstanding |
| FR-06 | The IDE plugin shall offer an automatic Quick Fix only for a verified, narrowly-scoped safe pattern (SQL parameterisation of a supported concatenation shape; `HostnameVerifier` unconditional `return true`), and shall fall back to a manual-remediation message otherwise. | Prevents unsafe automated remediation (Section 2.12's remediation-safety concern). | `SqlFixLocator.kt`, `CertificateFixLocator.kt`, `SafeSqlQuickFixJava/Kotlin.kt`, `SafeHostnameVerifierQuickFixJava/Kotlin.kt` | Validated — headless IDE test confirms only the targeted expression changes and a real backend re-scan confirms resolution |
| FR-07 | After a Quick Fix is applied, the system shall re-scan the modified code against the real backend and report whether the finding was actually resolved. | A fix must not be assumed successful; it must be verified. | `FixVerificationRunner.kt` | Validated — headless IDE test, real backend re-scan |
| FR-08 | The IDE plugin shall support a project-wide "Scan Project" action that batches source files, submits them to the backend, and renders an aggregated findings list with jump-to-source navigation. | Supports the security-analyst/researcher stakeholder's audit use case (Section 4.4). | `MyToolWindow.kt`, `ProjectFileCollector.kt`, `POST /developer/scan` | Implementation and automated testing were validated; live Android/IDE UI validation remained outstanding |
| FR-09 | The Flutter application shall allow a user to register and log in, with an authenticated session persisted across app restarts until explicit logout. | Baseline requirement for any user-specific functionality (assessment history, chat history). | `POST /register`, `POST /login`, `flutter_secure_storage` | Validated — live Android emulator session (Phase 14B) |
| FR-10 | The Flutter application shall allow a user to search for an application and view its real, stored security assessment, including risk level, recommendation, and evidence. | Core end-user decision-support requirement (Section 2.13). | `GET /apps/search`, `GET /apps/{id}/security` | Validated (known-application case, Phase 14B); unknown-application and network-error sub-cases: implementation and automated testing were validated, live Android UI validation remained outstanding |
| FR-11 | The Flutter application shall check and report Android-version, required-feature, and ABI compatibility using only real, extracted manifest data and real device data, reporting NOT_AVAILABLE rather than guessing when data is missing. | Prevents fabricated compatibility claims; a stated project-wide requirement (Chapter 3, Section 3.16). | `POST /apps/{id}/compatibility`, `compatibility.py` | Validated (COMPATIBLE case, Phase 14B); INCOMPATIBLE and NOT_AVAILABLE sub-cases: implementation and automated testing were validated, live Android UI validation remained outstanding |
| FR-12 | The Flutter application shall suggest safer alternative applications, excluding the target application and any HIGH/CRITICAL-risk candidate, each with a transparent, evidence-based reason. | Supports the user's decision when an application is assessed high-risk. | `GET /apps/{id}/alternatives`, `alternatives.py` | Validated — live Android emulator session (Phase 14B) |
| FR-13 | The system shall extract real APK manifest metadata upon APK upload and persist it as a single, all-or-nothing transaction. | Provides the real, verified data source for FR-11 and FR-02/03. | `POST /upload-apk`, `apk_scanner.py` (`pyaxmlparser`) | Validated — automated backend tests; no upload UI exists in the Flutter app (Not applicable at the mobile-UI level) |
| FR-14 | The chatbot shall answer general CWE-89/CWE-295 explanation questions using fixed, standard reference text, and application-specific questions using the real, stored assessment for a client-supplied `app_id`. | Addresses the requirement that chatbot answers never be fabricated; grounds every answer in real data. | `chatbot_logic.py`, `POST /ai-chat` | Validated for 2 of 8 required question types (live, Phase 14B); remaining 6: implementation and automated testing were validated (`test_chatbot.py`), live Android UI validation remained outstanding |
| FR-15 | The chatbot shall render the backend's reply verbatim in the Flutter UI, with no client-side rewriting. | Prevents the client from altering a factual, backend-grounded answer. | `chat_repository.dart`, `security_chat_screen.dart` | Validated — live Android emulator session (Phase 14B), direct visual comparison of logged reply vs. on-screen text |
| FR-16 | The system shall record and expose a user's own chat history, retrievable only by that authenticated user. | Closes the write-only chat-history gap identified during Phase 14B/14C code inspection. | `GET /user/chat-history`, `db/crud.py get_user_chat_history()`, `security_chat_screen.dart` | Implementation and automated testing were validated (7/7 backend + 2/2 Flutter tests); live Android UI validation remained outstanding |
| FR-17 | The system shall record a user's own APK-upload/scan history, correctly isolated per user. | Baseline user-data isolation requirement. | `GET /user/history`, `db/crud.py` | Validated — live Android emulator session (Phase 14B) |
| FR-18 | Research-only models (SVM, Random Forest, LSTM, CodeBERT) shall not be reachable through any production endpoint. | Enforces the frozen, XGBoost-only production architecture stated throughout this thesis. | `predictor.py` (imports only the production XGBoost artefact) | Validated — code review of `predictor.py`'s import/load path; confirmed absent from every endpoint in `app.py` |

## 4.6 Non-Functional Requirements

**Table 4.2. Non-functional requirements.**

| ID | Requirement | Rationale | System Component | Verification/Evidence |
|---|---|---|---|---|
| NFR-01 | Single-file real-time analysis should complete quickly enough for practical editor use. | Real-time feedback (Section 2.11) is only useful if latency does not disrupt the developer's workflow. | `predictor.py` | Measured (not a guaranteed SLA): feature construction ≈9.30 ms, XGBoost inference ≈0.40 ms, SHAP ≈28.93 ms, total `predict_code()` ≈70.03 ms (Phase 11); a separate later measurement recorded ≈39.82 ms under different warm-process conditions (Phase 12) |
| NFR-02 | The backend shall not crash on malformed or oversized input; the plugin shall never fail silently. | Reliability under real, imperfect developer input. | `APIClient.kt` (`lastError`/`lastBatchError`), backend size-limit guards | Validated — backend `pytest` suite; plugin unit tests |
| NFR-03 | Passwords shall never be stored in plaintext; sessions shall use signed, expiring JWTs; error responses shall never leak a token, password, or file-system path. | Baseline security requirement for any authenticated system. | Argon2 (`argon2-cffi`), `pyjwt` | Validated — code review of every `HTTPException` call site; live logout/re-login test (Phase 14B) |
| NFR-04 | The Flutter application shall present an honest empty/loading/error state for every screen, never a fabricated result. | Directly enforces the "no fabricated findings" principle stated throughout this research. | `state_views.dart`, `decision_card.dart` | Validated — live Android emulator session (Phase 14B) for the states actually reached; remaining error/empty sub-cases: implementation and automated testing were validated, live Android UI validation remained outstanding |
| NFR-05 | Every VULNERABLE/SUSPICIOUS_REVIEW finding shall carry both a SHAP-based model explanation and separately-labelled static/data-flow evidence. | Explainability requirement (Section 2.10/2.14). | `decision_engine.py`, `CodeSentinelAnnotator.buildTooltip()` | Validated — headless IDE test (Phase 14A) |
| NFR-06 | Model comparisons shall use a fixed random seed and a frozen, leakage-checked data split; production model artefacts shall be versioned and content-hashed. | Reproducibility requirement (Chapter 3, Section 3.21). | `research_eval/data_split.py` (seed=42), `predictor.py` (`PRODUCTION_MODEL_INFO`) | Validated — stored split/leakage-check artefacts; content-hash confirmed at backend startup |
| NFR-07 | Feature construction shall be implemented in exactly one shared module for both training and inference. | Prevents training/inference drift (Chapter 3, Section 3.10). | `ml/feature_pipeline.py` | Validated — module docstring and import graph confirm a single implementation |
| NFR-08 | The backend shall accept a bounded batch of files per project-scan request. | Scalability/resource-exhaustion protection. | `APIClient.MAX_FILES_PER_BATCH = 200` | Validated — enforced server-side, exercised by `BatchScanParsingTest` |
| NFR-09 | Compatibility checking shall never fabricate a RAM/CPU-model requirement in the absence of a verified data source. | Enforces the "no fabricated results" principle for a specific, previously-identified risk area. | `compatibility.py` (`hardware_compatibility_placeholder()`) | Validated — live Android emulator session confirms the UI displays "Hardware (RAM/CPU model): NOT AVAILABLE" verbatim (Phase 14B) |

## 4.7 System Constraints

Several constraints, architectural and environmental, shape what DualVulnDroid can be reasonably expected to do. The system has no verified source of an application's required RAM or CPU model anywhere in its data, so it deliberately never reports a RAM/CPU compatibility verdict rather than guessing one (NFR-09). The Flutter application has no APK-upload entry point; APK upload and manifest extraction are exposed only through the backend API — confirmed directly during Phase 14B validation via a `uiautomator` dump of the Dashboard, which showed no upload control. The backend has no offline mode: both the plugin and the Flutter application require the backend to be reachable, and the plugin's single-file scan uses a fixed 2-second network timeout, while its batch scan uses a longer, separately configured timeout suited to analysing up to 200 files in one request. The research-only models (SVM, Random Forest, LSTM, CodeBERT) are not exposed through any production endpoint (FR-18) and, per the explicit constraint governing this entire research programme, must not be integrated into production, retrained, or have the Decision Engine's thresholds altered as part of this or any subsequent chapter of this thesis. Finally, live GUI/device validation in this research was performed on a single Windows development machine and a single Android emulator profile (Pixel_4, API 36, x86_64); across Phases 14A–14D, live validation of several specific UI sub-cases was constrained by host resource availability at the time of each attempt, discussed fully in Section 4.15's validation status and carried forward honestly rather than claimed as complete.

## 4.8 Security Requirements

The system's security requirements, each verified against the implementation, are: user passwords are hashed with Argon2 before storage and are never persisted or logged in plaintext; authenticated requests use a signed JSON Web Token carried as an `Authorization: Bearer` header, verified server-side per request via the single `get_current_user` dependency; every user-scoped endpoint — scan history (`GET /user/history`) and, since Phase 14C, chat history (`GET /user/chat-history`) — derives the requesting user's identity exclusively from the verified JWT, never from a client-supplied identifier, and this isolation is directly tested (a second, independently authenticated user receives an empty result when requesting a different user's chat history, never that user's real messages); the Flutter application persists its token using `flutter_secure_storage` rather than plain local storage, and clears it on logout, confirmed live by relaunching the application post-logout and observing zero authenticated calls (Phase 14B); error responses returned to a client are generic and never include a stack trace, an internal file-system path, or a token/password value; and no research-only model or research-only Decision Engine threshold configuration is reachable through any production endpoint. A cross-cutting requirement re-stated here is that the system must never present a fabricated or invented result as if it were real — reflected in the Decision Engine's SUSPICIOUS_REVIEW state, the compatibility module's NOT_AVAILABLE state, and the chatbot's honest "not yet assessed" reply.

## 4.9 Machine Learning Requirements

The production ML pipeline is required to use a single, shared feature-construction module for both training and inference, producing a 7,610-dimensional hybrid representation (5,000-feature word TF-IDF + 2,000-feature character TF-IDF + 1,000-feature count vectoriser + 23 deterministic security/data-flow features), with every vectoriser fitted on the training split only (Chapter 3, Section 3.10). The production classifier is required to be **XGBoost** exclusively; the specific artefact loaded, its class order (s0, v0, s1, v1), and its selected boosting-round cutoff are version-identified via a content hash at load time. SVM, Random Forest, LSTM, and CodeBERT are required to remain research-only, evaluated under the shared protocol described in Chapter 3 and reported in Chapter 6, and are not integrated into `predictor.py` or reachable from any endpoint (FR-18). Every VULNERABLE/SUSPICIOUS_REVIEW prediction is required to carry a real SHAP explanation computed via a `TreeExplainer` against the actual loaded production booster, kept as a separately labelled field from the deterministic static/data-flow evidence (NFR-05). The Hybrid Decision Engine is required to load its operating thresholds from a calibrated, versioned artefact, falling back to fixed, documented reference defaults only if that artefact is absent, and must never have the research-only "Balanced" threshold configuration active in the production path — a constraint that remains explicitly frozen for the remainder of this thesis.

## 4.10 IDE Plugin Requirements

The plugin is required to register as an `ExternalAnnotator` for Java and Kotlin (and separately for XML, for network-security-configuration checks), so that annotation runs asynchronously and does not block the editor. It is required to attach, for every VULNERABLE finding, a severity-prefixed annotation message, a rich HTML tooltip (severity, confidence, decision, source-to-sink path or data-flow explanation, non-ML decision evidence, SHAP-flagged tokens, and, where no automatic fix is available, an explicit manual-remediation message), the Alt+Enter detail-view intention, and, where a locator confirms a supported pattern, exactly one Quick Fix. Scan Project is required to collect project source files (skipping empty, duplicate, and oversized files, each counted and reported), chunk them into backend-accepted batches, run the scan off the UI thread with IDE-native progress/cancellation support, and render results into the same shared findings list and detail renderer used by real-time findings. A Quick Fix is required to modify only the specific PSI expression it targets, to re-validate that its target pattern still matches immediately before applying, and to trigger a real, asynchronous backend re-scan afterward whose result is reported to the developer.

## 4.11 Mobile Application Requirements

The Flutter application is required to provide eight screens covering the full end-user workflow: Splash, Login, Dashboard, Search Application, Application Details, Device Compatibility, Security Chat, and Assessment History. It is required to present risk, recommendation, and compatibility information through consistent, reusable widgets (`RiskBadge`, `CompatibilityBadge`, `DecisionCard`, `VulnerabilityTile`, `AlternativeAppTile`, `CompatibilityCheckTile`) rather than ad hoc formatting per screen, so that the same real backend fields are always presented consistently. It is required to route every backend call through one centralised `ApiClient`, which automatically attaches the stored JWT and translates every HTTP failure mode into one of a small set of typed exceptions (`NetworkException`, `UnauthorizedException`, `NotFoundException`, `ValidationException`, `ServerException`), so that no screen constructs its own ad hoc error handling. It is required to never recompute a security score, risk level, or recommendation on the client — every such value is required to originate from a real backend response.

## 4.12 Chatbot Requirements

The chatbot is required to classify a user's message into one of a fixed set of intents (CWE-89 explanation, CWE-295 explanation, why-risky, what-to-do, explain-recommendation, compatibility, or a backward-compatible app-name lookup) using deterministic keyword matching, consistent with the project's existing non-LLM design; it is explicitly not required, and is not implemented, to perform general free-form natural-language understanding. For an application-context question, the chatbot is required to resolve a real, client-supplied `app_id` to the application's real, currently stored assessment rather than attempting to parse an application name out of free text — a requirement introduced specifically to fix a real, previously-existing defect in which a free-text context prefix could not be reliably matched by the backend's parser (found and fixed prior to Phase 14). The chatbot is required never to fabricate a finding, a risk level, or a recommendation. Every reply is required to be rendered verbatim by the Flutter client (FR-15). Since Phase 14C, the chatbot is additionally required to expose a user's own real chat history on request (FR-16), retrievable only by the authenticated user who sent those messages, in chronological order.

## 4.13 Backend and API Requirements

The backend is required to expose the following twenty endpoints, each verified present in `app.py`: authentication (`POST /register`, `POST /login`); developer-facing analysis (`POST /predict`, `POST /developer/predict`, `POST /developer/scan`, `POST /developer/explain`, `POST /developer/rescan`, `POST /decision`); application search and assessment (`GET /apps/search`, `GET /apps/{id}`, `GET /apps/{id}/security`, `POST /apps/{id}/compatibility`, `GET /apps/{id}/alternatives`); APK ingestion (`POST /upload-apk`); user-scoped history (`GET /user/history`, `GET /history/{user_id}` — the latter a documented, unauthenticated legacy endpoint retained only for backward compatibility, not the secure path); chat (`POST /chat`, `POST /ai-chat`, and, since Phase 14C, `GET /user/chat-history`); and a root health-check (`GET /`). The backend is required to persist every completed APK-derived scan as a single, all-or-nothing transaction. The backend is required to remain internally consistent about which recommendation is "current" for a given scan, using the same latest-recommendation tie-break rule everywhere a "current" recommendation is read.

## 4.14 Database Requirements

The database is required to be MySQL, accessed via SQLAlchemy, with schema evolution managed through Alembic migrations, and is required to never silently substitute SQLite in place of a genuinely configured MySQL connection. The schema is required to provide exactly the ten tables verified in `db/models.py`: `users`, `applications`, `app_versions`, `scans`, `vulnerabilities`, `ml_predictions`, `recommendations`, `alternative_apps`, `chat_history`, and `security_tips`. No schema change was required or made to implement chat-history retrieval (FR-16); the `chat_history` table already carried every field the read path needed. User-scoped data (scan history, chat history) is required to be isolated per user at the query level, not filtered client-side — directly confirmed for chat history by a dedicated automated test in which a second, independently authenticated user receives an empty result rather than another user's real messages.

## 4.15 Use Case Analysis

Table 4.3 summarises the use cases identified from the system's actual entry points; detailed flows for each follow.

**Table 4.3. Use case summary.**

| Use Case ID | Name | Actor |
|---|---|---|
| UC-01 | Real-time code inspection | Developer |
| UC-02 | View finding detail (Alt+Enter) | Developer |
| UC-03 | Scan Project | Developer, Security Analyst/Researcher |
| UC-04 | Apply Quick Fix | Developer |
| UC-05 | Register and log in | Application user |
| UC-06 | Search and review application security | Application user |
| UC-07 | Check device compatibility | Application user |
| UC-08 | View safer alternatives | Application user |
| UC-09 | Ask the security chatbot | Application user |
| UC-10 | Retrieve own chat history | Application user |
| UC-11 | Upload and assess an APK | Backend/API client (no Flutter UI) |

**UC-01 — Real-time code inspection**

- *Actor:* Developer
- *Preconditions:* Plugin installed and enabled; backend reachable.
- *Main Flow:* Developer edits a Java/Kotlin file → `CodeSentinelAnnotator.collectInformation()` captures the file text on the UI thread → `doAnnotate()` calls the real backend `/predict` on a background thread → the Hybrid Decision Engine returns VULNERABLE → the annotator attaches a severity-prefixed annotation with a rich tooltip (severity, confidence, decision, evidence, SHAP tokens) and, where applicable, a Quick Fix.
- *Alternative Flow:* If the Decision Engine returns SUSPICIOUS_REVIEW or SAFE, `doAnnotate()` returns no result and **no annotation is created** — a directly observed, deliberate consequence of the engine's conservative calibration, not a plugin defect. If the backend is unreachable, `APIClient.lastError` is set with a specific reason and no annotation appears, without crashing.
- *Postconditions:* The developer sees a real, evidence-backed annotation for every VULNERABLE finding, and no annotation for anything the engine does not confidently decide.

**UC-02 — View finding detail (Alt+Enter)**

- *Actor:* Developer
- *Preconditions:* A real-time finding exists (UC-01 completed).
- *Main Flow:* Developer invokes Alt+Enter on an annotated finding → `ShowFindingDetailsIntention.invoke()` calls `MyToolWindow.showFinding()` → the tool window activates and renders the finding via the same `renderDetailHtml()` used by Scan Project.
- *Alternative Flow:* None identified — the intention reports itself always available once attached.
- *Postconditions:* The full evidence set for that one finding is shown in the tool window.

**UC-03 — Scan Project**

- *Actor:* Developer, Security Analyst/Researcher
- *Preconditions:* Plugin installed; backend reachable; project contains supported source files.
- *Main Flow:* Actor clicks "Scan Project" → `ProjectFileCollector` walks the project, skipping empty/duplicate/oversized files → files are chunked (≤200 per request) and submitted to `POST /developer/scan` off the UI thread with progress reporting → results populate the shared findings list.
- *Alternative Flow:* If no supported files are found, or a batch request fails, the tool window reports the specific reason (file counts, or `APIClient.lastBatchError`) rather than failing silently. A concurrent second scan is prevented while one is already running.
- *Postconditions:* An aggregated, project-wide findings list is available; selecting an entry shows its detail and enables jump-to-source.

**UC-04 — Apply Quick Fix**

- *Actor:* Developer
- *Preconditions:* A finding with a locator-confirmed supported pattern exists (SQL concatenation or `HostnameVerifier` `return true`).
- *Main Flow:* Developer applies the offered fix → the fix re-validates its target pattern still matches → only the targeted PSI expression is rewritten → `FixVerificationRunner` triggers a real, asynchronous re-scan and reports whether the finding was actually resolved.
- *Alternative Flow:* If the source changed since the finding was computed, the fix declines to apply and shows a "re-scan" warning rather than mutating stale code. Unsupported patterns never reach this use case — they remain a manual-remediation message in the tooltip.
- *Postconditions:* Code is modified at the expression level only; the developer receives a real, re-scanned confirmation of the outcome.

**UC-05 — Register and log in**

- *Actor:* Application user
- *Preconditions:* Backend reachable.
- *Main Flow:* User submits registration → `POST /register` creates an Argon2-hashed account → user logs in → `POST /login` returns a signed JWT → the token is stored via `flutter_secure_storage` and attached automatically to subsequent requests.
- *Alternative Flow:* Wrong password → 401, generic "Invalid email or password" message, no leaked detail. Relaunching the app after a prior login restores the session with no new `/login` call, only an authenticated `GET` using the persisted token.
- *Postconditions:* An authenticated session exists; protected screens become accessible.

**UC-06 — Search and review application security**

- *Actor:* Application user
- *Preconditions:* User authenticated.
- *Main Flow:* User searches by name → `GET /apps/search` → user opens a result → `GET /apps/{id}/security` returns the real, stored risk level, recommendation, and evidence.
- *Alternative Flow:* Unknown/no-match application, or a network error during the request — implementation and automated testing were validated; live Android UI validation of these two specific sub-cases remained outstanding (Section 4.16).
- *Postconditions:* The user sees a real assessment, or an honest "not yet assessed" state.

**UC-07 — Check device compatibility**

- *Actor:* Application user
- *Preconditions:* Application has extracted manifest metadata.
- *Main Flow:* User requests a compatibility check → `POST /apps/{id}/compatibility` compares real manifest data against real/entered device data → COMPATIBLE/INCOMPATIBLE/NOT_AVAILABLE per dimension, plus a combined recommendation.
- *Alternative Flow:* INCOMPATIBLE and NOT_AVAILABLE outcomes — implementation and automated testing were validated; live Android UI validation of these two specific outcomes remained outstanding. The COMPATIBLE case was directly observed live, including the confirmed architectural property that a favourable compatibility result never overrides an independently computed HIGH-risk security verdict.
- *Postconditions:* The user sees an honest, per-dimension compatibility result and a combined recommendation that never lets one override the other.

**UC-08 — View safer alternatives**

- *Actor:* Application user
- *Preconditions:* Application assessed HIGH/CRITICAL risk.
- *Main Flow:* User views the alternatives section → `GET /apps/{id}/alternatives` returns real, ranked, reason-carrying candidates.
- *Alternative Flow:* No qualifying candidate exists → an honest empty result, never a fabricated suggestion.
- *Postconditions:* The user sees real alternatives or an honest absence of them.

**UC-09 — Ask the security chatbot**

- *Actor:* Application user
- *Preconditions:* User authenticated.
- *Main Flow:* User asks a question, optionally with a selected application's `app_id` → `POST /ai-chat` classifies intent and resolves any app-specific data from real storage → the reply is rendered verbatim.
- *Alternative Flow:* No recognised app context and no recognised app name → generic greeting, never a fabricated answer. Six of the eight required question types: implementation and automated testing were validated; live Android UI validation remained outstanding.
- *Postconditions:* A real, grounded reply is displayed, or an honest fallback.

**UC-10 — Retrieve own chat history**

- *Actor:* Application user
- *Preconditions:* User authenticated; may or may not have prior chat messages.
- *Main Flow:* User opens the Security Chat screen → `initState()` calls `GET /user/chat-history` with the stored JWT → the backend returns only that user's own messages, chronologically → the screen displays them before becoming interactive.
- *Alternative Flow:* No prior history → an empty list, silently falling back to the existing empty-suggestions state. Fetch failure → the same silent fallback, never a fabricated transcript. A different authenticated user requesting this endpoint receives only their own (possibly empty) history, never another user's messages — verified directly by an automated test.
- *Postconditions:* Implementation and automated testing were validated (7/7 backend, 2/2 Flutter tests); live Android UI validation remained outstanding.

**UC-11 — Upload and assess an APK**

- *Actor:* Backend/API client (no Flutter UI reaches this use case)
- *Preconditions:* Valid APK file under the configured size limit.
- *Main Flow:* Client uploads a real APK → `apk_scanner.py` extracts real manifest metadata via `pyaxmlparser` → application/version/scan/vulnerability rows are persisted as one transaction.
- *Alternative Flow:* A mid-transaction failure leaves no partial rows (verified by an explicit rollback test).
- *Postconditions:* A new, real, queryable assessment exists. Not applicable / not implemented as a Flutter-UI-reachable use case — confirmed via a live `uiautomator` dump showing no upload control exists in the mobile application.

## 4.16 Requirements Traceability

Table 4.4 traces each research objective stated in Chapter 1 to the requirement(s), system component, implementation, and verification evidence that address it.

**Table 4.4. Requirements traceability matrix.**

| Research Objective (Ch. 1) | System Requirement | Component | Implementation | Verification Evidence |
|---|---|---|---|---|
| Investigate CWE-89/CWE-295 detection requirements | FR-01, FR-02 | Security feature extraction | `security_features.py`, `dataflow.py` | Chapter 6 model comparison; Chapter 7 per-CWE Decision Engine metrics |
| Prepare and validate a labelled dataset | (Methodology, Ch. 3) | Dataset pipeline | `ml/dataset_prep.py`, `research_eval/data_split.py` | Chapter 3 §3.7–3.9; stored split/leakage-check artefacts |
| Develop feature-engineered ML models | FR-02, NFR-05 | Feature pipeline + classical models | `ml/feature_pipeline.py`, `research_eval/train_svm.py`, `train_random_forest.py`, `train_xgboost.py` | Chapter 6 test-set metrics |
| Compare SVM, Random Forest, XGBoost | FR-02, FR-18 | Model comparison protocol | `research_eval/compare_models.py` | Chapter 6 comparison table |
| Evaluate LSTM/CodeBERT as supplementary research models | FR-18 (research-only) | Deep-learning research pipeline | `research_eval/lstm_train.py`, `codebert_train.py` | Chapter 6; explicitly excluded from every production endpoint |
| Develop/use static and data-flow evidence | FR-03, FR-04 | Data-flow analysis | `dataflow.py`, `security_features.py` | Chapter 7; `CodeSentinelAnnotator` tooltip content (Phase 14A) |
| Integrate XGBoost with an explainable Hybrid Decision Engine | FR-03, FR-04, NFR-05, NFR-06 | Decision Engine + SHAP | `decision_engine.py`, `predictor.py` | Chapter 7 coverage/FNR/FPR analysis |
| Develop real-time IDE/Android Studio support | FR-05–FR-08, NFR-01 | IntelliJ plugin | `CodeSentinelAnnotator.kt`, `MyToolWindow.kt`, Quick Fix classes | 55 Kotlin tests incl. 9 headless-IDE integration tests (Phase 14A) |
| Develop a Flutter-based user security decision-support application | FR-09–FR-12, FR-14–FR-17, NFR-04 | Flutter application | `dualvulndroid_flutter/lib/screens/*`, `repositories/*` | 41 Flutter tests; live Android emulator validation (Phase 14B); chat-history read path (Phase 14C) |
| Evaluate the complete system through automated and real-environment testing | All FR/NFR | Full system | Backend `pytest`, Kotlin Gradle suite, `flutter test`, Phases 14A–14D | 323 backend tests passed/2 skipped, 55 Kotlin passed, 41 Flutter passed; live validation status per Table 4.3/Section 4.15 |

## 4.17 Chapter Summary

This chapter analysed the practical gap left by existing developer and end-user workflows for CWE-89/CWE-295 detection, established the developer, security-analyst, and application-user stakeholders DualVulnDroid was built to serve, and translated the resulting requirements into eighteen functional requirements and nine non-functional requirement categories, each traced to a verified system component and its specific evidence. Eleven use cases were identified from the system's actual entry points and described with their preconditions, main and alternative flows, and postconditions, including the chat-history retrieval use case added in Phase 14C. The requirements traceability matrix connects every research objective stated in Chapter 1 to a concrete requirement, implementation, and piece of evaluation evidence. Consistent with the validation language established for this chapter, several specific sub-cases — unknown-application and network-error search, INCOMPATIBLE and NOT_AVAILABLE compatibility outcomes, six of the eight required chatbot question types, and chat-history's on-device display — are reported precisely as: their implementation and automated tests were validated, while their live Android UI validation remained partially constrained by host resource availability during the final validation attempt (Phase 14D) and was not reported as complete. This is not presented as a software defect; the corresponding automated evidence is retained as verified, and no unsupported live-device result has been claimed. The following chapter, Chapter 5 — Dataset and Feature Engineering, returns to the research pipeline underlying these requirements, presenting in full the dataset preparation and 7,610-dimensional feature representation this chapter's machine-learning requirements (Section 4.9) depend on.
