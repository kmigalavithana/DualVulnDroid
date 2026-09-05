# Full Dataset Label Audit Report

**Scope:** Every one of the 1,128 rows in the current clean dataset
(`backend/research_eval_artifacts/clean_dataset.csv`, identical row-for-row to
`backend/ml/data/train.csv`+`val.csv`+`test.csv` combined) was independently
re-examined — not just the 56 CWE-89 + 23 CWE-295 rows from the prior narrower
audit. No original dataset, split file, or source file was modified. No model
was retrained. This report and its accompanying CSV/JSON are new files only,
in a new directory (`backend/research_eval_artifacts/full_dataset_label_audit/`);
the prior audit's `dataset_label_audit/corrected_dataset_candidate.csv` was
not touched or overwritten.

**Method.** Given the scale (1,128 rows), each row was classified by an
explicit, documented, code-grounded rule engine rather than by hand-writing
prose for every row individually, as was done for the prior 79-row audit.
Critically, this engine **reuses the project's own existing deterministic
analyzers** (`backend/dataflow.py`: `analyze_sql_dataflow`,
`sql_sink_safety_summary`, `analyze_cert_dataflow`, `SQL_SOURCES`,
`SQL_SINK_NAMES`) as read-only oracles — the same functions the production
Decision Engine and ML feature pipeline already rely on — rather than a fresh,
ad-hoc keyword scan. Where those analyzers, or the supplementary rules
built on top of them, cannot resolve a claim from a single extracted line,
the row is marked `AMBIGUOUS`, never guessed. **The engine was independently
validated against the prior 79-row manual audit before being run at scale**
(78/79 exact agreement; the single disagreement is the automated engine being
*more* conservative, not less, than the manual call — see Section 4), and
during that validation process **three genuine false-positive/false-negative
bugs were found and fixed** in the engine itself (identifier extraction that
mistook a method name for a concatenated variable; a keyword filter that
missed terms embedded in camelCase identifiers like `sslSocketFactory`; and
Kotlin string-template interpolation `${...}` being mistaken for static
literal text). This debugging process is disclosed in full because it
materially affects how much the automated results at this scale should be
trusted — see Section 9.

---

## Executive Summary

Of the full 1,128-row clean dataset:

| | Count | % of dataset |
|---|---|---|
| **DEFINITELY_VULNERABLE** | 81 | 7.2% |
| **DEFINITELY_SAFE** | 231 | 20.5% |
| **AMBIGUOUS** (insufficient context) | **698** | **61.9%** |
| **NOT_RELEVANT** (not a genuine example of the claimed CWE) | 118 | 10.5% |

**Confirmed, definite mislabels: 73** (all CWE-89, all originally labeled `s0`
"vulnerable" but confirmed by code evidence to be safe). **Recommended
removals: 118** (bare imports/declarations, or content containing no
certificate-validation-related term at all despite a CWE-295 label).
**Zero rows were found where a `v0`/`s0`-vulnerable label was confirmed
correct where the prior label said "safe,"** and — new relative to the
narrower audit — **zero rows anywhere in the 372-row CWE-89 class were found
where a genuine, single-line, source-to-sink SQL injection could be
established at all** (Section 9 explains why this is a structural property
of the single-line dataset format, not a claim that CWE-89 vulnerabilities
never existed in the original source code).

**The single most important number in this report is 61.9%**: on strict,
evidence-only standards (no forcing, no keyword-only guessing), a majority of
the entire "clean" dataset cannot be confidently verified as either correctly
or incorrectly labeled from the information available in this dataset's
single-line, no-provenance format.

---

## 1. Original Dataset

| | Rows |
|---|---|
| Total clean dataset | 1,128 |
| `s0` (CWE-89, vulnerable) | 196 |
| `s1` (CWE-89, safe) | 176 |
| `v0` (CWE-295, vulnerable) | 426 |
| `v1` (CWE-295, safe) | 330 |
| CWE-89 total | 372 |
| CWE-295 total | 756 |

Matches `backend/ml/data/dataset_report.json` and
`backend/research_eval_artifacts/split_metadata.json` exactly.

---

## 2. CWE-89 (`s0`/`s1`) Audit — 372 rows

| Classification | Count | Of `s0` (196) | Of `s1` (176) |
|---|---|---|---|
| DEFINITELY_SAFE | 186 | 73 | 113 |
| AMBIGUOUS | 179 | 116 | 63 |
| NOT_RELEVANT | 7 | 7 | 0 |
| DEFINITELY_VULNERABLE | **0** | 0 | 0 |

**Rule engine, in order:** (1) bare import/declaration → `NOT_RELEVANT`; (2)
no recognized SQL sink call (`rawQuery`/`execSQL`/`compileStatement`/`query`)
→ `AMBIGUOUS`; (3) `sql_sink_safety_summary()` confirms every sink call is a
parameterized literal → `DEFINITELY_SAFE`; (4) the sink's query argument,
isolated via the same paren/argument-splitting logic `dataflow.py` uses
internally, is a fully literal hardcoded string with no concatenation →
`DEFINITELY_SAFE`; (5) the argument is a bare reference to an ALL-CAPS or
`Class.CONSTANT`-styled identifier → `DEFINITELY_SAFE`; (6) concatenation is
present and a recognized untrusted-input source pattern
(`Intent.getStringExtra`, `Uri.getQueryParameter`, `Bundle.getString`,
`EditText.getText()`) appears in the same line → `DEFINITELY_VULNERABLE`; (7)
concatenation is present and every concatenated term is constant-styled →
`DEFINITELY_SAFE` (MEDIUM confidence); (8) otherwise → `AMBIGUOUS`.

**The headline finding: 73 confirmed mislabels, up from 56 in the narrower
audit.** The prior audit only examined rows whose `explanation` field
*already sounded safe* (a text-matching heuristic). This full, code-based
audit independently re-examined all 196 `s0` rows regardless of their
explanation wording, and found **17 additional mislabeled rows whose
explanation text did not clearly signal safety but whose code
unambiguously does** — e.g. `db.execSQL(CREATE_TABLE_CERTIFICATES);` (a bare
constant reference) and `Cursor rawQuery = this.db.rawQuery("select * from
sqlite_master", new String[0]);` (a fully literal query) were not caught by
the original explanation-text method but are just as structurally safe as
the 56 originally found.

**Zero `DEFINITELY_VULNERABLE` findings anywhere in CWE-89.** Verified
directly (not merely inferred from an absent count): across all 372 rows,
only 2 contain any recognized untrusted-input source pattern in the same
line as a SQL sink call at all (`this.mDescription.getText().toString()`,
appearing twice, from the same underlying code sample duplicated with two
different variable-naming conventions) — and **both instances already use a
fully parameterized `?`-placeholder query**, so they resolve to
`DEFINITELY_SAFE`, not `DEFINITELY_VULNERABLE`. See Section 9 for why this is
expected given the dataset's single-line format, not a surprising anomaly.

---

## 3. CWE-295 (`v0`/`v1`) Audit — 756 rows

| Classification | Count | Of `v0` (426) | Of `v1` (330) |
|---|---|---|---|
| AMBIGUOUS | 519 | 281 | 238 |
| NOT_RELEVANT | 111 | 64 | 47 |
| DEFINITELY_VULNERABLE | 81 | 81 | 0 |
| DEFINITELY_SAFE | 45 | 0 | 45 |

**Rule engine, in order:** (1) bare import/declaration → `NOT_RELEVANT`; (2)
the line contains no SSL/TLS/certificate/TrustManager/HostnameVerifier-
related term at all (checked as a substring, not a whole-word match, since
these terms are frequently embedded in camelCase identifiers like
`sslSocketFactory`) → `NOT_RELEVANT`; (3) the project's own
`analyze_cert_dataflow()` finds a complete, self-contained
HostnameVerifier/X509TrustManager/`onReceivedSslError` implementation in the
line → use its verdict directly (`VULNERABLE`→`DEFINITELY_VULNERABLE`,
`SAFE`→`DEFINITELY_SAFE`, `SUSPICIOUS`→`AMBIGUOUS`); (4) a small set of
well-known, unambiguous single-expression patterns (deprecated
`ALLOW_ALL_HOSTNAME_VERIFIER` used as a value, `new AllowAllHostnameVerifier(`,
an inline always-true verifier lambda, an inline empty
`checkServerTrusted(){}`/`checkClientTrusted(){}`) → `DEFINITELY_VULNERABLE`;
(5) a small set of well-known safe patterns (direct, unwrapped delegation to
`HttpsURLConnection.getDefaultHostnameVerifier()`, `CertificatePinner`,
an explicit `throw new CertificateException`, `handler.cancel()`) →
`DEFINITELY_SAFE`; (6) otherwise → `AMBIGUOUS`.

**Zero `DEFINITELY_SAFE` findings among `v0` rows, and zero
`DEFINITELY_VULNERABLE` findings among `v1` rows.** Unlike CWE-89, no
row's original vulnerable/safe *direction* was found to be definitely
backwards for CWE-295. The 81 `DEFINITELY_VULNERABLE` findings are all `v0`
(confirmed correct), and the 45 `DEFINITELY_SAFE` findings are all `v1`
(confirmed correct).

**111 `NOT_RELEVANT` findings — far more than the 23 previously known.** Of
these: 23 are the already-known bare `import javax.net.ssl.*;` statements;
**88 are new** — lines that reference certificate-adjacent APIs in their
surrounding context (per their original curation) but contain **no
SSL/TLS/certificate/TrustManager/HostnameVerifier-related term anywhere in
the extracted line itself**. Examples: `settings.setAllowFileAccessFromFileURLs(true);`
(a WebView file-access setting, a different security concern entirely, not
certificate validation), `AsyncHttpClient client = new AsyncHttpClient();`
(bare object construction), `KeyManagerFactory kmf =
KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());`
(client-certificate *selection*, not server-certificate *validation* — a
related but distinct concern under CWE-295's specific definition). 41 of
these 88 are labeled `v0` (vulnerable) and 47 are labeled `v1` (safe) —
roughly even, meaning this is not a one-directional labeling bias, just
category-relevance noise in both directions.

**519 rows (68.7% of the entire CWE-295 class) remain AMBIGUOUS** — the
largest single bucket in this whole audit. Section 9 explains why this
figure is so high and should be read as an honest limitation of the data
format, not a failure to try.

---

## 4. Row-by-Row Findings

All 1,128 rows are recorded individually in **`full_dataset_label_audit.csv`**
with columns `row_id, original_label, CWE, code, explanation, classification,
recommended_label, confidence, reason, evidence, needs_human_review`, plus
`current_split`, `explanation_signal`, and
`code_verdict_agrees_with_original_label` for traceability. `row_id` is the
row's stable 0-indexed position in `clean_dataset.csv`.

**Engine validation before running at scale** (full detail, since this
materially bears on trust in the results): the automated engine was first run
against the 79 rows already manually classified in the prior audit.
- **First pass: 49/79 agreement.** Two bugs found: (a) identifier extraction
  was taking the whole line's identifiers rather than isolating the SQL
  sink's actual argument, so the method name itself (`execSQL`) was being
  treated as a "concatenated variable"; (b) a bare constant argument with no
  concatenation at all (`execSQL(SQL_CREATE_ENTRIES)`) fell through every
  rule to `AMBIGUOUS` instead of being recognized as safe.
- **Second pass (after fixing argument isolation): 66/79.** Further bugs
  found: dotted `Class.CONSTANT` references (`DBAdapter.DATABASE_CREATE`)
  were being split into two separate identifier tokens by the underlying
  tokenizer, breaking the "is this a constant?" check; a bare-function-call
  form (`execSQL(db, CONSTANT)`) wasn't recognized because the sink-detection
  pattern required a preceding dot.
- **Third pass (after fixing dotted-chain handling and the bare-function
  case): 75/79.** One remaining bug: a chained-call receiver
  (`oldDB.getReadableDatabase().rawQuery(...)`) was wrongly treated as the
  bare-function-call form because the character immediately before the whole
  matched substring was checked, not the character immediately before the
  sink *name* itself.
- **Fourth pass (after fixing the receiver-detection logic): 78/79.**
- **Separately, a broader spot-check** (not limited to the known 79 rows)
  found three more issues, all fixed: (i) `ALLOW_ALL_HOSTNAME_VERIFIER`
  matched even when it was merely the *name* of a constant whose actual
  value was the safe default verifier; (ii) `getDefaultHostnameVerifier()`
  matched as "safe" even when its result was passed through an unknown,
  possibly-unsafe wrapper function rather than used directly; (iii) Kotlin
  string-template interpolation (`"...${schema.feeds.prefixedColumns(FEEDS)}..."`)
  was being treated as static literal text by the (Java-oriented) string-
  literal parser, wrongly classifying a dynamic expression as a hardcoded
  literal.
- **The one remaining disagreement** (row `clean_164`,
  `db.execSQL("CREATE TABLE " + alarmsTableName + " (" + ...)`) is the
  automated engine correctly declining to extend the "constant-styled"
  leniency to a camelCase variable name (`alarmsTableName`) the way the
  original manual audit's judgment call did — the automated result here is
  *more* conservative than the manual one, not a regression.

This debugging trail is disclosed in full so the reader can judge the
engine's reliability from direct evidence rather than a bare summary
statistic.

---

## 5. Recommended Relabeling

| Action | Count |
|---|---|
| Relabel `s0` → `s1` (CWE-89, confirmed mislabeled) | **73** |
| Remove: bare import/declaration, no operation present | 30 (7 CWE-89 + 23 CWE-295) |
| Remove: CWE-295-labeled but contains no certificate-related content | 88 |
| Leave unresolved (AMBIGUOUS), flagged for human review | 698 |
| Relabel `v0`↔`v1` (CWE-295 direction reversal) | **0** |

No CWE-295 row's vulnerable/safe direction was found definitively reversed —
the CWE-295 problem is entirely one of *relevance* (many rows are not
genuine certificate-validation examples at all) and *unverifiability*
(most of the rest cannot be resolved from a single line), not of the
vulnerable/safe label itself being backwards.

---

## 6. Ambiguous Cases

**698 rows (61.9% of the dataset).** These are not a single homogeneous
group; the dominant patterns are:

- **CWE-89 (179 rows):** concatenation of a variable that is neither
  ALL-CAPS/constant-styled nor a recognized external-input source pattern
  (e.g. a lowercase local variable, a method call whose return value's
  provenance is unknown, a cast expression) — genuinely could be a constant
  or genuinely could be tainted data, and this dataset provides no way to
  tell from the extracted line alone.
- **CWE-295 (519 rows, the largest bucket in the whole audit):**
  overwhelmingly, lines that reference a certificate-related API but do not
  contain a complete, self-contained validation implementation. CWE-295 is a
  *behavioural* weakness — whether `checkServerTrusted()` actually validates
  depends on its full method body, which a single extracted line essentially
  never contains unless the whole implementation happens to fit on one
  physical line (rare, but the 81 confirmed `DEFINITELY_VULNERABLE` and 45
  `DEFINITELY_SAFE` findings show it does happen often enough to matter).
  This structural mismatch between what CWE-295 requires to verify and what
  a single-line dataset can supply is, by row count, the single largest
  finding of this entire audit.

Per the audit policy, **none of the 698 was forced toward a label.** All
retain their original label in `final_candidate_dataset.csv` (the documented
`retain_original` policy — see Section 8) and are marked
`needs_human_review = YES`.

---

## 7. Train/Validation/Test Impact

**Nothing was modified in `train.csv`, `val.csv`, or `test.csv`.** The table
below reports what the audit found within each split, for information only.

| Split | Rows | AMBIGUOUS | DEFINITELY_SAFE | DEFINITELY_VULNERABLE | NOT_RELEVANT |
|---|---|---|---|---|---|
| train | 791 | 489 (61.8%) | 164 | 54 | 84 |
| validation | 169 | 113 (66.9%) | 33 | 10 | 13 |
| **test** | **168** | **96 (57.1%)** | 34 | 17 | 21 |

**Confirmed mislabels (disagreements) by split: train 52, validation 12,
test 9.** All 9 test-set mislabels are CWE-89 `s0` rows confirmed
`DEFINITELY_SAFE` (up from the 7 identified in the prior, narrower audit —
2 more found: `clean_1` and `clean_2`, both fully literal `rawQuery()` calls
whose explanations did not use safe-sounding language but whose code
unambiguously shows no injection vector). All 9 are listed by `row_id` in
`full_dataset_label_audit.csv`.

**Combining confirmed problems in the test set alone:** 9 confirmed
mislabels + 21 `NOT_RELEVANT` rows = **30 of 168 test rows (17.9%) have a
confirmed data-quality problem**, and a further 96 of 168 (57.1%) are
unverifiable from available evidence. Only **42 of 168 test rows (25.0%)**
are both resolved by this audit *and* confirmed consistent with their
original label.

---

## 8. Before/After Class Distribution

**Ambiguous-row policy (Step 9, documented): `retain_original`** — all 698
ambiguous rows keep their existing label unchanged in
`final_candidate_dataset.csv`, for the same reason as the prior audit: there
is not enough evidence to justify overwriting an unresolved label with a new
guess.

| | Original clean dataset | Final candidate dataset | Change |
|---|---|---|---|
| Total rows | 1,128 | 1,010 | −118 |
| `s0` | 196 | 116 | −80 (−73 relabeled to s1, −7 removed) |
| `s1` | 176 | 249 | +73 |
| `v0` | 426 | 362 | −64 (removed) |
| `v1` | 330 | 283 | −47 (removed) |
| **CWE-89 total** | **372** | **365** | −7 |
| **CWE-295 total** | **756** | **645** | −111 |

The CWE-89/CWE-295 class ratio shifts from 372:756 (≈1:2.03) to 365:645
(≈1:1.77) — a small move toward better balance, driven almost entirely by
removing CWE-295's 111 not-relevant rows, not by any change to CWE-89's
size (which only drops by 7).

---

## 9. Remaining Ground-Truth Risks

- **CRITICAL — 61.9% of the entire clean dataset is unverifiable from this
  audit's evidence, not merely the previously-known 79 rows.** This is the
  central, dataset-wide finding: strict, non-forced, evidence-based auditing
  at full scale converts the vast majority of the dataset from "assumed
  correct" to "unknown." That is a categorically different, much larger
  finding than the prior audit's narrower 79-row result.
- **CRITICAL — CWE-89's single-line format appears structurally unable to
  capture genuine end-to-end SQL injection.** Zero `DEFINITELY_VULNERABLE`
  findings across all 372 rows is not evidence that CWE-89 vulnerabilities
  never existed in the underlying source applications — it is evidence that
  extracting one line per example, without the preceding line(s) where a
  tainted variable is typically first assigned from user input, removes the
  very information needed to demonstrate a source-to-sink flow. This is a
  fundamental format limitation of the dataset as currently constructed, not
  a claim about the original (unseen) source code.
- **HIGH — the 73 confirmed CWE-89 mislabels are a lower bound, not a final
  count.** They were found because the code-level evidence for them was
  unambiguous (bare constants, fully-literal queries, true parameterization,
  or constant-only concatenation). The 179 CWE-89 rows now marked AMBIGUOUS
  include cases that may, on human review with more context, turn out to be
  further mislabels; this audit does not claim otherwise.
- **HIGH — CWE-295's 519 AMBIGUOUS + 111 NOT_RELEVANT rows (88.3% of the
  entire 756-row class) mean the large majority of the "certificate
  validation" half of this dataset is either unverifiable or not actually
  about certificate validation.** Only 126 of 756 CWE-295 rows (16.7%) were
  resolved to a definite, code-confirmed verdict.
- **MEDIUM — this audit's own rule engine required four rounds of bug-fixing
  before it agreed with the (much more carefully, manually reasoned) prior
  79-row audit at 78/79.** The remaining, unfixed edge cases in a rule
  engine of this complexity applied to 1,128 rows cannot be assumed to be
  zero; Section 4's disclosed debugging trail is offered so this can be
  judged directly rather than taken on faith.
- **MEDIUM — the `s1`/`v1` (safe-labeled) classes were audited with the same
  rigor as `s0`/`v0` this time** (unlike the prior, narrower audit), and no
  hidden vulnerable-but-labeled-safe rows were confirmed — but 63 `s1` rows
  and 238 `v1` rows are themselves AMBIGUOUS, so this is an absence-of-
  evidence result, not evidence-of-absence.
- **LOW-MEDIUM — no application/project identifier still exists** (carried
  forward from the prior audit); this remains outside what any label audit
  of this dataset's schema can resolve.

---

## 10. Final Recommendation

**Answers to the required summary statistics:**

- **TOTAL CLEAN DATASET:** 1,128
- **DEFINITELY VULNERABLE:** 81 (all CWE-295, all confirmed consistent with
  their original `v0` label)
- **DEFINITELY SAFE:** 231 (186 CWE-89 + 45 CWE-295; of the 186 CWE-89, 73
  are confirmed mislabels and 113 are confirmed-consistent `s1` rows; all 45
  CWE-295 are confirmed-consistent `v1` rows)
- **AMBIGUOUS:** 698 (179 CWE-89 + 519 CWE-295)
- **NOT RELEVANT:** 118 (7 CWE-89 + 111 CWE-295)
- **POTENTIAL MISLABELS (confirmed, definite):** 73 — all CWE-89 `s0`→`s1`
- **RECOMMENDED REMOVALS:** 118
- **RECOMMENDED RELABELS:** 73

**Separately for CWE-89:** 372 total — 0 vulnerable, 186 safe (73 of which
are corrected mislabels), 179 ambiguous, 7 not relevant.

**Separately for CWE-295:** 756 total — 81 vulnerable (all confirmed
correct), 45 safe (all confirmed correct), 519 ambiguous, 111 not relevant.

**Is the entire dataset now scientifically trustworthy?** **No — and this
audit's own scale-up from 79 to 1,128 rows is itself the evidence for that
answer.** The infrastructure (splitting, leakage prevention, cross-model
consistency) remains sound, as established in the earlier forensic audit.
But at full-dataset scale, strict evidence-based auditing does not converge
toward "the rest of the dataset is fine" — it converges toward "most of the
dataset's individual row-level correctness cannot currently be verified at
all," which is a materially more serious and more general finding than "56
(now 73) specific rows are wrong."

**Does a human expert still need to review unresolved rows?** **Yes — for
698 rows**, a number too large for this audit, or any similarly-scoped
follow-up automated pass, to responsibly resolve alone. Meaningful further
resolution would most plausibly require either (a) recovering additional
context per row (surrounding code, source file, source application) that
does not currently exist anywhere in this dataset, or (b) a human security
reviewer manually reading each ambiguous line with domain judgment this
audit's rules deliberately declined to substitute for.

**Verdict, per the required safety rule:**

**"Candidate corrected dataset created; human review remains for 698 rows
(61.9% of the dataset), and this full-scale audit indicates the dataset's
verifiable-correctness problem is substantially larger than the prior
79-row audit suggested — not smaller or better-bounded."**

This is **not** "dataset fixed." `final_candidate_dataset.csv` is a
candidate only — 1,010 rows with 73 corrected CWE-89 labels and 118 rows
removed as not relevant to their claimed CWE, while 698 rows remain exactly
as originally labeled because the evidence to change them does not exist in
this dataset. The original `dataset .csv`, `clean_dataset.csv`, and
`train.csv`/`val.csv`/`test.csv` remain byte-for-byte unchanged and are
still what every existing evaluation artefact and reported model metric was
computed against. No model has been retrained on any candidate dataset from
either audit.
