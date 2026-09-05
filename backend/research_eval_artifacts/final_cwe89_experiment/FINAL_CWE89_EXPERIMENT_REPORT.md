# Final CWE-89 Feasibility Experiment — Report

**Run date:** 2026-08-29 · **Status: FEASIBILITY / PROOF-OF-CONCEPT EXPERIMENT — NOT a benchmark, NOT a production evaluation, NOT a statistically powered comparison, NOT a general Android vulnerability benchmark.** Every result below must be read with that framing; it is restated at the end of every section that reports a number.

---

# Executive Summary

This experiment trained three classical text-only classifiers (Linear SVM, Random Forest, XGBoost), built an independent static/data-flow baseline from a read-only, experiment-scoped wrapper around `backend/dataflow.py`, combined them via a predefined (not test-tuned) late-fusion rule, and evaluated a selective-prediction (abstain) variant — all strictly on `new_cwe89_corpus_final/` (34 samples, 18 projects, project-level split independently re-verified before training). No old dataset, old model checkpoint, old vectorizer, or old Decision Engine weight was loaded.

**The headline result is a clean, concrete demonstration of exactly the limitation the prior feasibility review predicted, not a working detector.** All three ML models correctly classify the one training-set vulnerable example (memorization) but **all three fail to detect the validation-set's vulnerable example** (`ts-001`) — 0/3 recall on validation. On the test set, XGBoost happens to catch the vulnerable example (`os-001`) while SVM and Random Forest do not; because XGBoost failed on the mechanistically-equivalent validation case one split earlier under an identical setup, this single test-set success cannot be attributed to genuine learned generalization rather than chance, and the report does not claim otherwise. The independent static baseline achieves perfect recall (3/3) but catastrophic precision (14%–71% false-positive rate depending on split) because its parameterization check is too strict for this corpus's common "concatenate several literal fragments and constants" safe-coding style. Late fusion inherits the static baseline's behavior almost entirely — the ML component's score range is too narrow to meaningfully shift the fused decision — and the predefined abstention band triggers zero abstentions on any split.

**Final classification: B — INCONCLUSIVE DUE TO DATA LIMITATION.**

---

# 1. Corpus Used

**Exclusively** `backend/research_eval_artifacts/new_cwe89_corpus_final/`. Counts independently re-verified from the CSV/JSON files before any training step (not assumed from the corpus's own report):

| Check | Verified value |
|---|---|
| Total samples | 34 |
| Vulnerable / Safe / Ambiguous | 3 / 31 / 0 |
| Independent projects | 18 |
| Train / Validation / Test projects | 7 / 5 / 6 |
| Vulnerable project per split | 1 each (`andstatus-andstatus`→train, `tasks-tasks`→validation, `openintents-safe`→test) |

No file under `new_cwe89_corpus/`, `new_cwe89_corpus_expanded/`, or `new_cwe89_corpus_final/` was modified. No old 1687-row/1128-row dataset, old `train.csv`/`validation.csv`/`test.csv`, old XGBoost/SVM/RF/LSTM/CodeBERT checkpoint, old TF-IDF vectorizer/scaler, old SHAP explainer, or old Decision Engine weights were loaded — confirmed in `experiment_config.json`'s `old_artifacts_loaded: "NONE"` field, and true by construction (every model/vectorizer object in this run was freshly instantiated and fit inside this experiment's own script).

# 2. Project-Level Split

Re-verified programmatically (Python sets over `project_id`, from `final_project_split_manifest.csv` and cross-checked against every sample's own `split` field in `final_candidate_cwe89_samples.csv`) before any preprocessing or training:

```
train ∩ validation = ∅   train ∩ test = ∅   validation ∩ test = ∅
train ∪ validation ∪ test = all 18 projects
zero mismatches between manifest split and per-sample split field
```

**No change was made to the existing split** — no integrity error was found, so per the task's instruction the split was used exactly as delivered. The test set's labels and samples were not inspected for any tuning decision (vectorizer, model hyperparameters, decision threshold, fusion weight, or abstention band) at any point before final evaluation — every one of those was fixed using only train and/or validation data, as detailed in Sections 4–7.

| Split | Projects | Samples | Vulnerable | Safe |
|---|---|---|---|---|
| TRAIN | 7 | 15 | 1 | 14 |
| VALIDATION | 5 | 11 | 1 | 10 |
| TEST | 6 | 8 | 1 | 7 |

# 3. Experimental Protocol

1. **Text representation** (`code_context` column only). Explicitly excluded from any ML input: `label`, `source`, `sink`, `tainted_variable`, `dataflow_path`, `parameterized`, `sanitized`, `evidence_type`, `cwe`, `label_confidence` — confirmed in `feature_metadata.json`.
2. **TF-IDF fit on TRAIN documents only** (15 documents): `lowercase=True`, default word token pattern (`\b\w\w+\b`), unigrams only, `min_df=1`, `max_features=1000` → **vocabulary size 251, feature dimensions 251** (all 251 vocabulary terms fit within the 1000-feature cap, so no truncation occurred). Validation and test text were transformed using this already-fitted vectorizer only — no refitting, no vocabulary leakage.
3. **Three classical models trained** on `X_train`/`y_train`: `LinearSVC(class_weight="balanced")`, `RandomForestClassifier(n_estimators=200, max_depth=4, class_weight="balanced")`, `XGBClassifier(n_estimators=100, max_depth=3, scale_pos_weight=14.0)`. `class_weight`/`scale_pos_weight` handle TRAIN's 14:1 safe:vulnerable imbalance — this is imbalance handling, not test-set tuning. LSTM, CodeBERT, and generic transformers were **not trained**, per the task instruction and the prior feasibility review's explicit exclusion.
4. **Decision threshold fixed at 0.5** for all ML scores and the fusion score — not searched or tuned, given how degenerate a 1-positive validation set would make any such search.
5. **Independent static/data-flow baseline**: see Section 5.
6. **Late fusion**: `combined_score = 0.5 * ml_probability(SVM) + 0.5 * static_score` — a predefined, fixed weighting (see Section 6).
7. **Selective prediction**: abstain if `0.45 < combined_score < 0.55`, decide otherwise — a predefined, fixed band selected before observing validation's score distribution (see Section 7).
8. **Random seed 42** used everywhere a seed applies (`numpy`, `LinearSVC`, `RandomForestClassifier`, `XGBClassifier`).

# 4. ML Baselines

Full detail: `model_results.csv`, `confusion_matrices.csv`.

| Model | Train (n=15, 1 pos) | Validation (n=11, 1 pos) | Test (n=8, 1 pos) |
|---|---|---|---|
| **SVM** | TP=1 TN=14 FP=0 FN=0 (perfect — memorized) | TP=0 TN=10 FP=0 FN=1 **(missed)** | TP=0 TN=7 FP=0 FN=1 **(missed)** |
| **Random Forest** | TP=1 TN=14 FP=0 FN=0 (perfect — memorized) | TP=0 TN=10 FP=0 FN=1 **(missed)** | TP=0 TN=7 FP=0 FN=1 **(missed)** |
| **XGBoost** | TP=1 TN=14 FP=0 FN=0 (perfect — memorized) | TP=0 TN=10 FP=0 FN=1 **(missed)** | TP=1 TN=7 FP=0 FN=0 **(caught)** |

**All three models achieve trivially perfect train performance** (expected — a model with 251 features and 15 documents can separate 1 point from 14 in almost any reasonable configuration) **and all three fail identically on the validation set**, missing `ts-001` entirely. This is the central, clean finding of Experiment A: **none of the three models generalized past memorizing the training-set positive's specific vocabulary** — confirmed directly in Section 6's interpretability analysis, where the SVM's highest-weighted tokens toward "VULNERABLE" are literal identifiers unique to the one training example (`note`, `notetable`, `myquery`, `quoteifnotquoted`, `fixonenote`, `getcontenttosearch`) rather than any general lexical signature of SQL injection.

XGBoost's test-set success (catching `os-001`) is reported honestly but **cannot be read as evidence of genuine learned discrimination**: the identical model, trained identically, failed on `ts-001` — a different vulnerable example from a different project, encountered one split earlier under otherwise the same conditions. A model that had learned something generalizable about CWE-89 would be expected to succeed or fail somewhat consistently across similarly out-of-distribution positive examples; instead it failed on one and succeeded on the other, which is the behavior pattern expected from chance/lexical-coincidence, not signal. **No "best model" claim is made from this result.**

*Power note, per Step 11: with 1 true positive per split, recall/F1/FNR on every split above are LOW_POWER/DESCRIPTIVE, not statistically robust estimates. Where precision is undefined (no positive predictions made), it is reported as `NOT_ESTIMABLE` rather than a fabricated value — see `model_results.csv`.*

# 5. Static/Data-Flow Baseline

**Determination on adapting `backend/dataflow.py`:** the existing, unmodified tool's sink-name list (`SQL_SINK_NAMES` = `rawQuery`/`execSQL`/`compileStatement`/`SimpleSQLiteQuery`) does not include `.query()`, which is `os-001`'s actual sink — the unmodified tool is **structurally blind** to 1 of the corpus's 3 vulnerable examples (confirmed directly: unmodified `sql_sink_safety_summary()` returns `sinks_found=0` for `os-001`). Per the task's Step 6 instruction, an **experiment-specific wrapper** was written (not modifying `dataflow.py`) that extends only the sink-name list to also match `.query(`/`.update(`/`.delete(`/`.insert(` — the same four SQLite API calls this corpus's own construction methodology grepped for. The parameterization-check logic itself (`_extract_sink_args`, `_has_placeholder`) is reused **unchanged** from `dataflow.py`. This wrapper does not use ML output and does not know any sample's label.

**Result, all 34 samples:**

| Split | Decided | Abstained (`NO_SINK`) | TP | TN | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|---|
| Train | 15/15 | 0 | 1 | 1 | 13 | 0 | 7.1% | 100% |
| Validation | 9/11 | 2 | 1 | 0 | 8 | 0 | 11.1% | 100% |
| Test | 7/8 | 1 | 1 | 0 | 6 | 0 | 14.3% | 100% |

**The static baseline achieves perfect recall (3/3 vulnerable samples caught, including `os-001`, which the unmodified tool would have missed) at the cost of catastrophic precision** (86–93% of its "VULNERABLE" verdicts on safe code are false positives). The root cause, confirmed by direct inspection: the parameterization check requires a sink's entire SQL-text argument to be a *single* quoted literal string; this corpus's safe class is dominated by code that builds SQL text via `+`-concatenation of *multiple* literal fragments and compile-time constants (a common, safe, but structurally different pattern from a single literal) — the check flags nearly all of it as "not cleanly parameterized" even though no actual data value is unsafely concatenated. This is an honest, reportable limitation of the tool as applied to this corpus's code style, not a new defect introduced by the wrapper.

# 6. Late Fusion

`combined_score = 0.5 × ml_probability(SVM) + 0.5 × static_score` (`static_score` ∈ {0.1 = SAFE, 0.5 = NO_SINK, 0.9 = VULNERABLE}). **Weights were fixed at 0.5/0.5 by predefined choice, not selected via any search on validation or test** — per the task's explicit fallback for validation sets too small to reliably estimate weights (11 samples, 1 positive).

| Split | TP | TN | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|
| Train | 1 | 1 | 13 | 0 | 7.1% | 100% |
| Validation | 1 | 2 | 8 | 0 | 11.1% | 100% |
| Test | 1 | 1 | 6 | 0 | 14.3% | 100% |

**Fusion essentially inherits the static baseline's behavior**, improving true negatives by exactly 1 per split relative to Experiment B alone — mechanically traceable to the two `NO_SINK`-flagged safe samples (`sn-001`, `sn-002`) whose `static_score=0.5` combined with a low SVM score pulls their `combined_score` below 0.5, correctly resolving what the static baseline alone would have abstained on. **This is the entirety of the fusion's measurable contribution in this run.** The reason is visible directly in the score distributions (`dataset_manifest.csv`): SVM scores cluster tightly in ~0.29–0.35 for almost every sample regardless of label, while static scores are far more extreme (0.1/0.5/0.9) — under equal weighting, the static component's wider dynamic range dominates the sum, and the ML component contributes negligible discriminative shift to the final decision. **No claim is made that fusion "improves" on either component** beyond this one mechanically-explained, marginal effect; the precision numbers above are nearly identical to Section 5's static-alone numbers.

# 7. Selective Prediction

Predefined, fixed abstention band `0.45 < combined_score < 0.55`, chosen before this script's first run (not adjusted after observing the resulting behavior). **Result: 0 abstentions on every split** (train, validation, test) — `abstention_results.csv` shows 100% coverage everywhere, and Experiment D's confusion counts are therefore identical to Experiment C's on every split.

**Why:** the validation `combined_score` distribution (visualized in `plots/combined_score_distribution.png`) is bimodal — two `NO_SINK`-flagged safe samples sit near 0.40, and the remaining nine samples (including the one true positive, `ts-001` = 0.603) cluster tightly between 0.596 and 0.699, with **no natural separation between the true positive and its safe neighbors within that cluster**. No threshold or band placed in this score space can isolate `ts-001` from the safe examples surrounding it, because the fusion score (Section 6) does not carry enough discriminative information to do so. This is reported as the honest outcome of the predefined rule, not adjusted post hoc: **the abstention mechanism, as configured, added no observable value in this run**, and the report does not claim otherwise.

# 8. Ablation

| Ablation | Test-split TP/TN/FP/FN | What it tested |
|---|---|---|
| A. ML only (SVM) | 0/7/0/1 | Whether lexical text signal alone, with zero dataflow evidence, separates the classes. Result: fails on the split's positive example. |
| B. Static/data-flow only | 1/0/6/0 (7 decided, 1 abstained) | Whether deterministic sink/parameterization evidence alone separates the classes. Result: perfect recall, near-zero precision. |
| C. ML + static (fusion) | 1/1/6/0 | Whether combining the two changes the outcome. Result: near-identical to B alone; +1 TN mechanically attributable to the `NO_SINK` case. |
| D. ML + static + abstention | 1/1/6/0 (0 abstained) | Whether adding a disagreement/uncertainty abstention rule changes decision behavior. Result: no change — zero abstentions triggered. |

**The additional evidence (static, then fusion, then abstention) changed decision behavior only at the margin (B→C: +1 TN) and not at all from C→D.** The ablation does not demonstrate that combining evidence sources yields a meaningfully different or better outcome than the static baseline alone on this corpus.

# 9. Results

Consolidated in `model_results.csv`, `confusion_matrices.csv`, `fusion_results.csv`, `abstention_results.csv`; visualized in `plots/`. No metric above should be read outside the caveats stated in Sections 4–7 and restated in Section 10.

# 10. Error Analysis

- **All 3 ML models miss `ts-001` on validation** — the SVM's own top coefficients (Section 4, `feature_metadata.json`) show the model attached almost all of its "VULNERABLE" weight to literal tokens from `as-001` alone (`note`, `notetable`, `myquery`, `quoteifnotquoted`, `fixonenote`, `getcontenttosearch`, `iscancelled`, `content_to_search`) — none of which appear in `ts-001`'s Kotlin ContentProvider code. The model did not learn a transferable notion of "unparameterized SQL text reaching a sink"; it learned to recognize one specific method's vocabulary.
- **XGBoost's test-split success on `os-001` is not corroborated by its validation-split behavior on `ts-001`** under an identical setup — the single most important honesty check available with this data, and it does not support treating the test success as generalization.
- **The static baseline's false positives are concentrated in exactly the pattern identified in the prior feasibility review's Section 3 (safe-class diversity):** most false positives are safe samples whose SQL text is built from multiple literal/constant fragments joined by `+` — precisely the "compile-time constants" category that made up 52% of the corpus's safe class. The static wrapper's strict single-literal check cannot distinguish this from genuinely risky concatenation.
- **Fusion's only measurable effect (Section 6) is explainable by one mechanical interaction** (the `NO_SINK` static score pulling two specific samples' combined score below threshold) rather than any broader synergy between the two evidence sources.

# 11. Reproducibility

Full detail in `reproducibility_report.json` and `experiment_config.json`: corpus path and SHA-256 hash of both corpus CSVs consumed, project split, random seed (42), Python 3.11, scikit-learn 1.9.0, xgboost 3.2.0, numpy 2.4.6, pandas 3.0.3, matplotlib 3.11.1, full vectorizer/model parameter dictionaries, threshold/fusion-weight values, and UTC run timestamp. `old_artifacts_loaded: "NONE"` is recorded explicitly and is true by construction — every vectorizer and model object was freshly instantiated inside this experiment's own script.

# 12. Threats to Validity

- **Sample size dominates every other threat.** 1 vulnerable sample per split makes every point-estimate metric above a single-observation outcome, not a rate estimate (restated from the prior feasibility review, now empirically demonstrated rather than only argued).
- **Static baseline wrapper extension**: extending the sink-name list (Section 5) was a deliberate, documented, structurally-motivated choice, but it was made by the same person who also labeled the corpus — a residual risk of unconscious alignment between the wrapper's design and the corpus's construction methodology exists, even though the extension itself is mechanical (sink-name matching) rather than label-derived.
- **TF-IDF dimensionality**: 251 features from 15 training documents is a severe curse-of-dimensionality situation; no feature selection was applied to reduce this, since doing so risks indirectly encoding label information into the pipeline — but this means the raw feature-to-sample ratio itself is a threat to any generalization claim, independent of which model is used.
- **Single reviewer, single run**: no repeated-sampling, cross-validation-style, or multi-seed analysis was performed (a meaningful k-fold CV is not feasible with 1 positive example per split in the first place).
- **Fusion weight and abstention band were fixed by predefined choice, not estimated** — a different (still principled) choice could produce different Section 6/7 numbers; the report makes no claim that 0.5/0.5 or (0.45, 0.55) are optimal or representative choices.

# 13. What the Results Demonstrate

- **Feasibility**: an end-to-end pipeline (text-only ML, independent static/dataflow evidence, late fusion, selective prediction) can be built and run on this corpus without a train/validation/test leakage error, without loading any invalidated old artifact, and while respecting the double-counting constraint (ML saw code text only; the static wrapper's evidence was computed independently and never fed into the ML feature space).
- **Proof-of-concept for evidence fusion machinery**: the late-fusion and abstention code paths function correctly and produce interpretable, traceable numbers (Sections 6–7), even though the *result* in this run is that fusion added negligible value.
- **A concrete, reproducible illustration of the memorization-not-generalization failure mode** predicted by the prior feasibility review's Section 6 (ML Feasibility) — Section 4's validation-split results are direct empirical evidence for that prediction, not merely a restatement of it.
- **A concrete, reproducible illustration of an existing tool's limited transfer** to a new, more code-style-diverse corpus (Section 5), including the specific, fixable coverage gap (`.query()`-family sinks) that this experiment's wrapper corrected.

# 14. What the Results Do NOT Demonstrate

- **Not "best model."** XGBoost's one test-split success is not corroborated by its validation-split behavior and is not claimed as evidence of superiority.
- **Not "state of the art."** No comparison to any external tool or published result was made.
- **Not "general Android vulnerability detection."** All evaluation is confined to this corpus's 34 samples.
- **Not "production accuracy."** No metric here reflects deployment-scale behavior.
- **Not "statistically significant improvement."** No confidence interval, significance test, or robust effect-size estimate is reported anywhere in this document — where a metric was undefined, it is marked `NOT_ESTIMABLE`, never invented.
- **Not "robust benchmark."** 34 samples, 1 vulnerable per split, is not a benchmark.
- **Not "generalizes to unseen Android applications."** Section 4/10 directly show the opposite on this run's evidence (validation-split failure across all three models).
- **Not "highly accurate."** No accuracy number in this report should be read as evidence of accuracy at any scale beyond the specific samples decided.
- **Not "solves CWE-89."** Nothing here approaches that claim.

# 15. Recommendation for the Conference Paper

**Do not present this experiment as a validated detector or as the paper's evidence of a working hybrid method.** If a paper section draws on this experiment, it should be framed exactly as this report frames it: a feasibility/proof-of-concept run whose main contribution is methodological (a leakage-safe, double-counting-safe, old-dataset-free pipeline) and whose main empirical finding is a clear, concrete demonstration of *why* this corpus's current scale cannot yet support a supervised CWE-89 detector — evidenced by validation-split failure across three independent classical model families and a static baseline whose precision collapses under this corpus's realistic safe-coding style. This is a legitimate, honest contribution to a thesis chapter on methodology and corpus limitations; it is not evidence for a results chapter claiming a working system. Per the earlier feasibility review's Section 12, the path to a stronger paper claim runs through collecting more independent vulnerable-class projects (target: ~5–8 per split), not through re-running this same experiment with different hyperparameters on the same 3 vulnerable samples.

---

## Final Decision

**B — INCONCLUSIVE DUE TO DATA LIMITATION.**

Not A: the pipeline runs and produces predictions, but Section 4 shows all three ML models fail on the validation split and Section 6 shows fusion adds no demonstrable value beyond the static baseline's own (poor) behavior — there is no honest basis to claim feasibility was *demonstrated* rather than *attempted*. Not C: nothing here shows the hybrid method *cannot* work — only that this corpus's scale (1 vulnerable sample per split) makes it impossible to tell. The data limitation, not a methodological flaw, is the binding constraint, which is precisely what classification B is for.
