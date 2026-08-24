K M IGLAVITHANA
DUAL-VULNERABILITY DETECTION IN ANDROID CODE: REAL-TIME SQL INJECTION AND CERTIFICATE VALIDATION DETECTION
CHAPTER 05 – SYSTEM DESIGN AND ARCHITECTURE

## 5.1 Introduction

Chapter 4 established what DualVulnDroid must do: eighteen functional requirements, nine non-functional requirements, and eleven use cases, all derived from the implemented system. This chapter explains how those requirements are structurally realised as working software. It documents the system's architectural style, its component decomposition, the internal design of the machine-learning detection pipeline and the Hybrid Decision Engine built on top of it, the design of the IntelliJ/Android Studio plugin and the Flutter mobile application, the relational database schema that persists results, and the data flow that connects all of these parts for both a developer scanning source code and an end user assessing an installed application.

Every component, class, table, and endpoint described in this chapter is drawn directly from the current, working DualVulnDroid codebase (`backend/`, `DualVulnDroid/`, `dualvulndroid_flutter/`), re-verified against source during the writing of this chapter. No component described here is planned, aspirational, or fictional. The production XGBoost model, its 7,610-dimensional hybrid feature space, its 103-of-123 selected boosting rounds, and its four-class output ordering (`s0=0`, `v0=1`, `s1=2`, `v1=3`) are unchanged from the model already trained, evaluated, and reported on in earlier chapters; this chapter does not retrain, re-tune, or otherwise modify that model or the Hybrid Decision Engine that consumes its output. Where a described capability has been implemented and automatically tested but not yet observed on a live Android device, this chapter says so explicitly, using the same validation status already established in Chapter 4, rather than presenting it as a confirmed live result.

## 5.2 Overall System Architecture

**Figure 5.1. Overall DualVulnDroid Architecture.** *(figure_5_1_overall_architecture.png)*

Figure 5.1 shows the system's four architectural layers. The two entry points — the IntelliJ/Android Studio plugin, used by a developer scanning source code, and the Flutter application, used by an application user assessing an installed app — are structurally independent clients that never communicate with each other directly. Both issue HTTPS/JSON requests to a single FastAPI backend (`app.py`), which is the only component in the system with a loaded copy of the production XGBoost model, the SHAP explainer, and the Hybrid Decision Engine. Every prediction, decision, scan record, and chat message that either client produces is persisted to one MySQL database through SQLAlchemy models (`db/models.py`) and a shared data-access layer (`db/crud.py`).

This layering directly satisfies FR-01 through FR-06 (real-time and batch developer-side detection) and FR-09 through FR-14 (mobile-side application lookup, security assessment, compatibility, and alternatives) established in Chapter 4, without requiring either client to know anything about how the other is built.

## 5.3 Architectural Design

DualVulnDroid follows a **client–server architecture with a single shared analysis core**. Two independent clients — a developer-facing IDE plugin and an end-user-facing mobile application — both depend on the same backend service for every piece of machine-learning inference, decision logic, and persisted data. Neither client embeds its own copy of the model, the feature pipeline, or the Decision Engine; both call the same HTTP API and receive the same underlying analysis.

This single-backend style was a deliberate choice, not a default, for three reasons specific to this project:

- **One production model, one place to reason about it.** The XGBoost booster, its feature pipeline, and the Hybrid Decision Engine are loaded once, in one process (`predictor.py`), and every caller — plugin or mobile app — reaches the identical decision logic. A duplicated on-device model on the plugin side and a separate one on the mobile side would have created two independently-drifting sources of truth for the same CWE-89/CWE-295 detection task, which this project explicitly avoids.
- **Heterogeneous clients, homogeneous contract.** The plugin (Kotlin, IntelliJ Platform SDK) and the mobile application (Dart, Flutter) are built on unrelated runtimes with no natural way to share code. A REST/JSON contract is the only integration surface both can consume without either language depending on the other.
- **Server-side persistence, not client-side state.** Scan history, chat history, and application/vulnerability records must be available across sessions and, for the mobile app, across the user's own devices. Centralising storage in one MySQL database behind the backend is what makes `GET /user/history` and `GET /user/chat-history` meaningful at all.

Within the backend itself, the design separates three concerns that could otherwise have become entangled: **feature construction** (`ml/feature_pipeline.py`, `security_features.py`), **prediction and explanation** (`predictor.py`, which owns the loaded XGBoost booster and the SHAP explainer), and **decision-making** (`decision_engine.py`, which turns a raw model prediction plus corroborating evidence into a final `VULNERABLE` / `SAFE` / `SUSPICIOUS_REVIEW` outcome). This separation means the Decision Engine's thresholds and evidence weights can be reasoned about, and were calibrated, independently of the model's own probability outputs — a distinction returned to in Section 5.11.

## 5.4 DualVulnDroid Component Architecture

Before each component is examined in depth, this section catalogues the major components that make up the system, all confirmed present in the current codebase:

- **IntelliJ/Android Studio plugin** (`DualVulnDroid/`) — real-time and project-wide developer-side detection inside the IDE (Section 5.5).
- **Backend FastAPI application** (`backend/app.py`) — the single service both clients depend on (Section 5.6).
- **Hybrid feature pipeline and XGBoost production model** (`ml/feature_pipeline.py`, `security_features.py`, `predictor.py`) — the machine-learning core (Sections 5.7–5.9).
- **SHAP explainability layer** (`predictor.py`) — per-prediction, per-class feature attribution against the production booster (Section 5.10).
- **Hybrid Decision Engine** (`decision_engine.py`) — combines the model's prediction with corroborating evidence into a final decision (Section 5.11).
- **CWE-89 and CWE-295 detection logic** — realised jointly across the feature pipeline, the Decision Engine's evidence weighting, and the plugin's Quick Fix locators (Sections 5.12–5.13).
- **Flutter mobile application** (`dualvulndroid_flutter/`) — the end-user-facing client (Section 5.14).
- **Chatbot** (`chatbot_logic.py`, `/ai-chat`) — deterministic, intent-classified assistant grounded in real stored data (Section 5.15).
- **MySQL database** (`db/models.py`) — ten tables persisting users, applications, scans, findings, and chat history (Section 5.16).
- **Authentication mechanism** (`db/security.py`, JWT) — protects the user-scoped routes (Section 5.20).

These components are not independent subsystems bolted together; Section 5.21 returns to this list to describe specifically how each pair of components integrates.

## 5.5 IntelliJ/Android Studio Plugin Architecture

**Figure 5.6. IntelliJ Plugin Architecture.** *(figure_5_6_plugin_architecture.png)*

The plugin is structured around two entry points that share the same backend contract. Real-time detection is implemented as an IntelliJ Platform `ExternalAnnotator` (`CodeSentinelAnnotator`), registered in `plugin.xml` for Java and Kotlin files, following the platform's own three-stage annotation lifecycle: `collectInformation()` runs on the UI thread to gather the current file's PSI (Program Structure Interface) state; `doAnnotate()` runs on a background thread and is the only place network I/O is allowed, where `APIClient.kt` issues a `POST /predict` request carrying the file's source text; `apply()` runs back on the UI thread and turns a returned finding into a visible editor annotation, but **only when the backend response reports `vulnerable == true`**. A `SUSPICIOUS_REVIEW` decision from the Hybrid Decision Engine (Section 5.11) is deliberately not surfaced as an inline annotation — this is a real, verified characteristic of the current implementation, reflecting a conscious choice to reserve the always-visible in-editor signal for the model's higher-confidence findings.

Project-wide detection uses `ProjectFileCollector` to gather files for a "Scan Project" flow, driving `MyToolWindow` through a single `POST /developer/scan` batch request rather than one request per file. `MyToolWindow` maintains one shared findings list regardless of which entry point produced a given finding, with jump-to-source navigation from any entry. From an annotated line, or from the tool window, a developer can invoke `ShowFindingDetailsIntention` (Alt+Enter) to open a structured explanation reusing the same finding data already returned by the backend.

### 5.5.1 Quick Fix Subsystem

Quick Fixes are deliberately split into two responsibilities that do not share a class: **locators** (`SqlFixLocator.kt`, `CertificateFixLocator.kt`) decide *whether* a narrowly-scoped, safe rewrite applies to a given finding; **Quick Fix actions** (`SafeSqlQuickFixJava.kt`/`SafeSqlQuickFixKotlin.kt`, `SafeHostnameVerifierQuickFixJava.kt`/`SafeHostnameVerifierQuickFixKotlin.kt`) perform the actual PSI expression rewrite, once a locator has already confirmed it is safe to do so. After a Quick Fix is applied, `FixVerificationRunner` triggers a genuine asynchronous re-scan of the modified code through the same backend pipeline used everywhere else, so that "the fix worked" is a real, re-observed backend decision rather than an assumption baked into the fix itself.

### 5.5.2 Validation Status

The plugin's classes have been exercised through headless, automated IntelliJ Platform tests — including a dedicated integration test built on `BasePlatformTestCase` that drives the real `CodeSentinelAnnotator`, Quick Fix, and tool-window classes against the real backend rather than mocks (55 Kotlin tests passing in total). This headless platform-test escalation is a genuine increase in rigour over plain unit tests, because it exercises real plugin classes inside a real, if invisible, IntelliJ Platform instance. It is distinct from, and not a substitute for, live GUI validation, in which a human observes the plugin running inside a visible IDE window. Implementation and automated testing were validated for the plugin's core annotation, tool-window, and Quick Fix behaviour; a fully human-observed live-IDE validation session, distinct from the headless platform tests, was not separately conducted as part of this chapter's scope.

## 5.6 Backend Architecture

The backend is a single FastAPI application (`app.py`) that hosts the feature pipeline, the production model, the Decision Engine, and the data-access layer in one process. Startup performs a best-effort, non-fatal database connectivity check (`check_connection()`), logged but not blocking, since routes such as `/predict` have no database dependency and must keep working even if MySQL is briefly unavailable. Cross-cutting concerns are centralised rather than duplicated per route: a top-level exception handler converts any unhandled exception into a `500 internal_error` response instead of leaking a raw stack trace; a dedicated `HTTPException` handler normalises every application-raised error into a consistent `{"error": ..., "detail": ...}` shape; and a dedicated `DatabaseNotConfiguredError` handler returns an explicit `503` naming exactly what is missing, rather than a generic failure. Cross-origin access is enabled via FastAPI's `CORSMiddleware` so that both the plugin and the Flutter application can reach the API from their respective runtimes.

Internally, the backend is layered into request models (Pydantic, e.g. `CodeRequest`, `BatchScanRequest`, `ChatMessage`, `DeviceProfile`), route handlers (`app.py`), the shared analysis core (`predictor.py`, `decision_engine.py`), domain services (`compatibility.py`, `alternatives.py`, `apk_scanner.py`, `chatbot_logic.py`), and the data-access layer (`db/crud.py`, `db/models.py`). No route handler talks to the database directly; every query and write goes through `db/crud.py`, which is what allowed the chat-history read path (Section 5.15.1) to be added as one new query function plus one new route, without touching any other route's logic.

## 5.7 Machine Learning Architecture

**Figure 5.3. ML Detection Pipeline.** *(figure_5_3_ml_pipeline.png)*

`predictor.py` is the single, shared entry point every backend route ultimately calls (`predict_code()`), so the plugin's real-time flow, the plugin's batch scan flow, and any future caller all execute the identical pipeline:

1. **Text normalisation.** Raw source text is normalised (`ml/feature_pipeline.py`) before feature extraction, so superficial formatting differences do not by themselves change a prediction.
2. **Hybrid feature construction.** The normalised code is converted into the 7,610-dimensional hybrid feature vector described in Section 5.9.
3. **XGBoost prediction.** The production booster produces a four-way class-probability distribution over `s0`, `v0`, `s1`, `v1` (Section 5.8).
4. **SHAP explanation.** Per-prediction, per-class feature attribution is computed against the same loaded production booster (Section 5.10).
5. **Decision Engine evaluation.** Only after the SHAP computation completes is `decision_engine.evaluate()` invoked (`predictor.py`, line 377), combining the ML prediction with data-flow and static-rule evidence into a final decision (Section 5.11).

This ordering — features, then model, then explanation, then decision — reflects a real constraint: the Decision Engine's evidence score incorporates the model's own class probability alongside independently-computed corroborating evidence, so it must run after both are available.

## 5.8 XGBoost Production Model Architecture

**Table 5.1. Production XGBoost Model Configuration.**
| Property | Value |
|---|---|
| Objective | `multi:softprob` (4-class) |
| Feature dimensionality | 7,610 (hybrid: word TF-IDF + char TF-IDF + count vectors + 23 security features) |
| Saved boosting rounds | 123 |
| Selected (validated) boosting rounds | 103 of 123, applied via `booster[0:103]` slicing at load time |
| Class order | `s0=0`, `v0=1`, `s1=2`, `v1=3` |
| Artefact versioning | SHA-256 content hash of the loaded booster file, recorded in `PRODUCTION_MODEL_INFO` (`predictor.py`) |
| Explanation method | Real SHAP `TreeExplainer` against the loaded production booster |

The 123-tree saved booster extends past the round at which validation performance was actually confirmed; rather than silently serving 20 additional, unvalidated rounds, the production loader deterministically slices the booster to the first 103 validated rounds at load time. This is a load-time correctness fix, not a retraining step, and this chapter makes no change to it. The artefact itself is content-hash-versioned so `PRODUCTION_MODEL_INFO` can always answer, at runtime, exactly which trained booster is currently being served.

**Table 5.2. Production Model vs. Research Model Comparison.**
| Role | Model(s) |
|---|---|
| Production (deployed, serving live predictions) | XGBoost |
| Research comparison (evaluated, not deployed) | Linear SVM, Random Forest, XGBoost, LSTM, CodeBERT |

This distinction is architectural, not incidental: only XGBoost is loaded by `predictor.py` and reachable through any API route. LSTM and CodeBERT were evaluated during the research phase reported in earlier chapters and are not production components — no backend route, plugin class, or Flutter service loads or calls either of them. XGBoost was selected as the production model based on the combined research evaluation, existing explainability support, and established backend/plugin integration, not on a claim that it is superior to every alternative on every individual metric considered during that comparison.

## 5.9 Hybrid Feature Engineering Architecture

**Figure 5.4. XGBoost Hybrid Feature Architecture.** *(figure_5_4_xgboost_features.png)*

The production feature space combines three learned text-vectorisation views of the source code with one deterministic, hand-engineered view:

- A **word-level TF-IDF** vectoriser (`max_features=5000`, word n-grams 1–3), capturing lexical patterns such as identifier and API-call vocabulary.
- A **character-level TF-IDF** vectoriser (`max_features=2000`, character n-grams 2–5), capturing sub-token patterns that survive minor identifier renaming.
- A **count vectoriser** (`max_features=1000`, n-grams 1–2), capturing raw term frequency independent of TF-IDF weighting.
- **23 deterministic security and data-flow features** (`security_features.py`), covering signals such as traced source-to-sink concatenation, use of parameterised query APIs, and hostname-verification/certificate-validation patterns — the same category of signal the Hybrid Decision Engine separately reasons over as corroborating evidence (Section 5.11).

All four views are fit exclusively on the training split (the same 791-sample split reported in Chapter 3) and concatenated (`hstack()`) into a single vector before being handed to XGBoost. The three `max_features` values above are upper bounds, not guaranteed output sizes: the actual fitted vocabularies on this training corpus are smaller than their caps, so the true concatenated dimensionality is **7,610 features**, not the arithmetic sum of the three caps — the same, already-verified figure used throughout the model-training chapters, restated here unchanged.

## 5.10 SHAP Explainability Architecture

Explainability is not a separate model or a post-hoc approximation layered on top of the production booster — it is computed directly against it. `shap.TreeExplainer(model)` is instantiated once, against the same sliced, versioned booster described in Section 5.8, and reused across requests. For each prediction, `predictor.py` extracts the top contributing features twice: once for the model's predicted class, and once per class across all four classes, so that a route such as `/developer/explain` can answer not only "why was this flagged" but also "what would push this toward a different class." Because the explainer is built against the identical booster object the backend actually serves, SHAP output is guaranteed to describe the real production decision — it cannot silently drift from a separately-maintained explanation model, since no such second model exists.

## 5.11 Hybrid Decision Engine Architecture

**Figure 5.5. Hybrid Decision Engine Flow.** *(figure_5_5_decision_engine.png)*

The Hybrid Decision Engine (`decision_engine.py`) converts a raw XGBoost class-probability output into one of three final decisions: `VULNERABLE`, `SAFE`, or `SUSPICIOUS_REVIEW`. It exists as a distinct architectural layer, separate from the model itself, because a raw class probability alone does not capture corroborating structural evidence — such as whether a SQL string was actually traced from an external source to a query sink, or whether a certificate check was confirmed parameterised — that a security reviewer would reasonably weigh alongside the model's own confidence.

**Table 5.3. Decision Engine Evidence Weights (reference configuration).**
| Evidence signal | Weight | Direction |
|---|---|---|
| ML prediction (class probability) | ×1.0 | Signed by predicted class |
| Traced SQL source-to-sink | +2.0 | Toward VULNERABLE |
| Unparameterised string concatenation into a query | +1.2 | Toward VULNERABLE |
| Confirmed parameterised query | −1.5 | Toward SAFE |
| Confirmed certificate-validation vulnerability | +2.0 | Toward VULNERABLE |
| Suspicious (incomplete) certificate validation | +0.6 | Toward VULNERABLE |
| Confirmed safe certificate validation | −1.5 | Toward SAFE |
| Static keyword-rule corroboration | +0.4 | Toward VULNERABLE |

These signed weights are summed into a single `evidence_score`, compared against two calibrated thresholds loaded from `ml/artifacts/decision_engine_thresholds.json` at process start: a `vulnerable_threshold` and a `safe_threshold`. Scores at or above the vulnerable threshold produce `VULNERABLE`; scores at or below the safe threshold produce `SAFE`; scores between the two produce `SUSPICIOUS_REVIEW`. The reference values documented alongside this configuration are 1.5 and −0.9 respectively, but the values actually loaded and applied in production are the calibrated pair persisted in the JSON artefact (1.379 and −0.926) — the reference values exist as a documented default, not as what is currently active.

The three-way output design exists specifically to avoid forcing a binary choice on cases the evidence does not clearly support either way; the `SUSPICIOUS_REVIEW` band makes the boundary case a distinct, honestly-labelled outcome rather than an over-confident push to one side. This has a direct, already-documented consequence at the plugin layer (Section 5.5): because `CodeSentinelAnnotator.apply()` only annotates on `vulnerable == true`, a `SUSPICIOUS_REVIEW` result produces no inline annotation — a deliberate consequence of the Decision Engine's three-way design being consumed by a two-way (annotate / do not annotate) UI signal, confirmed as real, observed behaviour during headless plugin validation.

## 5.12 CWE-89 SQL Injection Detection Architecture

CWE-89 (SQL Injection) detection is realised jointly across the feature pipeline, the model's class structure, and the Decision Engine's evidence weighting — it is not a separate detector. In the production class order, `s0=0` denotes SQL-Injection-vulnerable and `s1=2` denotes SQL-Injection-safe; these two classes carry the model's learned signal for this vulnerability class specifically. At the feature level, the 23 deterministic security features (Section 5.9) include SQL-specific data-flow signals — whether a query string can be traced from an externally-influenced source to a query-execution sink, and whether the query construction uses parameterised APIs rather than direct string concatenation. At the decision level, the Hybrid Decision Engine weights a traced source-to-sink pattern at +2.0 toward `VULNERABLE`, unparameterised concatenation at +1.2, and a confirmed parameterised query at −1.5 toward `SAFE` (Table 5.3), independently of the model's own `s0`/`s1` probability, so that a case where the model is uncertain but the structural evidence is clear can still be resolved correctly.

On the plugin side, `SqlFixLocator.kt` is the component that decides whether a flagged SQL Injection finding has a structurally simple enough shape to offer a safe, automated rewrite; where it does, `SafeSqlQuickFixJava.kt`/`SafeSqlQuickFixKotlin.kt` perform the rewrite into a parameterised call, and `FixVerificationRunner` re-scans the result through the same production pipeline to confirm the class/decision actually changed.

## 5.13 CWE-295 Certificate Validation Detection Architecture

CWE-295 (Improper Certificate Validation) detection follows the same architectural pattern as CWE-89, applied to the certificate-validation classes. In the production class order, `v0=1` denotes Certificate-Validation-vulnerable and `v1=3` denotes Certificate-Validation-safe. The 23 deterministic security features include certificate/hostname-verification signals derived from the code's actual TLS-handling patterns — for example, whether a custom `HostnameVerifier` or `TrustManager` unconditionally accepts all certificates, versus one that performs a real validation check. At the decision level, the Hybrid Decision Engine weights a confirmed certificate-validation vulnerability at +2.0 toward `VULNERABLE`, a suspicious but incomplete validation pattern at +0.6, and a confirmed safe validation pattern at −1.5 toward `SAFE` (Table 5.3).

On the plugin side, `CertificateFixLocator.kt` decides whether a flagged certificate-validation finding can be safely rewritten; where it can, `SafeHostnameVerifierQuickFixJava.kt`/`SafeHostnameVerifierQuickFixKotlin.kt` perform the rewrite, again followed by a real `FixVerificationRunner` re-scan rather than an assumed outcome.

## 5.14 Flutter Mobile Application Architecture

**Figure 5.7. Flutter Application Architecture.** *(figure_5_7_flutter_architecture.png)*

The Flutter application is layered into screens, reusable widgets, repositories, per-concern API services, and one centralised HTTP client. Eight screens (Splash, Login, Dashboard, Search, Application Details, Device Compatibility, Security Chat, Assessment History) each depend on a repository rather than talking to HTTP directly. Repositories (`AuthRepository`, `AppsRepository`, `HistoryRepository`, `ChatRepository`, `DeviceProfileRepository`) each wrap one API service and expose a small, screen-facing method surface; API services each own exactly one HTTP concern.

`ApiClient` is the single point through which every request leaves the application: it attaches the persisted JWT (stored via `flutter_secure_storage`) automatically where one exists, and translates raw HTTP failures into a fixed set of typed exceptions (`NetworkException`, `UnauthorizedException`, `NotFoundException`, `ValidationException`, `ServerException`), so no screen has to parse a status code or a raw error body itself. This centralisation is what let the chat-history read path (Section 5.15.1) be added by extending one service and one repository method, without any change to `ApiClient` itself.

Implementation and automated testing were validated for the application's search, security-assessment, compatibility, and history features (41 Flutter tests passing); live Android UI validation was completed for known-application search, application details, security assessment, the compatible-device compatibility case, alternatives, and history isolation. For the unknown-application and network-error search sub-cases, and the incompatible / missing-device-information compatibility sub-cases, implementation and automated testing were validated, but live Android UI validation remained outstanding, blocked by a measured Android emulator/System-UI resource instability on the development host rather than by any defect in the application code.

## 5.15 Chatbot Architecture

**Figure 5.8. Chatbot Architecture.** *(figure_5_8_chatbot_architecture.png)*

The in-app assistant is deliberately not a large-language-model integration; `chatbot_logic.py` performs deterministic keyword-based intent classification over the caller's message text, matching it to a fixed set of intents (CWE-89 explanation, CWE-295 explanation, why-risky, what-to-do, explain-recommendation, compatibility, and general app lookup) and then answering using **real, already-stored data** for the application the question concerns — pulled through `database.get_app_assessment_by_id()` when the request carries a concrete `app_id`, rather than fuzzy name matching, whenever the client already has that context.

From the Flutter side, `SecurityChatScreen` sends messages through `ChatRepository`/`ChatApiService` to `POST /ai-chat`, and every exchange is persisted server-side via `database.save_chat_message()` into the `chat_history` table regardless of which intent matched.

### 5.15.1 Chat History Read Path

Until this was addressed directly, `chat_history` had a write path with no corresponding read path: every message was saved, but nothing ever read a user's own history back. This was identified through direct code inspection of `app.py`, `db/crud.py`, and the Flutter chat screen. The fix follows the exact security pattern already established by `GET /user/history`: `GET /user/chat-history`, protected by the same JWT dependency, retrieved strictly through the authenticated user's own identity (`current_user.id`), never a client-supplied identifier, and stored in and read from MySQL. On the Flutter side, `ChatApiService.getHistory()` and `ChatRepository.getHistory()` were added, and `SecurityChatScreen` now loads history in `initState()` when a signed-in user is present.

Implementation and automated testing were validated for this path — seven new backend tests (message-stored, own-history-retrieval-in-order, cross-user isolation, empty history, and three unauthorized-access cases) and two new Flutter repository tests, all passing — but live Android UI validation remained outstanding. For the chatbot generally, two of the eight required conversational questions (CWE-295 explanation and why-risky) were live-validated on-device in an earlier validation session; implementation and automated testing were validated for the remaining six required questions, but live Android UI validation remained outstanding for them.

## 5.16 Database Architecture

**Figure 5.9. Database Entity-Relationship Diagram.** *(figure_5_9_database_er.png)*

The schema (`db/models.py`) comprises ten MySQL tables, re-verified directly against source, `db/crud.py`, `app.py`, the chat-history implementation, and the authentication implementation for this chapter:

**Table 5.4. Database Tables and Relationships.**
| Table | Purpose | Key relationships |
|---|---|---|
| `users` | Registered accounts (email, Argon2 password hash, name) | Parent of `scans`, `chat_history` |
| `applications` | Distinct Android applications known to the system | Parent of `app_versions`, `scans`, `alternative_apps` |
| `app_versions` | A specific analysed build of an application (SDK levels, manifest features/ABIs) | FK → `applications`; parent of `scans` |
| `scans` | One analysis run, tying together a user, application, and version | FK → `users` (nullable), `applications` (nullable), `app_versions` (nullable); parent of `vulnerabilities`, `ml_predictions`, `recommendations` |
| `vulnerabilities` | Individual findings belonging to a scan (CWE, type, severity, source/sink) | FK → `scans`, cascade delete-orphan |
| `ml_predictions` | Stored model-output records for a scan | FK → `scans`, cascade delete-orphan |
| `recommendations` | Stored recommendation text/reason for a scan | FK → `scans`, cascade delete-orphan |
| `alternative_apps` | Curated application-to-alternative links | Two FKs → `applications` (self-referential) |
| `chat_history` | Persisted chatbot question/answer pairs | FK → `users` (nullable) |
| `security_tips` | Standalone reference content | No foreign key |

No table beyond these ten exists anywhere in the schema. `scans.user_id` is nullable, so a scan can exist without being tied to a signed-in user (a guest APK upload, for example); `vulnerabilities`, `ml_predictions`, and `recommendations` all cascade-delete with their parent `scan`, so a scan's full record is removed as one unit. `chat_history.user_id` is also nullable, matching `save_chat_message()`'s actual behaviour of only persisting a message against a user when `user_id` is supplied on the request. `GET /user/chat-history` is JWT-protected, user-specific, and retrieved strictly through the authenticated user's identity derived from the verified token — never a client-supplied user ID — reading only that user's own rows through this same nullable foreign key.

Multi-row writes that must succeed or fail together are wrapped in a single transaction rather than left to succeed partially: `POST /upload-apk` persists an application, version, scan, vulnerability, and recommendation set as one transaction, so a failure partway through leaves no partial, inconsistent record behind.

## 5.17 API Architecture

The backend exposes twenty routes, verified directly from `app.py`. All routes return JSON; validation errors and application-raised exceptions are normalised through centralised handlers (Section 5.6) into a consistent error shape.

**Table 5.5. Backend API Endpoints (verified against `app.py`).**
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/register` | none | Create a new user account |
| POST | `/login` | none | Authenticate and issue a JWT |
| GET | `/history/{user_id}` | none (legacy) | Unauthenticated, URL-supplied scan history; kept only for backward compatibility |
| GET | `/user/history` | JWT | Authenticated user's own scan history |
| GET | `/user/chat-history` | JWT | Authenticated user's own chat transcript |
| GET | `/` | none | Liveness/health message |
| POST | `/predict` | none | Single-file prediction (plugin real-time default) |
| POST | `/developer/predict` | none | Single-file prediction, full structured developer response |
| POST | `/developer/scan` | none | Batch prediction across up to 200 files |
| POST | `/developer/explain` | none | SHAP + evidence explanation for one file |
| POST | `/developer/rescan` | none | Re-scan with optional real before/after comparison |
| POST | `/decision` | none | Decision-Engine-only view of one prediction |
| GET | `/apps/search` | none | Search stored applications by name |
| GET | `/apps/{app_id}` | none | Application metadata |
| GET | `/apps/{app_id}/security` | none | Full stored security assessment for an application |
| POST | `/apps/{app_id}/compatibility` | none | Device-compatibility evaluation against a caller-supplied device profile |
| GET | `/apps/{app_id}/alternatives` | none | Curated or ranked alternative applications |
| POST | `/chat` | none | Legacy dashboard chatbot query |
| POST | `/ai-chat` | none | Conversational chatbot endpoint |
| POST | `/upload-apk` | none | APK upload, scan, and persistence |

For every route, request validation is performed by a Pydantic model (e.g. `CodeRequest`, `BatchScanRequest`, `DeviceProfile`); authentication, where required, is performed by the shared `get_current_user()` dependency (Section 5.20); processing calls into the shared analysis core or data-access layer described in Sections 5.7 and 5.16; the response is a plain JSON object built from real computed or stored values, never a fabricated placeholder; and error handling is centralised (Section 5.6) so that a malformed request, a missing resource (`404`), an authentication failure (`401`), or an unexpected server error (`500`/`503`) is reported consistently across all twenty routes. Twelve of the twenty routes have no authentication mechanism at all; this is a deliberate, documented characteristic — most of these routes return either stateless analysis results or already-public application data, and carry no per-user data that authentication would protect. Only the routes that expose a specific user's own private data (`/user/history`, `/user/chat-history`) are JWT-protected. No endpoint beyond these twenty exists in the implementation.

## 5.18 Data Flow

Two categories of input drive the system's data flow. A developer's source code, submitted through the plugin, flows through `predict_code()` directly (`/predict` or the `/developer/*` family) without ever touching the database unless the caller separately persists a result. An application user's interactions — search, security assessment, compatibility, alternatives, chat — instead flow through the database-backed `/apps/*`, `/chat`, and `/ai-chat` routes, reading and, where applicable, writing real stored `Application`, `Scan`, `Vulnerability`, `Recommendation`, and `ChatHistory` rows. The batch scanning route (`/developer/scan`) is a request-shaping convenience over the same single-file `predict_code()` path used everywhere else, accepting between 1 and 200 files in one call and reporting each file's own result or error independently, so a single bad file cannot fail an entire project-wide scan.

## 5.19 End-to-End Detection Workflow

**Figure 5.2. Real-Time Vulnerability Detection Workflow.** *(figure_5_2_realtime_workflow.png)*

**Figure 5.10. End-to-End Data Flow.** *(figure_5_10_end_to_end_flow.png)*

The detection pipeline, from source input to developer/user-facing response, is implemented as follows, with each stage's real location named:

- **Source Code** — supplied by the developer through the plugin's editor, or by an application user's APK upload.
- **Plugin / API Input** — `CodeSentinelAnnotator`/`ProjectFileCollector` via `APIClient.kt` (plugin), or `POST /upload-apk` / `POST /predict` directly (`app.py`).
- **Feature Construction** — `ml/feature_pipeline.py` text normalisation and vectorisation.
- **Hybrid Security Features** — `security_features.py`, 23 deterministic signals (Section 5.9).
- **XGBoost Prediction** — the production booster (Section 5.8), producing class probabilities.
- **Class + Confidence** — the `s0`/`v0`/`s1`/`v1` probability distribution.
- **SHAP Explanation** — `shap.TreeExplainer` per-prediction, per-class attribution (Section 5.10).
- **Data-flow / Static Evidence** — the same 23 security features, reasoned over independently by the Decision Engine.
- **Hybrid Decision Engine** — `decision_engine.evaluate()` (Section 5.11).
- **SAFE / VULNERABLE / SUSPICIOUS_REVIEW** — the Decision Engine's final three-way output.
- **Developer/User Response** — rendered by the plugin as an annotation, tool-window entry, or Quick Fix; rendered by the Flutter application as a security assessment, recommendation, or chat answer.

Every stage above corresponds to a real, named module or class already described in Sections 5.7–5.11; no stage in this list is implemented anywhere other than where stated.

## 5.20 Security and Authentication Architecture

Authentication is JWT-based (`db/security.py`, PyJWT). `POST /login` verifies credentials against an Argon2 password hash and, on success, issues a signed access token alongside the pre-existing `user`/`message` response fields — an additive change that left clients reading only the legacy shape unaffected. Every protected route depends on one shared FastAPI dependency, `get_current_user()`, which requires a well-formed `Authorization: Bearer <token>` header, decodes and verifies the token, and rejects expired tokens, structurally invalid tokens, and tokens referring to a user that no longer exists — each with a distinct `401` response — before resolving the request to a real `models.User` row.

No route derives "whose data is this" from a client-supplied user ID; `/user/history` and `/user/chat-history` both use `current_user.id` taken from the verified token, which is what makes their cross-user isolation guarantee structural rather than a convention that individual route handlers must remember to honour. The one exception, `GET /history/{user_id}`, is a legacy, intentionally-unauthenticated route retained only for backward compatibility and explicitly documented in-source as a known limitation, superseded by `GET /user/history`.

## 5.21 Integration Between Components

The components catalogued in Section 5.4 integrate through a small number of well-defined contracts, rather than ad hoc coupling:

- **Plugin ↔ Backend.** `APIClient.kt` is the plugin's sole integration point with the backend, issuing REST/JSON requests to `/predict` and `/developer/*`; the plugin holds no model, feature pipeline, or Decision Engine of its own.
- **Flutter ↔ Backend.** `ApiClient` (Dart) plays the identical role on the mobile side, adding JWT attachment and typed-exception translation on top of the same REST/JSON contract.
- **Backend ↔ ML core.** `app.py` route handlers never touch feature extraction, the XGBoost booster, or the Decision Engine directly; every route funnels through `predictor.predict_code()`, which internally sequences the feature pipeline, the model, SHAP, and `decision_engine.evaluate()` (Section 5.7).
- **Backend ↔ Database.** `app.py` never issues SQL directly; every read and write goes through `db/crud.py` against the SQLAlchemy models in `db/models.py` (Section 5.16), which is what keeps the authentication boundary (Section 5.20) enforceable in one place.
- **Decision Engine ↔ CWE-specific evidence.** The Decision Engine does not contain separate CWE-89 and CWE-295 code paths; it applies the same signed-evidence-sum mechanism (Table 5.3) to whichever of the 23 security features (Section 5.9) are relevant to the finding under evaluation, which is what allows Sections 5.12 and 5.13 to describe two vulnerability classes sharing one decision mechanism.
- **Chatbot ↔ Stored data.** `chatbot_logic.py` integrates with the rest of the system only by reading already-persisted `Application`/`Scan` data (`database.get_app_assessment_by_id()`) and writing to `chat_history` (`database.save_chat_message()`) — it does not call the ML pipeline or the Decision Engine directly, and it does not know about the plugin at all.

This integration pattern — a small number of narrow, one-directional contracts between components that otherwise know nothing about each other's internals — is what allowed the chat-history fix (Section 5.15.1) to be made by adding one new query, one new route, and one new client-side method, without any change to the ML pipeline, the Decision Engine, the plugin, or any other route.

## 5.22 Design Decisions and Justifications

**Table 5.6. Key Architecture Decisions.**
| Decision | Alternative considered | Justification |
|---|---|---|
| Single shared backend for both clients | On-device model in the plugin and/or the mobile app | Avoids two independently-drifting copies of the same detection logic; keeps the SHA-256-versioned production booster as the one source of truth |
| XGBoost as the production model | Deploying the best-performing research model regardless of integration cost | XGBoost was selected as the production model based on the combined research evaluation, existing explainability support, and established backend/plugin integration — not a claim of superiority on every individual metric |
| Hybrid security features alongside learned TF-IDF/count features | Learned text features alone | Gives the Decision Engine independently-computed, human-interpretable structural evidence (traced source-to-sink, parameterisation, hostname verification) that corroborates or tempers the model's own probability |
| Real SHAP against the production booster | A simplified or approximate explainability layer | Guarantees every explanation reflects the actual production decision, since no second, separately-maintained model exists to drift from it |
| Three-way Decision Engine output (`VULNERABLE`/`SAFE`/`SUSPICIOUS_REVIEW`) | Binary vulnerable/safe classification | Avoids forcing borderline evidence scores into an over-confident binary label; makes the boundary case an honest, distinct outcome |
| FastAPI backend | A framework without built-in request validation/typing | Pydantic request models give every route (Section 5.17) consistent input validation with minimal boilerplate |
| IDE plugin for developer-side detection | A standalone command-line scanner | Real-time, in-editor feedback matches the requirement (FR-01–FR-06) for detection during active development, not after the fact |
| Flutter for the mobile application | Separate native Android/iOS codebases | One Dart codebase serving both the UI and the API-integration layer described in Section 5.14 |
| MySQL via SQLAlchemy | A schemaless document store | Scan results, vulnerabilities, and chat history are inherently relational (Section 5.16); foreign-key cascades keep a scan's records consistent as one unit |
| Deterministic keyword-based chatbot | LLM-backed conversational chatbot | Keeps every chatbot answer traceable to a fixed intent and real stored data, with no possibility of a fabricated or hallucinated answer about a specific application's security status |

None of these decisions were revisited or changed while writing this chapter; they are documented as already-implemented, already-justified choices, consistent with the constraint that this chapter must not alter the XGBoost model, the Decision Engine, or any other production component.

## 5.23 Chapter Summary

This chapter has described DualVulnDroid's architecture component by component: the IntelliJ/Android Studio plugin, the FastAPI backend, the hybrid feature pipeline and production XGBoost model, the SHAP explainability layer, the Hybrid Decision Engine, the CWE-89 and CWE-295 detection logic realised jointly across them, the Flutter mobile application, the chatbot, the MySQL database, and the authentication mechanism and integration contracts that tie all of these together. Every element described — the 7,610-dimensional hybrid feature space, the 103-of-123-round production booster, the four-class `s0/v0/s1/v1` ordering and its mapping to CWE-89 and CWE-295, the real SHAP explainer, the Hybrid Decision Engine's three-way output, the twenty verified API endpoints, the JWT authentication boundary, the ten-table schema, and the newly-added chat-history read path — reflects the system as it is actually implemented today, cross-checked against source rather than against memory of earlier project phases.

Across the components discussed, implementation and automated testing were validated throughout the system, evidenced by 323 passing backend tests (2 skipped), 41 passing Flutter tests, and 55 passing plugin (Kotlin) tests, including a headless IntelliJ Platform integration test driving real plugin classes against the real backend. Live Android UI validation was completed for the system's core end-user flows (login, registration, session restore, logout, dashboard, known-application search, application details, security assessment, the compatible-device compatibility case, alternatives, and history isolation) and for the plugin's core annotation behaviour under headless platform testing. For a defined, narrower set of remaining cases — the unknown-application and network-error search sub-cases, the incompatible and missing-device-information compatibility sub-cases, six of the chatbot's eight required questions, and the chat-history UI flow — implementation and automated testing were validated, but live Android UI validation remained outstanding, a resource-availability limitation on the development host during this project's validation window rather than an architectural defect in any component documented in this chapter. APK upload is not applicable / not implemented from the Flutter client's UI, confirmed by direct UI inspection.

Chapter 4's functional and non-functional requirements are each traceable to a specific component documented here; Chapter 6 can proceed to describe how this architecture was implemented and tested in further detail, building on the design established in this chapter without needing to revisit or re-justify it.
