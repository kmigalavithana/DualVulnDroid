# CWE-89 Corpus Expansion + Experiment v3 — Report

**Run date:** 2026-08-29 · **Status:** Data expansion + confirmatory experiment, NOT a conference paper. No paper was written or modified in this phase.

---

## 1. Executive Summary

This phase attempted a targeted expansion of the CWE-89 corpus's most critical shortage — independent vulnerable projects — by shifting strategy from blind repository sampling (used in all three prior rounds) to two more efficient sources the task explicitly recommended: (a) publicly disclosed, CVE-documented Android ContentProvider SQL-injection advisories, and (b) a known Android security-testing benchmark application. This yielded **3 new, fully independently-traced vulnerable findings** — one new project (owncloud/android, CVE-2023-24804), one new benchmark project (InsecureBankv2, OWASP MASTG-APP-0010), and one new sample added to an *existing* project (nextcloud/android, re-investigated at its pre-3.18.1 commit, CVE-2021-43863) — taking the corpus from 3 to **6 independent vulnerable projects (2 per split, up from 1 per split)**. This falls short of the operational target of 5 per split; that limitation is stated explicitly, not minimized. A fresh experiment (v3), methodologically identical to the prior round's rigorous protocol, was then run on the expanded corpus. The core finding **replicates rather than resolves**: even with double the vulnerable examples and zero structurally-degenerate out-of-fold folds (a specific problem that affected the prior round), both SVM and XGBoost still fail to detect either test-split vulnerable sample, the fusion model's coefficient on the ML feature remains inverted (smaller in magnitude but still wrong-signed), calibration again collapses the fused score to a near-constant value, and the predeclared safety-first abstention policy again forces 0% coverage. **Final verdict: B — still insufficient for a defensible quantitative claim**, now with stronger, replicated evidence for why.

## 2. Corpus Construction

Starting point: `backend/research_eval_artifacts/new_cwe89_corpus_final/` (34 samples, 18 projects), used read-only and **not modified**. New directory: `backend/research_eval_artifacts/cwe89_corpus_v3/`. Strategy change this round, per task instruction: rather than continuing blind sampling of popular Android apps (the approach used in all three prior rounds, yielding roughly 1 vulnerable project per 6–7 repositories investigated), this round searched for (a) publicly disclosed CVEs/security advisories naming real Android ContentProvider SQL injection flaws, and (b) known, intentionally-vulnerable Android security-training benchmark applications explicitly listed as a priority source in this round's instructions. Three candidates were investigated and traced; a fourth (`b3nac/InjuredAndroid`) was investigated and correctly **excluded** — its one SQL-adjacent file (`FlagSevenSqliteActivity.kt`) turned out to be an insecure-local-storage / root-access challenge, not a CWE-89 source-to-sink flow, and was not force-labeled from API presence alone.

## 3. Provenance

| New sample | Project | Repository | Commit / tag | License | Independent corroboration |
|---|---|---|---|---|---|
| `oc-001` | owncloud-android | owncloud/android | `53e4dee38022a851aa5d8950cfc6bd8848574e15` (tag `oc-android-2.21.1`) | GPL-2.0 | CVE-2023-24804 / GitHub Security Lab advisory GHSL-2022-059 |
| `ib-001` | insecurebankv2 | dineshshetty/Android-InsecureBankv2 | `3c8cc3a3ce45ed56d0f58f236b541b41f992e51f` | MIT | OWASP MASTG-APP-0010 (listed benchmark app) |
| `nc-002` | nextcloud-android (existing project, new commit) | nextcloud/android | `df232d93a4375c4b395187819563fe98b88b1eda` (tag `rc-3.18.0-02`, pre-3.18.1) | GPL-2.0 | CVE-2021-43863 / GitHub Security Lab advisory GHSL-2021-1007 |

All three were **independently re-traced against the actual source code** by this session, not merely cited from the advisory text — full evidence chains (source, sink, guard logic read directly, manifest exported/permission status confirmed) are in `label_evidence.csv` and `corpus_v3_candidate_samples.csv`. This is a meaningful methodological strength over the prior three rounds: two of the three new findings now have independent, third-party corroboration (a published CVE) in addition to this project's own manual trace, rather than resting on single-reviewer tracing alone.

## 4. Vulnerable-Project Independence

Total independent vulnerable projects: **6** (up from 3). Mechanism diversity, extending the prior round's table:

| Project | Mechanism | Sink API | Reachability |
|---|---|---|---|
| andstatus-andstatus (prior) | Flawed escaping helper | `execSQL` | Internal, no IPC |
| tasks-tasks (prior) | Query-builder bind-mechanism discarded | Custom `rawQuery` wrapper | External IPC (custom permission) |
| openintents-safe (prior) | Structured-API misuse via file import | `query()` selection param | Local file import |
| **owncloud-android (new)** | **Weak guard (whereArgs!=null check only, no content validation)** | `delete()` concatenation | **External IPC, NO permission required** |
| **insecurebankv2 (new)** | **Zero validation, raw parameter pass-through** | `delete()`/`query()`/`update()` | **External IPC, NO permission required** |
| **nextcloud-android/nc-002 (new)** | **Permission-gate excludes the main file table; no content validator existed pre-3.18.1** | `delete()` pass-through | **External IPC, NO permission required (for the ungated table)** |

**Notable, honestly-reported pattern:** all three *new* vulnerable findings are exported ContentProviders reachable with **no permission requirement at all** — a more severely exposed reachability profile than any of the three prior-round findings. This is reported as observed, not as evidence of a general trend (n=3 new findings is far too few to support a claim about ContentProvider vulnerability patterns in general).

**Fork-lineage disclosure:** owncloud-android and nextcloud-android share real historical ancestry (nextcloud/android is a fork of owncloud/android; the pre-3.18.1 nextcloud source still uses the `com.owncloud.android` package name). Direct line-by-line comparison confirmed the sampled code differs substantively at both commits (different guard logic, and a full Java-to-Kotlin rewrite occurred at nextcloud/android between the vulnerable and safe commits) — both are retained as independent projects, and are deliberately placed in **different splits** (train / test) specifically so that this judgment being wrong would not contaminate a single split. Full detail in `duplicate_analysis.csv`.

## 5. Safe-Class Diversity

No new safe samples were deliberately collected this round, per the task's explicit instruction to prioritize vulnerable-project independence over safe-example row count and to avoid padding with trivial constant-only examples. The safe class remains at 31 samples (unchanged from the prior round), spanning the four evidence categories already documented (parameterized/bind, compile-time constants, framework-constrained, allowlist). `nc-001` (the current, defended nextcloud/android commit) now sits alongside its own project's newly-added vulnerable predecessor `nc-002`, forming a genuine, historically-real (not fabricated) same-project vulnerable→fixed pair.

## 6. Project-Level Split

Verified programmatically (Python sets over `project_id`, cross-checked against every sample's own `split` field): `train ∩ validation = ∅`, `train ∩ test = ∅`, `validation ∩ test = ∅`; union covers all 20 projects; zero sample-to-manifest mismatches.

| Split | Projects | Vulnerable projects | Samples | Vulnerable samples |
|---|---|---|---|---|
| Train | 8 | 2 (andstatus-andstatus, owncloud-android) | 16 | 2 |
| Validation | 6 | 2 (tasks-tasks, insecurebankv2) | 12 | 2 |
| Test | 6 | 2 (openintents-safe, nextcloud-android) | 9 | 2 |
| **Total** | **20** | **6** | **37** | **6** |

Every split now has exactly 2 vulnerable projects (up from 1) — a real, structural improvement, though still well short of the 5-per-split operational target. Full manifest: `project_split_manifest.csv`; per-split project lists: `train_projects.txt`, `validation_projects.txt`, `test_projects.txt` (in `cwe89_corpus_v3/`).

## 7. Experimental Protocol

Identical in design to the prior round's protocol, re-run from scratch on the expanded corpus: TF-IDF fit on train only; leave-one-out out-of-fold ML-score generation over train; an independent static analyzer (same experiment-local, documented `dataflow.py` sink-list extension as before, `dataflow.py` itself unmodified); a logistic-regression fusion model trained on OOF ML score + static evidence + completeness indicator; Platt calibration fit on validation only; a predeclared, safety-first abstention threshold band selected on validation only (maximize coverage s.t. FNR ≤ 0); freeze; evaluate once on test. No old dataset, checkpoint, vectorizer, or threshold was reused (`experiment_config.json` → `old_artifacts_loaded: "NONE"`).

## 8. ML Baselines

TF-IDF: 256-term vocabulary (up from 251), fit on 16 train documents (up from 15). SVM (`LinearSVC`, class-weight balanced) and XGBoost (`scale_pos_weight` = train class ratio), both freshly trained, seed 42.

**Test-split result (n=9, 2 positive):** SVM — TP=0, TN=7, FP=0, FN=2 (0% recall). XGBoost — TP=0, TN=7, FP=0, FN=2 (0% recall). **Both models miss both test-split positives.** This is a materially different, and more consistent, outcome than the prior round, where XGBoost happened to catch its one test positive (credited there, correctly, as likely chance rather than generalization, since it had failed on the equivalent validation positive one step earlier). That "lucky catch" **does not replicate** in this round with more data — direct evidence supporting the prior round's caution against crediting it.

## 9. Static Baseline

Unmodified `dataflow.py` + the same documented, experiment-local sink-list extension as the prior round. All 6 vulnerable samples are correctly flagged `VULNERABLE` by the extended wrapper (`sinks_found` ≥ 1, not all-parameterized) — including both new CVE-derived samples, confirming the static approach's core strength (high recall) continues to hold on genuinely new, independently-sourced vulnerable code. Test-split result: 88.9% coverage (8/9 decided, 1 abstained on `NO_SINK`), TP=2, TN=0, FP=6, FN=0 — perfect recall, 25% precision. The same root cause as before (the strict single-literal parameterization check misreading safe multi-fragment concatenation as unsafe) accounts for all 6 false positives (`error_analysis.csv`).

## 10. Late Fusion

**Fusion coefficients:** `oof_ml_svm = -0.2512`, `static_score = 0.2092`, `completeness = -0.0003`, intercept `-0.0951` (`fusion_results.csv`). **The ML-feature coefficient remains negative** — smaller in magnitude than the prior round's -1.1468 (a ~4.5× reduction), consistent with the fact that this round has **zero structurally degenerate OOF folds** (vs. 1 of 15 previously), since holding out one of train's two positives still leaves one positive to train that fold on. Despite removing that specific structural artifact, **the sign is still wrong** — meaning the underlying OOF ML signal still does not correlate positively with the true label across the training set even without the degenerate-fold distortion. This is a stronger, cleaner piece of evidence than the prior round could offer: the inverted relationship is not fully explained by the single-positive degeneracy alone.

Raw fusion scores on test are again extremely tightly clustered (0.482–0.504, spanning 0.022) — both test positives (`os-001`=0.501, `nc-002`=0.492) sit inside this same narrow band, indistinguishable from the safe examples around them. After Platt calibration, **all 9 test scores collapse to 0.166611–0.166628** (span < 0.00002) — again a near-constant output, this time close to the corpus's overall base rate (6/37 ≈ 16.2%). Brier score improves numerically (0.2476→0.1389) and ECE reaches 0.0000 on validation — again reflecting the calibrator correctly recognizing the raw score carries ~no signal, not a working calibrated detector.

## 11. Selective Prediction

Under the predeclared objective (maximize coverage s.t. FNR ≤ 0 on validation), the fusion+abstention configuration (E) again achieves only a **0% coverage** band on validation, frozen and applied once to test (also 0% coverage, 9/9 abstained). The ML-only selective configuration (F) also collapses to **0% coverage** this round (a change from the prior round's 37.5%) — with the SVM's own validation scores now clustered even more tightly around 0.5 (0.48–0.52-ish range) than in the prior round, no non-trivial band satisfies the zero-FNR constraint. The rule-only selective configuration (G) again collapses to full (100%) coverage due to the static score's coarse {0.1, 0.5, 0.9} discretization.

## 12. Matched-Coverage Results

All configurations (A–G) evaluated on the identical, frozen 9-sample test split; no comparison here contrasts a full-coverage result against a partial-coverage result and claims superiority (`model_results.csv`).

| Config | Coverage | TP | TN | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| A. Rule-only | 88.9% | 2 | 0 | 6 | 0 | 0.25 | 1.00 |
| B. SVM-only | 100% | 0 | 7 | 0 | 2 | N/A | 0.00 |
| C. XGBoost-only | 100% | 0 | 7 | 0 | 2 | N/A | 0.00 |
| D. Late fusion (no abstain) | 100% | 0 | 7 | 0 | 2 | N/A | 0.00 |
| E. Late fusion + abstention | 0% | — | — | — | — | — | — |
| F. ML-only selective | 0% | — | — | — | — | — | — |
| G. Rule-only selective | 100% | 2 | 0 | 7 | 0 | 0.22 | 1.00 |

Configuration D makes **identical** predictions to configuration B on every test sample (confirmed directly, and independently by McNemar's test below) — fusion again does not change the ML-only outcome.

## 13. Statistical Analysis

Project-level bootstrap (2,000 resamples over the 6 test projects): SVM-only test accuracy 0.785 (95% CI [0.60, 1.00]); late-fusion test accuracy 0.785 (95% CI [0.60, 1.00]) — near-identical, wide intervals, explicitly reported as low-power given 6 resampled projects. **McNemar's exact test, SVM-only vs. late fusion: 0 discordant pairs** (identical predictions on all 9 test samples) — no p-value is computable, replicating the prior round's identical finding exactly. AURC (fusion score, test split) = 0.2767, explicitly labeled LOW\_POWER/DESCRIPTIVE (n=9). No fabricated confidence interval or significance claim appears anywhere in this section or its source files.

## 14. Error Analysis

10 rows in `error_analysis.csv`: 2 SVM false negatives, 2 XGBoost false negatives (both test positives, both models), and 6 rule-only false positives. Every SVM/XGBoost miss is categorized `training_data_coverage_gap` — neither test-split positive (`os-001`: XML-backup-to-SQL; `nc-002`: an unguarded ContentProvider table) shares close vocabulary with either training-split positive (`as-001`: a flawed escaping helper; `oc-001`: a different ContentProvider guard pattern) — consistent with, and extending, the prior round's finding that these models learn to recognize specific training examples' vocabulary rather than a general CWE-89 signature. All 6 rule-only false positives are categorized `sanitization_parameterization_misunderstanding`, the same root cause identified and unchanged from the prior round. No fabricated or illustrative-only example is used; every case is an actual test-split misclassification.

## 15. Plugin Evaluation

Not re-measured this round — the prior round's backend inference latency measurement (`final_cwe89_experiment_v2/backend_latency_report.json`: short/medium/long snippets, 65/45/110 ms mean, p99 84/50/119 ms, 0 errors over 90 calls) stands unchanged, since neither the plugin nor the backend inference pipeline was modified in this data-expansion phase. **IDE end-to-end latency remains not established** — this phase did not attempt to measure it, and no such claim is made.

## 16. Security Limitations

Unchanged from the prior round: the backend remains HTTP-only (no TLS configured) and the code-submission endpoints (`/predict`, `/developer/*`) remain unauthenticated, verified directly against `backend/app.py` in the prior round and not modified since. No secure-deployment claim is made. Retained explicitly as a research-prototype limitation.

**A new, incidental observation from this round's own data collection:** two of the three newly-added vulnerable findings (`oc-001`, `nc-002`) are themselves examples of exported Android ContentProviders reachable with no permission requirement — the same class of exposure (unauthenticated, unvalidated access to an exported interface) this project's own backend exhibits. This parallel is noted for context; it is not evidence about this project's own backend beyond what was already established in the prior round.

## 17. Reproducibility

`reproducibility_report.json`: SHA-256 hashes of both `cwe89_corpus_v3` CSVs consumed; random seed 42; Python 3.11, scikit-learn, xgboost, numpy, pandas versions recorded; full vectorizer/model parameter dictionaries in `experiment_config.json`; UTC run timestamp. A direct `comparison_to_prior_experiment_v2` block is included in `reproducibility_report.json`, recording the exact deltas cited throughout this report (vulnerable projects 6 vs 3; degenerate OOF folds 0 vs 1; fusion coefficient sign negative in both; McNemar discordant pairs 0 in both; abstention coverage 0% in both).

## 18. Threats to Validity

- **Two of three new vulnerable samples come from a shared historical codebase lineage** (owncloud/nextcloud) — mitigated by placing them in different splits and disclosing the lineage explicitly (Section 4), but a residual risk that the two are more similar than fully independent projects would be.
- **The third new sample (`ib-001`) is from a deliberately-vulnerable teaching application**, not a production app — disclosed explicitly (Sections 2–3); its vulnerability is real and traceable, but its *context* (an app built to be broken) differs from the other 5 vulnerable projects' organic, unintentional flaws.
- **The static-analyzer sink-list extension** (documented, structural, non-label-derived) was again authored by the same person who labeled the corpus — the same disclosed residual risk as the prior round.
- **Corpus scale remains the binding limitation.** 2 vulnerable projects per split is a genuine, structural improvement over 1, but is still far short of the 5-per-split operational target this round explicitly aimed for, and every quantitative result in Sections 8–13 demonstrates, not merely asserts, that this scale is insufficient.

## 19. What Was Demonstrated

- A genuine, ~2× expansion of the corpus's independent vulnerable-project count, achieved through a more targeted, higher-yield collection strategy (CVE-documented advisories + a known benchmark app) than the blind sampling used in all three prior rounds — itself a useful, reusable methodological finding for any future expansion effort.
- Independent, third-party corroboration (published CVEs) for 2 of the 3 new vulnerable findings, strengthening this corpus's provenance beyond single-reviewer tracing alone.
- **Replication** of the prior round's core negative findings under a materially different (larger, less structurally degenerate) sample: both ML models still fail on unseen vulnerable examples, the fusion coefficient is still inverted, calibration still collapses to a near-constant, and safety-constrained abstention still forces zero coverage. Replication under a changed condition (0 vs. 1 degenerate OOF folds) is stronger evidence than a single round could provide that these are not artifacts of one specific structural quirk.

## 20. What Was Not Demonstrated

- **Not** that late fusion improves detection — it still does not, and makes literally identical predictions to ML-only on this round's test split (0 McNemar-discordant pairs, replicated).
- **Not** that the corpus is now sufficient for a statistically powered claim — 2 positives per split remains a low-power regime by every metric computed in Section 13.
- **Not** that the targeted CVE/benchmark-app collection strategy would continue to yield new independent vulnerable projects at the same rate if extended further — n=3 new findings from this round's targeted search is too small to project a sustained yield rate.
- **Not** "state of the art," "best," "production-ready," "general Android detection," "solves CWE-89," "highly accurate," or "generalizes to all Android applications" — none of these claims is supported by any result in this report, and none is made.

## 21. Final Scientific Verdict

**Part G decision: B — still insufficient.**

Independent vulnerable projects: 6 (2 per split) against an operational target of 5 per split (15 total) — not reached, and stated plainly rather than reframed. Independent safe-only projects: 14. Vulnerable samples: 6. Safe samples: 31.

Per the task's explicit instruction not to proceed to ML merely because row count increased: this verdict is not based on row count, but on the actually-measured outcomes in Sections 8–13, all of which replicate the prior round's inconclusive result under a materially improved (though still small) sample. The improvement this round achieved was real (a targeted collection strategy roughly doubled the vulnerable-project count with genuine, CVE-corroborated evidence) and running experiment v3 was justified precisely because it produced new, useful confirmatory evidence — not because it was expected to, or did, yield a positive result. The recommended next step, unchanged in kind from the prior round but now with a demonstrated, higher-yield collection method to build on, is to continue the CVE-advisory and benchmark-application search strategy (Section 19) toward the 5-per-split target before attempting any experiment intended to support a quantitative accuracy or fusion-benefit claim.

---

*Per explicit instruction: this report and its accompanying artifacts are the end of this phase. No conference paper was written or modified. `new_cwe89_corpus_final/` and all prior experiment directories were not modified.*
