# Evidence Audit — Final CWE-89 IEEE Manuscript

**Companion document to:** `FINAL_CWE89_IEEE_PAPER.md` / `.docx`
**Purpose:** map every quantitative or provenance claim in the manuscript to its exact source artifact, verified directly against the underlying files in this session (not copied from a prior summary), and record every claim type deliberately excluded and why.
**Scope discipline:** `new_cwe89_corpus_final/`, `final_cwe89_experiment/`, `final_cwe89_experiment_v2/`, `cwe89_corpus_v3/`, `cwe89_experiment_v3/`, and every thesis chapter were opened read-only and **not modified** to produce this paper. Only `backend/research_eval_artifacts/final_ieee_cwe89_paper/` was created.

---

**Author-information insertion addendum (this update):** the venue-neutral author placeholder block described in the addendum below was replaced with the author's actual, user-supplied information:
- **Author:** K M Igalavithana
- **Affiliation:** Department of Computing, Faculty of Computing, NSBM, Sri Lanka
- **Email:** kmigalavithana.km@gmail.com

This information was supplied directly by the user in-session as authoritative; it was not searched for, inferred, or fabricated by this process. No other region of the manuscript was edited — the change was a single, exact replacement of the five-line placeholder block (and its bracketed "REQUIRES AUTHOR/UNIVERSITY CONFIRMATION" note) with the five-line real author block, verified via a single-match `Edit` operation and confirmed by direct visual inspection of the freshly re-rendered PDF (title, author block, and abstract all render correctly on page 1 of 8; no other page changed relative to the minor-revision-pass state). No number, count, confusion-matrix value, coefficient, p-value, latency figure, table, figure, or reference was touched. The disposition of this item in `FINAL_SUBMISSION_READINESS_AUDIT.md` §4/§19 is updated from "REQUIRES AUTHOR INPUT" to "FIXED" accordingly.

---

**Minor-revision pass addendum (earlier update):** the manuscript wording changed in the following locations; no scientific evidence mapping in Section 1 below changed as a result, since none of these edits touched a number, a result, or the conclusion:
- A venue-neutral author/affiliation placeholder block was added directly under the title (five lines: Author Name(s) / Department-School / University / City, Country / Email, italicized) plus an explicit bracketed note "[AUTHOR INFORMATION REQUIRES AUTHOR/UNIVERSITY CONFIRMATION — placeholder only, not a real identity]". No name, institution, or email was invented — see `FINAL_SUBMISSION_READINESS_AUDIT.md` §4 for the disposition of this item.
- The abstract was condensed from 274 to exactly 210 words. Every fact required by this revision pass (CWE-89 problem, independent ML/static evidence, project-level leakage-safe evaluation, late fusion, selective prediction, v3 corpus scale, non-established ML generalization, non-established fusion benefit, the need for more independent vulnerable projects) is retained; only phrasing was compressed. The full, uncompressed original wording remains available in `FINAL_CWE89_IEEE_PAPER_pre_minor_revision.md`.
- The keyword list was reduced from 10 to 5 terms (Android security, SQL injection, CWE-89, static analysis, machine learning).
- References [4] and [5] were completed with verified author names and (for [5]) a resolved venue, per §2 below.
- Three DOCX-rendering defects present in the prior DOCX build (a markdown-converter bug that misparsed the `*` inside `` `allow_origins=["*"]` `` as an italic marker, a literal backslash leaking from an unescaped `\_`, and a stray horizontal-rule artifact after the Keywords line) were fixed by correcting the Markdown-to-DOCX conversion script itself (it now protects backtick code spans from emphasis parsing, resolves backslash escapes, and silently consumes horizontal-rule markers). The Markdown source text was never itself wrong in the first two cases — only the DOCX rendering was — and this was confirmed by direct visual inspection of the freshly re-rendered PDF pages (not XML inspection alone).
- Table VI's header row was marked to repeat across a page/column break (`w:tblHeader`) as a durability fix; in the freshly re-rendered layout the table now fits within a single column without breaking at all, so this fix currently acts as a safety margin rather than being visibly exercised.

No number, count, confusion-matrix value, coefficient, p-value, latency figure, or security-posture statement was altered anywhere in this pass. Section 1 below is otherwise unchanged from the previous revision of this audit.

---

## 1. Claim-to-Artifact Mapping

| Paper claim | Exact artifact | Exact value | Interpretation | Limitation |
|---|---|---|---|---|
| 37 total samples, 6 vulnerable, 31 safe | `cwe89_corpus_v3/corpus_v3_candidate_samples.csv` | Independently re-counted this session: `Counter({'SAFE': 31, 'VULNERABLE': 6})`, `len(rows)==37` | Corpus scale as of the primary evidence round | Ambiguous-labeled candidates are excluded from this file entirely (never forced in), so this count already reflects only DEFINITE labels |
| 20 independent projects, 6 vulnerable (2/split) | `cwe89_corpus_v3/project_split_manifest.csv` | Re-verified: `Counter({'train': 8, 'validation': 6, 'test': 6})`; vulnerable projects `{andstatus-andstatus, owncloud-android}` (train), `{tasks-tasks, insecurebankv2}` (validation), `{openintents-safe, nextcloud-android}` (test) | Every split has exactly 2 vulnerable projects | Falls short of the 5-per-split operational target stated in the paper itself (Table I, Section IV-D) |
| Split disjointness (`train ∩ val = ∅` etc.) | Computed directly this session as Python set operations over `project_split_manifest.csv`, cross-checked against every sample's own `split` field | All three pairwise intersections empty; zero sample-to-manifest mismatches | Programmatic verification, not assumed | — |
| `oc-001` (owncloud/android) vulnerability, CVE-2023-24804 | `cwe89_corpus_v3/corpus_v3_candidate_samples.csv` (row `oc-001`); `label_evidence.csv`; independently re-read against the actual cloned source at tag `oc-android-2.21.1`, commit `53e4dee38022a851aa5d8950cfc6bd8848574e15`, during the collection session | `FileContentProvider.kt` `delete()`, guard checks only `whereArgs != null`, not `where`'s content | Corroborated by GitHub Security Lab advisory GHSL-2022-059 (external, independent source) **and** this project's own direct source trace | Advisory text was read via WebFetch; the source-code trace was performed directly by this session against the cloned repository, not merely copied from the advisory |
| `ib-001` (InsecureBankv2) vulnerability | `corpus_v3_candidate_samples.csv` (row `ib-001`) | `TrackUserContentProvider.java` `delete()`/`query()`/`update()` pass raw `selection`/`selectionArgs` straight to the SQLite sink | Deliberately vulnerable teaching app (OWASP MASTG-APP-0010), documented as such in the paper (Section IV-B), not presented as an accidental production defect | — |
| `nc-002` (nextcloud/android pre-3.18.1) vulnerability, CVE-2021-43863 | `corpus_v3_candidate_samples.csv` (row `nc-002`); cloned at tag `rc-3.18.0-02`, commit `df232d93a4375c4b395187819563fe98b88b1eda` | `isCallerNotAllowed()` excludes `ROOT_DIRECTORY`/`SINGLE_FILE`/`DIRECTORY` from its permission gate; no content validator for `where` exists at this commit | Corroborated by GHSL-2021-1007; forms a genuine, historically real vulnerable→fixed pair with `nc-001` (same project, later commit) | Both samples share one `project_id` and are kept in the same split (test), per the project-level independence rule stated in the paper (Section IV-D) |
| `InjuredAndroid` excluded (not a CWE-89 finding) | `corpus_v3_inventory.csv`, row `injuredandroid` | `FlagSevenSqliteActivity.kt`'s `db.insert()` calls seed local storage for a root-access/ADB challenge | Correctly excluded rather than force-labeled from API presence alone | — |
| SVM/XGBoost test recall 0/2 (v3) | `cwe89_experiment_v3/model_results.csv`, rows `B_svm_only`/`C_xgb_only` | `TP=0,TN=7,FP=0,FN=2` for both | Neither model detects either test-split positive | `power_note` column explicitly reads `LOW_POWER/DESCRIPTIVE (n_pos=2)` in the source file itself |
| XGBoost test recall 1/1 (v2), did not repeat in v3 | `final_cwe89_experiment_v2/ablation_results.csv`, row `B_ml_only_xgb` (`TP=1,TN=7,FP=0,FN=0`) vs. `cwe89_experiment_v3/model_results.csv`, row `C_xgb_only` (`TP=0,TN=7,FP=0,FN=2`) | Re-verified directly this session by re-reading both files side by side | Central replication finding (Section 7.8, Table VI) | Both files independently confirmed to contain these exact rows before the comparison was written into the manuscript |
| Fusion coefficient on ML feature: −1.1468 (v2) → −0.2512 (v3) | `final_cwe89_experiment_v2/fusion_model_report.json` → `coefficients.oof_ml_probability_svm`; `cwe89_experiment_v3/fusion_results.csv` → `fusion_coefficient_oof_ml_svm` | −1.1468 and −0.2512 respectively, both re-read directly this session | Sign remains inverted in both rounds; magnitude reduced alongside the degenerate-OOF-fold count dropping from 1 to 0 | The paper does not claim the smaller magnitude is itself meaningful progress toward a working fusion model — only that it isolates the sign inversion from the specific single-positive degeneracy |
| Degenerate OOF folds: 1 (v2) → 0 (v3) | v2: `final_cwe89_experiment_v2/fusion_model_report.json` → `degenerate_oof_folds: 1`; v3: `cwe89_experiment_v3/fusion_results.csv` → `degenerate_oof_folds,0` | Re-verified directly | Structural artifact resolved by corpus expansion | — |
| Calibrated test fusion scores collapse to 0.166611–0.166628 (v3) | Computed during the v3 experiment run (console log + `fusion_results.csv` derived values); the full-precision array was printed and re-derivable from `dataset_manifest_v2.csv`-equivalent data in the v3 run | Span < 0.00002 across all 9 test samples | Near-constant, uninformative output after calibration | The exact full-precision array is not a separately saved file in v3 (unlike v2's `calibration_report.json`); it was captured from the run's own console output at generation time and is reproducible by re-running the experiment with the fixed seed (42) and the hashed corpus files |
| McNemar: 0 discordant pairs (both v2 and v3) | v2: `final_cwe89_experiment_v2/statistical_analysis.json`; v3: `cwe89_experiment_v3/fusion_results.csv` → `mcnemar_discordant_pairs,0` | Re-verified directly in both files | Fusion and ML-only produce identical predictions in both rounds | No p-value is fabricated where none is computable — both source files record `NOT_APPLICABLE_ZERO_DISCORDANT`/equivalent |
| Abstention coverage 0% under predeclared FNR≤0 (both rounds) | v2: `final_cwe89_experiment_v2/abstention_report.json`; v3: `cwe89_experiment_v3/abstention_results.csv` | Both confirm 0.0 validation and frozen test coverage | Safety-constrained selective prediction forces total abstention in both rounds | — |
| AURC = 0.2767 (v3, n=9) | `cwe89_experiment_v3/fusion_results.csv` → `aurc_test,0.2767`; curve data in `risk_coverage.csv` | Re-verified directly | Explicitly labeled LOW\_POWER/DESCRIPTIVE in the manuscript (Section 7.6) | No confidence interval is attached to this value anywhere, matching its source file |
| Bootstrap CIs: SVM 0.785 [0.60,1.00]; fusion 0.785 [0.60,1.00] | `cwe89_experiment_v3/fusion_results.csv` → `bootstrap_svm_accuracy_*`, `bootstrap_fusion_accuracy_*` | Re-verified directly | Project-level, 2,000 resamples, 6 test projects | Explicitly described as wide/low-power in the manuscript, matching the small resampling base |
| Rule-only (static) test: 88.9% coverage, TP=2,TN=0,FP=6,FN=0 | `cwe89_experiment_v3/model_results.csv`, row `A_rule_only` | Re-verified directly | 100% recall, 25% precision | — |
| Error-analysis categories | `cwe89_experiment_v3/error_analysis.csv` | 10 rows: 2 SVM FN, 2 XGBoost FN (`training_data_coverage_gap`), 6 rule-only FP (`sanitization_parameterization_misunderstanding`) | Re-verified via direct `Counter` computation this session: `Counter({('rule_only','FP'): 6, ('svm_only','FN'): 2, ('xgb_only','FN'): 2})` | Every case cited in the manuscript is an actual row in this file; none is illustrative-only |
| Backend inference latency (short/medium/long) | `final_cwe89_experiment_v2/backend_latency_report.json` | short 65.25ms mean/84.31ms p99; medium 45.41/50.29; long 110.03/118.75; 0 errors/90 calls | Re-verified directly this session | Not re-measured in v3 (backend/plugin unchanged since v2); manuscript states this explicitly and does not claim IDE end-to-end latency |
| Backend HTTP-only, unauthenticated code-submission endpoints | `backend/app.py`, re-grepped directly this session | No `ssl_keyfile`/`ssl_certfile`; `allow_origins=["*"]`; `/predict`, `/developer/predict`, `/developer/scan`, `/developer/explain`, `/developer/rescan` have no `Depends(...)` auth dependency, unlike `/user/*` routes | Re-verified directly against current source, not assumed from a prior round's finding | Confirms the finding is still true as of this session, not stale |

## 2. Citation Verification

References [1]–[6] were verified via live web search in an earlier session round (cross-checked against at least two independent listings per reference: publisher pages, institutional repositories, or arXiv). References [8] and [9] (the two GitHub Security Lab advisories) were read directly via WebFetch during this session's corpus-expansion work, and their technical claims (affected file, vulnerable method, CVE identifiers, fix version) were independently re-confirmed against the actual cloned source code before being used as corpus evidence — not merely restated from the advisory. Reference [10] (OWASP MASTG-APP-0010) was located via web search identifying InsecureBankv2 as a listed OWASP benchmark application. No reference in this manuscript was cited from model memory without this verification chain.

**Minor-revision pass update:** references [4] and [5], flagged incomplete by `FINAL_SUBMISSION_READINESS_AUDIT.md`, were completed in this pass using a fresh, targeted verification search (not guessed or carried over from memory):
- **[4]** — author list (J. Zhu, K. Li, S. Chen, L. Fan, J. Wang, X. Xie), volume/issue/pages (vol. 50, no. 12, pp. 3385–3402, Dec. 2024), and DOI (10.1109/TSE.2024.3488041) confirmed via IEEE Xplore, ACM DL's mirror listing, and the paper's own arXiv abstract page (arXiv:2410.20740, retained alongside the DOI as the openly-accessible preprint).
- **[5]** — author list (V. Kouliaridis, G. Karopoulos, G. Kambourakis), corrected title ("...Vulnerability **Analysis**," not "...Detection" as in the pre-revision draft), and venue (*Attacks and Defenses for the Internet-of-Things (ADIoT 2024)*, Lecture Notes in Computer Science vol. 15397, Springer, Cham, 2025) confirmed via the Springer Link chapter page, replacing the prior unresolved "[Springer conference series]" placeholder. DOI (10.1007/978-3-031-85593-1_9) unchanged — it was already correct.

No page number, volume, or author name in either corrected reference was invented; both are drawn directly from the publisher/repository listings found in this pass's verification search.

## 3. Excluded Claim Types — Confirmed Absent

A direct text search of `FINAL_CWE89_IEEE_PAPER.md` was run this session (not merely intended) for each of the following, with results recorded:

| Search term | Occurrences | Context of each occurrence |
|---|---|---|
| "state of the art" / "state-of-the-art" | 1 | Section I, in "does not claim... state-of-the-art" — negated |
| "best" | 1 | Same sentence, "nor does it claim... best" — negated |
| "first" (as in "first Android"/"first real-time"/"first XAI") | 2 | Same sentence, "does not claim to be the first..." — negated |
| "100%" | 8 | All are literal, exact computed percentages (e.g. "100% recall on n=1", "0% coverage") reported with their sample size and a LOW\_POWER caveat in the source table — none is an unsupported completeness claim |
| "production-ready" | 1 | Same negation sentence in Section I |
| "generalizes" / "generalization" | 2 | Section VII-B, both in "does not demonstrate that... generalizes" / "not as evidence that... generalizes" — negated |
| "highly accurate" | 1 | Same negation sentence in Section I |
| "HTTPS" | 1 | Section X, in "does not claim secure deployment, HTTPS..." — negated |
| "secure deployment" | 1 | Same sentence, negated |
| "solves CWE-89" | 0 | Not present anywhere |

No occurrence required removal; every hit is either a correctly-scoped negation (as the manuscript instructions required) or a literal, caveated statistic.

A second search confirmed the following are **not present as evidence** anywhere in the manuscript: "CWE-295" (0 occurrences), "Flutter" (0), "Security Chat" (0), "1,128"/"1128-row" (1 occurrence, inside the explicit "no prior dataset... was loaded" exclusion statement, Section V), "1,687"/"1687-row" (1 occurrence, same sentence), "CodeBERT" (1 occurrence, same sentence, listed as NOT used), "LSTM" (1 occurrence, same sentence, listed as NOT used).

## 4. Figures and Tables — Source Mapping

| Figure/Table | Source |
|---|---|
| Fig. 1 (pipeline) | Newly generated this session (`plots/figure1_pipeline.png`), a schematic diagram, not derived from measured data — labeled as an architecture diagram, not a results figure |
| Fig. 2 (split protocol) | Newly generated this session (`plots/figure2_split_protocol.png`), reflecting the exact v3 counts (8/6/6 projects, 2 vulnerable each) verified in Section 1 above |
| Fig. 3 (ML/static/fusion architecture) | Newly generated this session (`plots/figure3_architecture.png`), a schematic diagram |
| Fig. 4 (risk-coverage curve) | Copied unmodified from `cwe89_experiment_v3/plots/risk_coverage_curve.png` — an actual experiment output, not redrawn or altered |
| Fig. 5 (IDE evidence trace) | **Deliberately omitted.** No existing, verified-readable screenshot of the plugin's evidence-trace UI was available and independently confirmed in this session; per the manuscript-generation instruction ("if an appropriate existing screenshot is available"), fabricating or guessing at one was avoided rather than included on uncertain grounds |
| Table I (corpus provenance/split) | `cwe89_corpus_v3/corpus_v3_candidate_samples.csv` + `project_split_manifest.csv`, counts independently recomputed this session (Section 1) |
| Table II (evidence categories) | Carried forward from the prior round's established safe-class categorization (unchanged safe-sample set; re-verified the 16/6/6/3 split sums to 31) |
| Table III (experimental configurations) | `cwe89_experiment_v3/model_results.csv` config IDs A–G |
| Table IV (main results) | `cwe89_experiment_v3/model_results.csv`, rows A–D |
| Table V (selective prediction) | `cwe89_experiment_v3/model_results.csv`, rows E–G |
| Table VI (error analysis / replication) | `cwe89_experiment_v3/error_analysis.csv` + the v2/v3 cross-file comparison documented in Section 1 above |

## 5. Unresolved Limitations (Carried Into the Manuscript, Not Hidden Here)

- Corpus scale (6 vulnerable projects, 2 per split) remains below the study's own 5-per-split operational target — stated in Table I's surrounding text and repeated in Sections VII and VIII.
- AST/clone-hash duplicate detection was not performed at any point across all four collection rounds — disclosed in Section IV-C.
- The static-analyzer sink-list extension was authored by the same person who labeled the corpus — disclosed in Section VII-C.
- Full end-to-end IDE latency was never measured in any round — disclosed in Section IX.
- Single reviewer labeled the corpus; no inter-rater agreement is available or claimed anywhere.

## 6. Files Created for This Deliverable

Only the following were created; nothing else was modified:

```
backend/research_eval_artifacts/final_ieee_cwe89_paper/
├── FINAL_CWE89_IEEE_PAPER.md
├── FINAL_CWE89_IEEE_PAPER.docx
├── FINAL_CWE89_IEEE_PAPER_EVIDENCE_AUDIT.md   (this file)
├── FINAL_SUBMISSION_READINESS_AUDIT.md
├── FINAL_CWE89_IEEE_PAPER_pre_minor_revision.md    (backup, pre-minor-revision snapshot)
├── FINAL_CWE89_IEEE_PAPER_pre_minor_revision.docx  (backup, pre-minor-revision snapshot)
└── plots/
    ├── figure1_pipeline.png        (newly generated schematic)
    ├── figure2_split_protocol.png  (newly generated schematic)
    ├── figure3_architecture.png    (newly generated schematic)
    └── figure4_risk_coverage.png   (copied unmodified from cwe89_experiment_v3/plots/)
```

`new_cwe89_corpus_final/`, `final_cwe89_experiment/`, `final_cwe89_experiment_v2/`, `cwe89_corpus_v3/`, `cwe89_experiment_v3/`, and every thesis chapter file were read-only inputs to this work and were not modified.
