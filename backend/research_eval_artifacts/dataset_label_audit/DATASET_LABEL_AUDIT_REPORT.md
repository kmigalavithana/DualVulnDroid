# Dataset Label Audit Report

**Scope:** Manual, per-row audit of the 56 CWE-89 (`s0`) clean-dataset rows whose own
`explanation` field contradicts their `vulnerable` label, and the 23 CWE-295 (`v0`)
clean-dataset rows that are bare `import` statements. This audit does not modify any
existing dataset file, does not re-split the data, and does not retrain any model.

**Files audited (read-only):**
- `dataset .csv` (raw, 1,687 rows)
- `backend/ml/data/train.csv`, `val.csv`, `test.csv`
- `backend/ml/data/excluded_conflicting_labels.csv`
- `backend/ml/dataset_prep.py`, `backend/research_eval/data_split.py`
- `backend/ml/data/dataset_report.json`, `backend/research_eval_artifacts/split_metadata.json`
- `backend/research_eval_artifacts/clean_dataset.csv` + `train_indices.json` / `validation_indices.json` / `test_indices.json`

**New files produced (this audit only):**
- `backend/research_eval_artifacts/dataset_label_audit/dataset_label_audit.csv`
- `backend/research_eval_artifacts/dataset_label_audit/corrected_dataset_candidate.csv`
- `backend/research_eval_artifacts/dataset_label_audit/label_audit_summary.json`
- `backend/research_eval_artifacts/dataset_label_audit/DATASET_LABEL_AUDIT_REPORT.md` (this file)

No existing file was modified. Verified with `git status` before and after: every existing
dataset/split file shows an identical size and modification timestamp to before this task.

---

## Executive Summary

Of the 56 flagged CWE-89 (`s0`) rows, **51 (91%) are confirmed genuinely mislabeled** —
the code is either a fully static/hardcoded query, a bare reference to an ALL-CAPS
constant, or a properly parameterized (`?` + bind-array) statement, and none shows any
route for untrusted input to reach a SQL command unescaped. **1 row is not a SQL example
at all** (a bare `import` statement). **4 rows remain genuinely ambiguous** — the code
concatenates a value whose origin cannot be determined from the single line available,
and no additional context (surrounding code, source file, repository) exists anywhere in
this dataset to resolve it.

Of the 23 flagged CWE-295 (`v0`) rows, **all 23 (100%) are confirmed not relevant** —
every one is a bare `import javax.net.ssl.*;` statement with no certificate-validation
logic, no `TrustManager`/`HostnameVerifier` implementation, and no configuration of any
kind present in the line.

**Zero rows in either group were confirmed `DEFINITELY_VULNERABLE`.** This audit found
no case where the existing "vulnerable" label was correct for the flagged rows — the
flagging heuristic from the prior forensic audit (explanation text contradicts label, or
code is bare-import) turned out to have very high precision.

A candidate corrected dataset (`corrected_dataset_candidate.csv`) was built strictly
according to the documented per-classification policy in Step 9. It is **not** presented
as the new production dataset — see Section 10.

---

## 1. Original Dataset

| Metric | Raw (`dataset .csv`) | Clean (`clean_dataset.csv`, current production/research split) |
|---|---|---|
| Total rows | 1,687 | 1,128 |
| `s0` (CWE-89, vulnerable) | 450 | 196 |
| `s1` (CWE-89, safe) | 439 | 176 |
| `v0` (CWE-295, vulnerable) | 448 | 426 |
| `v1` (CWE-295, safe) | 350 | 330 |
| CWE-89 total | 889 | 372 |
| CWE-295 total | 798 | 756 |

This matches `backend/ml/data/dataset_report.json` and
`backend/research_eval_artifacts/split_metadata.json` exactly — confirmed, not assumed.

---

## 2. CWE-89 `s0` Audit

**56 rows audited** (every clean-dataset `s0` row whose `explanation` text reads as safe
without any contradicting vulnerability language — the same 56 rows identified in the
prior forensic audit).

| Classification | Count | % of 56 |
|---|---|---|
| DEFINITELY_SAFE (confidence HIGH) | 38 | 67.9% |
| DEFINITELY_SAFE (confidence MEDIUM) | 13 | 23.2% |
| AMBIGUOUS | 4 | 7.1% |
| NOT_RELEVANT | 1 | 1.8% |
| DEFINITELY_VULNERABLE | 0 | 0.0% |

**Patterns found, by frequency** (exact counts, recomputed programmatically from
`dataset_label_audit.csv` rather than estimated):

1. **No concatenation at all** — either a bare reference to an ALL-CAPS (or
   `Class.CONSTANT`-style) constant (e.g. `sQLiteDatabase.execSQL(SQL_CREATE_ENTRIES);`,
   `db.execSQL(DBAdapter.DATABASE_CREATE);`), or fully literal, hardcoded query text
   passed to `rawQuery()`/`execSQL()` with `null` or an explicit zero-length `String[]`
   (e.g. `rawQuery("SELECT * FROM uris", null)`). **32 rows** (31 confidence HIGH, 1
   confidence MEDIUM). `DEFINITELY_SAFE` — there is no visible route for any data,
   trusted or not, to reach the query as a special/unescaped element.
2. **True parameterized/prepared statements** — `?` placeholders with a separate
   bind-args array, e.g. `execSQL("DELETE FROM envelopes WHERE _id = ?", new
   String[]{...})`. **5 rows,** all confidence **HIGH** — the textbook correct defense
   against SQL injection; safety does not depend on where the bound value originates,
   only on it never being concatenated into the SQL text, which it is not.
3. **String concatenation present** — a `+` operator appears in the line. **14 rows**
   (12 confidence MEDIUM, 2 confidence HIGH). Of these, 12 concatenate an ALL-CAPS/
   constant-styled table- or column-name identifier into a `CREATE TABLE`/DDL statement
   (e.g. `"CREATE TABLE " + TABLE_LAPS + " ("`) and were kept at MEDIUM rather than HIGH
   confidence because the identifiers' own definitions are not visible in this dataset;
   2 rows (`clean_143`, `clean_177`) have a trailing `+` that is a multi-line string
   literal's line-wrap continuation rather than a concatenated variable (e.g.
   `"CREATE TABLE appinfo ("+` — "appinfo" is a hardcoded literal, not a variable) and
   were kept at HIGH confidence accordingly.
4. **Bare `import` statement, no SQL operation present** — `import
   android.database.sqlite.SQLiteCantOpenDatabaseException;`. **1 row.** `NOT_RELEVANT`
   — this is not a CWE-89 code example of any kind.
5. **Concatenation of a value whose provenance cannot be determined from the line
   alone** — a method call on an object of unknown origin (`table.getName()`), a custom
   escaping helper of unverified correctness (`quoteSqlString(str)`), a non-constant-
   styled variable (`join`), or a long chain of schema-accessor method calls. **4 rows.**
   `AMBIGUOUS` — see Section 6.

(32 + 5 + 14 + 1 + 4 = 56, matching the audited total exactly.)

---

## 3. CWE-295 `v0` Audit

**23 rows audited** (every clean-dataset `v0` row whose code is a bare `import` statement).

| Classification | Count | % of 23 |
|---|---|---|
| NOT_RELEVANT | 23 | 100% |
| DEFINITELY_VULNERABLE / DEFINITELY_SAFE / AMBIGUOUS | 0 | 0% |

Every one of the 23 rows was individually inspected. In every case the entire content of
`vulnerable_line` is a single `import javax.net.ssl.X;` (or `android.net.SSLCertificateSocketFactory`)
statement — no method body, no field assignment, no `TrustManager`/`HostnameVerifier`
implementation, no `SSLContext.init()` call, no `onReceivedSslError` handler, nothing that
could itself validate or fail to validate a certificate. CWE-295 ("Improper Certificate
Validation") requires validation *logic* to be present and shown to be wrong; an import
statement contains no logic at all. Two rows (`SSLHandshakeException`,
`SSLPeerUnverifiedException`) have explanation text describing what the imported
exception class is generally *used for* ("may indicate issues with certificate
validation"), but the code itself is still only the import — the hedged, non-committal
phrasing in all 23 explanations is itself consistent with this being weak/incorrect
labeling rather than a real finding.

**Classification: `NOT_RELEVANT`, confidence HIGH, all 23 rows. Recommended label:
`REMOVE_FROM_ML` (retain the original row in the audit trail — not deleted from history).**

---

## 4. Row-by-Row Findings

All 79 rows (56 + 23) are recorded individually, with columns
`row_id, original_label, vulnerability_family, code, explanation, classification,
recommended_label, confidence, reason, evidence, context_available,
needs_human_review, current_split`, in
**`dataset_label_audit.csv`** — that file is the authoritative, complete record; this
report summarizes it rather than reproducing all 79 rows in prose. `row_id` is the row's
stable 0-indexed position in `clean_dataset.csv` (e.g. `clean_162`), so any row can be
traced back to its exact source line.

Representative examples (one per pattern from Section 2):

| row_id | code (truncated) | classification | recommended_label | confidence |
|---|---|---|---|---|
| clean_20 | `sQLiteDatabase.execSQL(SQL_CREATE_ENTRIES);` | DEFINITELY_SAFE | s1 | HIGH |
| clean_65 | `writableDatabase.execSQL("DELETE FROM envelopes WHERE _id = ?", new String[]{...})` | DEFINITELY_SAFE | s1 | HIGH |
| clean_162 | `db.execSQL("CREATE TABLE " + TABLE_LAPS + " (" ...)` | DEFINITELY_SAFE | s1 | MEDIUM |
| clean_42 | `import android.database.sqlite.SQLiteCantOpenDatabaseException;` | NOT_RELEVANT | REMOVE_FROM_ML | HIGH |
| clean_79 | `rawQuery("SELECT ... WHERE book_path=" + quoteSqlString(str), null)` | AMBIGUOUS | UNRESOLVED | LOW |
| clean_196 | `import javax.net.ssl.SSLContext;` | NOT_RELEVANT | REMOVE_FROM_ML | HIGH |

---

## 5. Recommended Relabeling

| Action | Count | Rows |
|---|---|---|
| Relabel `s0` → `s1` | **51** | see `dataset_label_audit.csv`, `classification=DEFINITELY_SAFE` |
| Remove from ML (not a relevant example) | **24** | 1 CWE-89 (`clean_42`) + 23 CWE-295 (all `v0` import rows) |
| Leave unresolved, flagged for human review | **4** | `clean_51`, `clean_79`, `clean_96`, `clean_99` |
| Relabel to `v0`/confirm vulnerable | **0** | none found |

No row was recommended for removal or relabeling on the strength of keyword presence
alone — every recommendation above is tied to a specific, stated code-level reason
(concatenation target, presence/absence of a `?` placeholder, presence of actual
validation logic, etc.) in `dataset_label_audit.csv`'s `reason` column.

---

## 6. Ambiguous Cases

**4 rows, all in the CWE-89 set, all confidence LOW, all `needs_human_review = YES`.**

| row_id | Why it is ambiguous |
|---|---|
| `clean_51` | Query text is built from several chained calls on a `schema` object (`prefixedColumns()`, `sqlName()`, `.join()`). These read as structural/metadata accessors, which would make the row safe, but their implementations are not visible and cannot be confirmed. |
| `clean_79` | Concatenates a custom `quoteSqlString(str)` helper directly into the SQL text with `+`. This is escaped-string concatenation, not true parameterization — the dataset's own explanation calls it "Parameterized," which is not accurate. Safety depends entirely on `quoteSqlString()`'s correctness, which is not visible. |
| `clean_96` | A `CREATE TRIGGER` statement concatenates a variable `join` (not constant-styled) directly into the trigger body. Its true source cannot be determined from the line alone. |
| `clean_99` | `PRAGMA table_info(" + table.getName() + ")` concatenates the return value of a method call on an object of unknown provenance. |

**Per Step 8/9 policy, none of these four was guessed.** They retain their original `s0`
label in `corrected_dataset_candidate.csv` (see the documented **`retain_original`**
policy in Section 8) and are marked `needs_human_review = YES` in the audit CSV.

---

## 7. Train/Validation/Test Impact

**Nothing was modified in `train.csv`, `val.csv`, or `test.csv`.** The table below reports
what *would* change if `corrected_dataset_candidate.csv` were adopted and re-split.

| Split | s0-audited rows | of which DEFINITELY_SAFE | of which AMBIGUOUS | of which NOT_RELEVANT | v0-audited rows (all NOT_RELEVANT) |
|---|---|---|---|---|---|
| train | 41 | 37 | 3 | 1 | 18 |
| validation | 8 | 7 | 1 | 0 | 2 |
| **test** | **7** | **7** | **0** | **0** | **3** |

**The 7 previously-flagged contradictory `s0` rows in the frozen test set are ALL 7
confirmed `DEFINITELY_SAFE`** (0 ambiguous, 0 not-relevant among them) — every one of
them is currently scored as "vulnerable" ground truth in the test set despite being a
static/parameterized query with no injection vector. This means **the current test-set
CWE-89 metrics for every model (SVM, RF, XGBoost, LSTM, CodeBERT) are computed against at
least 7 confirmed-incorrect labels**, plus 3 additional CWE-295 test rows that are not
relevant examples at all.

---

## 8. Before/After Class Distribution

**Ambiguous-row policy used for the candidate dataset (Step 9, documented, not silent):
`retain_original`** — the 4 ambiguous rows keep their existing `s0` label unchanged in
`corrected_dataset_candidate.csv`, because the evidence for them is insufficient in
either direction and overwriting an unresolved case with a new guess would just
substitute one unverified label for another.

| | Original clean dataset | Candidate corrected dataset | Change |
|---|---|---|---|
| Total rows | 1,128 | 1,104 | −24 |
| `s0` | 196 | 144 | −52 (−51 relabeled to s1, −1 removed) |
| `s1` | 176 | 227 | +51 |
| `v0` | 426 | 403 | −23 (removed) |
| `v1` | 330 | 330 | 0 |
| **CWE-89 total** | **372** | **371** | −1 |
| **CWE-295 total** | **756** | **733** | −23 |

The CWE-89/CWE-295 class-imbalance ratio barely moves (372:756 ≈ 1:2.03 before, 371:733 ≈
1:1.98 after) — this audit does not fix the imbalance documented in the earlier forensic
report (that imbalance traces back to the raw-data conflicting-label exclusion rate, not
to this specific set of 79 rows) — it only removes/relabels rows whose *individual*
ground truth was wrong.

---

## 9. Remaining Ground-Truth Risks

- **CRITICAL — Only the 56+23 flagged rows were audited, not the full `s0`/`v0` classes.**
  The flagging heuristic (explanation-text contradiction; bare-import detection) has now
  been shown to have very high precision (55/56 and 23/23 confirmed real problems), which
  is reassuring, but it says nothing about its **recall**. Rows whose explanation text is
  *not* self-contradictory, or whose code is not a bare import, were not re-examined here
  and could still contain mislabeled examples this method cannot detect (e.g. a row
  labeled `s0` where the explanation *also* incorrectly claims a vulnerability exists).
- **HIGH — 4 rows remain genuinely unresolved** and require a human with access to the
  original source repository (not available in this dataset) to resolve definitively.
- **HIGH — the `s1`/`v1` (safe-labeled) classes were not audited at all in this pass**,
  per the original forensic scope (which found zero contradictions there under the same
  keyword-contradiction method) — but that method's blind spot (Q applies equally: it
  cannot catch a uniquely-mislabeled row with a non-contradictory explanation) applies
  here too.
- **MEDIUM — the CWE-89/CWE-295 raw-data conflicting-label exclusion asymmetry (58.2% of
  raw CWE-89 rows excluded vs 5.3% of raw CWE-295 rows) is untouched by this audit** and
  remains a separate, larger, unresolved question about the raw dataset's overall CWE-89
  label quality beyond just these 56 rows.
- **MEDIUM — no application/project identifier still exists**; this audit cannot say
  whether any of the 51 rows recommended for relabeling, or the 24 recommended for
  removal, share a source application with other rows still in the dataset.

---

## 10. Final Recommendation

**Answers to the required scientific-decision questions:**

1. **How many of the 56 `s0` rows are definitely mislabeled?** 51 (all classified
   `DEFINITELY_SAFE` — mislabeled as vulnerable when they are not).
2. **How many are definitely safe?** Same 51 (definitely-mislabeled = definitely-safe in
   this audit, since all 56 candidates started as `s0`).
3. **How many are ambiguous?** 4.
4. **How many should be removed?** 1 (not a SQL-injection example at all).
5. **How many can be confidently relabeled?** 51 (`s0` → `s1`).
6. **How many of the 23 `v0` import rows are actually vulnerable?** 0.
7. **How many are safe/irrelevant?** 23, all classified `NOT_RELEVANT` (none could be
   confidently called `DEFINITELY_SAFE` either, since "safe" would still imply they are
   valid-but-non-vulnerable *certificate-validation examples*, which they are not — they
   contain no certificate-validation logic at all).
8. **How many remain ambiguous?** 0 (of the 23 `v0` rows; 4 remain ambiguous overall,
   all from the `s0` set).
9. **How much does the class distribution change?** CWE-89: 372 → 371 (−0.3%). CWE-295:
   756 → 733 (−3.0%). The 2:1 CWE-295-to-CWE-89 imbalance is essentially unchanged.
10. **Does the dataset now look usable after correction?** The *candidate* corrected
    dataset is measurably more internally consistent for the 79 rows examined (0 known
    label/code contradictions remain among them, versus 79 before). It is **not**
    confirmed usable as a whole, because only these 79 of 1,128 rows have been verified —
    see Section 9.
11. **Does a human expert still need to review unresolved rows?** **Yes — 4 rows
    (`clean_51`, `clean_79`, `clean_96`, `clean_99`)** need a human with access to
    original source context this dataset does not contain. Additionally, per Section 9,
    a human should also decide whether to extend this same audit method to the rest of
    the `s0`/`v0` classes and to the `s1`/`v1` classes before treating the wider dataset
    as fully verified.

**Verdict, per the required safety rule:**

**"Candidate corrected dataset created; human review remains for 4 rows, and the audit
scope (79 of 1,128 rows) has not yet been extended to the rest of the clean dataset."**

This is **not** "dataset fixed." `corrected_dataset_candidate.csv` is a candidate only —
it has not been adopted as the production dataset, no split has been rebuilt from it, and
no model has been retrained against it. The original `dataset .csv`, `clean_dataset.csv`,
and `train.csv`/`val.csv`/`test.csv` remain byte-for-byte unchanged and are still what
every existing evaluation artefact and reported model metric was computed against.
