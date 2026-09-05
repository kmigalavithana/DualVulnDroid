# Risk-Aware Hybrid Detection of SQL Injection in Android Source Code Using Static Data-Flow Evidence and Selective Machine Learning

## Abstract

Automated detection of SQL Injection (CWE-89) in Android source code is commonly attempted with either purely learned models or purely rule-based static analyzers, each with well-known weaknesses: learned models can memorize training-set artifacts rather than generalize, and rule-based analyzers can be precise but brittle to code style. We investigate whether independently computed lexical/model evidence and deterministic SQL source-to-sink data-flow evidence can be combined through leakage-safe late fusion and selective prediction to support risk-aware CWE-89 detection on previously unseen Android projects. We construct a new, source-to-sink-traced, project-independent CWE-89 corpus (34 samples, 18 independent Android projects, 3 independently confirmed vulnerable projects, project-level train/validation/test separation) after finding a prior 1,687-row dataset methodologically inadequate for this purpose. We evaluate a leave-one-out out-of-fold text classifier, an independent static data-flow analyzer, a regularized-logistic-regression late-fusion model with validation-only calibration, and a predeclared safety-constrained abstention policy, following a frozen train/validate/test protocol with a single test evaluation. At this corpus's current scale, the evidence does not support a claim of reliable generalization: all evaluated text classifiers fail on the validation project's vulnerable example, the fusion model's out-of-fold training signal is structurally degenerate with only one training-set positive, calibration collapses the fused score to an near-constant value, and a predeclared zero-missed-vulnerability abstention policy forces zero-coverage (total abstention) on both validation and test. We report these negative and inconclusive results directly, alongside a working developer-facing Android Studio/IntelliJ plugin prototype whose backend inference latency (not end-to-end IDE latency) we measure directly, and we specify the additional independent vulnerable-project collection this method requires before any accuracy claim would be defensible.

**Keywords:** SQL injection, Android security, static analysis, data-flow analysis, machine learning, late fusion, selective classification, abstention, empirical software engineering

---

## I. Introduction

### A. Motivation

SQL Injection (CWE-89) remains a concrete, exploitable vulnerability class in Android applications that store data locally via `SQLiteDatabase`, Room, or `ContentProvider` APIs. Unlike server-side SQL injection, Android CWE-89 instances arise from a smaller, more idiosyncratic set of source types (file imports, inter-process `ContentProvider` calls, locally-stored user content) and sink APIs (`execSQL`, `rawQuery`, `query`, `update`, `delete`, `insert`), which makes both automated detection and ground-truth labeling harder than the volume of prior work in this space might suggest.

### B. Problem

Two detection paradigms exist. Deterministic static/data-flow analysis traces a value from a source to a sink and checks for parameterization, but is only as good as its source/sink pattern coverage and cannot reason about code styles or APIs it was not built to recognize. Machine-learned text/token classifiers can in principle generalize across code styles, but require enough independently-provenanced, project-diverse labeled examples to do so — a requirement Android CWE-89 research has largely not satisfied, because genuinely vulnerable, non-synthetic CWE-89 examples are rare in real, well-maintained Android code (Section III).

### C. Gap

Prior systems in this space — most notably FedREVAN [2] and Defendroid [3], both trained on the LVDAndro dataset [1] and both already integrated into Android Studio with real-time inference and explainable-AI (XAI) output — report high (96% accuracy / 0.96 F1) binary detection performance. Neither system, however, reports (a) project-level independence between its training and evaluation data, (b) a leakage-safe procedure for combining independently-learned and independently-derived evidence, or (c) a selective-prediction / abstention mechanism with a predeclared safety objective. This paper's contribution is deliberately **not** "first Android Studio vulnerability detector," "first real-time detector," or "first XAI plugin" — those claims are already made by prior work and are not repeated here. The gap this paper addresses is methodological: whether *independently computed* learned evidence and *independently computed* source-to-sink evidence can be combined without evidence double-counting, evaluated under strict project-level separation, and gated by a predeclared, safety-first abstention policy — and, honestly, whether the answer at currently achievable corpus scale is yes.

### D. Research Questions

- **RQ1.** On previously unseen Android projects, how accurately do (a) a text-only machine-learned classifier, (b) a deterministic SQL data-flow analyzer, and (c) their leakage-safe late fusion detect CWE-89?
- **RQ2.** At matched automatic-decision coverage, does late fusion reduce false-negative rate relative to ML-only and rule-only selective baselines?
- **RQ3.** Can the developer-facing plugin deliver findings within a measured latency budget without materially disrupting source-code editing?

### E. Contributions

1. A new, project-independent, source-to-sink-traced CWE-89 corpus with fully documented provenance, superseding a prior 1,687-row dataset found to have unresolved ground-truth defects (Section III).
2. A leakage-safe evaluation protocol — out-of-fold fusion-feature generation, validation-only calibration and abstention-threshold selection, a single frozen test evaluation — applied honestly, including where it fails to produce a usable result.
3. A direct, quantitative demonstration of *why* the current corpus scale is insufficient for a reliable ML or hybrid CWE-89 detector, reported as primary evidence rather than as a caveat appended to a positive claim.
4. A working developer-facing Android Studio/IntelliJ plugin prototype with measured backend inference latency and an explicit, undisguised prototype-security threat model.

## II. Related Work

**Android source-code vulnerability detection surveys.** Senanayake et al. [1] systematically reviewed 118 Android source-code vulnerability detection studies (2016–2022) and released the LVDAndro labeled dataset, widely reused in subsequent work, including [2], [3].

**Android Studio-integrated, real-time, XAI detectors.** FedREVAN [2] and its extension Defendroid [3] (Senanayake et al.) train a federated neural network on LVDAndro, report 96% accuracy/0.96 F1 for binary vulnerability classification and 93%/0.91 F1 for CWE-category multi-class classification, and integrate the resulting model into Android Studio with per-token XAI output. Among the studies identified by our documented search, these are the closest prior work to the developer-facing delivery mechanism used here; we do not repeat their real-time/IDE-integration/XAI novelty claims, and our reported plugin latency (Section V-F) is a systems measurement, not a detection-accuracy comparison against these systems.

**Static Application Security Testing (SAST) for Android.** A recent comprehensive evaluation of Android SAST tools [4] unified vulnerability-type coverage and built a CVE-derived benchmark, finding substantial variation in tool effectiveness and reporting completeness — directly motivating this paper's requirement (Section III-D) that a data-flow analyzer's source/sink coverage, completeness, and known blind spots be explicitly documented rather than assumed.

**LLM-based vulnerability detection.** Among the studies identified by our documented search, LLM-based Android vulnerability analysis [5] is an emerging, largely separate approach from the deterministic/learned hybrid studied here; we do not evaluate an LLM baseline (Section V-D) because the current corpus scale does not justify one.

**Selective classification.** SelectiveNet [6] formalizes joint learning of a classifier and a reject option, optimizing the risk-coverage trade-off end-to-end. We adopt the risk-coverage/AURC evaluation vocabulary from this literature (Section V-G) but use a simpler, post hoc, threshold-based abstention rule rather than an end-to-end-trained reject head, because the corpus scale here (Section III) does not support training an additional reject-head model.

**Prior DualVulnDroid dataset validity.** An internal audit of this project's own original 1,687-row (1,128-row "clean") CWE-89/CWE-295 dataset — summarized in Section III — found unresolved ground-truth problems (undocumented provenance, boilerplate negative-class explanations, no project identifiers) that preclude its reuse as evidence for this paper's ML claims.

## III. Method

### A. Prior Dataset: Why It Is Not Used

The project's original dataset (1,687 raw rows; 1,128 after removing 559 excluded rows) was audited and found unsuitable as ground truth for this paper's CWE-89 claims: no project/application identifiers existed to support project-level splitting; negative ("safe") class explanations were боilerplate-templated with no case-specific reasoning; and a full source-to-sink re-audit of the CWE-89 class found the confirmed-vulnerable count in that class to be zero once boilerplate and ambiguous rows were removed. This dataset is **not used** for any ML training or evaluation claim in this paper.

### B. New Corpus Construction

A new corpus was built by cloning and manually source-to-sink tracing real, permissively-or-copyleft-licensed public Android repositories (23 repositories cloned and code-read across the full collection process; GitHub's code-search API was unavailable without a token, so candidate repositories were located via `git ls-remote` existence checks and grep for `execSQL|rawQuery|.query(|.insert(|.update(|.delete(`, followed by full-method manual tracing). A sample was labeled `DEFINITELY_VULNERABLE` only with a complete, individually-documented source→propagation→sink chain (never from sink-API presence alone); `DEFINITELY_SAFE` only with an individually-written, non-boilerplate reason (compile-time constant, correct `?`-parameterization, a framework-level constraint, or an explicit runtime allowlist); any candidate not meeting either bar was excluded rather than forced into a label. Two candidate near-duplicates (a `Uri.getRawQuery()` and a `DnsResolver.rawQuery()` API-name false positive) were excluded as not relevant; one entire project (a near-verbatim fork of an already-included project) was excluded for clone risk; two additional vulnerable-*shaped* code sites were found to have zero reachable callers anywhere in their host application and are documented as unreachable rather than counted as live findings. **Table I** reports the resulting corpus.

Labeling was performed by a single reviewer; a second independent reviewer was not available for this study, and inter-rater agreement is therefore not reported — stated here as an explicit limitation, not omitted.

**Duplicate/clone control:** exact and near-duplicate detection used code-text normalization (comment/literal stripping) and manual project-lineage inspection (which is how the one excluded fork was found); **AST-level or token-clone-hash detection was not performed** and is disclosed as an open limitation of this corpus.

**TABLE I. Corpus Provenance and Split Statistics**

| Split | Projects | Repositories | Samples | Vulnerable | Safe |
|---|---|---|---|---|---|
| Train | 7 | 7 | 15 | 1 | 14 |
| Validation | 5 | 5 | 11 | 1 | 10 |
| Test | 6 | 6 | 8 | 1 | 7 |
| **Total** | **18** | **18** | **34** | **3** | **31** |

Repositories cloned and code-read across the full three-round collection process: 23. Excluded (not counted above): 2 API-name false positives, 1 near-duplicate-fork project, 2 vulnerable-shaped-but-unreachable code sites (zero live callers found).

### C. Project-Level Split

Every sample from a given project belongs to exactly one of train/validation/test. The split was verified programmatically before any model training: all three pairwise project-set intersections are empty, and the union covers all 18 projects. Each of the 3 confirmed-vulnerable projects was placed in a different split, so that train, validation, and test each contain exactly one vulnerable-class project — the first round of this project's corpus-construction process (2 vulnerable projects) could not achieve this; the present round (3) can, though only marginally (Section V-E).

**Fig. 2** depicts the project-separated protocol: disjointness is verified programmatically before any training step, and one vulnerable-class project is placed in each split.

### D. Independent Static/Data-Flow Analyzer

The analyzer (`dataflow.py`, reused read-only from this project's existing codebase, not modified for this paper) performs line-level source-to-sink tracing, not a bare keyword/regex scan: it extracts method boundaries, tracks variable-to-variable taint propagation across assignment statements within a method body, and — for each recognized SQL sink call — extracts the sink's actual call arguments (via balanced-parenthesis parsing, not a single-line regex) to determine whether the query text is a parameterized literal or an unparameterized concatenation. Its documented scope and limitations:

- **Recognized sinks (as shipped):** `execSQL`, `rawQuery`, `compileStatement`, `SimpleSQLiteQuery`. **Recognized sources (as shipped):** `Intent.getStringExtra()`, `Uri.getQueryParameter()`, `Intent.getExtras()`, `EditText.getText()`/`.toString()`, `Bundle.getString()`.
- **Experiment-specific extension used in this paper** (a documented, non-label-derived wrapper around the unmodified tool, not a change to the tool itself): the sink list was widened to also match `.query(`, `.update(`, `.delete(`, `.insert(`, matching this corpus's own construction-time grep pattern. The parameterization check itself was reused unchanged.
- **Interprocedural scope:** intra-method only; no cross-method, cross-class, or cross-file taint propagation, and no alias analysis. No Android component-lifecycle or callback-ordering reasoning.
- **Completeness:** every finding records whether *any* recognized sink was found at all (`sinks_found`), so "no evidence" (no recognized sink) is distinguishable from "evidence of safety" (a recognized sink, cleanly parameterized) — this distinction is used directly as an abstention-relevant "analysis completeness" feature in the fusion model (Section III-F).
- **Known blind spot, found directly in this study (Section V-C):** the *unmodified* tool's source patterns do not recognize XML-attribute-derived input (a SAX parser's `atts.getValue(...)`) as a taint source at all, so the unmodified tool is structurally blind to one of this corpus's three confirmed vulnerable samples; the experiment-specific sink-list extension above corrects the resulting sink-side blindness for that case, but the source-side blind spot in the unmodified tool is disclosed, not silently patched over.
- **Known imprecision, found directly in this study (Section V-C):** the parameterization check requires a sink's *entire* SQL-text argument to be a single quoted literal; multi-fragment string concatenation of literals and compile-time constants (common, safe code in this corpus) is not distinguished from unsafe concatenation, producing a documented high false-positive rate (Table III).

**Fig. 1** summarizes the overall pipeline: independent text-based and static-analysis evidence, combined only at the fusion stage (never inside either evidence source's own feature computation), producing a three-way VULNERABLE / SAFE / SUSPICIOUS\_REVIEW output.

### E. Text-Only Machine-Learned Classifier

Input is the `code_context` field only — the raw source-code snippet — with **no** access to any manually-assigned evidence column (`source`, `sink`, `tainted_variable`, `dataflow_path`, `parameterized`, `sanitized`, `evidence_type`, `label_confidence`, or `label` itself). A `TfidfVectorizer` (lowercase, default `\b\w\w+\b` word tokens, unigrams, `min_df=1`, `max_features=1000`) is fit **only** on the 15 training documents (7 projects), yielding a 251-term vocabulary; validation and test text are transformed with this fitted vectorizer only. Two classifiers are trained on the resulting features: a linear SVM (`class_weight="balanced"`) and gradient-boosted trees (XGBoost, `scale_pos_weight` set to the training class ratio). Class-imbalance handling (14 negative : 1 positive in training) is imbalance correction, not test-tuning. Random seed 42 throughout.

### F. Leakage-Safe Late Fusion

1. **Out-of-fold (OOF) generation.** Leave-one-out cross-validation over the 15 training samples, refitting TF-IDF inside each fold, produces a held-out ML score for every training sample — never an in-sample prediction. One fold is structurally degenerate: holding out the training set's *only* positive example leaves zero positives in that fold's training data, so a classifier cannot be meaningfully fit; this fold's OOF score is fixed to the negative-class floor (0.0) and explicitly flagged, not silently substituted or dropped (Section V-D).
2. **Independent evidence.** The static analyzer (Section III-D) is run over the same text, independently of the ML model.
3. **Fusion model.** A regularized logistic regression (`class_weight="balanced"`, C=1.0) is fit on the training set using three features — OOF ML probability, static evidence score (0.1/0.5/0.9 for parameterized/no-sink-found/unparameterized), and a binary "analysis completeness" indicator (whether any sink was found at all) — never an ML feature that restates the static evidence, and never a static feature that consults the ML output.
4. **Calibration.** Platt scaling (a 1-D logistic regression of the fusion score against the true label) is fit on the validation set only.
5. **Abstention.** A threshold band is selected on validation only, under a **predeclared safety objective**: maximize coverage subject to false-negative rate ≤ 0 (never let the validation set's one true positive be auto-decided as safe).
6. **Freeze and evaluate once.** All thresholds, weights, and the calibrator are frozen after validation-only selection; the test set is scored exactly once, after every other decision was fixed.

## IV. Implementation

### A. Developer Plugin

The research prototype is delivered as an IntelliJ Platform / Android Studio plugin (Kotlin, package `com.dualvulndroid.dualvulndroid`) providing a live source-code annotator, an evidence/finding tool window, and narrow, single-purpose quick fixes (e.g., converting an unparameterized `execSQL` concatenation into a bound `?` placeholder) — never a general automated-repair claim. The plugin is presented here as the delivery mechanism for this paper's findings, not as evidence of scientific novelty in its own right (Section II).

### B. Inference Architecture

The plugin calls a FastAPI backend (`/developer/predict`, `/developer/scan`, `/developer/explain`) that runs the currently-deployed production inference pipeline (XGBoost classifier + handcrafted security features + the same `dataflow.py` analyzer + SHAP attribution). This deployed pipeline — distinct from, and **not** used as evidence for, this paper's new-corpus ML claims (Section III) — is used here **only** to obtain a real, measured latency figure for the developer-facing round trip (Section V-F); no accuracy claim is drawn from it.

### C. Evidence Trace and Model Attribution

Each finding surfaced to the developer carries the static analyzer's source/sink/path evidence alongside the classifier's SHAP-based feature attribution. Consistent with Section II's framing, SHAP attribution is not treated as proof of a vulnerability: it attributes the classifier's own score to input features, while the static analyzer independently supplies source-to-sink evidence; the two are shown side by side, not merged into a single unexplained number.

### D. Security Considerations

Directly verified in the current implementation, not assumed: the backend runs over plain HTTP (no `ssl_keyfile`/`ssl_certfile` configured for the ASGI server); CORS is configured permissively (`allow_origins=["*"]`); JWT-based authentication exists and protects user-account endpoints (`/user/history`, etc.) but the code-submission endpoints the plugin actually calls (`/predict`, `/developer/predict`, `/developer/scan`, `/developer/explain`, `/developer/rescan`) carry **no authentication or authorization check**. **This paper does not claim secure deployment.** The threat model is stated plainly: any network party positioned to observe or intercept this unencrypted, unauthenticated traffic can read submitted source code in transit, and any party able to reach the backend's network address can invoke code analysis without credentials. The plugin/backend is a research prototype; "production" wording is avoided throughout.

## V. Experimental Evaluation

**TABLE II. Baseline and Ablation Configurations (evaluated on the same 8 frozen test cases)**

| ID | Configuration | Coverage rule |
|---|---|---|
| A | Rule-only (static analyzer) | Decides unless no sink recognized |
| B-SVM | ML-only, Linear SVM | Full coverage |
| B-XGB | ML-only, XGBoost | Full coverage |
| C | Early/naive fusion (fixed 0.5/0.5 average) | Full coverage |
| D | Late fusion (logistic regression, OOF-trained) | Full coverage |
| E | Late fusion + abstention | Predeclared FNR≤0 band, validation-selected |
| F | ML-only selective (SVM) | Predeclared FNR≤0 band, validation-selected |
| G | Rule-only selective | Predeclared FNR≤0 band, validation-selected |

### A. Datasets and Baselines

Exclusively `new_cwe89_corpus_final/` (Section III); no old dataset, checkpoint, vectorizer, or explainer is loaded (verified by the reproducibility artifact accompanying this study). Baselines, per Section III: rule-only (static analyzer), ML-only (SVM; XGBoost), naive fixed-weight (0.5/0.5) fusion retained as a simplicity control, logistic-regression late fusion, and selective (abstaining) variants of the ML-only, rule-only, and late-fusion configurations. No neural/transformer baseline is trained: the corpus scale (34 samples, 3 positive) does not justify one (Section V-D), consistent with an explicit, methodology-review-established exclusion of LSTM and CodeBERT from this study.

### B. RQ1 — Detection Accuracy on Unseen Projects

**Table III** reports raw counts. On the frozen test split (8 samples, 1 vulnerable project): the rule-only analyzer decides 7/8 samples (abstaining on 1 with no recognized sink) and achieves perfect recall (1/1) at 14.3% precision (6 false positives). The SVM misses the test-split vulnerable sample entirely (0/1 recall); XGBoost catches it (1/1). This XGBoost result is reported but **not credited as evidence of generalization**: on the validation split, evaluated one step earlier under an identical procedure, XGBoost — like SVM — missed the validation project's vulnerable sample (0/1 recall). A classifier that had learned a transferable CWE-89 signal would be expected to succeed or fail with some consistency across two similarly out-of-distribution positive examples; instead it failed on one and succeeded on the other, the behavior pattern expected from a model relying on incidental lexical overlap rather than learned discrimination. Direct evidence for this: the SVM's largest positive coefficients are literal identifiers unique to the training set's single positive example (`note`, `notetable`, `myquery`, `quoteifnotquoted`, `fixonenote`, `getcontenttosearch`) — a demonstration of memorization, not of a generalizable lexical signature of CWE-89.

Late fusion (logistic regression) produces, on this run, **identical** binary predictions to SVM-alone on every test sample (0 discordant pairs; Section V-E) — it inherits SVM's single miss rather than correcting it. The simpler, naive fixed-weight fusion does correct one prediction relative to rule-only (Table III, row C vs. A) via a specific, traceable mechanical interaction (Section V-C), not a general fusion benefit.

**RQ1 answer, stated plainly:** on this corpus's held-out projects, none of the three approaches (text-only ML, rule-only static analysis, or their fusion) demonstrates reliable, evidence-supported detection. Rule-only achieves perfect recall at the cost of very low precision; ML-only is inconsistent across the two out-of-distribution positives it was tested against; late fusion, in the specific run reported here, does not improve on ML-only.

**TABLE III. Main Results — Test Split (n=8, 1 vulnerable project); raw counts, LOW-POWER/DESCRIPTIVE throughout**

| Config | Cov. | TP | TN | FP | FN | Precision | Recall | FNR |
|---|---|---|---|---|---|---|---|---|
| A. Rule-only | 87.5% (7/8) | 1 | 0 | 6 | 0 | 0.14 | 1.00 | 0.00 |
| B-SVM. ML-only | 100% | 0 | 7 | 0 | 1 | N/A (no positive predictions) | 0.00 | 1.00 |
| B-XGB. ML-only | 100% | 1 | 7 | 0 | 0 | 1.00 | 1.00 | 0.00 |
| C. Naive fusion | 100% | 1 | 1 | 6 | 0 | 0.14 | 1.00 | 0.00 |
| D. Late fusion (no abstain) | 100% | 0 | 7 | 0 | 1 | N/A | 0.00 | 1.00 |

Project-level bootstrap (2,000 resamples, 6 test projects): SVM-only accuracy 0.88 (95% CI [0.67, 1.00]); late-fusion accuracy 0.88 (95% CI [0.67, 1.00]) — wide intervals reflect n=6 resampled projects and should be read descriptively. McNemar's exact test, SVM-only vs. late fusion: 0 discordant pairs (identical predictions on all 8 test samples) — no p-value is computable.

### C. Root-Cause / Error Analysis

Every false positive and false negative on the test split was individually inspected (full detail: `error_analysis.csv`).

- **The SVM's one false negative** (the test project's vulnerable sample) is categorized as a **training-data coverage gap**: the training set's single positive example uses a completely different vulnerability mechanism (a flawed string-escaping helper acting on in-app note content) than the missed test example (an XML backup file's attribute value reaching a SQL selection clause with no escaping at all) — no interprocedural, aliasing, or parser limitation is implicated; the model simply never saw this mechanism's vocabulary.
- **All six of the rule-only analyzer's false positives** are categorized as **sanitization/parameterization misunderstanding**: each flagged sample builds its SQL text via `+`-concatenation of multiple literal fragments and/or compile-time constants — safe, but not recognized as such by a check that requires the *entire* argument to be a single literal (Section III-D).

No fabricated or illustrative-only examples are used above; every case cited was an actual test-split misclassification.

**TABLE VI. Error Categories — Test Split**

| Category | Count | Model | Description |
|---|---|---|---|
| Training-data coverage gap | 1 (FN) | SVM | Positive example's mechanism/vocabulary entirely absent from training data |
| Sanitization/parameterization misunderstanding | 6 (FP) | Rule-only | Multi-fragment literal/constant concatenation misread as unsafe |

No occurrences were found in this test split for: missed source, missed sink (after the documented `.query()`-family extension), interprocedural flow, aliasing, callback/lifecycle, parser limitation, uncommon SQL API, truncation/context loss, custom query builder, dead/unreachable code, or label uncertainty — stated explicitly rather than padded with categories that do not apply to this data.

### D. ML Feasibility at This Scale

Consistent with an explicit prior assessment of this corpus (not repeated in full here), LSTM and CodeBERT were excluded from this study: with 15 training documents (1 positive) and a 251-dimensional feature space even for a linear model, a recurrent or pretrained-transformer architecture's parameter count vastly exceeds the available signal, and — specific to CodeBERT — an existing project checkpoint was fit on the invalidated old dataset (Section III-A) and reusing it would silently reintroduce exactly the contamination this corpus-construction effort exists to remove. SVM and XGBoost were retained specifically because their failure modes are legible (an inspectable coefficient vector; a small number of boosted trees) rather than because either was expected to generalize.

### E. RQ2 — Matched-Coverage Selective Prediction

**Table IV** reports the full ablation (A–G) on the same, frozen test cases; no comparison in this table compares a method's full-coverage result against another method's easy-subset result. Two results define the answer to RQ2:

1. **The properly-trained (OOF-based) late-fusion model exhibits an inverted machine-learning coefficient.** The fusion logistic regression's weight on the OOF ML probability feature is **negative** (−1.1468): *higher* ML score is associated with *lower* fused vulnerability probability — the opposite of the intended relationship. Root cause, confirmed directly: leave-one-out CV with exactly one positive training example forces that example's held-out OOF score to the negative-class floor (0.0, Section III-F) — the lowest ML score in the entire training set is attached to the only positive label, and a regression fit on this single, structurally-forced data point learns an inverted coefficient. This is reported as direct evidence that OOF-based fusion training is not statistically meaningful with one positive training example — not as an implementation defect.
2. **Under the predeclared, safety-first abstention objective (maximize coverage subject to FNR ≤ 0 on validation), the only threshold band satisfying the constraint on validation achieves 0% coverage** — every validation sample's fusion score falls too close to every other's for any non-trivial band to isolate the one true positive without risking it. Applying this frozen band to test (no re-selection after seeing test, per protocol) likewise yields 0% coverage.

**RQ2 answer, stated plainly:** at matched coverage, late fusion does not measurably reduce false-negative rate relative to the selective baselines in this run — the fully safety-constrained fusion variant achieves its zero-FNR guarantee only by deciding nothing at all, and the non-abstaining fusion variant makes the same predictions as ML-only. This is a negative result and is reported as one.

**TABLE IV. Selective Prediction / Matched-Coverage Results — Test Split**

| Config | Coverage | Abstained | Decided TP/TN/FP/FN | FNR (decided) |
|---|---|---|---|---|
| E. Late fusion + abstention | 0% | 8/8 | 0/0/0/0 | N/A — nothing decided |
| F. ML-only selective (SVM) | 37.5% (3/8) | 5/8 | 0/3/0/0 | N/A (0 positives among decided) |
| G. Rule-only selective | 100% (8/8) | 0/8 | 1/0/7/0 | 0.00 |

Config F's abstention band (selected on validation, frozen before test) happens to exclude the one test-split positive from the auto-decided set entirely — the model abstains on it rather than guessing wrong, which is a safety-consistent (if low-coverage) outcome, not a "correct detection." Config G's static-score discretization ({0.1, 0.5, 0.9}) collapses its selective variant to full coverage, reproducing rule-only's low-precision behavior with no NO\_SINK abstention preserved.

**Calibration finding.** Post-calibration, the fused probability on the test split ranges from **0.090920 to 0.090935** across all 8 samples — a span under 0.00002, i.e., a practically constant output close to the training base rate regardless of sample content (`calibration_report.json`). Brier score and expected calibration error both improve numerically after calibration (Brier 0.214→0.083; ECE 0.364→0.000), but this reflects the calibrator correctly recognizing that the raw fusion score carries no exploitable signal at this validation size (11 samples, 1 positive) — not a working, well-calibrated detector.

### F. RQ3 — Plugin Latency

Full end-to-end editor-to-annotation IDE latency was **not measured** in this study (it would require a live, instrumented IDE session, which was outside this study's scope) and no such claim is made. What **was** measured directly, over 30 repeated calls per snippet after 3 warm-up calls (0 request errors): the currently-deployed backend's compute-path latency (`predict_code()`, in-process, no network layer) for representative short (53-char), medium (341-char), and long (4,719-char) code snippets (**Table V**; full data in `backend_latency_report.json`). Model/vectorizer load time was 8.14 s (a one-time cold-start cost per backend process, not per request). This is reported explicitly as **backend inference latency**, not real-time IDE latency, per the distinction this study maintains throughout.

**RQ3 answer, stated plainly:** backend compute latency is low (tens to ~120 ms at p99 for the snippet sizes tested) and would not obviously disrupt editing if end-to-end IDE latency scaled similarly, but this study does not establish that it does, because end-to-end measurement was not performed.

**TABLE V. Backend Inference Latency (predict_code() compute path only; 30 repeated calls per snippet after 3 warm-up calls; 0 request errors)**

| Snippet | Size | Mean | p50 | p95 | p99 |
|---|---|---|---|---|---|
| Short | 53 chars | 65 ms | 65 ms | 73 ms | 84 ms |
| Medium | 341 chars | 45 ms | 45 ms | 49 ms | 50 ms |
| Long | 4,719 chars | 110 ms | 111 ms | 117 ms | 119 ms |

Model/vectorizer cold-load time (one-time, per backend process, not per request): 8.14 s. The non-monotonic short-vs-medium relationship is reported as observed, not adjusted or explained away.

### G. Statistical Reporting

Project-level bootstrap (2,000 resamples over the 6 test projects) gives SVM-only test accuracy 0.880 (95% CI [0.667, 1.0]) and late-fusion test accuracy 0.882 (95% CI [0.667, 1.0]) — reported with an explicit low-power caveat given only 6 resampled projects. McNemar's exact test comparing SVM-only and late fusion on matched test cases has **zero discordant pairs** (the two methods make identical predictions on all 8 test samples), so no p-value is computable or meaningful — this is itself the finding, not a null result requiring further explanation. A risk-coverage curve and its area (AURC = 0.2365, **Fig. 3**) are reported for the fusion score on the 8-sample test split with an explicit LOW\_POWER/DESCRIPTIVE label; no confidence interval is attached to the AURC value itself given the sample size. The curve is **not monotonically increasing** (risk peaks at 25% coverage before declining toward 100% coverage) — reported as observed; a well-behaved selective classifier's risk-coverage curve is expected to be monotonic, and this departure is a further symptom of the near-constant, low-information fusion score documented above, not a separately investigated phenomenon. Four decimal places are reported only where the underlying computation is exact (e.g., a fusion coefficient); metrics computed from single-digit counts are rounded to at most two decimals or reported as raw counts.

## VI. Discussion and Threats to Validity

**Internal validity.** The frozen train→validate→test protocol (Section III-F) was followed without exception; the test set was scored exactly once. The one point requiring judgment — the experiment-local sink-list extension to `dataflow.py` (Section III-D) — was a documented, structural, non-label-derived fix and is disclosed as a residual risk (the same reviewer who extended the tool also labeled the corpus).

**Construct validity.** "Analysis completeness" (Section III-F) is operationalized narrowly, as "did the analyzer recognize any sink at all" — a coarser signal than the richer notion (interprocedural completeness, alias resolution) the term could imply; this is stated explicitly rather than left ambiguous.

**External validity — the central limitation of this study.** 34 samples across 18 projects, with exactly 3 independently confirmed vulnerable projects (1 per split), is not enough to support a generalization claim, and this study does not make one. Every quantitative result in Section V is reported with this constraint attached, not as a footnote to a positive headline result.

**Conclusion validity.** No statistical-significance claim is made anywhere in this paper beyond the exact test explicitly run (Section V-G), and where that test was inapplicable (zero discordant pairs), that inapplicability is reported rather than substituted with an unsupported claim.

## VII. Conclusion

This study set out to determine whether independently computed learned evidence and independently computed SQL source-to-sink evidence could be combined, under a leakage-safe protocol, to support risk-aware CWE-89 detection on unseen Android projects. Following the full protocol honestly, on the currently available corpus, the answer is **not yet**: text-only classifiers do not generalize consistently across the corpus's mechanistically distinct vulnerable examples; a properly out-of-fold-trained fusion model exhibits a structurally inverted coefficient traceable directly to having only one positive training example; and a predeclared, safety-first abstention policy is only satisfiable by declining to decide anything at all. These are reported as this study's primary findings, not as limitations appended to a claimed improvement. The corpus, protocol, and developer plugin are retained and documented as the infrastructure for a follow-up study; the concrete next step is collecting substantially more independent vulnerable-project examples (an operational target of approximately 5–8 per split, not a statistical guarantee) before any accuracy or fusion-benefit claim would be defensible.

## References

[1] J. Senanayake, H. Kalutarage, M. O. Al-Kadri, A. Petrovski, and L. Piras, "Android Source Code Vulnerability Detection: A Systematic Literature Review," *ACM Computing Surveys*, vol. 55, no. 9, 2023.

[2] J. Senanayake, H. Kalutarage, A. Petrovski, M. O. Al-Kadri, and L. Piras, "FedREVAN: Real-time DEtection of Vulnerable Android Source Code Through Federated Neural Network with XAI," in *Computer Security. ESORICS 2023 International Workshops (WASP)*, Springer, 2024.

[3] J. Senanayake, H. Kalutarage, A. Petrovski, M. O. Al-Kadri, and L. Piras, "Defendroid: Real-time Android Code Vulnerability Detection via Blockchain Federated Neural Network with XAI," *Journal of Information Security and Applications*, vol. 82, art. 103741, 2024.

[4] "A Comprehensive Study on Static Application Security Testing (SAST) Tools for Android," *IEEE Transactions on Software Engineering*, 2024 (arXiv:2410.20740).

[5] "Assessing the Effectiveness of LLMs in Android Application Vulnerability Detection," in *Proc. [Springer conference series]*, 2025 (DOI: 10.1007/978-3-031-85593-1_9).

[6] Y. Geifman and R. El-Yaniv, "SelectiveNet: A Deep Neural Network with an Integrated Reject Option," in *Proc. 36th Int. Conf. on Machine Learning (ICML)*, PMLR vol. 97, 2019.

[7] MITRE, "CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')," *Common Weakness Enumeration*.
