# DualVulnDroid

**Dual-Vulnerability Detection in Android Code: Real-time SQL Injection and Certificate Validation Detection**

A 4th-year Software Engineering undergraduate research project by **K M Iglavithana**. DualVulnDroid combines a production machine-learning detection pipeline, a static/data-flow-aware Decision Engine, a real-time IntelliJ/Android Studio plugin, and a Flutter mobile application into one system for detecting **CWE-89 (SQL Injection)** and **CWE-295 (Improper Certificate Validation)** in Android source code.

---

## 1. Project Overview

DualVulnDroid is a research-and-engineering project that investigates whether real-time, explainable, machine-learning-assisted vulnerability detection can be integrated directly into an Android developer's workflow (via an IDE plugin) while also giving end users a way to assess the security posture of applications they're considering installing (via a mobile app). The system is built around a single shared backend so both surfaces draw from the same production detection pipeline rather than two independently-maintained implementations.

## 2. Research Problem

Android applications continue to ship with well-documented, high-impact vulnerability classes — unsanitized SQL query construction (CWE-89) and improperly validated TLS/SSL certificates (CWE-295) — that existing static-analysis tooling often detects late (post-build/CI) or without machine-learning-assisted prioritization and explanation. This project investigates a combined ML + static/data-flow evidence approach evaluated against classical and deep-learning baselines, integrated into a real-time developer tool rather than an offline scanner.

## 3. Objectives

1. Investigate CWE-89/CWE-295 detection requirements, coding patterns, and data-flow characteristics.
2. Prepare, clean, and validate a labelled, leakage-checked training dataset.
3. Design and implement a feature-engineered ML pipeline combining lexical (TF-IDF) and deterministic security features.
4. Train and compare Linear SVM, Random Forest, and XGBoost under an identical evaluation protocol.
5. Evaluate LSTM and CodeBERT as supplementary research comparisons.
6. Develop deterministic static/data-flow analysis and combine it with the ML prediction.
7. Select a production classifier and build a Hybrid Decision Engine combining prediction, evidence, and SHAP explainability.
8. Design and implement a real-time IntelliJ plugin (annotation, detail view, project scanning, Quick Fix).
9. Design and implement a Flutter user-facing application (assessment, compatibility, alternatives, grounded chatbot).
10. Evaluate the system through automated testing and real-device validation.

## 4. Key Features

- Real-time, in-editor vulnerability annotation and Quick Fix in Android Studio/IntelliJ.
- A production XGBoost classifier over a 7,610-dimensional hybrid feature representation (learned lexical features + 23 deterministic security/data-flow features).
- Real SHAP (`TreeExplainer`) explainability computed directly against the production model — never an approximation.
- A Hybrid Decision Engine combining the ML prediction with independent static/data-flow evidence into a calibrated `VULNERABLE` / `SAFE` / `SUSPICIOUS_REVIEW` decision.
- A Flutter mobile app for application security assessment, device-compatibility checking, safer-alternative suggestions, and an AI security chatbot grounded strictly in real stored assessment data.
- A five-model research comparison (SVM, Random Forest, XGBoost, LSTM, CodeBERT) evaluated under one shared protocol, with per-CWE breakdowns.

## 5. System Architecture

```
                     ┌───────────────────────────┐
                     │   FastAPI Backend (app.py) │
                     │  Shared prediction engine   │
                     └─────────────┬─────────────┘
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
   ┌─────────▼─────────┐  ┌─────────▼─────────┐  ┌─────────▼─────────┐
   │  Feature Pipeline   │  │  Decision Engine    │  │  MySQL Database     │
   │  (TF-IDF + 23        │  │  (ML + static/data-  │  │  (users, apps,      │
   │  security features) │  │  flow evidence)      │  │  scans, chat)       │
   └─────────┬─────────┘  └───────────────────────┘  └───────────────────┘
             │
   ┌─────────▼─────────┐
   │  XGBoost (production) │
   │  + real SHAP          │
   └───────────────────────┘

     ┌────────────────────┐          ┌────────────────────┐
     │  IntelliJ Plugin     │          │  Flutter Mobile App  │
     │  (Kotlin, real-time)│          │  (Dart, user-facing) │
     └──────────┬──────────┘          └──────────┬──────────┘
                └──────────── HTTP/JSON ──────────┘
                          (shared backend)
```

## 6. Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python, FastAPI, Uvicorn |
| Database / ORM | MySQL, SQLAlchemy 2.x, Alembic migrations |
| Auth | Argon2 password hashing, PyJWT |
| ML — production | XGBoost, scikit-learn (TF-IDF/count vectorizers), SHAP |
| ML — research comparison | Linear SVM, Random Forest (scikit-learn), LSTM (TensorFlow/Keras), CodeBERT (HuggingFace `transformers`/`tokenizers`, PyTorch) |
| Mobile app | Flutter/Dart, Provider (state management), `http`, `flutter_secure_storage`, `device_info_plus` |
| IDE plugin | Kotlin, IntelliJ Platform SDK, Gradle |
| Testing | pytest (backend), `flutter test` (mobile), JUnit/IntelliJ Platform test framework (plugin) |

## 7. ML Models

Five models were evaluated under a single shared protocol on a frozen, leakage-checked test split (N=168):

| Model | Accuracy | Macro F1 | AUC | FPR | FNR |
|---|---|---|---|---|---|
| Linear SVM | 0.8036 | 0.7789 | 0.9025 | 0.2000 | 0.1828 |
| Random Forest | 0.7738 | 0.7519 | 0.8758 | 0.2133 | 0.2366 |
| **XGBoost (production)** | 0.7917 | **0.7874** | 0.8957 | **0.1467** | 0.2581 |
| LSTM | 0.7798 | 0.7448 | 0.8845 | 0.1600 | 0.2688 |
| CodeBERT | 0.7976 | 0.7780 | 0.8764 | 0.1733 | 0.2258 |

No single model dominates every metric. XGBoost leads Macro F1 and has the lowest FPR; Linear SVM has the lowest FNR. See Chapter 8 (`backend/research_eval_artifacts/final_documentation/thesis/`) for the full interpretation, including per-CWE breakdowns.

## 8. Production Model

**XGBoost is the sole production model.** It is selected on combined evidence (Macro F1, FPR, per-CWE-89 F1, existing SHAP/backend/plugin/Decision-Engine integration, and inference latency ≈0.40ms), not because it wins every metric — see the honest trade-off discussion in Chapter 8. The production booster is sliced to the first 103 of 123 saved boosting rounds at load time, over a 7,610-dimensional hybrid feature vector (word/char TF-IDF + count vectorizer + 23 deterministic security features). Artifacts: `backend/xgboost_artifacts/`.

**LSTM and CodeBERT are research-comparison models only.** Neither is loaded by the production backend, neither is reachable from the plugin or mobile app, and neither is part of the deployed detection pipeline. They exist purely to evaluate whether deep-learning approaches offer an advantage over the classical hybrid pipeline actually selected (see Chapter 8, Section on classical vs. deep learning — the answer, on this dataset, was no on aggregate Macro F1, though CodeBERT led CWE-89 recall specifically).

## 9. Security Detection

- **CWE-89 (SQL Injection)**: detected via the hybrid ML classifier plus deterministic source→sink data-flow analysis (`backend/dataflow.py`) tracing externally-influenced input into raw query construction.
- **CWE-295 (Improper Certificate Validation)**: detected via the same ML pipeline plus static analysis of certificate/hostname verification logic.
- **Decision Engine** (`backend/decision_engine.py`): combines the ML class probability (±1.0 weight) with independently-computed evidence (e.g. a confirmed certificate-validation issue carries a +2.0 weight) into a final `VULNERABLE`/`SAFE`/`SUSPICIOUS_REVIEW` decision. The deployed operating point is deliberately conservative: 32.7% auto-decision coverage, 3.03% FNR among auto-decided cases, 9.09% FPR. A higher-coverage (88.7%) candidate exists in research artifacts but is **not deployed** — its cross-split robustness was classified inconclusive.

## 10. Explainability

Real SHAP (`TreeExplainer`) values are computed directly against the exact loaded production XGBoost booster — never an approximation or a separately-trained explainer model. SHAP output is kept explicitly distinct from the deterministic data-flow evidence, so a user/developer can see "why the model predicted this" and "what static evidence corroborates it" as two separate, honestly-labeled things.

## 11. IntelliJ Plugin

Location: `DualVulnDroid/` (Kotlin, IntelliJ Platform SDK, Gradle). Provides real-time in-editor annotation of detected vulnerabilities, a finding detail view, whole-project scanning, and a Quick Fix action (with a locator/action separation so a fix is only offered when it's verifiably safe to apply, and the annotation is re-verified via a real re-scan after a fix is applied — never assumed). Validated via 55 automated Kotlin tests, including 9 platform-integration tests (`LiveAnnotatorIntegrationTest.kt`) that drive the real plugin classes against the real backend inside a headless IntelliJ Platform instance. **No visible-GUI (human-observed, on-screen IDE window) validation has been performed for this plugin** — this is an explicit, honestly-reported scope boundary, not a claim of full validation.

## 12. Flutter Mobile Application

Location: `dualvulndroid_flutter/` (Dart, Provider state management). Provides: authentication (login/registration, no 2FA), a dashboard with a real risk-summary and recent-assessments view, application search, application security-assessment detail (status, confidence, per-finding CWE detail), device-compatibility checking, safer-alternative suggestions, assessment history, a Settings screen, and the security chatbot below. A 4-tab bottom navigation (Home/Search/History/Chat) wraps the app; an "Installed Apps" listing and "Upload APK" flow are shown as honest "not available in this version" placeholders since neither has real backend/device capability behind it yet — see the app's own screens for the exact wording, and `backend/research_eval_artifacts/final_documentation/phase_ui_implementation_and_validation.md` for the full disposition of every design element implemented, restyled, or honestly deferred.

## 13. Security Chatbot

Backed entirely by the existing `POST /ai-chat` and `GET /user/chat-history` backend endpoints — every reply shown in the app is exactly what the backend returned, never generated, edited, or supplemented client-side. Grounded strictly in real, stored assessment data; an unknown question or missing data produces an honest fallback, never a fabricated answer.

## 14. Testing

| Component | Result | Notes |
|---|---|---|
| Backend (pytest) | **323 passed, 2 skipped** | Re-verified during this repository-preparation phase |
| Flutter (`flutter test`) | **59 passed, 0 failed** | Re-verified during this repository-preparation phase (baseline was 43 before the most recent UI-restyle phase, which added 16 new tests) |
| IntelliJ plugin (Kotlin) | **55 total** (46 `@Test` + 9 platform-integration tests) | Previously verified; not re-run in this phase since no Kotlin source changed |

`flutter analyze` is clean (0 errors; a handful of pre-existing, non-functional style-only lint infos).

## 15. Live Validation

Live, on-device validation status is reported honestly and is **not** uniformly "fully validated":

- **Phase 14B**: core flows (login, registration, session restore, logout, dashboard, known-app search, application details, security assessment, compatible-device compatibility, alternatives, cross-user history isolation, chatbot mechanism) — **PASS**, real device, real backend.
- **Phase 21**: the full chatbot experience (all required questions, suggestion chips, multi-turn conversation, chat-history persistence, unknown-question fallback, empty-input handling, a genuine network-outage-and-recovery cycle, long-response scrolling) plus the Home → Security Chat FAB — **PASS**, real device, 48 genuine screenshots.
- **Phase 22**: four remaining cases (Search — unknown application; Search — network error; Compatibility — INCOMPATIBLE; Compatibility — NOT_AVAILABLE) — **NOT VALIDATED**. The emulator entered a persistent System UI ANR before the app could launch; RAM was confirmed healthy (~4GB free) at the time, ruling out a memory cause. This is an unresolved host/environment issue, not an application defect.
- **Most recent UI-restyle phase**: an emulator boot was attempted again (same AVD, same config that succeeded in Phase 21) specifically to visually validate the restyled UI — the identical ANR reproduced immediately and did not clear after the standard bounded recheck, so the attempt was stopped. **No screen from the most recent restyle has on-device visual confirmation**; every claim about it rests on source review and the automated widget-test suite only.

No screenshot in this project is fabricated. See `backend/research_eval_artifacts/final_documentation/` for the full phase-by-phase validation reports.

## 16. Project Structure

```
vibe cording/
├── backend/                          FastAPI backend, ML pipeline, Decision Engine
│   ├── ml/                           Feature engineering, ablation artifacts
│   ├── xgboost_artifacts/            Production model (tracked, <1MB)
│   ├── research_eval_artifacts/      5-model comparison, CWE breakdowns, thesis
│   │   └── final_documentation/
│   │       └── thesis/               Chapters 1-8
│   ├── db/, alembic/                 Database models and migrations
│   └── tests/                        323 passed, 2 skipped
├── dualvulndroid_flutter/            Flutter mobile app
│   ├── lib/                          App source
│   └── test/                         59 passed, 0 failed
├── DualVulnDroid/                    IntelliJ/Android Studio plugin (Kotlin)
├── LARGE_FILES.md                    What's excluded from git and why
└── README.md                         This file
```

## 17. Installation

Clone the repository, then set up each component independently (they can be run/developed separately). Requires: Python 3.10+, a MySQL server, Flutter SDK `^3.12.2`, and a JDK for the IntelliJ plugin (via its bundled Gradle wrapper).

## 18. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env           # then fill in real values - see Environment Variables below
alembic upgrade head             # apply database migrations
uvicorn app:app --host 0.0.0.0 --port 8000
```

Run tests: `pytest`

## 19. Flutter Setup

```bash
cd dualvulndroid_flutter
flutter pub get
flutter test                     # run the test suite
flutter run                      # launch on a connected device/emulator
```

The app's backend base URL is configured in `lib/core/api_config.dart` (defaults to `10.0.2.2` for the Android emulator's host-loopback alias, or `127.0.0.1` for other targets).

## 20. IntelliJ Plugin Setup

```bash
cd DualVulnDroid
./gradlew.bat runIde              # Windows; ./gradlew runIde on macOS/Linux — launches a sandboxed IDE with the plugin installed
./gradlew.bat test                # run the automated test suite
```

## 21. Environment Variables

Defined in `backend/.env` (never committed — see `backend/.env.example` for the template):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | MySQL connection string for the application database |
| `TEST_DATABASE_URL` | MySQL connection string used by the backend test suite |
| `JWT_SECRET` | Secret used to sign/verify authentication JWTs — generate a real random value, never reuse the placeholder |
| `JWT_EXPIRE_MINUTES` | Token expiry, in minutes |
| `API_HOST` / `API_PORT` | Host/port the FastAPI server binds to |

## 22. Running the System

1. Start MySQL and ensure `DATABASE_URL` in `backend/.env` points to it.
2. Start the backend: `uvicorn app:app --host 0.0.0.0 --port 8000` (from `backend/`).
3. Run the Flutter app against it: `flutter run` (from `dualvulndroid_flutter/`) — the emulator reaches the host backend via `10.0.2.2:8000` automatically.
4. Run the IntelliJ plugin in a sandboxed IDE: `./gradlew runIde` (from `DualVulnDroid/`), then configure the plugin to point at the same running backend.

## 23. Research Artifacts

`backend/research_eval_artifacts/` holds the full research evaluation: per-model test metrics, confusion matrices, false positive/negative case lists, CWE-89/CWE-295 breakdowns, robustness/cross-split analysis, coverage-optimization analysis for the Decision Engine, and the complete thesis (`final_documentation/thesis/`, Chapters 1–8). The `codebert/` directory holds the **authoritative** CodeBERT results cited throughout the thesis; `codebert_final_artifacts/` and `codebert final result/` hold an earlier, superseded/disputed training run kept for provenance transparency only (see `LARGE_FILES.md`). Two Chapter 2 documents exist on disk — `Chapter_02_Critical_Literature_Review_and_Research_Gap_DualVulnDroid` is the canonical version actually cited by Chapters 7–8; `Chapter_02_Literature_Review_DualVulnDroid` is an earlier draft, kept but superseded.

## 24. Limitations

- All five-model and per-CWE metrics were measured on a single frozen 168-sample test split; no statistical significance test is reported, so close rankings between models should be read as directional, not certain.
- The Decision Engine's higher-coverage (88.7%) candidate operating point has inconclusive cross-split robustness and is not deployed.
- Four live-validation cases (Phase 22) remain unvalidated on-device due to an unresolved, intermittent host emulator instability (not RAM-related).
- The IntelliJ plugin has automated headless-platform validation only — no human-observed, visible-GUI validation exists.
- No user study, survey, or third-party human evaluation exists anywhere in this project; all claims are grounded in automated tests, research-evaluation artifacts, and the researcher's own live-validation sessions.
- "Installed Apps" and "Upload APK" are shown in the mobile UI as honest placeholders — no on-device app enumeration or APK-upload capability exists yet.
- Performance figures were measured on the researcher's own development host; no claim is made that they reproduce identically on different hardware or at production scale.

## 25. Future Work

- Resolve the remaining Phase 22 live-validation gaps once the underlying emulator/host instability is diagnosed and fixed.
- Gather further evidence (e.g. a larger or differently-composed dataset, cross-split robustness testing) before considering the Decision Engine's higher-coverage candidate for production.
- Implement real on-device "Installed Apps" enumeration and an "Upload APK" analysis flow to replace the current honest placeholders.
- Obtain visible-GUI (human-observed) validation of the IntelliJ plugin.
- Consider a controlled developer/user comprehension study to quantify how much SHAP and evidence explanations actually help end users, beyond the current mechanism-level verification.

## 26. Authors / Student Information

**K M Iglavithana** — 4th-year Software Engineering undergraduate, research project: *"Dual-Vulnerability Detection in Android Code: Real-time SQL Injection and Certificate Validation Detection."*

---

## License

No license has been selected yet for this repository. **User decision required** before publishing publicly — see the repository-preparation report for details. Until a license is added, all rights are reserved by default under standard copyright law; do not assume permissive reuse.
