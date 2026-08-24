# DualVulnDroid — Final Project Report

Hybrid Machine Learning-Based Real-Time Detection of SQL Injection (CWE-89) and Improper Certificate Validation (CWE-295) in Android Applications.

*All numeric values in this report were read directly from stored artifacts under `backend/research_eval_artifacts/` and cross-checked against the independently-supplied verification values for Phase 13; every value matched exactly except one resolved provenance ambiguity noted in Section 6 (CodeBERT). No number was invented or silently changed.*

## 1. Executive Summary

DualVulnDroid detects CWE-89 (SQL Injection) and CWE-295 (Improper Certificate Validation) in Android code through a hybrid pipeline: a 7,610-dimensional feature representation (TF-IDF word/char + count features + 23 deterministic security/data-flow features) feeds a production **XGBoost** classifier, whose output is combined with rule-based evidence and SHAP explanations inside a **Hybrid Decision Engine** that either auto-decides or defers to manual review. The system spans an IntelliJ developer plugin, a FastAPI + MySQL backend, and a Flutter end-user application with a grounded security chatbot. Four additional models (SVM, Random Forest, LSTM, CodeBERT) were evaluated as research comparisons on an identical frozen test set; none is deployed to production. This report documents the verified final state of the research and the software system, with an explicit, honest accounting of what was and was not validated in the current session.

## 2. Final Production Status

- **Production ML model:** XGBoost. *Not* claimed as universally best — see Section 8.
- **Production feature pipeline:** 7,610-dimensional full hybrid pipeline (7,587 text + 23 security features).
- **Selected XGBoost rounds:** 103 of 123 boosted rounds (raw booster sliced to `[0:103]` at load time — the early-stopping-selected cutoff, verified bit-identical to `iteration_range`-based prediction).
- **Class order:** s0, v0, s1, v1.
- **Production Decision Engine:** existing calibrated thresholds unchanged (`vulnerable_threshold=1.379`, `safe_threshold=-0.926`).
- **Balanced research candidate:** NOT DEPLOYED.
- **Research-only models:** SVM, Random Forest, LSTM, CodeBERT.

## 3. Research Contribution

1. A grouped, leakage-checked, label-noise-cleaned dataset split (1,687 raw → 1,128 clean → 791/169/168), reused identically across five models for fair comparison.
2. A five-model empirical comparison (classical ML, gradient boosting, and two DL approaches) on identical CWE-89/CWE-295 data, with per-CWE breakdowns.
3. A Hybrid Decision Engine combining ML prediction with deterministic rule/data-flow evidence, evaluated under both its current production thresholds and a research-only "Balanced" alternative, with an explicit robustness study (bootstrap + 5 alternative random splits + threshold-sensitivity analysis).
4. A working, tested, end-to-end system (plugin + backend + Flutter app) integrating the validated research model into production without re-implementing or retraining it.

## 4. Main Model Comparison

Frozen 168-row test set, identical across all five models.

| Model | Type | Accuracy | Macro F1 | ROC-AUC | Binary F1 | FPR | FNR |
|---|---|---|---|---|---|---|---|
| SVM | ML | 0.8036 | 0.7789 | 0.9025 | 0.8261 | 0.2000 | 0.1828 |
| Random Forest | ML | 0.7738 | 0.7519 | 0.8758 | 0.7889 | 0.2133 | 0.2366 |
| XGBoost | ML | 0.7917 | 0.7874 | 0.8957 | 0.7977 | 0.1467 | 0.2581 |
| LSTM | DL | 0.7798 | 0.7448 | 0.8845 | 0.7861 | 0.1600 | 0.2688 |
| CodeBERT | Transformer/DL | 0.7976 | 0.7780 | 0.8764 | 0.8090 | 0.1733 | 0.2258 |

*(See Section 6 for a provenance note on the CodeBERT source artifact.)*

**These are research comparison results, not a claim of universal superiority.**

### Security-specific findings

- **SVM:** lowest overall FNR = 18.28%.
- **XGBoost:** best macro-F1 = 78.74%; lowest FPR = 14.67%.
- **CodeBERT:** competitive overall performance; best CWE-89 recall = 86.21%.
- **LSTM:** lowest macro-F1 among the evaluated models; visible overfitting.
- **Random Forest:** generally weakest overall classical baseline.

**No single model dominates every security-relevant metric.**

## 5. CWE-89 / CWE-295 Findings

### CWE-89 (SQL Injection)

| Model | Precision | Recall | F1 | FNR |
|---|---|---|---|---|
| SVM | 0.7273 | 0.8276 | 0.7742 | 0.1724 |
| Random Forest | 0.7188 | 0.7931 | 0.7541 | 0.2069 |
| XGBoost | 0.7931 | 0.7931 | 0.7931 | 0.2069 |
| LSTM | 0.7083 | 0.5862 | 0.6415 | 0.4138 |
| CodeBERT | 0.7143 | 0.8621 | 0.7813 | 0.1379 |

CodeBERT has the strongest CWE-89 recall and lowest CWE-89 FNR, while XGBoost has the strongest CWE-89 F1.

### CWE-295 (Improper Certificate Validation)

| Model | Precision | Recall | F1 | FNR |
|---|---|---|---|---|
| SVM | 0.8966 | 0.8125 | 0.8525 | 0.1875 |
| Random Forest | 0.9057 | 0.7500 | 0.8205 | 0.2500 |
| XGBoost | 0.9020 | 0.7188 | 0.8000 | 0.2812 |
| LSTM | 0.9107 | 0.7969 | 0.8500 | 0.2031 |
| CodeBERT | 0.9400 | 0.7344 | 0.8246 | 0.2656 |

SVM has the strongest CWE-295 recall and lowest FNR.

## 6. Decision Engine Conclusion

**Current production** (thresholds `1.379` / `-0.926`, evaluated on the 168-row frozen test set):

- Coverage: **32.7%** (55 of 168 cases auto-decided; 67.3% deferred to manual review)
- Auto-decision FNR: **3.03%**
- Auto-decision FPR: **9.09%**
- Auto-decision precision: **≈0.941**

*These metrics apply only to automatically-decided cases* — the 67.3% of cases the engine defers are not counted as correct or incorrect here; they are explicitly excluded from this view (source: `security_selection/decision_engine_metrics.json`, `auto_decision_view`).

**Balanced research candidate** (thresholds `0.753` / `-0.376`, NOT DEPLOYED):

- Coverage: **88.7%**
- FNR: **20.24%**
- FPR: **13.85%**
- Review workload: **11.31%**
- Robustness: **INCONCLUSIVE** (H1 cross-split FNR advantage SUPPORTED; H2 threshold stability INCONCLUSIVE; H3 CWE asymmetry NOT SUPPORTED)
- Research recommendation: **PROMISING BUT MORE DATA REQUIRED**

The Balanced thresholds remain **NOT DEPLOYED**. See `decision_engine_summary.csv` for the machine-readable version of both rows.

**CodeBERT artifact provenance note:** three directories exist under `research_eval_artifacts/` containing CodeBERT results (`codebert/`, `codebert final result/`, `codebert_final_artifacts/`). `codebert/test_metrics.json` matches the independently-supplied verification numbers for this phase exactly (accuracy 0.7976, macro-F1 0.7780, ROC-AUC 0.8764, CWE-89/295 precision-recall-F1-FNR all exact matches) and is the source used throughout this report. The other two directories report a different run (accuracy 0.8333, macro-F1 0.7871) and were **not** used — they are retained on disk as earlier/superseded experimental output, not deleted, but explicitly excluded from every number reported here.

## 7. System Architecture Summary

See `architecture_description.md` for full diagrams. In brief: developer code flows through the plugin/API into the shared feature pipeline, XGBoost, data-flow evidence, SHAP, and the Hybrid Decision Engine, producing a decision + evidence + explanation surfaced in the plugin UI or API response. Separately, an uploaded APK flows through manifest extraction, application/version/scan persistence (MySQL), security assessment, compatibility checking, and alternative-app ranking, surfaced in the Flutter UI. The chatbot (`/ai-chat`) resolves a real `app_id` to real stored data for app-context questions, and answers CWE-89/CWE-295 explanation questions from static reference text — never a fabricated finding.

## 8. Test Status

| Suite | Result |
|---|---|
| Backend pytest | 315 passed, 2 skipped (MySQL-only tests, no MySQL server reachable — honest skip) |
| Kotlin plugin (Gradle) | 46 passed, 0 failed (forced fresh execution, verified via JUnit XML) |
| Flutter test | 39 passed, 0 failed |
| Flutter analyze | 0 errors (6 pre-existing style infos) |
| IntelliJ live sandbox UI | NOT VALIDATED (no IDE sandbox run — disk/resource constraint) |
| Flutter live device/emulator | NOT VALIDATED (no Android emulator/device connected) |

Performance (real measurements, not a guaranteed production SLA — environments/measurement conditions differ between the two sessions below, so these are observed measurements, not a formal benchmark comparison):

| Path | Phase 11 | Phase 12 (warm process) |
|---|---|---|
| `predict_code()` full pipeline | ≈70.03 ms | ≈39.82 ms |
| Feature construction | ≈9.30 ms | — |
| XGBoost inference | ≈0.40 ms | — |
| SHAP | ≈28.93 ms | — |
| Chatbot, app_id path | — | ≈5.76 ms |
| Chatbot, static CWE explanation | — | <0.01 ms |

## 9. Live-Validation Limitations

- **IntelliJ plugin live UI** (real-time annotation, tooltip, Alt+Enter, Quick Fix preview/diff, project batch-scan UI): **NOT VALIDATED** this session — no IDE sandbox run (disk/resource constraint on this machine). Underlying logic is covered by the 46 passing Kotlin unit/integration tests.
- **Flutter live device/emulator** (Login → Dashboard → Search → Details → Compatibility → Chatbot → History → Logout): **NOT VALIDATED** this session — no Android emulator or physical device connected (`flutter devices` showed only Windows desktop, Chrome, Edge). Any earlier manual-device evidence from prior phases is a separate, distinctly-provenanced result and is not combined with the current session's status.
- **No screenshots** were produced or fabricated for this phase, since no live UI session was run.

See `limitations.md` for the complete list.

## 10. Research Questions

See `research_conclusion.md` for the full RQ1–RQ5 answers and the final production conclusion. Summary:

- **RQ1** (best overall model): No universal winner — XGBoost best macro-F1/FPR, SVM best FNR/ROC-AUC, CodeBERT best CWE-89 recall.
- **RQ2** (safest against missed vulnerabilities): SVM, by overall FNR, among full-coverage models.
- **RQ3** (does DL outperform classical ML): No, not on this dataset.
- **RQ4** (is the Hybrid Decision Engine useful): Yes, especially when it auto-decides; current coverage is limited (32.7%).
- **RQ5** (should production switch away from XGBoost): No, based on current evidence.

## 11. Files Created

See `Section 12` below and the directory listing of `backend/research_eval_artifacts/final_documentation/`.

## 12. Final Production Conclusion

> "XGBoost remains the selected production model. The selection is based not on dominance across every metric, but on the combined research evidence, competitive macro-F1/false-positive performance, mature SHAP support, and established integration with the Hybrid Decision Engine, FastAPI backend, and IntelliJ plugin. SVM and CodeBERT demonstrate useful security advantages on specific metrics, while LSTM underperforms in this dataset. These alternatives remain research findings pending additional labelled data and further robustness validation."
