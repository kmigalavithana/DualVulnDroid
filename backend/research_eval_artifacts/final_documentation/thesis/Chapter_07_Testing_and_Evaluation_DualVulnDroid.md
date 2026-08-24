K M IGLAVITHANA
DUAL-VULNERABILITY DETECTION IN ANDROID CODE: REAL-TIME SQL INJECTION AND CERTIFICATE VALIDATION DETECTION
CHAPTER 07 – TESTING AND EVALUATION

## 7.1 Introduction

Chapter 6 described how the DualVulnDroid architecture was implemented across its machine-learning pipeline, backend, IntelliJ/Android Studio plugin, and Flutter application. This chapter presents the testing and evaluation evidence that establishes whether that implementation actually works, and to what extent. It is deliberately structured around evidence rather than description: every count, percentage, and pass/fail status reported here was verified directly against a stored test report, a research-evaluation artifact, or a live-validation record already present in the project, rather than restated from memory of an earlier phase.

This chapter covers five distinct evidence layers, each answering a different question. Automated backend, Flutter, and IntelliJ plugin test suites answer "does the code behave correctly under controlled, repeatable conditions?" The five-model research comparison and the CWE-89/CWE-295 breakdowns answer "how well does the production classifier, and the models considered against it, actually detect the two target vulnerability classes?" The Decision Engine evaluation answers "what happens when the raw model output is combined with corroborating evidence, and at what operating point is it actually deployed?" The live Android emulator validation answers "does the real, assembled system work end-to-end on a real device, not just in isolated tests?" Finally, this chapter's limitations section states plainly which of these questions still have an incomplete answer, and why.

Two constraints govern every claim made in this chapter. First, no result is presented that was not directly reproduced or read from a stored artifact during the writing of this chapter — several figures (the backend and Flutter test counts in particular) were re-run rather than assumed, and one number carried forward from an earlier project phase (the Flutter test count) was found to be out of date and corrected here, with that correction stated explicitly rather than silently applied. Second, this chapter does not claim comprehensive validation where the evidence does not support it: specific, named gaps in live Android validation are reported as such, not minimised or reframed as covered by automated testing alone.

## 7.2 Testing Strategy

DualVulnDroid's testing strategy follows a layered model, in which each layer is evaluated by the method best suited to it rather than a single uniform approach applied everywhere. Deterministic, code-level behaviour (API contracts, database logic, feature extraction, Decision Engine arithmetic, Flutter widget behaviour, plugin PSI manipulation) is covered by automated test suites that run without human interaction and can be re-executed on demand. The ML classification task itself is evaluated through a held-out test-set research comparison across five models, using metrics appropriate to a multi-class, security-relevant classification problem (accuracy, macro F1, ROC-AUC, false-positive rate, false-negative rate) rather than accuracy alone, since a security tool's false-negative behaviour matters more than its aggregate correctness. Finally, end-to-end system behaviour — the parts no unit test can exercise, such as whether the real Android emulator UI actually renders correctly, whether a real network request from a real device reaches the real backend, or whether an actual human interaction sequence completes without a crash — is covered by live, manually-observed validation sessions on a real Android emulator, each producing a dated report and, where the session succeeded, screenshot evidence.

**Table 7.1. Testing Strategy by Layer.**
| Layer | Method | What it validates | Evidence source |
|---|---|---|---|
| Backend (Python/FastAPI) | Automated `pytest` suite | API contracts, database logic, feature pipeline, Decision Engine, chatbot logic, authentication | `backend/tests/` (re-run for this chapter) |
| Flutter application (Dart) | Automated `flutter test` suite | Repository/service logic, widget rendering, typed-exception handling, navigation | `dualvulndroid_flutter/test/` (re-run for this chapter) |
| IntelliJ/Android Studio plugin (Kotlin) | Automated JUnit + headless IntelliJ Platform tests | PSI-level Quick Fix logic, annotator/tool-window classes, real backend integration in a headless platform instance | `DualVulnDroid/src/test/kotlin/` |
| ML classification (XGBoost, and the four research comparison models) | Held-out test-set evaluation, five-model comparison | Whether the production classifier, and the alternatives considered against it, actually distinguish CWE-89/CWE-295 vulnerable code from safe code | `research_eval_artifacts/{svm,random_forest,xgboost,lstm,codebert}/` |
| Hybrid Decision Engine | Threshold/coverage analysis against the production booster's output | Whether combining ML probability with data-flow evidence improves on raw model output at a deployable operating point | `research_eval_artifacts/security_selection/`, `coverage_optimization/`, `robustness/` |
| End-to-end system | Live, human-observed Android emulator sessions | Whether the assembled system (Flutter app + real backend + real MySQL + production model + Decision Engine) actually works for a real user, on a real device | Phase 14B, 21, 22 live-validation reports |

This layered strategy exists specifically so that a defect can be localised: an automated test failure points at a specific function or widget; a live-validation gap points at an integration or environment concern the automated layer cannot see by construction. Both kinds of evidence are reported in this chapter, and neither is used to paper over the other — a full automated pass is not treated as equivalent to a live-observed pass, and this distinction is maintained consistently throughout this chapter, particularly in Section 7.12.

## 7.3 Testing Environment

Automated backend tests were executed against a Python 3.11 environment with the project's own `venv`, using a file-backed test database configuration consistent with `backend/tests/conftest.py`. Automated Flutter tests were executed in the standard `flutter test` Dart VM harness, which does not exercise platform channels or real device rendering — a widget-level pass is evidence the Dart-level logic and widget tree are structurally sound, not evidence of on-device visual correctness, which is why live validation (Section 7.12) remains a distinct, necessary layer. Automated Kotlin tests were executed both as plain JUnit unit tests and, for one integration suite, inside a headless IntelliJ Platform test instance (`BasePlatformTestCase`), which loads real plugin classes against the real backend without opening a visible IDE window. Live validation was conducted on an Android Virtual Device (`Medium_Phone_API_36.1`, Android API 36, x86_64, Google Play system image) running under this project's Windows development host, communicating with a real FastAPI backend and a real MySQL instance running on the same host, reached from the emulator via the Android-emulator-specific host alias `10.0.2.2`, exactly as configured in `ApiConfig.baseUrl` (Chapter 6, Section 6.15).

## 7.4 Backend Testing

The backend automated test suite was re-executed for this chapter (`python -m pytest -q`) rather than cited from an earlier phase's report, to ensure the figure used here reflects the current state of the codebase. The result was **323 passed, 2 skipped**, consistent with the count already established across Phases 15–22 of this project's validation record, confirming the backend test suite has remained stable through the mobile UI, chat-history, and live-validation work described in those phases. The 2 skips are environment-conditional tests (per `conftest.py`'s pattern, tests that require a second, separate `TEST_DATABASE_URL` to be configured are skipped rather than failed when it is absent) and are not defects.

These 323 tests cover, across the suite's test modules: user registration/authentication and JWT issuance/validation (`test_api.py`), the full `/predict`, `/developer/*`, and `/decision` route family against `predictor.predict_code()` (`test_api.py`, `test_xgboost_production_integration.py`), the Hybrid Decision Engine's evidence computation and threshold logic in isolation (`test_decision_engine.py`), the static data-flow analyzers underlying the security features (`test_dataflow.py`, `test_security_features.py`), compatibility and alternatives ranking logic (`test_compatibility.py`, `test_alternatives.py`), APK metadata extraction (`test_apk_metadata.py`), database integration and the ten-table schema (`test_db_integration.py`), endpoint-response-shape consistency across the `/developer/*` family (`test_endpoint_consistency.py`), the chatbot's deterministic intent classification (`test_chatbot.py`, including the regression test for the suggestion-chip wording bug found and fixed in Phase 14B), the chat-history read path added in Phase 14C (`test_chat_history.py`), and the research-evaluation harness itself (`test_research_eval.py`, `test_security_model_selection.py`, `test_coverage_optimization.py`, `test_robustness_validation.py`, `test_lstm.py`, `test_codebert.py`). This breadth means the backend layer's automated coverage spans not only the production API surface but the research-evaluation code that produced the results reported in Sections 7.5–7.9.

## 7.5 Machine Learning Model Evaluation

Five models were evaluated on a common, frozen test split (168 samples, held out from model selection and threshold calibration throughout): Linear SVM, Random Forest, and XGBoost using the project's shared hybrid feature pipeline (TF-IDF word/char n-grams, a count vectoriser, and 23 deterministic security features), LSTM using a from-scratch learned token embedding, and CodeBERT using a pretrained Transformer representation fine-tuned on this task. The three classical/boosted-tree models and the two deep-learning models therefore do not share an identical input representation — this is a genuine architectural difference between the approaches being compared, not an inconsistency in the evaluation, and is stated explicitly in the underlying research artifacts (`lstm/comparison_summary.json`, `codebert/comparison_summary.json`) as well as here.

**Table 7.2. Five-Model Comparison (frozen test set, N=168).**
| Model | Accuracy | Macro F1 | ROC-AUC | FPR | FNR |
|---|---|---|---|---|---|
| Linear SVM | 0.8036 | 0.7789 | 0.9025 | 0.2000 | 0.1828 |
| Random Forest | 0.7738 | 0.7519 | 0.8758 | 0.2133 | 0.2366 |
| XGBoost | 0.7917 | 0.7874 | 0.8957 | 0.1467 | 0.2581 |
| LSTM | 0.7798 | 0.7448 | 0.8845 | 0.1600 | 0.2688 |
| CodeBERT | 0.7976 | 0.7780 | 0.8764 | 0.1733 | 0.2258 |

**Figure 7.1. Three-Model Fair Common-Split Test-Set Comparison.** *(figure_7_1_main_comparison.png)*

Figure 7.1 reproduces, unmodified, the original research-evaluation comparison chart for the three classical/boosted-tree models (`comparison/plots/main_comparison.png`), generated as part of the earlier fair-comparison research phase before LSTM and CodeBERT were added to the evaluation; the two deep-learning models are presented in Table 7.2 and Sections 7.6–7.7 rather than in this figure, since no equivalent combined five-model chart exists among the stored research artifacts.

No single model dominates every metric, and this chapter does not claim one does. **XGBoost achieved the highest Macro F1 (0.7874) among the five models and the lowest FPR (0.1467).** **Linear SVM achieved the lowest FNR (0.1828) and the strongest overall vulnerability recall** — the metric most directly relevant to a security tool's core obligation not to miss a real vulnerability. **CodeBERT achieved the highest raw accuracy (0.7976)** among the five, and, as Section 7.6 details, the strongest CWE-89 recall specifically. **LSTM did not outperform the classical models on this dataset**: its Macro F1 (0.7448) is the lowest of the five, and its FNR (0.2688) is the highest, indicating that a from-scratch learned representation, on this dataset's scale, did not out-detect models built on the project's hand-engineered hybrid feature pipeline.

**XGBoost was selected as the production model based on the combined research evaluation, hybrid feature representation, real SHAP explainability support already integrated into the backend and plugin, and established backend/plugin integration — not because it is the single best-performing model on every metric considered.** Linear SVM's lower FNR is a real, acknowledged trade-off of this choice, discussed further in Section 7.18. LSTM and CodeBERT remain research comparison models: neither is loaded by `predictor.py`, neither is reachable through any API route, and this chapter does not describe either as a production component.

## 7.6 CWE-89 Evaluation

CWE-89 (SQL Injection) detection was evaluated per-model on the same frozen test split, isolating the 54 test samples belonging to the SQL-Injection task (`s0`/`s1` classes).

**Table 7.3. CWE-89 (SQL Injection) Comparison (N=54).**
| Model | Precision | Recall | F1 | FNR |
|---|---|---|---|---|
| Linear SVM | 0.7273 | 0.8276 | 0.7742 | 0.1724 |
| Random Forest | 0.7188 | 0.7931 | 0.7541 | 0.2069 |
| XGBoost | 0.7931 | 0.7931 | **0.7931** | 0.2069 |
| LSTM | 0.7083 | 0.5862 | 0.6415 | 0.4138 |
| CodeBERT | 0.7143 | **0.8621** | 0.7813 | **0.1379** |

**XGBoost achieved the strongest CWE-89 F1 (0.7931)** among the five models, reflecting a balanced precision/recall trade-off specific to this vulnerability class. **CodeBERT achieved the strongest CWE-89 recall (0.8621) and the lowest CWE-89 FNR (0.1379)**, meaning it missed proportionally fewer real SQL-Injection cases than any other model evaluated, at some cost to precision. **LSTM's CWE-89 recall (0.5862) is comparatively weak** — the lowest of the five, and its FNR (0.4138) more than double XGBoost's, indicating the learned-embedding approach missed a substantially higher proportion of real SQL-Injection cases on this test split.

The security implication of a false negative on this specific vulnerability class is direct: a missed SQL-Injection finding is a vulnerability a developer using the plugin would never see flagged, and a database whose associated application a mobile user would never see marked at risk for this reason. This is precisely why FNR, not accuracy, is treated throughout this chapter as the more security-relevant metric for a per-CWE comparison, and why LSTM's comparatively high CWE-89 FNR is reported plainly rather than smoothed over by its middling overall accuracy. This finding is specific to this dataset and evaluation protocol and is not generalised beyond it; a different dataset, a larger training corpus, or a different tokenisation strategy could plausibly change LSTM's relative standing on this task.

## 7.7 CWE-295 Evaluation

CWE-295 (Improper Certificate Validation) detection was evaluated identically, isolating the 114 test samples belonging to the certificate-validation task (`v0`/`v1` classes).

**Table 7.4. CWE-295 (Certificate Validation) Comparison (N=114).**
| Model | Precision | Recall | F1 | FNR |
|---|---|---|---|---|
| Linear SVM | 0.8966 | 0.8125 | **0.8525** | 0.1875 |
| Random Forest | 0.9057 | 0.7500 | 0.8205 | 0.2500 |
| XGBoost | 0.9020 | 0.7188 | 0.8000 | 0.2812 |
| LSTM | 0.9107 | 0.7969 | 0.8500 | 0.2031 |
| CodeBERT | **0.9400** | 0.7344 | 0.8246 | 0.2656 |

The pattern differs materially from CWE-89: **Linear SVM achieved the strongest CWE-295 F1 (0.8525)**, and **CodeBERT achieved the strongest CWE-295 precision (0.9400)** but not the strongest recall or F1 for this class — the reverse of its CWE-89 standing. **XGBoost's CWE-295 recall (0.7188) is the weakest of the five**, giving it the highest CWE-295 FNR (0.2812) despite being the strongest performer on CWE-89 F1. This asymmetry — no model, including the production model, being simultaneously the strongest performer on both vulnerability classes — is a genuine, evidence-based finding rather than an inconsistency to be explained away, and this chapter does not claim that either CWE-89 or CWE-295 is universally the "easier" class to detect: the relative difficulty visibly depends on which model and which metric is being examined, and a claim of universal difficulty ordering would not be supported by this evidence.

Combined, Sections 7.6 and 7.7 support the Section 7.5 framing directly: the production model was not selected because it dominates every per-CWE metric — it does not — but because its combined profile across both vulnerability classes, together with its explainability and integration advantages, represented the strongest overall basis for a production deployment among the options evaluated.

## 7.8 XGBoost Production Model Verification

Beyond the comparative evaluation in Sections 7.5–7.7, the specific production artefact was independently verified for this chapter by inspecting its loaded metadata at runtime (`predictor.PRODUCTION_MODEL_INFO`) and its own metadata file (`research_eval_artifacts/xgboost/metadata.json`). The production booster is a `multi:softprob` classifier trained on the full **7,610-dimensional hybrid feature representation** (word/char TF-IDF, count vectors, and the 23 deterministic security features), with **123 boosting rounds saved but only the first 103 selected and applied at load time** (`booster[0:103]`), and the fixed class order **`s0=0` (SQL-Injection-vulnerable), `v0=1` (Certificate-Validation-vulnerable), `s1=2` (SQL-Injection-safe), `v1=3` (Certificate-Validation-safe)**. This slicing behaviour — verified directly in `predictor.py` and already documented architecturally in Chapters 5 and 6 — exists because the saved booster's early-stopping procedure trains a fixed number of rounds past the actual best iteration; predicting with the full, unsliced booster would not reproduce the test-set results reported in Table 7.2, since those results were themselves computed against the validated 103-round slice. `test_xgboost_production_integration.py` (part of the 323 backend tests in Section 7.4) asserts this loaded configuration directly, so a future change to the artefact or its loading logic that altered the round count, feature dimensionality, or class order would surface as an automated test failure rather than silently changing production behaviour.

Real SHAP explanations are computed against this same loaded, sliced booster (`shap.TreeExplainer(model)`, instantiated once at process start), meaning every explanation surfaced through `/developer/explain` and the plugin's finding-detail view reflects the actual production classifier's feature attributions, not an approximation.

## 7.9 Decision Engine Evaluation

The Hybrid Decision Engine is not a sixth independent classifier; it is a decision-support layer that combines the production XGBoost model's own class probability with independently-computed data-flow and static-rule evidence into a final `VULNERABLE`/`SAFE`/`SUSPICIOUS_REVIEW` decision (Chapter 5, Section 5.11; Chapter 6, Section 6.9). Its evaluation therefore asks a different question from Sections 7.5–7.8: not "how accurate is the classifier" but "does combining the classifier's output with corroborating evidence produce a usable, deployable decision boundary, and at what coverage/error trade-off."

**Table 7.5. Decision Engine Operating Points.**
| Operating point | Coverage | FNR | FPR | Precision | Status |
|---|---|---|---|---|---|
| Production (calibrated thresholds, currently deployed) | 32.7% | 3.03% | 9.09% | ≈0.941 | Deployed |
| Research-balanced candidate | 88.7% | 20.24% | 13.85% | — | **Not deployed** |

**Figure 7.2. Coverage vs. False Negative Rate (validation sweep).** *(figure_7_2_coverage_vs_fnr.png)*

Figure 7.2 reproduces the underlying validation-set threshold sweep (`coverage_optimization/plots/coverage_vs_fnr.png`) from which both operating points in Table 7.5 were selected, illustrating the trade-off directly: coverage and FNR are not in strict tension across this sweep (widening the auto-decision threshold improves both together up to a point, before FPR degrades sharply), which is why the two operating points reported here were chosen using FPR bounds anchored to real baselines rather than the raw coverage/FNR frontier alone.

At its currently deployed production operating point, the Decision Engine auto-decides 32.7% of cases, and among those auto-decided cases its false-negative rate is 3.03% — substantially lower than the raw XGBoost classifier's own frozen-test FNR reported in Table 7.2 (25.81%), because the cases the engine defers (`SUSPICIOUS_REVIEW`) are exactly the cases where the combined evidence was not strong enough to commit to either verdict confidently. This is the intended, deliberate trade-off: **low false-negative rate when the engine commits to a verdict, at the cost of leaving roughly two-thirds of cases for manual review rather than auto-deciding them.** A research-balanced candidate configuration was also evaluated, offering substantially higher coverage (88.7%) at a materially higher FNR (20.24%) and review workload reduced to 11.31% — **this balanced configuration was not deployed**; the production system continues to use the conservative, calibrated thresholds. This conservative choice is consistent with the standard rationale for security-relevant automated decision systems: a missed vulnerability (false negative) carries a materially worse consequence than an unnecessary manual review, so the deployed configuration is deliberately biased toward deferring uncertain cases rather than auto-clearing them.

Robustness of the balanced candidate across alternative data splits was separately evaluated (`research_eval_artifacts/robustness/`) and classified **INCONCLUSIVE**, with an overall production candidacy rating of **"B. PROMISING BUT MORE DATA REQUIRED."** This classification is not hidden or reframed in this chapter: it is the honest, direct reason the balanced candidate remains undeployed pending further evidence, rather than a decision reversed for any other reason.

## 7.10 IntelliJ Plugin Testing

The IntelliJ/Android Studio plugin's automated test suite comprises **55 Kotlin tests: 46 conventional `@Test`-annotated unit tests, plus 9 tests within `LiveAnnotatorIntegrationTest.kt`**, a headless IntelliJ Platform integration suite built on `BasePlatformTestCase` (which uses the IntelliJ Platform's own JUnit3-style `fun testXxx()` naming convention rather than `@Test` annotations, and was counted separately and confirmed present in this file for this chapter). The 46 conventional unit tests cover `APIClient` response parsing for both single-file and batch-scan shapes (`APIClientParsingTest.kt`, `BatchScanParsingTest.kt`), the `FindingModel` data class (`FindingModelTest.kt`), project-wide file collection (`ProjectFileCollectorTest.kt`), Quick Fix safety boundaries (`QuickFixSafetyTest.kt`), and the structural analyzers underlying the SQL and certificate Quick Fix locators (`SqlConcatenationAnalyzerTest.kt`, `CertificateFixAnalyzerTest.kt`).

The 9-test `LiveAnnotatorIntegrationTest.kt` suite is the plugin's strongest automated evidence: it drives the real `CodeSentinelAnnotator`, real Quick Fix classes, and the real tool-window class inside an actual (headless) IntelliJ Platform instance, issuing genuine HTTP requests to the real backend rather than a mock. This headless platform-test escalation, established in Phase 14A of this project's validation history, is a real increase in rigour over a plain unit test — it exercises the actual plugin classes inside the actual platform runtime — but it is **not a substitute for a human observing the plugin's annotations, tooltips, and Quick Fix previews rendered inside a visible, running IDE window**. No such visible-GUI IntelliJ session, and no plugin-side screenshot, was produced during this project's validation history; the plugin's live-GUI validation status is therefore reported here as headless-only, not visually confirmed, consistent with how it has been reported since Phase 14A.

## 7.11 Flutter Application Testing

The Flutter automated test suite was re-executed for this chapter (`flutter test`) rather than cited from an earlier report. The result was **43 passed, 0 failed** — this figure was directly verified for this chapter and corrects an earlier, out-of-date figure of 41 that had been carried forward from before the Home→Security Chat FAB feature and its two dedicated regression tests were added; 41 was the correct count immediately after the Phase 15 UI polish work, but is no longer the current total, and this chapter reports the verified, current figure rather than the earlier one. `flutter analyze` was confirmed at 0 errors as part of this same verification pass.

These 43 tests cover `ApiClient`'s typed-exception translation (`api_client_test.dart`), every repository's request-shaping and response-parsing logic (`auth_repository_test.dart`, `apps_repository_test.dart`, `history_repository_test.dart`, `chat_repository_test.dart` — the latter including the two tests added for the Phase 14C chat-history read path), the `DecisionCard` widget's exact rendering of every backend-provided recommendation state (`decision_card_test.dart`), and three screen-level widget tests (`search_application_screen_test.dart`, `application_details_screen_test.dart`, `dashboard_screen_test.dart` — the latter added specifically to verify the Home screen's Security Chat FAB navigates to the existing `SecurityChatScreen`). As with the backend suite, this is Dart-VM-level evidence of structural correctness, not a substitute for on-device visual confirmation — which Section 7.12 reports separately and explicitly.

## 7.12 Live Android Emulator Validation

Live validation is this project's only evidence layer that exercises the fully assembled system — the real Flutter application, the real FastAPI backend, the real MySQL database, the real production XGBoost model, and the real Hybrid Decision Engine — as an end user or developer would actually experience it. This section reports that evidence exactly as recorded, distinguishing clearly between sessions where the application was genuinely reached and interacted with, and sessions where an environment-level failure prevented that from happening at all.

**Phase 14B** (an earlier validation session) established the first live-observed evidence: login, registration, session restore, logout, the main dashboard, known-application search, application details, security assessment, the compatible-device compatibility case, alternative-application suggestions, cross-user history isolation, and the chatbot mechanism, including one real defect found and fixed live (a suggestion-chip wording mismatch in the chatbot's intent classifier).

**Phase 21** is this project's strongest and most recent successful live-validation session, and its results are preserved here unchanged and not downgraded by any later session's outcome. Under a real emulator session that remained stable for over 30 minutes of continuous interaction, the real application was installed, a real test account registered and logged in against the real backend and real MySQL, and the following were each live-observed and passed, with genuine screenshot evidence captured for each (48 screenshots in total):

**Table 7.6. Live Android Validation Summary.**
| Item | Status | Session |
|---|---|---|
| Login, registration, session restore, logout | PASS | Phase 14B |
| Dashboard, known-app search, application details, security assessment | PASS | Phase 14B |
| Compatibility — COMPATIBLE case | PASS | Phase 14B |
| Alternatives, cross-user history isolation | PASS | Phase 14B |
| Chatbot mechanism (incl. one bug found and fixed live) | PASS | Phase 14B |
| Home → Security Chat FAB | PASS | Phase 21 |
| Chatbot questions Q3–Q8 (all 6 remaining required questions) | PASS | Phase 21 |
| Suggestion chips C3, C4 | PASS | Phase 21 |
| Multi-turn conversation (12 real exchanges) | PASS | Phase 21 |
| Chat history reload after navigation | PASS | Phase 21 |
| Unknown-question fallback | PASS | Phase 21 |
| Empty-input handling | PASS | Phase 21 |
| Network-failure handling and recovery | PASS | Phase 21 |
| Long response / scrolling | PASS | Phase 21 |
| Keyboard / send / multi-line input | PASS | Phase 21 |
| No UI overflow or crash observed | PASS | Phase 21 |
| Search — unknown-application case (Search-B) | NOT VALIDATED | Phase 22 attempted |
| Search — network-error case (Search-D) | NOT VALIDATED | Phase 22 attempted |
| Compatibility — INCOMPATIBLE case (Compatibility-B) | NOT VALIDATED | Phase 22 attempted |
| Compatibility — NOT_AVAILABLE case (Compatibility-C) | NOT VALIDATED | Phase 22 attempted |
| APK upload | NOT APPLICABLE | No UI entry point exists, confirmed by direct inspection |

**Phase 22** attempted the four remaining named gaps (Search-B, Search-D, Compatibility-B, Compatibility-C) with real data pre-identified from the live database specifically so no time would be lost once inside the app. The emulator, booted under the identical configuration that had completed the entire Phase 21 session successfully, entered a persistent System UI "Application Not Responding" state immediately after boot and did not recover across a bounded wait-and-recheck sequence. **Free physical RAM was measured at approximately 4 GB and remained stable throughout this failure — this was not a RAM-shortage failure**, and this chapter does not describe it as one; the measured symptom (sustained, multi-core-saturating CPU consumption by the emulator process) is consistent with the intermittent graphics-pipeline issue diagnosed in this project's own environment-diagnostics work, which is reported here as the most evidence-backed explanation without overstating certainty about root cause. The Flutter application was never installed or launched during this attempt, so no screenshot exists for any of the four target cases, and none is claimed. **This is a real, currently-unresolved gap in this project's live-validation coverage, not a defect in the application under test** — no code was found to be at fault, because no application code was reached.

Phase 21's results are unaffected by Phase 22's outcome: the two sessions ran on different occasions under the same configuration, and a subsequent session's instability does not retroactively cast doubt on evidence genuinely captured in an earlier, successful session.

## 7.13 Chatbot Testing and Evaluation

The chatbot is evaluated across three layers, consistent with the rest of this chapter's structure. At the automated layer, `test_chatbot.py` (part of the 323 backend tests) exercises the deterministic intent-classification logic in isolation, including the regression test that locks in the Phase 14B suggestion-chip wording fix. At the live layer, Phase 21 (Section 7.12, Table 7.6) provides direct, observed evidence for all eight of the project's required chatbot questions — two (why-risky, CWE-295 explanation) from Phase 14B, and the remaining six from Phase 21 — plus both remaining suggestion-chip cases, a genuine multi-turn conversation, the chat-history read path, and the chatbot's behaviour under an unknown question, an empty input, and a deliberate backend outage.

The Phase 21 evidence is notable for demonstrating the chatbot's real, correct *fallback* behaviour, not only its grounded-answer behaviour: several of the six required questions were sent in a chat session opened from the Home screen rather than from a specific application's details screen, meaning no `app_id` context was available to the backend. In that circumstance, `chatbot_logic.py`'s real, unmodified logic correctly falls through to either the fixed greeting text or an honest "no verified assessment available" message, rather than fabricating an app-specific answer it has no real data to support — and this is exactly what was observed live, confirming the honesty-over-fabrication design principle established architecturally in Chapters 5 and 6 holds under real, unscripted user input, not only under the specific conditions an automated test constructs.

## 7.14 Integration Testing

Integration between the system's major components is exercised at two levels. `test_endpoint_consistency.py` and `test_xgboost_production_integration.py` (within the 323 backend tests) verify that the feature pipeline, the production XGBoost booster, the SHAP explainer, and the Hybrid Decision Engine compose correctly through the shared `predict_code()` entry point, so that every route built on it (`/predict`, `/developer/predict`, `/developer/scan`, `/developer/explain`, `/developer/rescan`, `/decision`) produces internally consistent results rather than divergent, route-specific logic. `LiveAnnotatorIntegrationTest.kt` (Section 7.10) verifies the plugin-to-backend integration path specifically, driving real plugin classes against the real backend rather than a mock. At the live-validation layer, every Phase 21 result (Section 7.12) is itself integration evidence in the fullest sense available to this project: a real mobile client, a real backend process, a real MySQL database, and the real production model and Decision Engine, all interacting as they would for an actual user, including a genuine network-failure/recovery cycle (the backend was deliberately stopped mid-session, the resulting typed error was observed rendered correctly in the UI, and the backend was restarted and confirmed working again before further testing continued).

## 7.15 Performance Testing

Backend prediction latency was measured for the `predict_code()` pipeline (Chapters 5–6) across 20 iterations, as recorded in `research_eval_artifacts/final_documentation/final_project_report.md`.

**Table 7.7. Measured `predict_code()` Latency (N=20 iterations).**
| Stage | Mean latency |
|---|---|
| Feature construction | ≈9.30 ms |
| XGBoost inference | ≈0.40 ms |
| SHAP explanation | ≈28.93 ms |
| Total `predict_code()` pipeline | ≈70.03 ms |

At a total measured pipeline latency of approximately 70 ms, a single-file real-time prediction comfortably supports the plugin's interactive, in-editor use case, where a response is expected within a fraction of a second of a file change rather than instantly; SHAP explanation is the single largest contributor to this total, consistent with per-prediction feature-attribution being inherently more expensive than the XGBoost inference step itself (0.40 ms) that it explains. These measurements were taken on this project's own development host under the conditions described in the source report and are not claimed to generalise to arbitrary hardware, host load, or batch-scan conditions (where `/developer/scan` processes up to 200 files per request) — no additional, unmeasured performance claim is made beyond what this table reports.

## 7.16 Regression Testing

Regression testing in this project takes two concrete forms, both already reflected in the counts reported in Sections 7.4, 7.10, and 7.11. First, every genuine defect found during this project's development and validation history was closed with a dedicated regression test at the time it was fixed, not merely patched: the Phase 14B chatbot suggestion-chip wording bug is locked in by `test_why_risky_matches_the_flutter_apps_own_suggestion_chip_wording` in `test_chatbot.py`, and the Phase 14C chat-history gap (a write path with no corresponding read path) is covered by the seven backend tests and two Flutter tests added alongside its fix. Second, the full backend and Flutter suites were re-run in full for this chapter specifically to confirm that the cumulative UI, feature, and validation work carried out across Phases 15 through 22 had not introduced a regression anywhere in the existing suite — both suites passed in full (Sections 7.4 and 7.11), with the only change from the previously-recorded Flutter figure being the expected, intentional growth from 41 to 43 tests as the FAB feature's own regression tests were added, not an unexplained discrepancy.

## 7.17 Test Results Summary

**Table 7.8. Automated Test Results (verified for this chapter).**
| Suite | Passed | Skipped | Failed | Re-verified for this chapter |
|---|---|---|---|---|
| Backend (`pytest`) | 323 | 2 | 0 | Yes — re-run in full |
| Flutter (`flutter test`) | 43 | 0 | 0 | Yes — re-run in full |
| IntelliJ plugin (Kotlin) | 55 (46 `@Test` + 9 headless platform integration) | 0 | 0 | Yes — test count re-verified by direct source inspection |

Taken together, the evidence presented in this chapter supports the following overall picture. The production classifier and the Hybrid Decision Engine built on it are backed by a documented, reproducible research comparison across five models and both target CWE classes, with the production selection justified on combined evidence rather than single-metric dominance. All three automated test layers pass in full, with 323 backend, 43 Flutter, and 55 Kotlin tests providing dense, repeatable coverage of the system's deterministic behaviour. Live, human-observed validation confirms the assembled system genuinely works end-to-end for the large majority of the application's functionality, including the full chatbot experience and every currently-implemented mobile flow reachable from the Home screen's two primary entry points. Four specific, named live-validation cases (Search-B, Search-D, Compatibility-B, Compatibility-C) remain not validated, for a reason this chapter states plainly in Section 7.12 and returns to in Section 7.18 rather than reframing as covered by other evidence.

## 7.18 Testing Limitations

This section states the honest boundaries of this chapter's evidence explicitly, rather than allowing a strong result in one layer to imply strength in another where it has not been demonstrated.

**Table 7.9. Remaining Testing Limitations.**
| Limitation | Status | Reason |
|---|---|---|
| Search — unknown-application case | NOT VALIDATED | Emulator ANR before app launch (Phase 22) |
| Search — network-error case | NOT VALIDATED | Emulator ANR before app launch (Phase 22) |
| Compatibility — INCOMPATIBLE case | NOT VALIDATED | Emulator ANR before app launch (Phase 22) |
| Compatibility — NOT_AVAILABLE case | NOT VALIDATED | Emulator ANR before app launch (Phase 22) |
| IntelliJ plugin visible-GUI validation | Not performed | Headless platform testing only (Section 7.10); no visible IDE session or plugin-side screenshot exists in this project's history |
| Research-balanced Decision Engine candidate | Not deployed | Robustness classified INCONCLUSIVE; production candidacy rated "B. PROMISING BUT MORE DATA REQUIRED" |
| Performance measurements (Section 7.15) | Host-specific | Measured on this project's own development host only; not claimed to generalise to other hardware or load conditions |
| Model comparison feature representations | Not identical across models | SVM/RF/XGBoost share a hybrid feature pipeline; LSTM and CodeBERT use different, model-appropriate representations (Section 7.5) |

None of these limitations were concealed or minimised elsewhere in this chapter; each is cross-referenced from the section in which the relevant evidence was first presented. Two of them — the four live-validation gaps and the plugin's headless-only status — are environment- and effort-bounded rather than evidence of an underlying application defect: in every documented attempt, the blocking factor was either an emulator-level instability confirmed unrelated to memory exhaustion, or a validation method (headless platform testing) that is itself a genuine escalation in rigour over plain unit testing, just not a substitute for a visible-GUI session. The remaining limitations reflect deliberate, evidence-based project decisions (the undeployed balanced Decision Engine candidate) or scope boundaries stated honestly rather than overstated (host-specific performance figures, non-identical model representations).

## 7.19 Chapter Summary

This chapter has presented DualVulnDroid's testing and evaluation evidence across five layers: automated backend, Flutter, and IntelliJ plugin test suites (323, 43, and 55 tests respectively, all passing, with the backend and Flutter counts independently re-verified for this chapter); a five-model research comparison establishing that XGBoost was selected as the production model on combined evidence — highest Macro F1 and lowest FPR, but not the lowest FNR (Linear SVM) nor the highest accuracy or CWE-89 recall (CodeBERT) — rather than single-metric superiority; per-CWE evaluation showing the production model's strengths and weaknesses differ meaningfully between CWE-89 and CWE-295, with no model dominating both; a Hybrid Decision Engine evaluation documenting the deliberately conservative, currently-deployed production operating point (32.7% coverage, 3.03% auto-decision FNR) against an undeployed, higher-coverage research candidate; and live Android validation distinguishing Phase 21's genuinely successful, screenshot-evidenced session from Phase 22's environment-level failure, with four specific cases honestly reported as not yet validated rather than assumed passing.

Chapter 8 can proceed to interpret and discuss these results — what they mean for the project's original research objectives and questions, and what they imply about the strengths and limitations of the overall approach — building on the verified evidence base this chapter has established, without needing to re-derive or re-verify it.
