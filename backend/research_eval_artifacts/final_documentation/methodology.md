# Research Methodology

DualVulnDroid — Hybrid Machine Learning-Based Real-Time Detection of SQL Injection (CWE-89) and Improper Certificate Validation (CWE-295) in Android Applications.

All values below are read directly from stored research artifacts under `backend/research_eval_artifacts/`, not recomputed for this document.

## A. Dataset

The labelled dataset (`dataset .csv`) contains **1,687 raw rows**, each a code snippet labelled with one of four classes describing SQL Injection (CWE-89) or Improper Certificate Validation (CWE-295) status:

- `s0` — SQL Injection, vulnerable
- `v0` — Certificate Validation, vulnerable
- `s1` — SQL Injection, safe (the safe counterpart of the same task)
- `v1` — Certificate Validation, safe

Raw label distribution: s0=450, v0=448, s1=439, v1=350.

## B. Label Distribution

See A above for the raw distribution and Section 5 (`clean_label_distribution`) for the post-cleaning distribution used for training. The dataset is reasonably balanced across the four classes at the raw level.

## C. Label-Noise Detection

Rows were checked for label noise using `ml.feature_pipeline.normalize_code()` template matching: any two rows whose normalized code text is exact-duplicate or near-duplicate-template or matches were compared against their labels. Where the same normalized template appeared with **more than one distinct label** elsewhere in the raw dataset, this is treated as label noise (a genuine annotation conflict), not benign duplication.

## D. Conflicting-Label Exclusion

**559 rows across 270 conflicting-label groups** were excluded entirely from train/validation/test. These rows are not silently dropped — they are preserved separately in `excluded_conflicting_labels.csv` for traceability. This leaves **1,128 clean rows** for the frozen split.

## E. Normalized-Code Grouping

Every row is assigned a group key via `ml.feature_pipeline.normalize_code()` — the same normalization function used for TF-IDF/count text features. Rows sharing a group key (i.e. representing the same underlying code template) are always kept together on the same side of the train/validation/test split.

## F. Grouped Train/Validation/Test Split

Split produced by `ml.dataset_prep.grouped_stratified_split()` with `random_seed=42`:

| Split | Rows | Fraction |
|---|---|---|
| Train | 791 | 70.12% |
| Validation | 169 | 14.98% |
| Test | 168 | 14.89% |

The test split is **frozen** — reused identically across every model evaluated (SVM, Random Forest, XGBoost, LSTM, CodeBERT) for a fair, apples-to-apples comparison.

## G. Leakage Prevention

`ml.dataset_prep.assert_no_group_leakage()` verifies zero overlap between splits on both the normalized-template group key and exact row text:

- Cross-split normalized-template overlap: train/val=0, train/test=0, val/test=0
- Cross-split exact-text overlap: train/val=0, train/test=0, val/test=0
- Near-duplicate template groups within the clean dataset: 23 groups / 48 rows (correctly kept together on one side of the split by the grouping above, not leaked across)

**Why grouping was used:** to prevent near-identical code templates from crossing splits — without grouping, a model could see a near-duplicate of a test-set template during training and appear to generalize when it is actually pattern-matching a memorized template.

**Stated limitation:** the dataset carries no application/project identifier, so this is a near-duplicate-grouped split, not a true application-level split. A model's real generalization to genuinely unseen applications is not directly measured by this split; it measures generalization to unseen code templates within the same dataset.

## H. Feature Engineering

See "Feature Engineering" section below for the full production pipeline description (TF-IDF word/char, count features, 23 security features, 7,610 total dimensions, train-only fitting).

## I. Security/Data-Flow Features

23 deterministic, rule-based features computed directly from the code text (not learned), covering: SQL source/sink detection, source-to-sink tracing, string concatenation vs. parameterized queries, raw-query/exec-SQL/compile-statement patterns, certificate HostnameVerifier/TrustManager/exception-validation/default-verifier patterns, WebView SSL error handling, and data-flow depth/interprocedural-flow/unsafe-safe-suspicious flow counts. Full list: `sql_source_detected, sql_sink_detected, sql_source_to_sink, sql_string_concatenation, sql_parameterized_query, sql_user_input, sql_raw_query, sql_exec_sql, sql_compile_statement, certificate_hostname_verifier, certificate_return_true, certificate_trust_manager, certificate_empty_trust_check, certificate_exception_validation, certificate_default_verifier, webview_ssl_error, webview_handler_proceed, webview_handler_cancel, dataflow_depth, interprocedural_flow, unsafe_flow_count, safe_flow_count, suspicious_flow_count`.

## J. Model Training

Five models were trained/evaluated on the identical frozen split: Linear SVM (calibrated, `CalibratedClassifierCV(cv=3)` fit on train only), Random Forest, XGBoost (`multi:softprob`, 4-class, early-stopping on validation), LSTM (from-scratch, code-aware tokenizer, learned embeddings — a genuinely different input representation from the TF-IDF/count/security-feature pipeline used by the classical ML models), and CodeBERT (fine-tuned transformer). Hyperparameters for the classical/XGBoost models were selected by maximum validation macro-F1 across a fixed candidate grid — validation only, never test.

## K. Model Comparison

All five models were evaluated on the same 168-row frozen test set. See the Model Comparison chapter/table for the full results. No single model dominates every metric — see Section 8 (Security-Specific Findings) and the CWE-89/CWE-295 tables.

## L. Decision Engine

The production **Hybrid Decision Engine** (`decision_engine.py`, unmodified in this phase) combines the XGBoost model's prediction with rule-based evidence (source-to-sink tracing, parameterization detection, keyword corroboration) into a weighted evidence score, then applies two calibrated thresholds (`vulnerable_threshold=1.379`, `safe_threshold=-0.926`, calibrated on the validation set) to output `VULNERABLE`, `SAFE`, or `SUSPICIOUS_REVIEW` (deferred for manual review). See the Decision Engine Research section for full production and research-candidate metrics.

## M. Explainability

Two distinct, separately-labelled forms of explanation are produced (never conflated): (1) **SHAP** model explanation via a real `shap.TreeExplainer` over the production XGBoost booster, and (2) **deterministic rule/data-flow evidence** (the same 23 security features plus source→sink tracing) — the latter is never described as "SHAP."

## N. Production Integration

The production pipeline (Phase 11) loads the validated XGBoost artifact from `research_eval_artifacts/xgboost/` directly (not a separately-retrained copy), reusing the identical feature pipeline, class order, and the exact `num_boost_round_selected=103` early-stopping cutoff via booster slicing (`booster[0:103]`), verified bit-identical to the research evaluation's own predictions on the frozen 168-row test set.

## O. End-to-End Validation

End-to-end validation (Phase 12) exercised the real FastAPI backend (`pytest`, 315 passed/2 skipped), the real Kotlin plugin test suite (46 passed, forced fresh Gradle execution), and the real Flutter test suite (39 passed) — plus 8 required live chatbot questions run against the real `/ai-chat` endpoint with real stored data. IDE-sandbox and physical/emulated-device UI validation were not performed in this environment (see Limitations).
