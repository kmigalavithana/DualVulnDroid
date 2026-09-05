# DATASET VALIDITY VERDICT — DualVulnDroid

**Role:** Senior professor / research supervisor review, conducted in response to the strict IEEE/Scopus review (`DualVulnDroid_Strict_IEEE_Scopus_Review.docx`, reviewed 28 Aug 2026) and the professor's recommended focused topic, *"Risk-Aware Hybrid Detection of SQL Injection in Android Source Code Using Static Data-Flow Evidence and Selective Machine Learning."*

**Scope of this document:** Dataset validity only. No paper was written or rewritten. No model was retrained. No existing file was modified. This document does not assume the recommended CWE-89-focused direction is valid — that is exactly the question being tested.

**Evidence sources actually opened for this review** (every claim below cites one of these):
`dataset .csv` (raw, 1,687 rows); `backend/ml/data/{train,val,test,excluded_conflicting_labels}.csv`; `backend/ml/data/dataset_report.json`; `backend/research_eval_artifacts/{clean_dataset.csv, split_metadata.json, train/validation/test_indices.json}`; `backend/ml/dataset_prep.py`; `backend/research_eval/data_split.py`; `backend/ml/feature_pipeline.py`; `backend/security_features.py`; `backend/dataflow.py`; `backend/research_eval_artifacts/dataset_label_audit/*` (79-row audit); `backend/research_eval_artifacts/full_dataset_label_audit/*` (1,128-row audit); `git log`; root `README.md`; thesis Chapters 1–3; and a fresh, targeted re-investigation of the 559 excluded rows performed specifically for this review (Section 10).

Where a claim is **inferred** rather than directly observed, it is labeled as such. Where evidence is missing, this document says `UNKNOWN` rather than guessing.

---

## 1. Executive Conclusion

**VERDICT: INVALID for the claim the manuscript currently makes (application-level Android vulnerability detection); PARTIALLY VALID for a narrower, explicitly-scoped code-template classification study — and even that narrower claim requires corrective action before it is trustworthy.**

Two independently-run audits already exist in this project (a 79-row targeted audit and a 1,128-row full-dataset audit). This review re-verified their key numbers directly against the underlying CSV/JSON files (Section 3) rather than trusting either audit's own summary, and **found the numbers accurate** — but it also found a **new, more fundamental problem neither prior audit surfaced**: the entire "safe" class of the dataset (100% of all `s1` and `s0`-safe-side, `v1` rows, in both the raw 1,687-row file and the clean 1,128-row file) is labeled with one of exactly two generic, boilerplate explanation strings ("Secure SQL Injector Code" / "Secure Certificate Validation Code"), with **zero case-specific reasoning anywhere in the safe class**, while every vulnerable-labeled row has varied, case-specific text. This is direct, file-level evidence that the negative (safe) class was very likely generated in bulk rather than individually verified — a ground-truth risk that sits underneath, and is more serious than, the row-level mislabeling the two prior audits already found (Section 10).

Combined with the confirmed absence of any application/project identifier (Section 7) and the confirmed absence of any documented dataset source anywhere in the project (Section 2), the dataset **cannot currently support an application-level CWE-89 detection claim**, and its CWE-89 vulnerable-class ground truth specifically **cannot currently support a strong claim of genuine source-to-sink vulnerability at all** (Section 5) — a full-dataset audit found zero rows with defensible single-line evidence of an actual tainted-source reaching a SQL sink.

---

## 2. Dataset Provenance

| Question | Finding | Evidence | Status |
|---|---|---|---|
| Where did `dataset .csv` originate? | **Not documented anywhere in the project.** No README, data card, citation, scraping script, or collection tool references its source. | `git log --oneline --all -- 'dataset .csv'` shows exactly one commit, `e014d4f "Initial DualVulnDroid research and implementation"` — the file appears fully-formed with no prior history. Repo-wide search for "LVDAndro" and "Kaggle" across all `.md`/`.py`/`.json`/`.txt` files found **zero matches outside the literature-review reference list**, where LVDAndro is cited as *related work*, never as the source of this project's own dataset. `DualVulnDroid/src/.../ProjectFileCollector.kt` is the IDE **plugin's own live-scanning code** for a developer's open project at inference time — unrelated to how the training dataset was built. | `UNKNOWN` |
| Collection method (scraping, manual curation, synthetic generation, LLM-generated)? | Not documented. | Same search as above; no collection script exists in the repository. | `UNKNOWN` |
| License / redistribution rights? | Not documented. | No LICENSE reference tied to the dataset anywhere found. | `UNKNOWN` |
| Time period of collection? | Not documented. | No dated metadata found. | `UNKNOWN` |
| Label-generation method (human annotators, rule-based, LLM-generated)? | Not documented directly, but **strong indirect evidence** points to a bulk/templated process for the safe class specifically — see Section 10. | `dataset .csv` explanation column, quantified in Section 10. | Partially inferable from evidence, not documented |

**This is itself a rejection-level finding independent of anything else in this report.** A dataset with no stated source, license, collection method, or annotation protocol cannot be cited or defended in a peer-reviewed paper, matching the professor's review verbatim ("The dataset source is not clearly cited... no app/repository provenance, time period, collection process, license statement, annotation protocol, annotator expertise, agreement statistic, or adjudication record").

---

## 3. Dataset Composition (verified directly, not taken from either prior audit's summary)

| | Raw (`dataset .csv`) | Clean (`clean_dataset.csv` = `train.csv`+`val.csv`+`test.csv`, byte-identical row sets confirmed by direct set comparison in this session's prior work) |
|---|---|---|
| Total rows | 1,687 | 1,128 |
| `s0` (CWE-89, vulnerable) | 450 | 196 |
| `s1` (CWE-89, safe) | 439 | 176 |
| `v0` (CWE-295, vulnerable) | 448 | 426 |
| `v1` (CWE-295, safe) | 350 | 330 |
| CWE-89 total | 889 | 372 |
| CWE-295 total | 798 | 756 |
| Columns | `vulnerable_line`, `explanation`, `label` — **exactly three, confirmed by direct `pd.read_csv` inspection** | same |

**Re-verification of the full-dataset audit's headline numbers**, read directly from `full_dataset_audit_summary.json` rather than from the audit's own prose report:

```
"overall_classification_counts": {"AMBIGUOUS": 698, "DEFINITELY_SAFE": 231, "NOT_RELEVANT": 118, "DEFINITELY_VULNERABLE": 81}
"by_cwe.CWE-89.classification_counts": {"DEFINITELY_SAFE": 186, "AMBIGUOUS": 179, "NOT_RELEVANT": 7}  (no DEFINITELY_VULNERABLE key = 0)
"by_cwe.CWE-295.classification_counts": {"AMBIGUOUS": 519, "NOT_RELEVANT": 111, "DEFINITELY_VULNERABLE": 81, "DEFINITELY_SAFE": 45}
```

**These numbers match the audit's own report exactly** (total 1,128 = 81+231+698+118; CWE-89 372 = 186+179+7+0; CWE-295 756 = 519+111+81+45). The user's summary of "0 DEFINITELY_VULNERABLE for CWE-89" is **confirmed accurate**, not merely asserted.

---

## 4. Label Validity

**Label definitions** (confirmed via `backend/ml/dataset_prep.py` and direct data inspection): `s0` = CWE-89 vulnerable, `s1` = CWE-89 safe, `v0` = CWE-295 vulnerable, `v1` = CWE-295 safe. These four codes are the only schema for "label validity" — there is no severity, confidence, or multi-label field.

**Verified label-quality findings** (from the full 1,128-row audit, itself re-validated in this review — see Section 6, plus the new Section 10 finding):

- 73 of 196 `s0` rows (37.2%) are **confirmed mislabeled** — code-level evidence (parameterized queries, fully-literal hardcoded SQL, bare references to ALL-CAPS/constant-styled identifiers) directly contradicts the "vulnerable" label. 9 of these are in the frozen test set.
- 0 of 176 `s1`, 0 of 426 `v0`, 0 of 330 `v1` rows were found **definitely** mislabeled in the opposite direction — but see Section 10: this is very plausibly an absence-of-evidence result, not evidence of correctness, given the safe class's boilerplate-explanation pattern.
- 118 rows (7 CWE-89, 111 CWE-295) are **not genuine examples of their claimed CWE at all** (bare imports, or code containing no certificate-related term whatsoever despite a CWE-295 label).
- 698 rows (61.9% of the whole dataset) are **unverifiable from the information present** — neither confirmed correct nor confirmed wrong.

**Overall label-validity status: PARTIALLY VALID, CRITICAL RESERVATIONS.** The subset of labels this review can defend (81 confirmed-vulnerable CWE-295, 231 confirmed-consistent-with-code) is real and usable. The majority of the dataset's labels cannot currently be defended either way.

---

## 5. CWE-89 Validity — the central question for the professor's recommended direction

**Direct re-investigation performed for this review** (not merely re-quoting the full audit): every `s0` row's `vulnerable_line` is, without exception, a **single line of code with no surrounding method, class, or file context**. The dataset schema has no `context`, `preceding_lines`, `method_body`, or `file` field of any kind — confirmed by direct column inspection (`vulnerable_line, explanation, label` only, both raw and clean). This is a **structural, not incidental**, limitation:

- A genuine CWE-89 finding requires evidence that an **untrusted source** (e.g., `Intent.getStringExtra()`, `EditText.getText()`, a network/IPC parameter) reaches a **SQL sink** (`rawQuery`/`execSQL`/`compileStatement`) via **unparameterized string construction**. In real Android code, the source is almost always assigned on an *earlier* line than the sink call — the single-line extraction format used to build this dataset removes exactly the information needed to demonstrate that flow.
- Confirmed directly: across all 372 CWE-89 rows, only **2** contain any of the project's own recognized taint-source patterns (`Intent.getStringExtra`, `Uri.getQueryParameter`, `Bundle.getString`, `EditText.getText()`) on the same line as a SQL sink — and **both already use a fully parameterized `?`-placeholder query**, so even these two are not evidence of a vulnerability.
- **Zero rows across the entire 372-row CWE-89 class were found, by rule-based code analysis reusing the project's own `dataflow.py` source-to-sink analyzer, to contain defensible evidence of an actual exploitable SQL injection.** This is a direct, quantified, file-level finding, not an inference from absence.

**Per the explicit instruction not to call something vulnerable merely because it contains SQL/SQLite/rawQuery/concatenation/"select": this review applied that exact discipline and still found zero defensible vulnerable examples.** The 116 `s0` rows marked `AMBIGUOUS` are cases where concatenation occurs with a variable of unclear provenance (not proven safe, not proven unsafe) — genuinely undetermined, not silently counted as vulnerable.

**Conclusion: as currently constructed, this dataset does not contain a verified population of genuine CWE-89 vulnerable examples sufficient to train or evaluate a supervised classifier's ability to detect real source-to-sink SQL injection.** It may be usable for a much narrower, honestly-scoped task — see Section 15/17.

---

## 6. CWE-295 Validity

- **81 rows (19.0% of the 426 `v0` rows) are confirmed genuinely vulnerable** by the project's own structural analyzer (`analyze_cert_dataflow`), which requires a complete, self-contained implementation (e.g., an inline empty `checkServerTrusted(){}`, an always-`true` `HostnameVerifier` lambda, an unconditional `handler.proceed()`). This is real, defensible positive evidence — stronger than anything found for CWE-89.
- **45 rows (13.6% of the 330 `v1` rows) are confirmed genuinely safe** by the same analyzer (explicit delegation to the platform default verifier, `CertificatePinner` usage, an explicit `throw CertificateException`).
- **111 rows (14.7% of the 756-row class) are not certificate-validation examples at all** — 23 bare imports plus 88 rows containing no SSL/TLS/certificate-related term whatsoever.
- **519 rows (68.7%) are ambiguous** — CWE-295 is a behavioral property of a complete method body, and a single extracted line usually cannot show one.

**Conclusion: CWE-295's *positive* evidence (the 81 confirmed-vulnerable rows) is more defensible than anything found for CWE-89, but the *majority* of the class is unusable from this dataset's format, and — critically for a paper narrowed to CWE-89 as the professor recommends — CWE-295 is out of scope for that direction regardless of its own separate validity.**

---

## 7. Project/Application Provenance

**Directly searched:** every CSV column, every JSON report, the entire `backend/` source tree, `git log`, and root/module `README.md` files.

**Finding, stated in the terms required: application-level generalization cannot currently be claimed.**

- No project, repository, application, package, or file identifier exists in `dataset .csv`, `clean_dataset.csv`, `train.csv`/`val.csv`/`test.csv`, or any accompanying JSON/report. Confirmed by direct column inspection (exactly 3 columns, none of them an identifier) and confirmed explicitly in the dataset's own generation code's docstring (`backend/ml/dataset_prep.py`: *"The raw dataset ... has NO application/project identifier"*).
- The current split is **template-level**, not row-level, file-level, repository-level, or application-level. Mechanism (`backend/research_eval/data_split.py`, `backend/ml/dataset_prep.py`): rows are grouped by `normalize_code()` — lowercasing, comment stripping, and replacing string/char/number literals with placeholder tokens — and a `GroupShuffleSplit` keeps every row sharing a normalized template on one side of the split. This prevents *template* leakage (verified independently twice: `assert_no_group_leakage()` in `dataset_prep.py`, and a second, separately-computed set-intersection check in `data_split.py`'s `split_metadata.json`, both showing zero cross-split template overlap) — but it says nothing about whether two *different* templates originate from the same real application.
- **No project identifiers can be recovered from this data as it stands.** Attempting to infer them (e.g., from variable-naming style) would be invention, which this review was explicitly told not to do.

**Duplicate/near-duplicate risk, quantified from `split_metadata.json`:** 0 exact-duplicate-text rows in the clean dataset (all exact duplicates were either unique or removed as conflicting); 48 rows across 23 near-duplicate template groups within the clean dataset (correctly kept on one side of the split each, so no *template*-level leakage) — but **whether any of those 23 templates, or any of the 1,103 distinct remaining templates, share a real source application with a template on the *other* side of the split is `UNKNOWN` and cannot be determined from this dataset.**

---

## 8. Split Integrity

| Property | Status | Evidence |
|---|---|---|
| Fixed, documented seed (42) | Confirmed | `dataset_report.json`, `split_metadata.json` |
| Template-level leakage prevention | Confirmed, independently verified twice | `assert_no_group_leakage()` + `split_metadata.json`'s separate cross-split overlap check, both zero overlap |
| Row-set identity between production (`ml/data/*.csv`) and research (`research_eval_artifacts/clean_dataset.csv` + indices) pathways | Confirmed identical, verified by direct set comparison of (code, label) pairs in this session's prior work | `ml/data/{train,val,test}.csv` vs. `clean_dataset.csv` sliced by `{train,validation,test}_indices.json` |
| Application-level leakage prevention | **Not possible to verify or claim** — no application identifier exists | Section 7 |
| All 5 model-training scripts (SVM, RF, XGBoost, LSTM, CodeBERT) use the identical split | Confirmed by direct source inspection (`from research_eval.data_split import load_split` in every `train_*.py`/`*_train.py` script) | previously verified in this session, re-confirmed here |

**Verdict: PARTIALLY VALID.** The split is genuinely leak-free at the level it claims to operate at (template), and that claim is verified, not merely asserted. It is not, and cannot currently be made, an application-level split.

---

## 9. Duplicate/Near-Duplicate Risk

Already covered quantitatively in Section 7. Summary: template-level duplication is well-controlled (0 exact, 48/1,128 near-duplicate rows, all correctly grouped). Application/repository-level duplication (the same real app contributing textually-different rows to both train and test) is **`UNKNOWN`** — genuinely unknowable from this dataset's schema, not merely unverified.

---

## 10. The 559 Excluded Rows — Full Re-Investigation

**The professor's review explicitly rejected the prior explanation ("conflicting normalized templates were removed") as insufficient. This review re-investigated directly rather than accepting it.**

**Mechanism, confirmed from `backend/ml/dataset_prep.py`:** a row is excluded if its `normalize_code()`-normalized text is shared with at least one other row (anywhere in the raw 1,687) that carries a **different** label. 559 rows across 270 conflicting groups. Composition (directly counted): 254 `s0` + 263 `s1` + 22 `v0` + 20 `v1`.

**New finding from direct sampling of the actual conflicting pairs** (not present in either prior audit): examples pulled directly from `excluded_conflicting_labels.csv` —

```
[s0] "((f.t.a.g.a) bVar).f2220e.execSQL(sb.toString());"   — "Dynamic SQL with StringBuilder, injection risk"
[s1] "((f.t.a.g.a) bVar).f2220e.execSQL(sb.toString());"   — "Secure SQL Injector Code"

[v0] '@SuppressLint("TrustAllX509TrustManager") private static class TrustAllManager implements X509TrustM...'
      — "Suppresses lint warning for trust-all manager implementation with security risks."
[v1] identical text — "Secure Certificate Validation Code"

[v0] 'conn.setRequestProperty("X-Skip-Cert-Verify", "true");'  — "...indicating security bypass."
[v1] 'conn.setRequestProperty("X-Skip-Cert-Verify", "false");' — "Secure Certificate Validation Code"
```

**Quantified pattern, checked across the entire raw dataset, not just the excluded rows:**

```
RAW s1: 439/439 (100.0%) rows use the single boilerplate explanation "Secure SQL Injector Code"
RAW v1: 350/350 (100.0%) rows use the single boilerplate explanation "Secure Certificate Validation Code"
RAW s0: 450 rows, 180 distinct (case-specific) explanations, 0 boilerplate matches
RAW v0: 448 rows, 251 distinct (case-specific) explanations, 0 boilerplate matches
```

**This holds identically in the clean 1,128-row dataset** (176/176 `s1` and 330/330 `v1` rows boilerplate; 0/196 `s0` and 0/426 `v0`).

**Interpretation (clearly separated from the observed fact above):** every single "safe" example in this entire dataset — 789 rows across both raw and clean — carries one of exactly two fixed strings with zero row-specific justification, while every "vulnerable" example has individually varied, case-referencing text. This is consistent with the safe/negative class having been generated in bulk (e.g., a blanket label applied to a set of counter-example snippets) rather than being individually security-reviewed the way the vulnerable class apparently was. It is **not proof** the safe labels are wrong — the third and fourth sampled examples above (`CertificateFactory.getInstance("X.509")` alone, `CertPathValidator.getInstance("PKIX")` alone) are plausible true negatives (obtaining an instance is not itself a vulnerability) — but it is direct evidence that the safe class's labeling process differed structurally from the vulnerable class's, and was **not** individually verified in the same way. Combined with the 559-row conflict rate itself (33.1% of the raw dataset), this indicates the vulnerable and safe example pools were very likely constructed **separately and then merged**, with the merge step being the first point at which the same code snippet's presence in both pools was ever checked — explaining both the high conflict rate and its resolution via exact/near-duplicate matching rather than semantic review.

**Recommendation for the 559 rows, per the required A–E categories: D — manually adjudicate.** Neither blanket retention nor blanket exclusion is defensible from the evidence:
- **Option A (retain all)** is indefensible: many conflicts are genuine, irreconcilable label contradictions on byte-identical text (example 1, 3 above).
- **Option B (relabel)** is not possible without human judgment — this review cannot determine, from the data alone, which of a conflicting pair is correct.
- **Option C (exclude with defensible reason), the status quo,** is *procedurally* defensible for the exact-duplicate-conflict cases (a model cannot learn from contradictory identical examples), but the review agrees with the professor: silently deleting a third of the raw dataset, disproportionately from the CWE-89 class specifically (58.2% of raw CWE-89 rows excluded vs. 5.3% of raw CWE-295 rows, confirmed by direct count in prior work this session), **is a selection-bias risk that has not been characterized or disclosed as such anywhere in the project's existing documentation.**
- **Option E (impossible to determine)** applies to some individual pairs (e.g., ones where neither explanation is clearly more credible than the other) but not to the population as a whole, where the pattern in this section gives real, usable signal.

**D is the correct recommendation:** a human security reviewer, using the same evidence-based method this and the prior audits used for the retained 1,128 rows, should adjudicate each of the 270 conflicting groups, informed by the boilerplate-vs-case-specific asymmetry documented here.

---

## 11. The 698 Ambiguous Rows

Already characterized in Sections 5–6. Composition: 179 CWE-89 (concatenation with unclear-provenance variables) + 519 CWE-295 (incomplete method-body context). **This is not a defect in the auditing method — it is the honest, majority outcome of applying a strict, non-forcing evidentiary standard to a single-line, no-context dataset.** No claim in a paper should rest on these 698 rows being correctly labeled; they should be treated as unknown, not as either 231 more "safe" examples or 81 more "vulnerable" examples.

---

## 12. Test-Set Contamination Risk

**Confirmed, not merely estimated (from `full_dataset_label_audit.csv`, filtered to `current_split == "test"`):**

| | Test set (168 rows) |
|---|---|
| AMBIGUOUS | 96 (57.1%) |
| DEFINITELY_SAFE | 34 |
| DEFINITELY_VULNERABLE | 17 |
| NOT_RELEVANT | 21 (12.5%) |
| **Confirmed mislabels within DEFINITELY_SAFE** | **9** (all CWE-89 `s0`→`s1`) |

**Combining confirmed problems: 9 confirmed mislabels + 21 not-relevant rows = 30 of 168 test rows (17.9%) have a directly confirmed data-quality defect, and a further 96 (57.1%) are unverifiable.** Only 42 of 168 test rows (25.0%) are both resolved by this line of investigation and confirmed consistent with their original label. **Every reported test-set metric in every existing model comparison in this project (SVM/RF/XGBoost/LSTM/CodeBERT, and the Decision Engine's 32.74%-coverage/3.03%-FNR/94.12%-precision figures) was computed against this same 168-row test set** — meaning those figures rest on ground truth that is, at minimum, 17.9% confirmed-imperfect and 57.1% unverified. **Per the explicit instruction, this observation is not used here as a claim about model performance being wrong — it is a statement about what the test set's ground truth can and cannot be trusted to measure.**

Application-level contamination (the same real app appearing in both train and test) remains `UNKNOWN`, per Section 7 — it can be neither confirmed nor ruled out.

---

## 13. Ground-Truth Confidence

| Population | Confidence | Basis |
|---|---|---|
| 81 confirmed-vulnerable CWE-295 rows | **HIGH** | Structural analyzer confirms complete, self-contained insecure implementation |
| 73 confirmed-mislabeled CWE-89 rows (should be safe) | **HIGH** | Parameterization/constant-reference/literal-query evidence is unambiguous |
| 45 confirmed-safe CWE-295 rows | **MEDIUM-HIGH** | Structural analyzer confirms complete safe implementation |
| 113 `s1`/confirmed-consistent CWE-89 rows | **LOW-MEDIUM** | Consistent with code evidence, but see Section 10's boilerplate-explanation finding — the *original* label's own provenance is itself suspect, so "consistent with code" is closer to "not contradicted" than "independently verified" |
| 118 NOT_RELEVANT rows | **HIGH** (that they are not relevant) | Direct text inspection (bare imports / absence of any topic-relevant keyword) |
| 698 AMBIGUOUS rows | **NONE** — explicitly unresolved | By design; not forced |
| All `s1`/`v1` "safe" labels as a class, prior to individual code verification | **LOW** | 100% boilerplate-explanation finding, Section 10 |

---

## 14. What This Dataset CAN Currently Support

- A **template/snippet-level classification task**, explicitly labeled as such, distinguishing code patterns the dataset's own construction process associated with "vulnerable" vs. "safe" — with the caveat that the "safe" side's original labeling process is evidenced to have been less rigorous than the "vulnerable" side's.
- A demonstration that a deterministic source-to-sink/certificate-validation analyzer (reusing this project's own `dataflow.py`) can be applied at scale to characterize a labeled corpus and surface label-quality problems — this is itself a legitimate, if modest, methodological contribution, and this review's own work (building on the two prior audits) is existence-proof of it.
- The **81 confirmed-vulnerable CWE-295 rows and the 73 confirmed-CWE-89-mislabel corrections** are individually defensible, citable facts about this specific dataset.

## 15. What This Dataset CANNOT Currently Support

- **Any application-level or "detects real Android vulnerabilities in unseen apps" claim** — no project/application identifier exists to evaluate this claim against (Section 7).
- **A CWE-89 "our classifier learns to detect genuine SQL injection" claim** — zero rows in the entire CWE-89 class were found with defensible single-line evidence of an actual source-to-sink flow (Section 5). A classifier trained on this data's `s0`/`s1` labels is, on the evidence available, learning to distinguish *labeling artifacts* (which pool a snippet was assigned to), not vulnerability.
- **Any claim resting on the currently-reported test-set metrics as evidence the dataset itself is sound** — this would be circular; per instruction, model F1 scores are not treated here as proof of dataset validity, and the reverse (using this audit to validate or invalidate specific F1 numbers) was also out of scope for this document.
- **A reproducibility/citation claim** — the dataset has no documented source, so no other researcher could independently obtain or verify it.

## 16. Required Corrective Actions

1. **Locate and document the actual dataset source**, or explicitly state in the paper that provenance is unknown and could not be recovered — do not omit the question.
2. **Manually adjudicate the 270 conflicting-label groups (559 rows)** using two independent reviewers, informed by the boilerplate-vs-case-specific asymmetry in Section 10, with a documented conflict log — not silent re-inclusion or continued silent exclusion.
3. **Independently re-verify a sample of the "safe" (`s1`/`v1`) class** given the 100% boilerplate-explanation finding — this class's ground truth has not been shown to be reliable merely because this audit's code-analysis heuristics did not contradict it.
4. **Either recover application/project identifiers, or explicitly and permanently scope every claim to "code-template classification," never "application-level detection."**
5. **For CWE-89 specifically: acquire or construct a genuinely multi-line/contextualized vulnerable-example corpus** (real source-to-sink pairs spanning at least two lines, ideally full method bodies) before claiming the paper detects real SQL injection — this dataset's single-line format cannot support that claim regardless of any subsequent modeling work.

## 17. Whether a Conference Paper Can Safely Use This Dataset

**Not in its current form, and not for the professor's recommended CWE-89-focused direction specifically**, because that direction's central claim — detecting genuine SQL injection via source-to-sink evidence — is exactly what Section 5 found this dataset cannot currently demonstrate even one confirmed example of. Using the CWE-295 side would fare somewhat better (81 confirmed-vulnerable, structurally-verified rows exist) but CWE-295 is outside the professor's recommended scope, and 68.7% of that class is still ambiguous.

## 18. Recommended Next Experiment

**Not a modeling experiment.** The next experiment should be the manual adjudication described in Corrective Action 2 (Section 16), applied first to a **stratified sample of the 116 currently-`AMBIGUOUS` CWE-89 `s0` rows** (the population closest to potentially containing genuine, defensible vulnerable examples) to determine, with real human judgment and — if at all possible — recovered source context, how many of them can be upgraded to `DEFINITELY_VULNERABLE` with real evidence. **The answer to that question, not any model's F1 score, determines whether CWE-89 is researchable with this data at all.**

---

# DECISION TREE OUTCOME

**OPTION C: "Dataset is not scientifically adequate; a new CWE-89 dataset/evaluation corpus must be collected."**

**Why not Option A:** Option A requires that, after documented corrections, the dataset becomes sufficiently valid for a focused CWE-89 paper. But the core problem for CWE-89 is not a labeling-cleanup problem that corrections can fix — it is a **format problem**: single-line extraction with no surrounding context structurally cannot demonstrate source-to-sink flow, no matter how carefully the existing 372 rows are re-labeled. Zero of them currently have defensible vulnerable evidence, and no amount of relabeling the *existing* rows can manufacture the missing context. Adjudicating the 559 excluded rows and the 698 ambiguous rows (Sections 16, 18) is worth doing regardless, but it cannot, by itself, create the multi-line evidence CWE-89 requires.

**Why not Option B:** Option B ("usable only for template-level classification") is the honest fallback if no new data is collected, but the professor's recommended direction explicitly requires source-to-sink evidence and a deterministic data-flow analyzer as a co-equal contribution — a template-classification-only dataset cannot support that specific research design, only a much weaker "can we distinguish code patterns the dataset's original creators called vulnerable vs. safe" study, which does not answer the professor's RQ1/RQ2.

**Therefore: Option C.** A new or substantially augmented CWE-89 corpus — with real multi-line/method-level context, application/repository identifiers, and individually-verified (not boilerplate) labels for both classes — is required before the professor's recommended direction can be executed as specified. Section 19 below designs the replacement protocol, per the task's Phase 10 instruction, so this is not merely a rejection but a concrete path forward.

---

## 19. Replacement Dataset Protocol (required because Option C was selected)

**Source:** Real, license-permitting Android open-source repositories (e.g., F-Droid-listed or permissively-licensed GitHub projects), selected and recorded by `repository_id` at collection time — not reconstructed after the fact.

**Recommended record structure** (per task instruction):

```
project_id           - stable identifier for the source application
repository_id        - VCS repository identifier (e.g., GitHub owner/repo)
file_id               - stable identifier for the specific source file
file_path             - path within the repository at the recorded commit
class_name            - enclosing class
method_name            - enclosing method
language              - Java | Kotlin
code_context          - the full enclosing method body (minimum), not a single line
source                - the specific untrusted-input API call, if any, with its own line
sink                  - the specific SQL sink call (rawQuery/execSQL/compileStatement/etc.)
tainted_variable       - the variable name carrying the source's value, if traced
dataflow_path          - the recorded source -> ... -> sink chain
parameterized          - boolean: does the sink call use '?' + bind args
sanitized              - boolean/description: any escaping/validation applied
label                  - vulnerable | safe
label_confidence        - HIGH | MEDIUM | LOW, tied to how completely the flow was observed
evidence_rule           - which specific rule/reviewer decision produced the label
license                - the source repository's license
commit_hash             - exact commit the sample was extracted from
split                  - train | validation | test, assigned by project_id
```

**Split rule (mandatory, per task instruction):** the unit of assignment is the **project**, not the row or template. Every sample from one `project_id` goes to exactly one of TRAIN / VALIDATION / TEST. No project may appear in more than one split. This directly resolves the professor's core objection ("The evaluation unit is not an application") and Section 7's finding in this report.

**Labeling protocol:** two independent security reviewers per sample, with disagreement resolved by documented adjudication (not deletion), and — critically, given Section 10's finding — **the safe/negative class must be labeled with the same individual, case-specific rigor as the vulnerable class**, not a blanket/templated label. Each safe example should record *why* it is safe (e.g., "parameterized," "constant-only DDL," "no reachable sink") in the same `evidence_rule` field used for vulnerable examples, so a future audit like this one cannot find a uniform boilerplate pattern.

---

## 20. Next Experimental Protocol — CONDITIONAL, NOT YET AUTHORIZED

**Per the task's own Phase 11 instruction, this section applies only "if and only if the dataset is scientifically usable."** Given the Section-19 verdict (Option C), **this protocol is not yet authorized to run** and is recorded here only as the target design for after a valid dataset exists, matching the professor's recommended leakage-safe late-fusion methodology: text-only baselines (Linear SVM, XGBoost) trained on training-project data only, with deterministic analyzer outputs excluded from the base model's own features; independently-computed source/sink/data-flow evidence; out-of-fold base-model probabilities calibrated on validation projects; a simple, interpretable late-fusion meta-model; an abstention threshold selected on validation projects only, targeting a predeclared FNR ceiling; and a single, final evaluation on the untouched external project-level test set, compared against ML-only and rule-only baselines at matched coverage. **No part of this section should be executed before the dataset verdict above is resolved.**

---

# FINAL OUTPUT

**A. DATASET VERDICT:** INVALID for application-level or genuine-source-to-sink CWE-89 detection claims; PARTIALLY VALID for a narrowly-scoped, explicitly-caveated template-classification study; the CWE-295 side has a small (81-row) but genuinely defensible vulnerable-evidence core that CWE-89 currently lacks entirely.

**B. CWE-89 VERDICT:** Not currently researchable as "SQL injection detection" in the professor's recommended sense. Zero of 372 rows have defensible single-line source-to-sink evidence; 73 (37.2% of `s0`) are confirmed mislabeled; 179 remain genuinely unresolved. The dataset's single-line format is the root cause and cannot be fixed by relabeling alone.

**C. APPLICATION-LEVEL VALIDITY:** Cannot be claimed. No project/application/repository identifier exists anywhere in the dataset or its generation code. The current split is template-level only, independently verified leak-free *at that level*, with application-level leakage genuinely `UNKNOWN`.

**D. LABEL QUALITY:** Mixed and, for the safe class specifically, newly suspect. Vulnerable-class labels (`s0`, `v0`) carry individually-varied, case-specific explanations. **100% of safe-class labels (`s1`, `v1`) — 789 rows across raw and clean datasets — use one of exactly two boilerplate explanation strings with zero case-specific reasoning**, a pattern this review discovered and quantified directly from the files, not inherited from either prior audit.

**E. TEST-SET TRUSTWORTHINESS:** Low-to-moderate. 17.9% of the 168-row test set has a directly confirmed data-quality defect (9 mislabels + 21 not-relevant rows); a further 57.1% is unverifiable; only 25.0% is both resolved and confirmed correct. Every previously-reported test-set model metric in this project rests on this ground truth.

**F. MAIN SCIENTIFIC RISKS:** (1) Undocumented dataset provenance — cannot be cited or defended. (2) No application identifier — no application-level generalization claim is possible. (3) CWE-89's single-line format cannot demonstrate genuine vulnerability regardless of relabeling. (4) The safe class's uniform boilerplate labeling pattern undermines confidence in the "confirmed correct" `s1`/`v1` population, not just the flagged mislabels. (5) The 559-row, 33.1%-of-raw-data exclusion was performed by an automated conflict rule, never manually adjudicated, and disproportionately affected CWE-89 (58.2% of raw CWE-89 excluded vs. 5.3% of CWE-295) without that asymmetry being previously disclosed.

**G. EXACT FIXES REQUIRED:** Document the dataset's actual source or explicitly disclose it as unknown; manually adjudicate all 270 conflicting-label groups with two independent reviewers; independently re-verify a sample of the boilerplate-labeled safe class; recover application identifiers or permanently narrow every claim to template-level; and — specifically for CWE-89 — collect or construct genuinely multi-line/contextualized vulnerable examples, since no amount of work on the existing 372 rows can supply evidence they do not contain.

**H. WHETHER WE SHOULD CONTINUE WITH THE PAPER:** Not yet, and not with this dataset for the CWE-89-focused direction as specified. The professor's recommended research question (RQ1/RQ2, requiring demonstrated source-to-sink evidence) cannot currently be answered with this data. Continuing to write the paper before this is resolved would reproduce the exact "dataset validity" rejection risk the professor's review already flagged as the top-priority problem.

**I. THE NEXT 5 CONCRETE ACTIONS:**
1. Attempt to recover the dataset's true source (check with whoever originally supplied `dataset .csv`, since no in-repo evidence identifies it); if genuinely unrecoverable, plan to state this explicitly in any future paper.
2. Manually adjudicate a first batch of the 270 conflicting-label groups (start with the 254 `s0`/`s1`-conflict groups, since CWE-89 is the priority direction) using two reviewers and a written rubric.
3. Manually re-examine a random sample (e.g., 50) of the 176 `s1` boilerplate-labeled "safe" CWE-89 rows with real security judgment, to test whether the boilerplate-labeling pattern found in Section 10 corresponds to an actual elevated error rate or merely a lazy-but-correct default.
4. Scope a small pilot collection of 30–50 real, multi-line, application-identified CWE-89 examples (vulnerable and safe) from permissively-licensed repositories, following the Section 19 protocol, to test feasibility before committing to a full replacement corpus.
5. Only after 1–4 produce a defensible verified corpus, revisit whether the professor's recommended RQ1/RQ2 experimental design (Section 20) is executable — do not begin writing the paper before this checkpoint.
