# Risk-Aware Hybrid Detection of SQL Injection in Android Source Code Using Static Data-Flow Evidence and Selective Machine Learning

## Abstract

**Background:** SQL Injection (CWE-89) remains a concrete risk in Android applications that build SQL statements from local `SQLiteDatabase`, Room, or `ContentProvider` inputs, and reliably evaluating automated detectors for it is complicated by weak ground truth, row-level leakage, and evidence double-counting in prior datasets. **Method:** we construct a provenance-verified, source-to-sink-traced CWE-89 corpus from real, independently-licensed Android repositories under strict project-level train/validation/test separation; combine a text-only machine-learned classifier with an independently computed static source-to-sink analyzer through a leakage-safe late-fusion procedure (out-of-fold training-feature generation, validation-only calibration, a predeclared safety-constrained abstention policy, and a single frozen test evaluation); and replicate the full evaluation on an expanded corpus (v3, six independent vulnerable projects, two per split) after an initial round (v2, three vulnerable projects, one per split) produced an inconclusive result. **Results:** the v3 evaluation does not establish reliable machine-learning generalization or a beneficial late-fusion effect: both a linear SVM and XGBoost miss both held-out test vulnerable examples; a specific favorable result observed in v2 (XGBoost detecting its one test-split positive) did not repeat in v3 and is accordingly not treated as evidence of generalization; the fusion model's coefficient on the learned-evidence feature remains sign-inverted; probability calibration collapses the fused score toward a near-constant value; and a predeclared, safety-constrained abstention policy forces zero decision coverage on both validation and test. **Conclusion:** this study does not establish reliable ML generalization or a beneficial late-fusion effect for CWE-89 detection on unseen Android projects. Instead, the replicated evaluation demonstrates that project-level provenance, independent static evidence, and leakage-safe experimental design are essential before stronger claims can be made, and it identifies the specific corpus-scale gap (independent vulnerable Android projects) that must be closed first.

**Keywords:** SQL injection, Android security, static analysis, data-flow analysis, machine learning, late fusion, selective classification, abstention, empirical software engineering, project-level evaluation

---

## I. Introduction

Android applications routinely construct SQL statements against local `SQLiteDatabase`/Room storage and expose data through `ContentProvider` interfaces reachable by other installed applications. SQL Injection (CWE-89) arises when a value influenced by an external, untrusted source reaches SQL-statement construction without adequate parameterization or sanitization. Two broad automated-detection strategies exist. Static/data-flow analysis can trace a concrete source-to-sink path and check parameterization deterministically, but its recall is bounded by how completely its source and sink pattern coverage matches the code style under analysis. Machine-learned text/token classifiers can, in principle, generalize across code styles not explicitly enumerated by a static tool, but only if trained on enough independently-provenanced, project-diverse labeled examples — a condition Android CWE-89 research has not generally satisfied, because genuinely vulnerable, non-synthetic CWE-89 examples are scarce in real, actively-maintained Android code, and confirming one requires a real source-to-sink trace, not a keyword match.

Combining the two strategies is an intuitive next step, but a naive combination and evaluation can be invalidated by several well-documented failure modes: row-level or template-level data leakage between training and evaluation splits; weak or boilerplate ground-truth labels; evidence double-counting (feeding the static analyzer's own verdict into the learned model's feature space, then combining the two as if they were independent); and evaluating on a vulnerable-class sample too small to distinguish a genuine learned effect from chance. This study evaluates the combination under strict project-level separation, an independently computed static evidence channel that never enters the learned model's own feature space, and a fully specified, frozen evaluation protocol — and reports the resulting evidence directly, including where it is negative.

### Central Research Question

*Can independently computed lexical/model evidence and SQL source-to-sink data-flow evidence be combined through leakage-safe late fusion and selective prediction to provide risk-aware CWE-89 detection on previously unseen Android projects?*

This paper does not assume the answer is yes; Section VI–VIII report the answer the collected evidence actually supports.

### Research Questions

- **RQ1.** How do text-only machine-learning models and deterministic source-to-sink analysis behave on previously unseen Android projects?
- **RQ2.** Does leakage-safe late fusion provide evidence of improved detection or reduced risk compared with the individual baselines?
- **RQ3.** Can selective prediction provide useful risk/coverage behavior for developer-facing CWE-89 detection?
- **RQ4.** What dataset and evaluation limitations prevent stronger claims of generalization?

### Contributions

This paper's contributions are stated conservatively, matched to what the evidence in Section VI actually supports:

1. A provenance-aware, source-level CWE-89 corpus construction process grounded in real Android projects and individually-traced source-to-sink evidence, including two independently corroborated (CVE-documented) vulnerable findings.
2. A project-level, leakage-controlled evaluation protocol that keeps learned lexical evidence and independently derived static/data-flow evidence separate through feature generation, calibration, and abstention-threshold selection.
3. An empirical investigation of late fusion between machine-learned predictions and independently derived CWE-89 evidence, including a documented, mechanistic explanation for why the fusion model's learned coefficient is sign-inverted at this corpus's scale.
4. An investigation of selective prediction/abstention under an explicitly predeclared, safety-constrained decision objective (maximize coverage subject to a zero false-negative-rate ceiling on validation).
5. A **replicated** negative/inconclusive result: an initial corpus round (v2) produced one favorable individual-model result that did not repeat after the corpus was independently expanded (v3), directly demonstrating that apparent performance from a very small vulnerable-project sample does not necessarily generalize to unseen Android projects.

This paper does not claim to be the first Android Studio-integrated detector, the first real-time detector, or the first explainable-AI security tool — Section II identifies prior work that already makes these claims — nor does it claim state-of-the-art, best, production-ready, highly accurate, or general Android vulnerability detection status.

## II. Related Work

**Android source-code vulnerability detection surveys.** Senanayake et al. [1] systematically reviewed 118 Android source-code vulnerability detection studies (2016–2022) and released the LVDAndro labeled dataset, reused in [2] and [3].

**Android Studio-integrated, real-time, explainable detectors.** FedREVAN [2] and its extension Defendroid [3] (Senanayake et al.), trained on LVDAndro, report 96% accuracy/0.96 F1 for binary CWE detection and integrate the resulting model into Android Studio with per-token explainable-AI (XAI) output. Among the studies identified by our documented search, these are the closest prior work to this paper's developer-facing delivery mechanism (Section IX); we explicitly acknowledge that prior work already demonstrates Android Studio integration, real-time detection, and explainable security tooling, and we do not repeat those novelty claims. The research gap this paper addresses is not "no previous Android tool does this" — it is methodological: whether independently computed learned and static evidence can be combined and evaluated under project-level separation with a predeclared, safety-constrained abstention policy, and what the resulting risk/coverage trade-off actually looks like.

**Static Application Security Testing (SAST) for Android.** A recent comprehensive evaluation of Android SAST tools [4] unified vulnerability-type coverage and built a CVE-derived benchmark, finding substantial variation in tool completeness — directly motivating this paper's requirement (Section IV-C, V) that the static analyzer's source/sink coverage and known blind spots be documented rather than assumed.

**LLM-based vulnerability detection.** Among the studies identified by our documented search, LLM-based Android application vulnerability detection [5] is an emerging, largely separate approach from the deterministic/learned hybrid studied here; this paper does not evaluate an LLM baseline because the corpus scale established in Section IV does not justify one.

**Selective classification.** SelectiveNet [6] formalizes joint learning of a classifier and a reject option, optimizing the risk-coverage trade-off end-to-end. This paper adopts the risk-coverage/AURC evaluation vocabulary from this literature (Section VII-E) but uses a simpler, post hoc, threshold-based abstention rule rather than an end-to-end-trained reject head, since the corpus scale here does not support training an additional reject-head model.

## III. Research Methodology

This study follows an empirical, artefact-centric software-security research design: an evaluation artefact (the corpus, the detection pipeline, the evaluation protocol) is constructed, then evaluated against explicit research questions, with the artefact and protocol iterated across rounds as new evidence is obtained. This is explicitly a **feasibility-focused empirical investigation**, not a benchmark-scale study — the corpus (Section IV) is orders of magnitude smaller than would be required for a benchmark claim, and the paper's methodological contribution is the *evaluation protocol* (leakage control, independent evidence separation, predeclared decision objectives), not a claim that the current corpus scale is sufficient.

Three methodological controls structure every experimental round reported in Section VI:

1. **Project-level split.** Every sample from a given repository belongs to exactly one of train/validation/test, verified programmatically before any model training (Section IV-D). This is the unit of independence the study reasons about — not individual code samples, which can share near-duplicate structure within a project.
2. **Label adjudication.** A sample is accepted as `VULNERABLE` only with a complete, individually documented source→propagation→sink chain, never from sink-API presence alone; accepted as `SAFE` only with an individually written, non-boilerplate reason; anything not meeting either bar is excluded rather than forced into a label (Section IV-B, IV-E).
3. **Independent evidence generation.** The learned (text) and static (data-flow) evidence channels are computed independently of each other; the static channel's output is never inserted into the learned model's own feature space (Section V, Fig. 3), and calibration/abstention-threshold selection use validation data only, never test (Section VI).

## IV. CWE-89 Corpus Construction

### A. Provenance

Samples were collected across four collection rounds by cloning and manually source-to-sink tracing real, permissively- or copyleft-licensed public Android repositories. The first three rounds used broad candidate discovery (repository existence checks via `git ls-remote`, followed by grepping for `execSQL|rawQuery|.query(|.insert(|.update(|.delete(` and full-method manual tracing) across 23 repositories. The fourth round (this paper's primary corpus) shifted to a more targeted strategy — searching for publicly disclosed, CVE-documented Android `ContentProvider` SQL-injection advisories and known Android security-testing benchmark applications — which yielded three new, independently corroborated vulnerable findings from three additional repositories.

### B. Labeling Standard

A `VULNERABLE` label requires a traced chain: untrusted/external input → propagation → SQL-statement construction → SQL execution sink, without adequate parameterization or sanitization, confirmed by reading the actual call site and any intervening guard logic (not inferred from `rawQuery()`/`execSQL()`/string-concatenation presence alone). A `SAFE` label requires an individually written reason (parameterization, a compile-time constant, a framework-level constraint, or an explicit runtime allowlist/validator). Two of this round's three new vulnerable findings carry independent, third-party corroboration beyond this project's own tracing: CVE-2023-24804 (GitHub Security Lab advisory GHSL-2022-059, owncloud/android) and CVE-2021-43863 (GHSL-2021-1007, nextcloud/android, traced at its pre-3.18.1 commit) — both were re-traced directly against the actual source at the disclosed commits, not merely cited from the advisory text. The third (InsecureBankv2) is a deliberately vulnerable security-training benchmark application (OWASP MASTG-APP-0010), documented as such rather than presented as an accidental production defect. One additional benchmark candidate (`b3nac/InjuredAndroid`) was investigated and correctly excluded: its one SQL-adjacent file implements an insecure-local-storage/root-access challenge, not a CWE-89 source-to-sink flow.

### C. Duplicate and Fork Control

Exact and near-duplicate detection used code-text normalization and manual project-lineage inspection; a full AST-level or token-clone-hash pass was **not performed** and is disclosed as an open limitation. One genuine shared-lineage case was identified and documented rather than silently accepted or excluded: owncloud/android and nextcloud/android share real historical ancestry (the latter is a fork of the former). Direct line-by-line comparison confirmed the sampled code differs substantively at the two commits used (different guard logic; an intervening full Java-to-Kotlin rewrite), so both are retained as independent projects — but they are deliberately placed in different splits (train / test respectively) specifically so that this independence judgment being wrong would not contaminate a single split.

### D. Project-Level Split

Verified programmatically (set intersection over `project_id`, cross-checked against every sample's own split field) before any model training: `train ∩ validation = ∅`, `train ∩ test = ∅`, `validation ∩ test = ∅`; the union covers all 20 projects; zero sample-to-manifest mismatches.

**TABLE I. Corpus Provenance and Project-Level Split (v3, exact counts from `cwe89_corpus_v3/`)**

| Category | Count |
|---|---|
| Independent projects | 20 |
| Independent vulnerable projects | 6 |
| Independent safe-only projects | 14 |
| Accepted samples (total) | 37 |
| Vulnerable samples | 6 |
| Safe samples | 31 |
| Ambiguous samples retained in the supervised set | 0 |
| Train projects / samples / vulnerable | 8 / 16 / 2 |
| Validation projects / samples / vulnerable | 6 / 12 / 2 |
| Test projects / samples / vulnerable | 6 / 9 / 2 |
| Repositories cloned and code-read (cumulative, all 4 rounds) | 26 |

Every split contains exactly 2 vulnerable-class projects (train: andstatus-andstatus, owncloud-android; validation: tasks-tasks, insecurebankv2; test: openintents-safe, nextcloud-android) — up from 1 per split in the preceding round, but short of the 5-per-split operational target that round explicitly aimed for; this limitation is carried through every result in Section VI–VII rather than minimized. **Fig. 2** depicts the resulting split.

### E. Evidence Categories

**TABLE II. Label/Evidence Categories (safe-class, 31 samples)**

| Category | Samples | Description |
|---|---|---|
| Compile-time constants / fully literal | 16 | No runtime variable reaches the sink at all |
| Framework- or type-system-constrained input | 6 | e.g. a primitive numeric type, an enum-closed switch, a URI-router digit constraint |
| Parameterized query / bind arguments | 6 | Correct `?`-placeholder usage with a separate bind-args array |
| Explicit runtime allowlist / validation logic | 3 | e.g. a tokenizer-based `where`-clause validator |

The vulnerable-class mechanisms (6 samples) are individually distinct: a flawed escaping helper, a query-builder bind-mechanism silently discarded, a structured-API misuse via untrusted file import, a weak content-blind guard on a `delete()` call, a fully unvalidated parameter pass-through, and a permission gate that excludes the primary data table — no two vulnerable samples share the same underlying flaw mechanism.

## V. Detection Architecture and Experimental Protocol

Two evidence channels are computed independently (**Fig. 1**, **Fig. 3**) and combined only at decision time:

**Channel A — Machine Learning.** `code_context` (raw source text only — never the manually assigned `source`, `sink`, `dataflow_path`, `parameterized`, `sanitized`, `evidence_type`, or `label_confidence` columns) → TF-IDF (fit on training-project documents only) → a classifier (Linear SVM or XGBoost) → a probability.

**Channel B — Static/Data-Flow.** Android source → recognized-sink detection (an experiment-local, documented extension of this project's own `dataflow.py`, which is imported read-only and not modified, widening its sink-name list to also match `.query(`/`.update(`/`.delete(`/`.insert(`, matching this corpus's own construction-time grep pattern) → argument extraction via balanced-parenthesis parsing (not a single-line regex) → a parameterization determination → an independent evidence score, plus an explicit "analysis completeness" indicator (whether any recognized sink was found at all).

**Fusion.** A regularized logistic regression is fit on the training set using three features — the out-of-fold (never in-sample) ML probability, the static evidence score, and the completeness indicator — producing a fused probability. Calibration (Platt scaling) is fit on validation only. An abstention threshold band is selected on validation only, under a predeclared safety objective: maximize coverage subject to false-negative rate ≤ 0. The resulting three-way output is **VULNERABLE / SAFE / ABSTAIN**.

**Freeze and evaluate once.** All thresholds, the fusion model's weights, and the calibrator are frozen after validation-only selection; the test set is scored exactly once.

**No old artefact is reused anywhere in this pipeline**: every model, vectorizer, and threshold in Section VI was freshly fit inside this study's v3 experiment; no prior dataset (the original 1,687-row/1,128-row set), prior model checkpoint, prior TF-IDF vectorizer, prior CodeBERT or LSTM result, or prior Decision Engine weight was loaded.

**TABLE III. Experimental Configurations**

| ID | Configuration | Coverage rule |
|---|---|---|
| A | Rule-only (static analyzer) | Decides unless no sink recognized |
| B | ML-only, Linear SVM | Full coverage |
| C | ML-only, XGBoost | Full coverage |
| D | Late fusion (logistic regression, OOF-trained) | Full coverage |
| E | Late fusion + abstention | Predeclared FNR≤0 band, validation-selected |
| F | ML-only selective (SVM) | Predeclared FNR≤0 band, validation-selected |
| G | Rule-only selective | Predeclared FNR≤0 band, validation-selected |

## VI. Experimental Results

### 7.1 Dataset

37 samples, 20 independent projects, 6 independent vulnerable projects (2 per split) — Section IV, Table I. Test split: 9 samples, 2 vulnerable (`os-001` from openintents-safe, `nc-002` from nextcloud-android).

### 7.2 ML-Only Results

TF-IDF: 256-term vocabulary, fit on 16 training documents. **Both SVM and XGBoost miss both test-split positives** (TP=0, TN=7, FP=0, FN=2 for each; 0% recall). Both achieve trivially perfect training accuracy (expected, given the feature-to-sample ratio). Leave-one-out out-of-fold generation over the 16 training samples produced **zero structurally degenerate folds** this round (versus 1 of 15 in the preceding v2 round) — because training now contains 2 positive examples, holding out one still leaves a positive example for that fold to train on.

### 7.3 Static/Data-Flow Results

All 6 vulnerable samples, including both newly added CVE-derived findings, are correctly flagged `VULNERABLE` by the analyzer (100% recall, replicating the pattern from the preceding round). Test-split result: 88.9% coverage (8/9 decided, 1 abstained with no recognized sink), TP=2, TN=0, FP=6, FN=0 — 25% precision. All 6 false positives share the same, previously identified root cause: the parameterization check requires a sink's entire SQL-text argument to be a single quoted literal, and cannot distinguish safe multi-fragment literal/constant concatenation from unsafe concatenation of a real data value (Section VII-D).

### 7.4 Late-Fusion Results

The fusion logistic regression's coefficient on the out-of-fold ML feature is **−0.2512** — negative, i.e., sign-inverted relative to the intuitive expectation that a higher ML score should increase fused vulnerability probability. This is smaller in magnitude than the preceding round's −1.1468 (a document-cited, single-positive structural artifact), and this round has zero degenerate OOF folds, yet **the sign remains inverted**, indicating the underlying OOF signal still does not correlate positively with the true label across training even once that specific structural artifact is removed. Raw fusion scores on test are tightly clustered (0.482–0.504); after Platt calibration, all 9 test scores collapse to **0.166611–0.166628** (span < 0.00002) — a near-constant output close to the corpus's overall base rate (6/37 ≈ 16.2%). Late fusion without abstention (config D) makes **identical** binary predictions to SVM-only (config B) on every test sample.

### 7.5 Selective Prediction

Under the predeclared objective (maximize coverage s.t. FNR ≤ 0 on validation), late fusion + abstention (config E) achieves **0% coverage** on validation; the frozen band, applied once to test, likewise yields 0% coverage (all 9 samples abstained). ML-only selective (config F) also collapses to 0% coverage this round. Rule-only selective (config G) collapses to 100% coverage (the static score's coarse {0.1, 0.5, 0.9} discretization admits no useful intermediate band).

### 7.6 Ablation

**TABLE IV. Main Results — Test Split (n=9, 2 vulnerable), raw counts, LOW-POWER/DESCRIPTIVE throughout**

| Config | Coverage | TP | TN | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| A. Rule-only | 88.9% (8/9) | 2 | 0 | 6 | 0 | 0.25 | 1.00 |
| B. SVM-only | 100% | 0 | 7 | 0 | 2 | N/A | 0.00 |
| C. XGBoost-only | 100% | 0 | 7 | 0 | 2 | N/A | 0.00 |
| D. Late fusion (no abstain) | 100% | 0 | 7 | 0 | 2 | N/A | 0.00 |

**TABLE V. Selective Prediction / Risk-Coverage Results — Test Split**

| Config | Coverage | Decided TP/TN/FP/FN | Notes |
|---|---|---|---|
| E. Late fusion + abstention | 0% | 0/0/0/0 | Predeclared FNR≤0 band forces total abstention |
| F. ML-only selective (SVM) | 0% | 0/0/0/0 | Same objective, same outcome |
| G. Rule-only selective | 100% | 2/0/7/0 | Static-score discretization collapses to full coverage |

Risk-coverage curve (fusion score, test split): **Fig. 4**. AURC = 0.2767, explicitly labeled LOW\_POWER/DESCRIPTIVE (n=9). Project-level bootstrap (2,000 resamples over 6 test projects): SVM-only accuracy 0.785 (95% CI [0.60, 1.00]); late-fusion accuracy 0.785 (95% CI [0.60, 1.00]) — wide, near-identical intervals. **McNemar's exact test, SVM-only vs. late fusion: 0 discordant pairs** — no p-value is computable; the two methods produce literally identical predictions on all 9 test samples.

### 7.7 Error Analysis

Every test-split error was individually inspected (`error_analysis.csv`, 10 rows). Both SVM and XGBoost false negatives (2 each, the same 2 samples) are categorized **training-data coverage gap**: neither test-split positive shares close vocabulary with either training-split positive — the four vulnerable mechanisms involved (a flawed escaping helper, a weak `ContentProvider` guard, a file-import misuse, a permission-gate exclusion) are each lexically and structurally distinct. All 6 rule-only false positives are categorized **sanitization/parameterization misunderstanding** (Section VII-D). No fabricated or illustrative-only example is used; every case cited is an actual test-split misclassification.

### 7.8 Replication Comparison: v2 vs. v3

This comparison is the paper's central empirical finding. In the preceding round (v2; 3 vulnerable projects, 1 per split), **XGBoost correctly detected its one test-split positive** (TP=1, TN=7, FP=0, FN=0 — 100% recall on n=1), while SVM missed it (TP=0, FN=1). That XGBoost result was **not** credited as evidence of generalization at the time, because the same model, under an identical procedure, had already missed the mechanistically distinct validation-split positive one step earlier. In this round (v3; corpus independently expanded to 6 vulnerable projects, 2 per split), **XGBoost misses both test-split positives** (TP=0, FN=2) — the favorable v2 result **did not repeat**. This is reported precisely: XGBoost did not "fail completely" in v2 (it correctly classified its one available test positive), but that single correct classification is now shown, by direct replication under expanded data, to have been consistent with chance rather than a learned, generalizable signal. This is the strongest evidence in this study for treating small-sample favorable results in this problem domain with structural skepticism rather than as a positive finding.

**TABLE VI. Error Analysis and v2→v3 Replication Summary**

| Aspect | v2 (3 vulnerable projects, 1/split) | v3 (6 vulnerable projects, 2/split) |
|---|---|---|
| Test-split vulnerable samples | 1 | 2 |
| SVM test recall | 0/1 (0%) | 0/2 (0%) |
| XGBoost test recall | **1/1 (100%)** | **0/2 (0%) — did not replicate** |
| Degenerate OOF folds (train) | 1 of 15 | 0 of 16 |
| Fusion ML-feature coefficient | −1.1468 | −0.2512 (smaller, still inverted) |
| Fusion vs. ML-only, McNemar discordant pairs | 0 | 0 |
| Abstention coverage under predeclared FNR≤0 | 0% | 0% |
| Dominant error category (rule-only FP) | sanitization/parameterization misunderstanding | sanitization/parameterization misunderstanding (same root cause) |
| Dominant error category (ML FN) | training-data coverage gap | training-data coverage gap (replicated) |

The single row that changed in kind rather than only in degree — XGBoost's test recall — is the paper's central evidentiary point (Section 7.8): a favorable individual-round result did not survive independent corpus expansion, and every other row shows the same qualitative outcome replicating even as the specific structural artifact behind it (the single degenerate OOF fold) was resolved.

## VII. Discussion and Threats to Validity

### A. Results Interpretation

Following the evidence directly: **ML generalization is not established** (Section VII-A/7.2, 7.8). **Late-fusion improvement is not established** — fusion reproduces ML-only's predictions exactly (0 McNemar-discordant pairs, replicated across both rounds) and its learned ML-feature coefficient remains sign-inverted. **Selective-prediction usefulness under a safety-first objective is not established**, because the predeclared zero-FNR constraint forces zero coverage on both validation and test in both rounds — the mechanism itself functions correctly (it correctly refuses to guess on a corpus that does not support a confident guess), but this study does not demonstrate that it provides *useful* risk/coverage behavior at the current corpus scale. What this study does demonstrate is the practical importance of project-level evaluation and independent-evidence separation: had this study evaluated at the row level, or fed the static analyzer's verdict into the ML feature space, the corpus-scale limitations identified here could easily have been obscured rather than surfaced.

### B. Implemented vs. Experimentally Validated

This distinction is maintained explicitly throughout this paper and is restated here directly: the DualVulnDroid project contains a working, developer-facing Android IDE plugin (Section IX) — its existence does **not** demonstrate that the ML/data-flow fusion method generalizes; that is an empirical question this paper's Section VI answers negatively at the current corpus scale. Likewise, the broader DualVulnDroid project contains a Decision Engine component; its existence in the codebase does **not** constitute evidence that it improves detection — no claim about the Decision Engine's effectiveness is made anywhere in this paper, and it was not used in the v3 pipeline (which uses a freshly fit logistic-regression fusion model instead, Section V).

### C. Internal Validity

The frozen train→validate→test protocol was followed without exception in both the v2 and v3 rounds; test was scored exactly once per round. The one point requiring reviewer judgment — the experiment-local static-analyzer sink-list extension (Section V) — was authored by the same person who labeled the corpus, a disclosed residual risk, though the extension itself is structural (matching the corpus's own construction-time sink-discovery pattern) rather than derived from any individual sample's label.

### D. Construct Validity

"Analysis completeness" (Section V) is operationalized narrowly as "did the analyzer recognize any sink at all," not a richer notion of interprocedural completeness. The static analyzer's demonstrated imprecision (Section 7.3) — a parameterization check requiring a single literal argument, unable to recognize safe multi-fragment concatenation — is a specific, documented coverage limitation, not a general claim about static analysis.

### E. External Validity

20 projects, however deliberately diversified in mechanism and API usage, is not a representative sample of the Android application ecosystem; 6 vulnerable projects (2 per split) cannot support a claim about how common or rare any particular CWE-89 mechanism is in the wild, or that this pipeline would perform comparably on a different set of unseen projects.

### F. Reproducibility

Every result in Section VI traces to a specific, hashed artefact file (`cwe89_experiment_v3/`, SHA-256-recorded corpus files, a fixed random seed of 42, and fully specified vectorizer/model/threshold parameters) — see the accompanying evidence audit for the exact mapping.

## VIII. Conclusion

This study asked whether independently computed lexical/model evidence and SQL source-to-sink data-flow evidence could be combined, through leakage-safe late fusion and a predeclared, safety-constrained selective-prediction policy, to provide risk-aware CWE-89 detection on previously unseen Android projects. Following the full protocol honestly across two independently-expanded corpus rounds, **the study does not yet establish reliable ML generalization or a beneficial late-fusion effect for CWE-89 detection on unseen Android projects**. Instead, the replicated evaluation demonstrates that project-level provenance, independent static evidence, and leakage-safe experimental design are essential before stronger claims can be made — most concretely illustrated by the v2→v3 replication comparison (Section 7.8), where a single favorable individual-model result did not survive corpus expansion. This is not a failed study; it is an empirical feasibility investigation whose negative result is itself the finding, obtained through a protocol specifically designed to surface rather than obscure it. The corpus, pipeline, and evaluation protocol are retained as reusable infrastructure; the concrete next step, identified directly by this study's own evidence rather than assumed in advance, is continued collection of independent vulnerable Android projects — using the higher-yield, CVE-advisory-and-benchmark-informed strategy that produced this round's three new findings — toward the study's own previously stated operational target of five per split, before any accuracy or fusion-benefit claim is attempted.

## IX. Developer Plugin (Delivery Artefact)

The DualVulnDroid project includes a working IntelliJ Platform / Android Studio plugin that delivers this paper's detection pipeline to a developer inside the source editor: a live annotator, an evidence/finding display surfacing the static analyzer's source/sink/path trace alongside the classifier's own feature attribution, and narrow, single-purpose quick fixes (e.g., converting an unparameterized concatenation into a bound `?` placeholder) — never a general automated-repair claim. **The plugin is presented here as the delivery/artefact layer for this paper's findings, not as evidence that the underlying detection method generalizes** (Section VII-B). Backend inference (compute-path-only, no IDE, no network layer) latency was measured directly in the preceding experimental round over 30 repeated calls per representative snippet: short (53 chars) 65 ms mean (p99 84 ms), medium (341 chars) 45 ms mean (p99 50 ms), long (4,719 chars) 110 ms mean (p99 119 ms), 0 request errors. This is reported explicitly as **backend inference latency**, not end-to-end IDE latency — full editor-to-annotation latency was not measured in any round of this study, and no such claim is made.

## X. Security Limitations

Verified directly against the current backend implementation: the backend runs over plain HTTP (no TLS/`ssl_keyfile` configuration present); CORS is configured permissively (`allow_origins=["*"]`); and the code-submission endpoints the plugin actually calls (`/predict`, `/developer/predict`, `/developer/scan`, `/developer/explain`, `/developer/rescan`) carry **no authentication or authorization check**, even though JWT-based authentication exists and protects unrelated user-account endpoints elsewhere in the same backend. **This paper does not claim secure deployment, HTTPS, encryption in transit, or production readiness.** Source code submitted to this backend for analysis should be treated as unencrypted and unauthenticated in transit and at the request boundary; this is a genuine confidentiality risk for any non-trivial or proprietary source code and is stated here as a plain, undisguised research-prototype limitation, not deferred to future work without acknowledgment.

## References

[1] J. Senanayake, H. Kalutarage, M. O. Al-Kadri, A. Petrovski, and L. Piras, "Android Source Code Vulnerability Detection: A Systematic Literature Review," *ACM Computing Surveys*, vol. 55, no. 9, 2023.

[2] J. Senanayake, H. Kalutarage, A. Petrovski, M. O. Al-Kadri, and L. Piras, "FedREVAN: Real-time DEtection of Vulnerable Android Source Code Through Federated Neural Network with XAI," in *Computer Security. ESORICS 2023 International Workshops (WASP)*, Springer, 2024.

[3] J. Senanayake, H. Kalutarage, A. Petrovski, M. O. Al-Kadri, and L. Piras, "Defendroid: Real-time Android Code Vulnerability Detection via Blockchain Federated Neural Network with XAI," *Journal of Information Security and Applications*, vol. 82, art. 103741, 2024.

[4] "A Comprehensive Study on Static Application Security Testing (SAST) Tools for Android," *IEEE Transactions on Software Engineering*, 2024 (arXiv:2410.20740).

[5] "Assessing the Effectiveness of LLMs in Android Application Vulnerability Detection," in *Proc. [Springer conference series]*, 2025 (DOI: 10.1007/978-3-031-85593-1_9).

[6] Y. Geifman and R. El-Yaniv, "SelectiveNet: A Deep Neural Network with an Integrated Reject Option," in *Proc. 36th Int. Conf. on Machine Learning (ICML)*, PMLR vol. 97, 2019.

[7] MITRE, "CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')," *Common Weakness Enumeration*.

[8] GitHub Security Lab, "GHSL-2022-059/060: SQL injection vulnerabilities in Owncloud Android app," advisory, published 2023-02-02 (CVE-2023-24804, CVE-2023-23948).

[9] GitHub Security Lab, "GHSL-2021-1007: SQL Injection and insufficient permission control in Nextcloud Android app," advisory, published 2022-01-25 (CVE-2021-43863, CVE-2021-41166).

[10] OWASP Foundation, "MASTG-APP-0010: InsecureBankv2," OWASP Mobile Application Security Testing Guide, application catalog entry.
