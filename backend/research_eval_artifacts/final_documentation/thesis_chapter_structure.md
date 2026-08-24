# Suggested Thesis Chapter Structure

## Chapter 1 — Introduction
**Purpose:** Motivate the problem (SQL Injection and Improper Certificate Validation in Android apps), state the research gap (real-time, explainable, hybrid ML+rule detection integrated into both a developer tool and an end-user tool), and state the objectives and contributions.
**Key subsections:** Background and motivation; problem statement; research objectives; research questions (RQ1–RQ5); scope and contributions; thesis structure overview.
**Figures/tables:** None required; optionally a one-diagram system overview teaser.

## Chapter 2 — Literature Review
**Purpose:** Position the work against prior static-analysis, ML-based vulnerability detection, and mobile-security-specific literature.
**Key subsections:** Traditional static analysis for Android; ML/DL for source-code vulnerability detection; CWE-89/CWE-295-specific prior work; explainability in security ML (SHAP and alternatives); hybrid rule+ML decision systems; research gap synthesis.
**Figures/tables:** Comparison table of related work vs. this project's approach.

## Chapter 3 — Methodology
**Purpose:** Describe the end-to-end research methodology, from raw data to production integration.
**Key subsections:** Dataset (A); label distribution (B); label-noise detection (C); conflicting-label exclusion (D); normalized-code grouping (E); grouped split (F); leakage prevention (G); feature engineering (H); security/data-flow features (I); model training (J); model comparison (K); Decision Engine (L); explainability (M); production integration (N); end-to-end validation (O).
**Figures/tables:** Dataset cleaning funnel diagram (1,687 → 1,128 → 791/169/168); leakage-check results table.

## Chapter 4 — System Design and Architecture
**Purpose:** Present the full system architecture across all components.
**Key subsections:** Real-time code analysis pipeline (plugin/API); APK/application assessment pipeline (Flutter); database architecture; chatbot architecture; IntelliJ plugin architecture.
**Figures/tables:** The two pipeline diagrams from `architecture_description.md`; database ER diagram (10 tables).

## Chapter 5 — Dataset and Feature Engineering
**Purpose:** Detail the dataset and the 7,610-dimensional production feature pipeline.
**Key subsections:** Raw vs. clean dataset; class distribution before/after cleaning; TF-IDF word/char features; count features; the 23 security/data-flow features; train-only fitting and reuse for validation/test/inference.
**Figures/tables:** `model_comparison_table.csv`'s supporting split table; feature dimension breakdown table (7,587 text + 23 security = 7,610).

## Chapter 6 — ML/DL Model Development and Evaluation
**Purpose:** Present the five-model comparison and the CWE-specific findings.
**Key subsections:** Model configurations and hyperparameter selection; overall comparison table; security-specific findings (FNR/FPR by model); CWE-89 findings; CWE-295 findings; fairness-of-comparison notes (identical frozen test set, differing input representations for LSTM).
**Figures/tables:** `model_comparison_table.csv`, `cwe89_table.csv`, `cwe295_table.csv`; confusion matrices; ROC curves.

## Chapter 7 — Hybrid Decision Engine and Explainability
**Purpose:** Explain the production Decision Engine's rule+ML fusion, its current-vs-research-candidate thresholds, and the two forms of explainability.
**Key subsections:** Evidence-weight scoring; current production thresholds and auto-decision metrics; Balanced research candidate and why it is not deployed; robustness analysis (H1–H4, INCONCLUSIVE classification); SHAP model explanation vs. deterministic rule/data-flow evidence (kept distinct).
**Figures/tables:** `decision_engine_summary.csv`; robustness hypothesis table (H1–H4 verdicts); SHAP summary plot example.

## Chapter 8 — Software Implementation
**Purpose:** Describe the implemented software artifacts: FastAPI backend, IntelliJ plugin, Flutter app.
**Key subsections:** Backend API surface and persistence; IntelliJ plugin (real-time inspection, batch scan, Quick Fix, tool window); Flutter app (screens, widgets, JWT auth); chatbot implementation and the app_id bug fix.
**Figures/tables:** Screen/widget inventory table; plugin class inventory table.

## Chapter 9 — Testing and Validation
**Purpose:** Report what was actually tested, how, and with what result — including what could not be validated and why.
**Key subsections:** Backend test suite; Kotlin plugin test suite; Flutter test suite; the 8 required live chatbot questions; security check (no leaked secrets, no unsafe fallback); explicit NOT VALIDATED items (IDE sandbox, live device) with reasons.
**Figures/tables:** `testing_summary.csv`.

## Chapter 10 — Results and Discussion
**Purpose:** Synthesize the model comparison, Decision Engine, and system validation results into the research questions' answers.
**Key subsections:** RQ1–RQ5 answers; production model justification; discussion of trade-offs (coverage vs. safety, classical ML vs. DL on a small dataset).
**Figures/tables:** Reproduced summary tables from Chapters 6–7; RQ answer table.

## Chapter 11 — Limitations and Future Work
**Purpose:** State limitations honestly and propose concrete next steps.
**Key subsections:** Dataset size and application-level split limitation; Decision Engine robustness gap; DL supplementary status; live-validation gaps (IDE sandbox, device); chatbot NLU limitation; future work (more labelled data, application-level split if an identifier becomes available, further robustness studies before considering Balanced-threshold deployment, live device/IDE validation pass).
**Figures/tables:** None required; a limitations-to-future-work mapping table is optional.

## Chapter 12 — Conclusion
**Purpose:** Close the thesis with the final production conclusion and contribution summary.
**Key subsections:** Summary of contributions; final production model decision (verbatim conclusion text); closing remarks.
**Figures/tables:** None required.
