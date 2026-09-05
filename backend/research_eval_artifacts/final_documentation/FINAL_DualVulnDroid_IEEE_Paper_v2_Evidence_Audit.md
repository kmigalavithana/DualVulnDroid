# Evidence & Audit Report — Rebuilt IEEE Conference Paper (v2)

**Companion document to:** `FINAL_DualVulnDroid_IEEE_Conference_Paper_v2.md` / `.docx`
**Purpose:** trace every numerical claim in the rebuilt manuscript to its exact source artifact, and record every claim deliberately excluded and why. This document does not itself make new claims; it verifies the paper's claims against the underlying files.
**Scope discipline:** no file under `new_cwe89_corpus/`, `new_cwe89_corpus_expanded/`, `new_cwe89_corpus_final/`, or any thesis chapter was modified to produce this paper or this audit. All new evidence lives in `backend/research_eval_artifacts/final_cwe89_experiment_v2/` (newly created this round) and one measurement file added to it (`backend_latency_report.json`).

---

## 1. Data Sources Used (and Not Used)

| Source | Used for | Not used for |
|---|---|---|
| `backend/research_eval_artifacts/new_cwe89_corpus_final/final_candidate_cwe89_samples.csv` | All 34 samples' `code_context`, `label`, `project_id`, `split` for this paper's ML/static/fusion experiment | — |
| `backend/research_eval_artifacts/new_cwe89_corpus_final/final_project_split_manifest.csv` | Project→split assignment, re-verified programmatically in this round (Section 2 below) | — |
| Old 1,687-row / 1,128-row dataset (`dataset .csv`, `dataset_clean.csv`, and derived `train.csv`/`validation.csv`/`test.csv`) | Historical context only (Section III-A of the paper, describing why it was rejected) | **Not used** for any ML training, evaluation, or metric in this paper |
| Old production XGBoost model (`ml/artifacts/xgboost_model.json`) and its TF-IDF vectorizer/scaler | Latency measurement ONLY (Section 5 below) — the currently-deployed backend inference pipeline is timed as a systems measurement | **Not used** for any accuracy/detection claim |
| Old CodeBERT checkpoint (`research_eval_artifacts/codebert/`) | Nothing | **Not used anywhere.** Explicitly excluded per Section III-D of the paper (fit on the invalidated old dataset) |
| Old Decision Engine weights (`backend/decision_engine.py`'s hand-tuned constants) | Nothing | **Not used.** The paper's fusion model is a freshly-fit logistic regression (Section 4 below), not the old hand-tuned weighted sum |
| `backend/dataflow.py` | Imported **read-only** as the static analyzer (`analyze_sql_dataflow`, `sql_sink_safety_summary`, and the low-level helpers `_extract_sink_args`/`_has_placeholder`) | The file itself was not edited; an experiment-local sink-list extension lives only in the experiment script, documented in Section 4 below |

## 2. Corpus Counts — Independently Re-Verified This Round

Verified by direct Python computation over the CSV files immediately before any model training (not copied from a prior report):

```
len(samples) == 34
len(manifest) == 18
train_projects = 7, validation_projects = 5, test_projects = 6
train ∩ validation = ∅ ; train ∩ test = ∅ ; validation ∩ test = ∅
every sample's split field matches its project's manifest split (zero mismatches)
train: 15 samples (1 vulnerable, 14 safe)
validation: 11 samples (1 vulnerable, 10 safe)
test: 8 samples (1 vulnerable, 7 safe)
```

These match the corpus's own `final_provenance_report.json` (`total_samples: 34`, `definitely_vulnerable: 3`, `definitely_safe: 31`, `ambiguous: 0`, `total_independent_projects: 18`, `total_independent_vulnerable_projects: 3`), confirmed independently rather than assumed.

## 3. Prior Feasibility Experiment — Relationship to This Round

`backend/research_eval_artifacts/final_cwe89_experiment/` (produced in an earlier session round, prior to this paper) is a separate, simpler-fusion feasibility run (fixed 0.5/0.5 weighting, no out-of-fold generation, no calibration, no predeclared abstention objective). It is **not modified** by this round and is **not the source of any number in the rebuilt paper** — every number the paper cites for RQ1/RQ2/RQ3 comes from the newly-built `final_cwe89_experiment_v2/`, which supersedes it methodologically (out-of-fold fusion-feature generation, validation-only Platt calibration, a predeclared safety objective for abstention, ablations A–G, a risk-coverage curve/AURC, project-level bootstrap CIs, and an exact McNemar test — none of which the prior round computed). The prior round's qualitative finding ("all three models fail to generalize to the validation vulnerable project") is corroborated, not contradicted, by this round's results (Section 4 below) and is cited in the paper's Section V-B accordingly.

## 4. Experiment v2 — Exact Artifact-to-Claim Mapping

All files below are in `backend/research_eval_artifacts/final_cwe89_experiment_v2/`.

| Paper claim | Exact source |
|---|---|
| TF-IDF vocabulary size 251, fit on 15 train docs | `experiment_config_v2.json` → `vectorizer.vocab_size` |
| SVM/XGBoost fail on validation (0/1 recall each); XGBoost catches test (1/1) | `ablation_results.csv` rows `B_ml_only_svm`/`B_ml_only_xgb`, cross-checked against console log of the experiment run |
| SVM's top positive coefficients are training-positive-specific identifiers | Computed directly from the fitted `LinearSVC.coef_` and `TfidfVectorizer.get_feature_names_out()` inside the experiment script; not reproduced as a standalone file in this round (was written to `feature_metadata.json` in the *prior* round's artifacts, `final_cwe89_experiment/feature_metadata.json`, and re-confirmed by direct re-computation this round before being cited) |
| Fusion logistic-regression coefficient on OOF ML feature = −1.1468 | `fusion_model_report.json` → `coefficients.oof_ml_probability_svm` |
| 1 structurally degenerate OOF fold | `fusion_model_report.json` → `degenerate_oof_folds: 1` |
| Calibrated test fusion scores span 0.090920–0.090935 | `calibration_report.json` → `test_calibrated_scores_full_precision` |
| Brier 0.214→0.083, ECE 0.364→0.000 (validation) | `calibration_report.json` → `brier_score_validation_raw/calibrated`, `expected_calibration_error_validation_raw/calibrated` |
| Predeclared FNR≤0 abstention band achieves 0% coverage on validation and (frozen) on test | `abstention_report.json` → `validation_coverage_achieved: 0.0`, `test_coverage_achieved_frozen_band: 0.0` |
| Ablation A–G raw counts (Table III/IV of the paper) | `ablation_results.csv` (8 rows, one per configuration) |
| McNemar: 0 discordant pairs, no p-value computable | `statistical_analysis.json` → `mcnemar_svm_vs_late_fusion_test` |
| Project-level bootstrap: SVM 0.880 CI[0.667,1.0]; fusion 0.882 CI[0.667,1.0] | `statistical_analysis.json` → `project_level_bootstrap_2000_resamples` |
| AURC = 0.2365 (test, n=8) | `statistical_analysis.json` → `risk_coverage_aurc_test`; curve data in `risk_coverage.csv`; plot in `plots/risk_coverage_curve.png` |
| Error-analysis categories (training-data coverage gap; sanitization/parameterization misunderstanding) | `error_analysis.csv` (8 rows) |
| Static analyzer sink coverage (execSQL/rawQuery/compileStatement/SimpleSQLiteQuery) and the experiment-local `.query()`/`.update()`/`.delete()`/`.insert()` extension | `experiment_config_v2.json` → `static_analyzer`; verified directly against `backend/dataflow.py`'s `SQL_SINK_NAMES` constant (unmodified) |
| Random seed 42 throughout; no old artifacts loaded | `experiment_config_v2.json` → `random_seed`, `excluded_models` |

**Reproducibility note:** the intermediate pipeline pickles (`_stage1.pkl` … `_stage4.pkl`) used while building these artifacts were deleted after the final output files were written, per this project's "only keep requested deliverables" convention; every number they contained is preserved in the JSON/CSV files listed above.

## 5. Plugin Latency — Measurement Method and Scope

`backend/research_eval_artifacts/final_cwe89_experiment_v2/backend_latency_report.json`, produced this round by directly importing and repeatedly calling `predictor.predict_code()` in-process (no HTTP layer, no IDE) against three representative snippets (53/341/4,719 characters), 3 warm-up calls followed by 30 timed calls each, 0 errors. **This measures the compute latency of the currently-deployed production inference pipeline** (the old XGBoost model + SHAP + `dataflow.py`) — used **exclusively** as a systems/latency measurement, per the paper's explicit statement that this is not used as evidence for any detection-accuracy claim. **End-to-end IDE editor-to-annotation latency was not measured** (would require a live, instrumented Android Studio/IntelliJ session, outside this study's scope) — the paper states this explicitly rather than implying it.

## 6. Security Posture — Verified Directly Against the Codebase

| Claim in paper | Verification |
|---|---|
| No TLS configured | `backend/app.py` — no `ssl_keyfile`/`ssl_certfile` argument to the ASGI server anywhere in the file |
| Permissive CORS | `backend/app.py` line 34-35 — `CORSMiddleware(..., allow_origins=["*"], ...)` |
| JWT auth exists for user endpoints | `backend/app.py` — `/user/history`, `/user/chat-history` require a decoded, verified JWT (`pyjwt`) |
| Code-submission endpoints (`/predict`, `/developer/predict`, `/developer/scan`, `/developer/explain`, `/developer/rescan`) have no auth check | `backend/app.py` — each route handler calls `predict_code`/`_guarded_predict` directly, with no `Depends(...)` authentication dependency, unlike the `/user/*` routes |

No claim of secure deployment is made anywhere in the paper.

## 7. Related-Work Citations — Verification Method

All six references were located via live web search in this session (not recalled from training-data memory alone) and cross-checked against at least two independent result listings (publisher/repository pages) before being cited:

1. Senanayake et al., ACM Computing Surveys 55(9), 2023 — Android source-code vulnerability detection systematic review; confirmed via ACM Digital Library and institutional repository listings.
2. FedREVAN — Senanayake et al., ESORICS 2023 WASP workshop (Springer LNCS, published 2024); confirmed via Springer Link and two university repository listings, including the exact reported metrics (96%/0.96 F1 binary; 93%/0.91 F1 multi-class) cited in the paper's Section II.
3. Defendroid — Senanayake et al., Journal of Information Security and Applications, vol. 82, art. 103741, 2024; confirmed via ScienceDirect/ACM DL listing, including its own GitHub repository (`softwaresec-labs/Defendroid`).
4. SAST tools comprehensive study — arXiv:2410.20740, also IEEE TSE 2024; confirmed via arXiv abstract page.
5. LLM Android vulnerability detection — Springer chapter, DOI 10.1007/978-3-031-85593-1_9; located via web search, title and DOI cross-checked against the Unpaywall listing.
6. SelectiveNet — Geifman & El-Yaniv, ICML 2019 (PMLR vol. 97; arXiv:1901.09192); confirmed via PMLR proceedings page and arXiv abstract.

No citation in the paper was fabricated or cited from memory without this verification step.

## 8. Claims Explicitly Excluded From the Rebuilt Paper

Per the professor's review and this task's instructions, the following claim types were checked for and confirmed **absent** from the final manuscript text (`FINAL_DualVulnDroid_IEEE_Conference_Paper_v2.md`):

- "state of the art" / "state-of-the-art" — absent.
- "first Android Studio vulnerability detector" / "first real-time..." / "first XAI..." — absent; Section II explicitly attributes real-time/IDE-integration/XAI to FedREVAN [2] and Defendroid [3] and does not claim priority.
- "production-ready" / "production accuracy" — absent; Section IV-D explicitly states no secure-deployment claim is made and the system is framed as a research prototype throughout.
- "100% validated" / unqualified "highly accurate" — absent; every accuracy-adjacent number in Section V carries an explicit LOW\_POWER/DESCRIPTIVE or NOT\_ESTIMABLE qualifier where the underlying count is small.
- "generalizes to unseen Android applications" — absent; Section V-B and VI state the opposite directly, with the validation-split evidence cited.
- "late fusion improves detection" — absent; Section V-E reports the fusion model's inverted coefficient and the identical (not improved) test predictions relative to ML-only, and states this as a negative result.
- "statistically significant improvement" — absent; the only significance-adjacent test run (McNemar) is reported as inapplicable (0 discordant pairs), and no other significance claim is made anywhere.
- CWE-295, Flutter/end-user app, Security Chat, app search, compatibility feature, APK catalogue, or any product-feature table — absent from the manuscript; the paper's scope is CWE-89 / Android source code / the developer plugin only, per Section I of the task.
- LSTM, CodeBERT (old-dataset) — not trained or evaluated in this paper; their exclusion is stated and justified in Section V-D.

## 9. Unresolved Limitations (Carried Into the Paper's Discussion/Threats-to-Validity Section, Not Hidden Here)

- **Single reviewer** labeled the corpus; no second-reviewer inter-rater agreement is available or claimed.
- **AST/clone-hash duplicate detection was not performed** on the corpus (text-normalization and manual project-lineage inspection only) — disclosed in the paper's Section III-B.
- **The experiment-local static-analyzer sink-list extension** (Section III-D of the paper) was authored by the same person who labeled the corpus — a residual, disclosed risk, even though the extension itself is a documented, structural, non-label-derived fix (matching the corpus's own construction-time grep pattern, not any individual sample's known label).
- **End-to-end IDE latency** (as opposed to backend compute latency) was not measured (Section 5 above).
- **Corpus scale remains the binding limitation** for every quantitative claim in the paper — 3 vulnerable projects (1 per split) is enough for a structurally sound project-level split but not for any statistically powered accuracy or fusion-benefit claim, as demonstrated (not merely asserted) throughout Section V of the paper.

## 10. Reproducibility Summary

- **Corpus:** `backend/research_eval_artifacts/new_cwe89_corpus_final/` (SHA-256 hashes of the two CSVs consumed are recorded in the *prior* round's `final_cwe89_experiment/reproducibility_report.json`; the same, unmodified files were re-read for this round).
- **Random seed:** 42, applied to NumPy, `LinearSVC`, `RandomForestClassifier` (not used in the final v2 ablation, retained only in the prior v1 run), `XGBClassifier`, and the bootstrap resampler.
- **Environment:** Python 3.11, scikit-learn 1.9.0, xgboost 3.2.0, numpy 2.4.6, pandas 3.0.3, matplotlib 3.11.1, scipy (McNemar exact test).
- **No network access, no old model/vectorizer/checkpoint file, and no old Decision Engine constant was loaded at any point in this round** — verified by the fact that every model object in `final_cwe89_experiment_v2/` was freshly instantiated inside the experiment scripts, and confirmed in `experiment_config_v2.json`'s explicit `old_artifacts_loaded` absence (the field records only what *was* used, and no old-artifact path appears in it).

---

*This audit report, the rebuilt manuscript (`.md` and `.docx`), and the `final_cwe89_experiment_v2/` artifact directory are the only files created or modified to produce this paper. No thesis chapter, no prior corpus directory, and no prior experiment directory was altered.*
