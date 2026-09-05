K M IGLAVITHANA
DUAL-VULNERABILITY DETECTION IN ANDROID CODE: REAL-TIME SQL INJECTION AND CERTIFICATE VALIDATION DETECTION
CHAPTER 03 – RESEARCH AND DEVELOPMENT METHODOLOGY

## 3.1 Chapter Overview

Chapter 1 stated the research question, aim, and five objectives this research pursues; Chapter 2 derived, from a critical literature review, the five specific gaps — integration, vulnerability coverage, explainability, remediation/decision support, and the developer-to-end-user connection — that justify them. This chapter explains how those objectives were actually pursued: the overall research approach and why it was selected; the research design and software development approach followed; how the dataset was prepared and how features were engineered; how the five candidate models were trained and compared under one protocol; how the Hybrid Decision Engine was designed and evaluated; how the plugin, backend, and Flutter application were developed and integrated; how automated testing and live device validation were carried out and kept distinct; the metrics used and why; and the ethical, reproducibility, and methodological limitations of the work. This chapter reports method, not results: the performance figures and validation outcomes it refers to are presented and discussed in full in Chapters 6, 7, and 8. Where a specific number appears below — a dataset size, a split configuration, a hyperparameter — it is stated because it is itself a methodological parameter of the study design, not because it is a finding.

## 3.2 Research Approach and Methodological Rationale

This research does not fit a single, named methodology label without qualification, and forcing one would misrepresent what was actually done. Two methodological traditions apply to different parts of the work, and the evidence for each is drawn directly from the shape of the project itself.

The first is Design Science Research (DSR), which characterises research whose central activity is to design, build, and rigorously evaluate a novel artefact addressing an identified problem, extracting generalisable design knowledge from that process (Hevner et al., 2004). DualVulnDroid fits this directly: Chapter 1 identified a gap-motivated problem; this research responded by designing and constructing an artefact — the integrated plugin, backend, ML pipeline, Decision Engine, and Flutter application; and Chapters 6–8 evaluate that artefact against the objectives it was built to satisfy. DSR is the appropriate framing here because the research contribution is inseparable from the artefact's own construction, not merely from data collected about a phenomenon existing independently of the research.

The second is a controlled, quantitative, experimental software-engineering methodology, of the kind Wohlin et al. (2012) describe as a staged, evidence-driven investigation of a defined problem rather than an unstructured, exploratory process. This applies specifically to the machine-learning model-comparison thread of the work (Objective 2): five candidate models are trained and evaluated under one identical, frozen protocol, so that a difference in a reported metric can be attributed to the model itself rather than to an uncontrolled difference in data or procedure — the defining property of a controlled comparison in this tradition.

These two traditions are complementary rather than competing here: the DSR paradigm frames the research as a whole (why an artefact was built, and how its construction responds to the Chapter 2 gap), while the controlled-experiment tradition governs specifically how the ML component of that artefact was selected (Sections 3.8–3.9). Neither label is adopted because it sounds academic; both are supported directly by what Sections 3.3 onward describe as having actually been done.

## 3.3 Research Design

Table 3.1 lists the actual stages this research followed, each stage's output being a defined artefact consumed by the stage that follows it — a staged design chosen because several later stages, most importantly the frozen dataset split (Section 3.6), depend on an earlier stage's output being fixed before the next begins.

**Table 3.1. Research design stages and their objective mapping.**

| Stage | Output | Chapter 1 Objective Addressed |
|---|---|---|
| Literature review and gap identification | The five gaps in Chapter 2 | Objective 1 |
| Dataset collection, cleaning, and grouped split | A frozen, leakage-checked 791/169/168 split | Objective 2 |
| Feature engineering | A shared, 7,610-dimensional hybrid feature pipeline | Objective 2 |
| Model training and comparison | Five models evaluated under one protocol | Objective 2 |
| Production model selection | XGBoost selected on combined evidence | Objective 2, 3 |
| Hybrid Decision Engine design and calibration | A three-state, coverage-measured decision process | Objective 3 |
| Plugin and backend development | Real-time annotation, project scan, Quick Fix | Objective 4 |
| Flutter application development | Search, assessment, compatibility, chatbot | Objective 4 |
| Automated testing | Backend, Kotlin, and Flutter test suites | Objective 5 |
| Live device/emulator validation | Phase 14B–33 validation record | Objective 5 |

At no point in this sequence was the frozen test split consulted to select a hyperparameter, checkpoint, or decision threshold — a constraint enforced identically across every model and Decision Engine configuration described in this chapter, and a direct application of the leakage-prevention principle discussed further in Section 3.6 (Kaufman et al., 2012).

## 3.4 Software Development Methodology

DualVulnDroid was developed using an iterative and incremental approach: working, individually testable increments of functionality were implemented, integrated, and regression-tested in sequence, rather than through a single, monolithic build-then-test cycle. This description is deliberately specific rather than aspirational — no claim is made that a formally named process such as Scrum was followed, since no fixed-length sprint cadence, backlog-grooming ceremony, or defined role structure of that kind was actually used; the characterisation reflects only what the project's own commit and phase history actually shows.

Implementation proceeded through a sequence of coherent increments, each followed by testing before the next began: the FastAPI backend and MySQL persistence layer; the classical and deep-learning model research described in Sections 3.8–3.9; the Hybrid Decision Engine (Section 3.10); the IntelliJ/Android Studio plugin's real-time annotation and project-scan capability; the Flutter application's screens, beginning with authentication and search and extending to compatibility checking and the security chatbot; and a further sequence of live-validation phases (Phase 14B through Phase 33) used specifically to verify the system's behaviour in a real execution environment rather than only through automated tests. Whenever a later increment was added, the automated test suites covering earlier increments (Section 3.12) were re-run to confirm that new work had not silently altered previously verified behaviour — standard regression-testing practice within an iterative development approach.

## 3.5 Systematic Literature and Evidence Collection

The literature review presented in Chapter 2 was conducted as a structured, critical review rather than a formally registered systematic literature review: no pre-registered protocol such as PRISMA was followed, and this is stated explicitly rather than left ambiguous, since claiming a systematic review without following its formal procedure would misrepresent the method actually used. Relevant literature was identified through targeted searches of IEEE Xplore, the ACM Digital Library, Springer Link, ScienceDirect, and Google Scholar (used for discovery only), using search terms including "Android vulnerability detection," "CWE-89 Android," "CWE-295 certificate validation Android," "machine learning source code vulnerability detection," "CodeBERT vulnerability detection," "IDE-integrated security analysis," and "explainable vulnerability detection." Authoritative standards sources — MITRE's CWE-89 and CWE-295 definitions, OWASP's MASVS and MASTG, and NIST SP 800-163 — were consulted directly from their publishing organisations rather than through a secondary citation, and are treated in Chapter 2 as a distinct evidence category from peer-reviewed literature.

Studies were included where they addressed Android application security, CWE-89 or CWE-295 detection specifically, static/data-flow or ML/DL vulnerability-detection techniques, explainability in security contexts, or IDE-integrated or end-user-facing security tooling, and were excluded where a study's existence or reported detail could not be independently verified against a publisher, DBLP, or arXiv record — the same exclusion principle applied consistently while assembling this thesis's own reference list. This evidence base is what Chapter 2's comparative synthesis (Table 2.1) and the five identified gaps (Section 2.14) are built from, and is not repeated in full here; this section records only how that evidence was gathered.

## 3.6 Dataset Preparation and Data Processing

The raw labelled dataset used for model training and evaluation contains 1,687 rows of Android-relevant code samples, each carrying one of four labels combining vulnerability category and vulnerable/safe state: `s0` (CWE-89, vulnerable), `s1` (CWE-89, safe), `v0` (CWE-295, vulnerable), and `v1` (CWE-295, safe). Before this dataset could be split for training, label noise had to be identified and addressed: rows whose code text, once normalised (lower-cased, comments stripped, string/character/numeric literals replaced with placeholder tokens), is identical or near-identical to another row's normalised text but carries a different label. Since the same underlying code template cannot genuinely be both vulnerable and safe, such a conflict indicates an annotation inconsistency in the source data rather than a genuine distinction for a model to learn. Every row belonging to a group in which more than one distinct label appeared — 559 rows of the 1,687 — was excluded and preserved in a separate, inspectable file rather than deleted, leaving a clean dataset of 1,128 rows used for every subsequent step (Table 3.2).

**Table 3.2. Dataset preparation summary.**

| Stage | Row Count | Notes |
|---|---|---|
| Raw dataset | 1,687 | Original labelled dataset, before cleaning |
| Conflicting-label rows excluded | 559 | Normalised-template groups with more than one distinct label; preserved, not deleted |
| Clean dataset | 1,128 | Used for the grouped train/validation/test split |
| Training split | 791 | Fixed random seed 42; group-aware, leakage-checked |
| Validation split | 169 | Used for hyperparameter and threshold selection only |
| Test split | 168 | Consulted once per model/configuration, for final reported metrics only |

The clean dataset was then split into training, validation, and test subsets (791/169/168) using a fixed random seed of 42. This split was constructed to be group-aware rather than a naive row-level split, using the same normalised-code template as a grouping key so that every row from a given template is assigned to exactly one subset, never divided across more than one — a direct application of the leakage-avoidance principle that near-duplicate examples must not appear on both sides of a train/test boundary if a reported evaluation metric is to reflect genuine generalisation rather than memorisation (Kaufman et al., 2012). A group-key overlap check and an exact-text overlap check were then performed on the resulting split, both confirming zero overlap. A limitation stated plainly here, because it affects how the split should be interpreted, is that the dataset contains no reliable application- or project-level identifier, so template-based grouping is the closest leakage-preventing grouping the available data supports, not a guarantee that no two rows in different subsets originate from the same source application — a constraint returned to in Section 3.16.

## 3.7 Feature Engineering

The production feature pipeline combines two families of features into one 7,610-dimensional vector (Table 3.3): text-based features from three vectorizers fitted on the normalised code text — a word-level TF-IDF vectorizer (up to 5,000 features, word n-grams of length one to three), a character-level TF-IDF vectorizer (up to 2,000 features, character n-grams of length two to five), and a count vectorizer (up to 1,000 features, word n-grams of length one to two) — and a fixed set of 23 deterministic security- and data-flow-derived features computed directly from the code text. The security features cover, for CWE-89, indicators such as a detected untrusted source, a detected SQL sink, a traced source-to-sink relationship, string concatenation used to build a query, and use of a parameterised-query or raw-query API; for CWE-295, indicators such as a `HostnameVerifier` construct, an unconditional `return true` pattern, a `TrustManager` with an empty trust-check body, and WebView SSL-error-handling behaviour; and, separately, five indicators derived from the project's own data-flow analysis (Section 3.10) rather than raw keyword presence — overall flow depth, presence of an interprocedural flow, and counts of flows classified unsafe, safe, and suspicious.

**Table 3.3. Feature dimensionality.**

| Feature Family | Dimensions | Basis |
|---|---|---|
| Word-level TF-IDF | Up to 5,000 | Word n-grams (1–3) on normalised code |
| Character-level TF-IDF | Up to 2,000 | Character n-grams (2–5) on normalised code |
| Count vectorizer | Up to 1,000 | Word n-grams (1–2) on normalised code |
| Deterministic security/data-flow features | 23 | CWE-89 and CWE-295 keyword/API/data-flow indicators |
| **Total production dimensionality** | **7,610** | 7,587 text-derived + 23 security-derived |

The rationale for combining these two families, rather than relying on either alone, follows directly from Chapter 2's finding (Section 2.5) that lexical features cannot by themselves encode a source-to-sink relationship unless a dedicated feature is engineered to capture one, while a purely rule-based feature set cannot generalise beyond the specific patterns it was designed to recognise. Critically for leakage prevention, all three vectorizers are fitted on the training split only and reused, unmodified, to transform the validation split, the test split, and any later inference input; none is re-fitted on held-out data at any point.

## 3.8 Machine Learning Experimental Methodology

Five models were evaluated under the identical frozen split and feature representation described above, so that a difference in reported performance (Chapter 6) can be attributed to the model rather than to a difference in data or features. Three are classical models — Linear SVM, Random Forest, and XGBoost — and two are supplementary deep-learning models — an LSTM and CodeBERT — evaluated separately from, and methodologically distinct from, the classical group, consistent with Chapter 1's Objective 2 and the caution Chapter 2 establishes against assuming deep-learning superiority in advance.

The classical models share the identical feature representation and were each hyperparameter-tuned without ever consulting the frozen test split (Table 3.4). The Linear SVM was implemented as a `LinearSVC` with balanced class weights, wrapped in a `CalibratedClassifierCV` (three-fold, train-only) to obtain genuine class-probability estimates for ROC-AUC computation, with its regularisation parameter selected by five-fold stratified cross-validation on the training split, scored by macro-F1. The Random Forest was implemented as a `RandomForestClassifier` with balanced class weights, with its estimator count, maximum depth, and minimum leaf size selected under the identical train-only cross-validation protocol. XGBoost was trained as a multi-class softprob objective with validation-based early stopping (evaluated by multi-class log-loss on the validation split) rather than the train-only cross-validation used for the other two models — reflecting XGBoost's own established early-stopping mechanism for selecting boosting rounds, not an inconsistency in protocol. Class imbalance was addressed consistently across all three by weighting each class inversely to its training-split frequency.

**Table 3.4. Classical model configurations.**

| Model | Implementation | Hyperparameter Search | Selection Criterion |
|---|---|---|---|
| Linear SVM | `LinearSVC` + `CalibratedClassifierCV` (3-fold, train-only) | Grid search, C ∈ {0.01, 0.1, 1.0, 10.0} | 5-fold stratified CV macro-F1 (train split only) |
| Random Forest | `RandomForestClassifier`, balanced weights | Grid search over estimators, depth, leaf size | 5-fold stratified CV macro-F1 (train split only) |
| XGBoost | `multi:softprob`, native early stopping | max_depth ∈ {4, 6, 8}, eta ∈ {0.05, 0.1}; up to 300 rounds | Validation-set macro-F1, early stopping |

Both deep-learning models were trained and selected under materially different, but internally consistent, procedures because their input representations differ from the classical pipeline: this difference is stated explicitly rather than implied, because claiming an identical architecture or preprocessing across all five models would misrepresent what was actually done. The LSTM was trained entirely from scratch using a custom, case-sensitive, code-aware tokenizer (deliberately distinct from the TF-IDF normalisation, so that identifiers such as `HostnameVerifier` remain distinguishable), with a vocabulary built from the training split only and out-of-vocabulary tokens mapped to a dedicated token, trained on CPU with class weighting and validation-based early stopping. CodeBERT was fine-tuned from the pretrained `microsoft/codebert-base` checkpoint using its own shipped tokenizer, unmodified, with fine-tuning restricted strictly to the training split for weight updates and the validation split for checkpoint selection, and a fixed learning rate, batch size, and warm-up schedule. In both cases, the same train/validation/test protocol used for the classical models was applied once the model was frozen, and the test split was consulted only once, after training was complete, to produce the reported evaluation figures.

## 3.9 Model Training and Evaluation

Every model was evaluated once, after hyperparameter/checkpoint selection was complete, against the identical frozen test split (Section 3.6), using the metrics defined in Section 3.14. The classical models' comparative CWE-89/CWE-295 F1-scores obtained under this protocol were: Linear SVM 0.7742/0.8525, Random Forest 0.7541/0.8205, and XGBoost 0.7931/0.8000 — reported here as the methodological output of the comparison protocol just described, with full interpretation and the remaining metrics (accuracy, macro-F1, ROC-AUC, FPR, FNR) presented in Chapter 6. Consistent with Chapter 2's caution against assuming deep-learning superiority, no claim of LSTM superiority is made anywhere in this thesis; the LSTM's comparative standing is reported as an empirical finding in Chapter 6, not asserted here.

CodeBERT's evaluation record requires a specific methodological note. Multiple internally recorded CodeBERT evaluation runs exist across separate project artefact directories, and they report materially different CWE-89/CWE-295 metrics from one another. Rather than select whichever figure is most convenient, this discrepancy is treated here as an open provenance issue: it is documented as a methodological limitation (Section 3.16), and its detailed reconciliation — including which run, if any, should be treated as authoritative, and why — is deferred to Chapter 6, where the full evaluation record and artefact provenance can be examined directly. No CodeBERT figure is presented as settled fact in this chapter.

## 3.10 Hybrid Decision Engine Methodology

The Hybrid Decision Engine combines the production XGBoost model's prediction with the deterministic static/data-flow evidence described in Section 3.7 into a single, signed evidence score, rather than treating the ML prediction as the sole basis for a decision. The score accumulates weighted contributions from: the ML prediction, signed by predicted class and scaled by its own predicted probability; a traced SQL source-to-sink finding; an unparameterised-concatenation finding; confirmation that all SQL sinks are parameterised; a certificate-validation finding classified vulnerable, suspicious, or safe; and a static keyword-based corroboration. These weights were fixed by design, not learned, reflecting the deliberate choice that a genuinely traced, structural data-flow finding should carry more influence than an average-confidence ML prediction alone — directly operationalising the "evidence, not just prediction" argument developed in Chapter 2, Section 2.10.

The resulting score is compared against two thresholds to produce one of three states: VULNERABLE (score ≥ the upper threshold), SAFE (score ≤ the lower threshold), or SUSPICIOUS_REVIEW (any score between them, deferred rather than forced to a verdict). The thresholds actually governing the deployed engine were calibrated from the validation split only, never the test split, and are loaded from a versioned calibration artefact at runtime. A separate, higher-coverage "Balanced" threshold configuration was also evaluated as a research candidate but was not deployed, because its robustness across alternative data splits was assessed as inconclusive — this trade-off, and the full coverage/FNR/FPR figures for both configurations, are reported and discussed in Chapter 7, not asserted here. Methodologically, the engine's evaluation reports coverage (the proportion of test-set cases resolved automatically) alongside the reliability of exactly those automatically-resolved cases, rather than either figure in isolation, because a high-coverage configuration whose automatic decisions are not separately shown to be reliable would misrepresent what the engine actually achieves.

## 3.11 DualVulnDroid Artefact Development

The artefact comprises five methodologically distinct but integrated components, developed and verified as described in Sections 3.4 and 3.12. The **backend/API** (FastAPI, MySQL via SQLAlchemy) hosts the shared feature pipeline, the production XGBoost classifier, the static/data-flow analysis, and the Hybrid Decision Engine behind a common set of HTTP endpoints consumed by both client surfaces. The **ML pipeline and Decision Engine** are as described in Sections 3.7–3.10; XGBoost is the sole model loaded by the production backend, with the SVM, Random Forest, LSTM, and CodeBERT results kept explicitly as research-comparison evidence (Chapter 6), never as production behaviour. **Explainability** is provided by a live SHAP `TreeExplainer` computed against the production model at prediction time, kept methodologically and terminologically distinct from the deterministic static/data-flow evidence (Section 3.7), consistent with Chapter 2's argument (Section 2.9) that the two are different kinds of evidence and should not be merged. **Remediation** is offered as a narrowly-scoped Quick Fix, generated only when a finding matches a small set of verified, safe rewrite patterns, and re-verified with a fresh scan immediately after being applied, rather than assumed correct.

The **developer-facing IntelliJ/Android Studio plugin** was verified, by direct inspection of its `plugin.xml`, to register exactly three active extension points — a tool window for project-wide scanning, and two external annotators (Kotlin/Java source; Android manifest/network-security-configuration XML) providing real-time, in-editor annotation as the developer edits. Several additional inspection-style classes exist in the plugin's source tree but are not registered in `plugin.xml` and are not reachable through any active extension point; they are legacy artefacts of earlier increments and are not described anywhere in this thesis as active functionality. The **Flutter end-user application** was verified, by inspection of its service and repository layers, to perform no client-side source-code analysis: every finding and explanation displayed originates from a backend API response, positioning it as a backend-mediated presentation and decision-support client, not an independent detection engine — consistent with Chapter 2's (Section 2.12) positioning. Its **Security Chat** calls the backend's chat endpoint and renders the returned reply verbatim, grounded in the same stored assessment data. Its **compatibility assessment** compares a device profile against Android-manifest-derived metadata (permissions, SDK versions, hardware features) extracted by the backend; this is a manifest/metadata-level analysis, not equivalent to source-code CWE-89/CWE-295 detection. Two further claims are stated only because directly verified: the "Upload APK" and "Installed Apps" entry points present an honest "not available in this version" state, and the backend communicates with both client surfaces over plain HTTP, without TLS.

## 3.12 Testing and Validation Methodology

Automated testing and live device validation are methodologically distinct activities in this research and are reported separately throughout this thesis, because they answer different questions: automated testing verifies that individual components behave as coded, under the tester's control, while live validation verifies that the integrated system behaves correctly in a real execution environment neither fully scripted nor fully predictable. Automated testing was carried out at three structurally separate levels, each using a different test runner and covering a different part of the system (Table 3.5): backend unit, integration, and API-level tests (pytest, exercising the FastAPI endpoints, the Decision Engine, the data-flow analysis, and database persistence); IntelliJ plugin tests (Gradle-driven JUnit, including platform-integration tests that drive the plugin's real, registered classes inside a genuine, headless IntelliJ Platform test fixture rather than testing isolated functions alone); and Flutter widget/unit tests (`flutter test`), covering the application's screens, repositories, and services.

**Table 3.5. Automated test suite totals (most recently verified).**

| Suite | Result | Note |
|---|---|---|
| Backend (pytest) | 323 passed, 2 skipped | Skips are environment-conditional, requiring a separate test-database connection not available in every environment |
| IntelliJ plugin (Kotlin, JUnit) | 55 total (46 unit tests + 9 platform-integration tests) | Platform-integration tests run inside a real, headless IntelliJ Platform fixture |
| Flutter (`flutter test`) | 59 passed, 0 failed | Grew from a baseline of 43 after a later UI-implementation phase added 16 tests for newly built screens; both figures are genuine counts from different points in development, not a discrepancy |

These totals are reported here as evidence that a layered, automated testing strategy was executed across three structurally different runners, each targeting a different part of the system; they are not combined into a single number, since doing so would misrepresent what each individually verifies.

## 3.13 Live Mobile Validation Methodology

Live validation was carried out separately from automated testing, on a real Android Virtual Device (AVD) running the actual built APK against the real backend and a real MySQL database, and is reported using four distinct outcome categories applied consistently throughout this research: **PASS** (the behaviour was directly observed, on-device, against real backend/database state, with a captured screenshot as evidence); **FAIL** (the behaviour was observed and did not match the expected outcome); **PARTIAL** (some but not all of a feature's expected behaviour was observed); and **NOT VALIDATED** (the item was not reached or not attempted in a given session, for a stated reason). An item that was never attempted is recorded as NOT VALIDATED, never silently upgraded to PASS or downgraded to FAIL, and no previously genuine PASS result was ever revisited or altered by a later session.

This methodology was applied across a sequence of validation phases (Phase 14B through Phase 34), summarised in Table 3.6, because the AVD environment exhibited repeated, session-to-session instability — a `com.android.systemui` ANR and, once, a `system_server` kernel-level hang — diagnosed (Phase 18) as most likely attributable to the host machine's graphics driver and virtualisation configuration, not the application: RAM/CPU were monitored throughout and repeatedly confirmed healthy during failures, and the identical AVD configuration produced a fully stable, multi-hour session on other attempts. This distinction — an environment/evaluation constraint, not an application defect — materially affects how Table 3.6 should be interpreted.

**Table 3.6. Live validation phase history.**

| Phase | Outcome | Note |
|---|---|---|
| 14B | PASS (core flows) | Login, registration, dashboard, known-app search, compatibility (COMPATIBLE case), chatbot mechanism |
| 21 | PASS (full chatbot experience) | First fully stable, 30+ minute session; all required chatbot questions, chat history, network-failure recovery |
| 22, 27, 30 | NOT VALIDATED (blocked) | Emulator entered a persistent System UI ANR before the app could be installed/launched, in each case with RAM independently confirmed healthy |
| 32 | PASS (partial session) | First genuine live session for the restyled UI; ended when `system_server` entered an uninterruptible kernel state after ~23 minutes |
| 33 | PASS (most comprehensive session) | Recovered AVD ran stably for ~1h45m; Vulnerability Details, Security Chat, Chat History, Settings, both Compatibility branches, and Search (unknown app) all directly observed |

Phase 33 is the most comprehensive successful live-validation session in this research and is treated as the current validation baseline. As of Phase 33, exactly one tracked item remains **NOT VALIDATED**: the Search screen's network-error state, which was not attempted because exercising it requires deliberately stopping the backend mid-session, and was not reached given the time available in that session. This item is preserved here as NOT VALIDATED, not converted to PASS or FAIL, consistent with the outcome-category discipline stated above.

## 3.14 Evaluation Metrics and Statistical Measures

Different parts of the system are evaluated with different, purpose-specific metrics (Table 3.7), and only metrics actually computed in this research are reported anywhere in this thesis. For the classification models, Accuracy, Precision, Recall, and F1 (both macro-averaged across the four classes and computed on the derived binary VULNERABLE/SAFE view) are used alongside ROC-AUC. Recall and F1 are given particular weight in the interpretation of these results, and False Negative Rate (FNR) is reported explicitly rather than folded into an aggregate accuracy figure, because a missed vulnerability — a genuinely vulnerable sample classified safe — is a materially more serious practical failure in this domain than a false alarm: a false alarm costs a developer or reviewer avoidable attention, while a missed vulnerability can allow a real weakness to reach a production application undetected. False Positive Rate (FPR) is reported alongside FNR for the same reason a single aggregate figure would be insufficient: a system tuned only to minimise one of the two can trivially do so at the other's expense, and both must be visible for the trade-off to be judged.

**Table 3.7. Evaluation metrics used in this research.**

| Metric | Applied To | Rationale |
|---|---|---|
| Accuracy, Precision, Recall, macro-F1 | All five compared models | Standard multi-class classification performance |
| Binary F1 (VULNERABLE/SAFE view) | All five compared models | Security-relevant view collapsing category into detect/no-detect |
| ROC-AUC | All five compared models | Threshold-independent discrimination ability |
| FNR | All five compared models; Decision Engine auto-decided cases | Missed-vulnerability risk, weighted more heavily than FPR in this domain |
| FPR | All five compared models; Decision Engine auto-decided cases | False-alarm rate; reported alongside FNR to show the trade-off, not in isolation |
| Coverage | Hybrid Decision Engine only | Proportion of cases resolved automatically without deferral |
| Automated test pass/fail/skip | Backend, plugin, Flutter suites | Component-level correctness under the tester's control |
| Live validation PASS/FAIL/PARTIAL/NOT VALIDATED | Mobile UI flows | Integrated, real-environment behaviour outside the tester's full control |

## 3.15 Research Ethics, Reproducibility and Data Management

No formal human-subject study was conducted in this research, and no institutional ethics-board approval was sought or is claimed, because the work does not involve recruiting, surveying, or observing human participants; this is stated plainly rather than implied. The labelled vulnerability dataset and code samples were used exclusively for defensive research — training and evaluating detection models — and not for any purpose intended to facilitate exploitation. Credentials are handled defensively throughout the implemented system: passwords are hashed with Argon2 before persistence, authentication uses signed JSON Web Tokens, and the backend's `.env` configuration file (holding the database connection string and JWT signing secret) is excluded from version control rather than committed. Where a real user account was needed to validate authentication behaviour during live testing, a dedicated test account was created for that purpose rather than any pre-existing personal account.

Reproducibility was treated as a first-class requirement rather than an afterthought. A fixed random seed (42) was used consistently for dataset splitting and model training; the frozen train/validation/test split was constructed once and reused, unchanged, across every evaluated model; fitted vectorizers, trained model artefacts, evaluation metrics, and split indices were stored in versioned, inspectable form; and the test split was consulted, per model or configuration, exactly once. Where a test could not genuinely run in a given environment — the backend's database-dependent integration tests, when a separate test-database connection was unavailable — this was recorded as an explicit skip, not a fabricated pass. The CodeBERT provenance discrepancy noted in Section 3.9 is recorded here as a data-management issue rather than resolved, because doing otherwise would understate a genuine gap in this research's own artefact provenance.

## 3.16 Methodological Limitations

Several limitations materially affect how the methodology above, and the results built on it, should be interpreted. The cleaned dataset (1,128 rows) is small by the standards of deep-learning and Transformer fine-tuning specifically, which constrains how much can be concluded from the LSTM and CodeBERT results about deep learning's general potential for this task, as distinct from its measured performance on this specific dataset. The dataset's grouped split, while leakage-checked at the code-template level, is not a true application-level split, because no reliable application or project identifier exists in the source data (Section 3.6); this constrains how confidently the reported metrics can be assumed to generalise to genuinely unseen applications rather than unseen code templates. The CodeBERT provenance discrepancy across separately recorded evaluation runs (Section 3.9) is an unresolved methodological limitation of this research's own artefact management, not a claim about CodeBERT as a technique, and is carried forward rather than silently corrected. The live-validation record (Section 3.13) reflects a genuine environment constraint — AVD/host graphics-driver instability, diagnosed rather than assumed — that repeatedly interrupted validation sessions and left one item (Search network-error) without live-device confirmation; this is reported as an evaluation-environment limitation, not as an application defect, because the evidence gathered (stable RAM/CPU during failures, and fully successful sessions on the identical configuration) does not support attributing it to DualVulnDroid's own code. Finally, both the backend-to-plugin and backend-to-Flutter deployment configurations verified in this research communicate over plain HTTP without TLS, and the Flutter application's "Upload APK" and "Installed Apps" features are implemented as honest "not available" placeholders rather than functioning end-user flows; both are recorded here as scope/configuration limitations of the evaluated system, consistent with Chapter 1's stated scope boundaries, not as omissions from this methodology chapter.

## 3.17 Chapter Summary

This chapter has described how this research was actually conducted: a Design Science Research approach to the artefact-development thread, combined with a controlled, experimental methodology for the machine-learning comparison thread (Section 3.2); a staged research design and an iterative, incremental (not formally Agile) development approach (Sections 3.3–3.4); a structured critical literature review (Section 3.5); leakage-checked dataset preparation and a fixed, group-aware 791/169/168 split (Section 3.6); a shared, 7,610-dimensional feature pipeline (Section 3.7); the training and comparison of five models under one protocol, with the CodeBERT provenance conflict explicitly preserved rather than resolved (Sections 3.8–3.9); a Hybrid Decision Engine combining ML prediction with deterministic evidence into a measured, coverage-reported decision (Section 3.10); the actual, verified development of the plugin, backend, and Flutter application (Section 3.11); a layered automated testing strategy kept distinct from live device validation across the Phase 14B–33 record, with one item (Search network-error) honestly preserved as NOT VALIDATED (Sections 3.12–3.13); the specific metrics used and why (Section 3.14); and the ethical, reproducibility, and methodological limitations of the work (Sections 3.15–3.16). Table 3.8 consolidates how each of Chapter 1's five objectives was pursued.

**Table 3.8. Research objectives, methods, and evaluation traceability.**

| Objective (Chapter 1) | Method | Data/Evidence | Evaluation | Expected Output |
|---|---|---|---|---|
| 1. Investigate and compare existing approaches | Structured critical literature review (Section 3.5) | Peer-reviewed literature; MITRE/OWASP/NIST standards | Comparative synthesis (Chapter 2, Table 2.1) | A justified, evidence-based research gap |
| 2. Compare SVM/Random Forest/XGBoost against LSTM/CodeBERT under one protocol | Controlled ML experimentation (Sections 3.6–3.9) | Cleaned, leakage-checked dataset; shared 7,610-dim feature pipeline | Accuracy/F1/ROC-AUC/FNR/FPR on frozen test split (Chapter 6) | An empirically justified production-model candidate |
| 3. Design a Hybrid Decision Engine with SHAP explanation | Rule+ML evidence fusion, validation-calibrated thresholds (Section 3.10) | Static/data-flow evidence; XGBoost predictions | Coverage and auto-decided FNR/FPR (Chapter 7) | A three-state decision process with a measured coverage/reliability trade-off |
| 4. Build the IDE plugin and Flutter application | Iterative, incremental development (Sections 3.4, 3.11) | Verified source code (plugin.xml, backend API, Flutter screens) | Component-level correctness review | An integrated, testable developer- and end-user-facing artefact |
| 5. Evaluate through automated testing and live validation, honestly | Layered automated testing plus phased live validation (Sections 3.12–3.13) | pytest/Kotlin/Flutter test runs; Phase 14B–33 validation reports | PASS/FAIL/PARTIAL/NOT VALIDATED classification | An honestly reported validation record, including any unresolved item |

Chapter 4 now applies this methodology's requirements-analysis thread to derive the system's functional and non-functional requirements from the problem stated in Chapter 1.

## References (APA 7)

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 785–794). ACM. https://doi.org/10.1145/2939672.2939785

Cortes, C., & Vapnik, V. (1995). Support-vector networks. *Machine Learning*, 20(3), 273–297. https://doi.org/10.1007/BF00994018

Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5–32. https://doi.org/10.1023/A:1010933404324

Feng, Z., Guo, D., Tang, D., Duan, N., Feng, X., Gong, M., Shou, L., Qin, B., Liu, T., Jiang, D., & Zhou, M. (2020). CodeBERT: A pre-trained model for programming and natural languages. In *Findings of the Association for Computational Linguistics: EMNLP 2020* (pp. 1536–1547). Association for Computational Linguistics.

Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly*, 28(1), 75–105. https://aisel.aisnet.org/misq/vol28/iss1/6/

Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in data mining: Formulation, detection, and avoidance. *ACM Transactions on Knowledge Discovery from Data*, 6(4), Article 15. https://doi.org/10.1145/2382577.2382579

Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. In *Advances in Neural Information Processing Systems 30* (pp. 4765–4774). Curran Associates.

MITRE. (n.d.-a). *CWE-89: Improper neutralization of special elements used in an SQL command ('SQL Injection')*. Common Weakness Enumeration. Retrieved 2026, from https://cwe.mitre.org/data/definitions/89.html

MITRE. (n.d.-b). *CWE-295: Improper certificate validation*. Common Weakness Enumeration. Retrieved 2026, from https://cwe.mitre.org/data/definitions/295.html

Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.

Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., & Wesslén, A. (2012). *Experimentation in software engineering*. Springer. https://doi.org/10.1007/978-3-642-29044-2
