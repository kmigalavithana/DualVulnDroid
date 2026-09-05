## APPENDIX A – DETAILED FUNCTIONAL REQUIREMENTS

The full functional-requirements list is presented in Chapter 4, Table 4.1, and is not reproduced a second time here; this appendix instead consolidates the requirement identifiers and their final verification status in one compact index for reference.

**Table A.1. Functional requirement index and final status.**

| ID | Short Description | Final Status |
|---|---|---|
| FR-01 | Real-time + batch source-code analysis | Automated PASS; live IDE-GUI NOT VALIDATED |
| FR-02 | Four-label classification with confidence/severity | Validated (Chapter 6 test-set evaluation) |
| FR-03 | Hybrid Decision Engine 3-state decision | Validated (Chapter 6 coverage/reliability analysis) |
| FR-04 | SHAP + separated static/data-flow evidence | Automated PASS |
| FR-05 | In-editor annotation + Alt+Enter detail view | Automated PASS; live IDE-GUI NOT VALIDATED |
| FR-06 | Narrow-pattern Quick Fix | Automated PASS; live IDE-GUI NOT VALIDATED |
| FR-07 | Post-fix re-scan verification | Automated PASS; live IDE-GUI NOT VALIDATED |
| FR-08 | Scan Project (batch) | Automated PASS; live IDE-GUI NOT VALIDATED |
| FR-09 | Registration/login with persisted session | Live PASS |
| FR-10 | Search + security assessment | PARTIAL — known/unknown-app PASS; network-error NOT VALIDATED |
| FR-11 | Compatibility (3 dimensions, honest NOT_AVAILABLE) | Live PASS (all three outcomes observed) |
| FR-12 | Safer alternative suggestions | Live PASS |
| FR-13 | APK manifest extraction on upload | Automated PASS (backend); Not Applicable (mobile UI) |
| FR-14 | CWE explanation + app-specific chatbot answers | Live PASS |
| FR-15 | Verbatim chat-reply rendering | Live PASS |
| FR-16 | Own chat history retrieval | Live PASS |
| FR-17 | Own scan-history retrieval | Live PASS |
| FR-18 | Research-only models excluded from production | Validated (code/import review) |

## APPENDIX B – NON-FUNCTIONAL REQUIREMENTS AND USE CASES

**Table B.1. Non-functional requirement index.** Full rationale, design response, and verification method for each are presented in Chapter 4, Table 4.2.

| ID | Short Description |
|---|---|
| NFR-01 | Sub-100ms real-time analysis latency (measured, not a guaranteed SLA) |
| NFR-02 | No crash on malformed/oversized input; no silent plugin failure |
| NFR-03 | No plaintext passwords; signed, expiring JWT sessions |
| NFR-04 | Honest empty/loading/error states on every Flutter screen |
| NFR-05 | SHAP + separated static/data-flow evidence on every VULNERABLE/SUSPICIOUS_REVIEW finding |
| NFR-06 | Fixed seed; frozen, leakage-checked split; versioned production artefacts |
| NFR-07 | One shared feature-construction module for training and inference |
| NFR-08 | Bounded batch size per project-scan request |
| NFR-09 | No fabricated RAM/CPU compatibility verdict |

**Table B.2. Use case index.** Full actor/precondition/flow/postcondition detail is presented in Chapter 4, Section 4.6.

| ID | Name | Actor |
|---|---|---|
| UC-01 | Real-time code inspection | Developer |
| UC-02 | View finding detail (Alt+Enter) | Developer |
| UC-03 | Scan Project | Developer, Security Analyst/Researcher |
| UC-04 | Apply Quick Fix | Developer |
| UC-05 | Register and log in | Application user |
| UC-06 | Search and review application security | Application user |
| UC-07 | Check device compatibility | Application user |
| UC-08 | View safer alternatives | Application user |
| UC-09 | Ask the Security Chat | Application user |
| UC-10 | Retrieve own chat history | Application user |
| UC-11 | Upload and assess an APK | Backend/API client only (no Flutter UI reaches this) |

## APPENDIX C – LIVE VALIDATION EVIDENCE SUMMARY

This appendix consolidates the phase-by-phase live-validation record and the final validation tally reported in full in Chapter 7 (Sections 7.10, 7.16, 7.17), for reference in one place.

**Table C.1. Live validation phase history.**

| Phase | Outcome | Screenshots |
|---|---|---|
| 14B | PASS (core flows) | 70 |
| 17 | Blocked (System UI ANR before install) | 0 |
| 21 | PASS (full chatbot experience, first fully stable session) | 56 |
| 22 | Blocked (System UI ANR before install) | 0 |
| 27 | Blocked (delayed-onset ANR) | 0 |
| 30 | Blocked (ANR at +20s) | 0 |
| 31 | Root-cause diagnostics only — not a validation session | 0 |
| 32 | PASS (substantial results), then session-ending `system_server` hang | 22 |
| 33 | PASS (most comprehensive session; recovered from Phase 32) | 44 |

Total screenshots across all phases: 192.

**Table C.2. Final validation summary (`final_mobile_validation.csv`, 26 tracked rows).**

| Category | Count |
|---|---|
| Current Live PASS or PASS | 23 |
| FAIL | 0 |
| PARTIAL | 0 |
| NOT VALIDATED (live) | 2 |
| Not Applicable | 1 |

**Table C.3. Remaining NOT VALIDATED items.**

| Item | Reason |
|---|---|
| UI-01 Splash screen | Blocked before install in Phase 27/30; passed through too quickly to capture in Phase 32; automated-test coverage only |
| Search — network-error state | Attempted once (Phase 22), blocked by an unrelated emulator ANR; not re-attempted in Phase 33 due to time/scope; automated-test coverage only |
| Plugin real-time annotation/Quick Fix/Scan Project — human-observed on-screen IDE GUI | No session in this research's documented history includes a person directly observing the plugin's UI inside a visible IDE window; headless integration-test coverage only |

## APPENDIX D – MODEL CONFIGURATION AND HYPERPARAMETERS

**Table D.1. Classical model configurations.** (Reproduced from Chapter 3, Table 3.4.)

| Model | Implementation | Hyperparameter Search | Selection Criterion |
|---|---|---|---|
| Linear SVM | `LinearSVC` + `CalibratedClassifierCV` (3-fold, train-only) | Grid search, C ∈ {0.01, 0.1, 1.0, 10.0} | 5-fold stratified CV macro-F1 (train split only) |
| Random Forest | `RandomForestClassifier`, balanced weights | Grid search over estimators, depth, leaf size | 5-fold stratified CV macro-F1 (train split only) |
| XGBoost | `multi:softprob`, native early stopping | max_depth ∈ {4, 6, 8}, eta ∈ {0.05, 0.1}; up to 300 rounds | Validation-set macro-F1, early stopping |

**Table D.2. Production XGBoost final configuration.** (Verified against `research_eval_artifacts/xgboost/metadata.json`.)

| Parameter | Value |
|---|---|
| max_depth | 4 |
| eta | 0.1 |
| Boosting rounds selected (of rounds trained) | 103 (of 123) |
| Feature dimensionality | 7,610 (7,587 text + 23 security) |
| Validation macro-F1 at selection | 0.8684 |

## APPENDIX G – TRACEABILITY MATRICES

The full requirements-to-design traceability matrix (mapping each of Chapter 1's five research objectives to its requirement(s), design component, implementation location, and verification method) is presented in Chapter 4, Table 4.6, and the corresponding methodology-level traceability table (objective → method → data/evidence → evaluation → expected output) is presented in Chapter 3, Table 3.8. Both are the authoritative versions and are not duplicated here to avoid two diverging copies of the same evidence; this appendix records only that both exist and where to find them.

*Note on omitted appendices:* An "Appendix E — Additional Evaluation Tables" and an "Appendix F — Additional Screenshots" were considered but are not included. Chapter 6 already presents every evaluation table this research's stored artefacts support (dataset composition, feature representation, per-model results, the CodeBERT provenance table, the five-model comparison, the CWE-89 confusion breakdown, the Decision Engine evaluation, and the five-seed robustness table), and duplicating them here would not add evidence, only length. Likewise, Chapter 7 already presents five screenshots selected specifically because each demonstrates a distinct, cited claim; the remaining 187 screenshots in the project's phase directories were reviewed during this thesis's preparation but are not individually reproduced, since doing so without a specific claim for each would not meet this thesis's evidence-first standard.
