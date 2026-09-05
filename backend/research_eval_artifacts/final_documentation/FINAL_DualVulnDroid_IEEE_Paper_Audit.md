# FINAL_DualVulnDroid_IEEE_Conference_Paper — Audit Report

This report documents how the double-blind IEEE conference paper was produced from the supplied
`conference-template-a4.docx`, the IEEE 6-page writing guideline, the Author Compliance
Guidelines, and the completed DualVulnDroid thesis/evaluation evidence. It is a build/audit
record, not part of the paper itself.

**Addendum — exact title enforced.** After initial delivery, the user specified that the paper's
title must be used verbatim: "Dual-vulnerability Detection in Android Code: Real-time SQL
Injection and Certificate Validation Detection." All three content deliverables (DOCX, PDF, MD)
were updated to this exact string (title paragraph, Word/PDF document-properties `Title` field,
and the Markdown H1). No other section was rewritten, since the paper's existing Introduction,
Related Work, Methodology, System Design, Results, and Conclusion already address every theme the
title implies (dual-vulnerability detection, Android source code, CWE-89/SQL Injection, CWE-295/
Certificate Validation, real-time detection, ML classification, static/data-flow evidence,
explainability, the DualVulnDroid IDE plugin, and the backend-mediated end-user interface). During
this update, Word COM automation repeatedly hung when opening the DOCX specifically inside the
`final_documentation/` directory (most likely Windows Defender real-time scanning reacting to many
rapid rewrites of Office files in that folder — isolation testing showed the identical file content
opened instantly from a different folder, and a blank new document and the untouched original
template both opened instantly throughout, ruling out file corruption or a general Word-automation
fault). The fix was to rebuild and edit the document in a neutral working directory and copy the
finished file into `final_documentation/` as a plain filesystem operation, never opening the file
in that folder via Word. The rebuilt DOCX/PDF were re-verified in full: 5 pages, 28/28 references
cross-matched, all forbidden phrases absent, and no identity metadata leak.

## 1. Deliverables

| File | Path |
|---|---|
| Final Word document | `backend/research_eval_artifacts/final_documentation/FINAL_DualVulnDroid_IEEE_Conference_Paper.docx` |
| Final PDF | `backend/research_eval_artifacts/final_documentation/FINAL_DualVulnDroid_IEEE_Conference_Paper.pdf` |
| Source Markdown | `backend/research_eval_artifacts/final_documentation/FINAL_DualVulnDroid_IEEE_Conference_Paper.md` |
| This audit report | `backend/research_eval_artifacts/final_documentation/FINAL_DualVulnDroid_IEEE_Paper_Audit.md` |

The original `conference-template-a4.docx` (in the user's Downloads folder) was copied, never
edited in place; the DOCX above is a separate file built from that copy.

## 2. Files Inspected Before Writing

- `conference-template-a4.docx` (Downloads) — opened via Word COM (it is saved as **Strict
  Open XML**, which `python-docx` cannot parse — `docProps/_rels` use
  `purl.oclc.org/ooxml/...` relationship types instead of the standard transitional
  `schemas.openxmlformats.org` ones. Word COM automation was used instead for all inspection
  and construction). The template turned out to be a **filled example paper** (a "Smart Tea
  Estate Management System" paper) using the exact required IEEE section structure (I–VI), A4
  page size, 44.65 pt side margins, a 1-column title/author zone (Section 1), a 3-column
  author-block zone (Section 2, left empty in the supplied file), and a 2-column, 10 pt Times
  New Roman body (Section 4). All of its own content (title, abstract, body text, one figure,
  one equation, six references) was replaced; none of it remains in the final document
  (verified by text search — see Section 6).
- `IEEE_6_Page_Software_Research_Paper_Writing_Guideline.docx` (Downloads) — followed for
  section order, word-count targets, figure/table conventions, and the "do not alter template
  formatting to save space" rule.
- `Author-Compliance-Guidelines (1).pdf` (Downloads) — confirmed double-blind is strictly
  enforced, page count must be 4–6 inclusive, and IEEE formatting must be preserved exactly.
- `FINAL_DualVulnDroid_Thesis_Audit_Report.md`, `FINAL_DualVulnDroid_Complete_Thesis.md`, and
  the eight individual `Chapter_0X..._v2.md` files (all in
  `backend/research_eval_artifacts/final_documentation/thesis/`) — read in full for verified
  numeric evidence, methodology detail, and the master reference list. All dataset, model,
  Decision Engine, and live-validation figures used in the paper were cross-checked against
  these files and matched exactly (dataset counts, split, feature dimensionality, all five
  models' metrics, the CodeBERT provenance conflict, Decision Engine coverage/FNR/precision,
  five-seed robustness figures, latency figures, and live-validation row/PASS/NOT
  VALIDATED/Not Applicable counts).
- Real, project-generated figures under `.../thesis/`: `figure_5_1_overall_architecture.png`,
  `figure_5_5_decision_engine.png`, and `figure_ch6_5model_comparison.png` were used as Fig. 1,
  Fig. 2, and Fig. 3. No figure was fabricated or redrawn; all three are existing project
  artefacts, used unmodified as image files (only resized for column width).
- `_master_references.md` — the thesis's existing APA reference list was the source for the
  paper's IEEE-numeric reference list; 28 of its ~35 entries were selected as directly relevant
  to the compressed paper's citations and reformatted to IEEE numeric style. No reference was
  invented; author names, years, venues, and page numbers were carried over from the thesis's
  own verified list, which itself states its sources were checked against a publisher, DBLP, or
  arXiv record.

No new web research was required beyond what the thesis's own literature review had already
verified; the reference list is a curated subset of that existing, already-verified set.

## 3. Double-Blind Compliance

- The manuscript body contains no student name, supervisor name, university, department,
  faculty, email, or ORCID. The author line reads **"Anonymous Author(s)"** with a second line,
  **"Affiliation and contact details withheld for double-blind review."**
- **A real person's name was found embedded in the template's file metadata**
  (`docProps/core.xml` → `<cp:lastModifiedBy>Sameesha Anjalee</cp:lastModifiedBy>`, i.e. the
  Word "Last Author" property), left over from whoever last saved the supplied template file
  before it reached this project. This is not the student's own name. It was located by
  inspecting `BuiltInDocumentProperties` via Word COM, then removed by directly patching
  `docProps/core.xml` in the saved `.docx` (a zip archive) so the field is empty. A leftover
  placeholder title in `docProps/app.xml` ("Paper Title (use style: paper title)") was corrected
  to the paper's real title at the same time. The entire final `.docx` zip archive was then
  searched, file-by-file, for `Sameesha`, `Anjalee`, and the student's own name/initials — zero
  matches in any part (body, headers, footers, custom XML, web-extension parts).
- No acknowledgements section, no corresponding-author asterisk, and no funding footnote were
  added (none were applicable/available, and any of these could be identifying).

## 4. Page Count and Formatting Verification

- **Actual final PDF page count: 5** (within the required 4–6 inclusive range), confirmed twice
  independently: Word's own `ComputeStatistics(wdStatisticPages)` and `pypdf`'s
  `len(reader.pages)` on the exported PDF both report 5.
- A4 page size (595.32 × 841.92 pt) confirmed directly from the PDF's `MediaBox`.
- Every one of the 5 pages was rendered to a PNG at 150 dpi and visually inspected. No text
  overlaps, no clipped figures/tables, no orphaned single-column headings, no stray sample text.
- The two-column body layout, 44.65 pt margins, and Times New Roman body font were inherited
  unchanged from the template's own section formatting (Section 4 of the template document,
  which is the section whose `sectPr` — page size/margins/column count — is stored at the Word
  body level rather than attached to a paragraph, confirmed directly in the underlying XML).
  Only paragraph-level text and character formatting were changed; no section, margin, or
  column-count property was altered anywhere in the document.
- No page numbers were added (visually confirmed on all 5 rendered pages; the template's own
  footer, which carries the standard IEEE copyright-line placeholder
  "XXX-X-XXXX-XXXX-X/XX/$XX.00 ©20XX IEEE" rather than a page number, was left as supplied —
  this line is standard IEEE camera-ready boilerplate that conferences typically complete at
  production time, not authored sample content, so it was not text the brief's "remove
  sample/guidance text" instruction was understood to cover; flagged here for the user's own
  judgement).
- Two formatting defects found during the build were corrected before finalising: (1) the
  wrapped two-line title initially overlapped its own second line because the template's title
  paragraph used a fixed "exact" line-spacing tuned for a single line — fixed by setting the
  title paragraph to standard single line spacing; (2) Table I and Table II initially had
  columns too narrow for their content, causing mid-word line breaks (e.g., "Approach" →
  "Approa"/"ch", "0.7789" → "0.778"/"9") — fixed by setting explicit column widths sized to each
  column's actual content.

## 5. Content Verification Against Project Evidence

Every numeric claim in the paper was checked directly against the source chapters/audit report
listed in Section 2, not against the task brief alone:

- Dataset: 1,687 raw → 559 excluded → 1,128 clean; split 791/169/168; seed 42; leakage check
  passed — matches Chapter 3 §3.6 and the thesis audit report exactly.
- Feature dimensionality: 7,610 = 7,587 text + 23 security/data-flow — matches Chapter 3 §3.7.
- Model comparison table (Table II): all five models' Macro F1, CWE-89 F1, CWE-295 F1, FNR, FPR
  figures match Chapter 6 §6.8's comparative table exactly, including XGBoost's best macro-F1
  (0.7874)/lowest FPR (0.1467) and the LSTM's 41.4% CWE-89 FNR.
- CodeBERT provenance conflict: both the authoritative-artefact figures (0.7813/0.8246) and the
  two conflicting artefacts' figures (≈0.6047/≈0.9120) are reported, with the same
  not-independently-reproduced caveat used in Chapter 6 §6.7 and Chapter 8 §8.3.
- Decision Engine (Table III): deployed configuration (32.74% coverage / 3.03% FNR / 94.12%
  precision) and Balanced candidate (88.69% / 20.24% / 88.16%) match Chapter 6 Table 6.7
  exactly; the five-seed robustness range (88.69%–99.42% coverage, ≈5.7%–21.8% FNR) matches
  Chapter 6 Table 6.11.
- Live validation: 26 tracked rows, 23 PASS, 0 FAIL, 0 PARTIAL, 2 NOT VALIDATED (Splash;
  Search network-error), 1 Not Applicable (APK upload) — matches Chapter 7 §7.13 exactly, as
  does the Phase 32/33 narrative (Phase 32's `system_server` D-state failure attributed to host
  driver instability, not an application defect; Phase 33's ~1h45m session, 44 screenshots, 20
  new current live-PASS items).
- Latency: ≈70.03 ms (Session A) and ≈39.82 ms (Session B), explicitly stated as
  development-machine, non-comparable measurements — matches Chapter 6 §6.11.
- HTTP-only transport is stated as a current limitation in every place it is mentioned; no
  sentence in the paper claims HTTPS is implemented (see the forbidden-phrase scan below).

No project evidence was re-investigated from scratch for this paper; all of it was taken from
the already-verified thesis chapters and their own audit trail, consistent with the thesis's own
"synthesise, do not re-investigate" build discipline.

## 6. Forbidden/Unsupported Claim Scan

The final DOCX's full extracted text was programmatically searched for every phrase the brief
listed. Result (each is a genuine 0-count or an explicitly negated/future-work use):

| Phrase | Occurrences | Context |
|---|---|---|
| "100%" | 0 | — |
| "58/61", "61 rows", "61 validation rows" | 0 | — |
| "188 screenshots" | 0 | — |
| "production-ready" | 0 | — |
| "guaranteed" | 0 | — |
| "perfect" | 0 | — |
| "fully validated" / "completely validated" | 0 | — |
| "zero limitations" | 0 | — |
| "novel" | 0 | — |
| "first" (as an unsupported priority claim) | 0 | — |
| "successfully developed" | 0 | — |
| "best model" | 1 | Negated: "CodeBERT is not presented here as the best model overall" |
| "HTTPS" | 3 | All three are explicit statements that the system uses HTTP **not** HTTPS, or future-work language to migrate to HTTPS/TLS — none claims HTTPS is implemented |

## 7. Structural / Cross-Reference Verification

Verified programmatically against the extracted document text, not by inspection alone:

- Title, "Anonymous Author(s)" line, Abstract (one paragraph, no citations), Keywords, and all
  six numbered sections (I–VI) plus References are present in that order.
- **3 figures** (Fig. 1 architecture, Fig. 2 Decision Engine evidence-fusion flow, Fig. 3
  five-model comparison chart), each cited in text before/at its appearance and each with a
  caption below the figure, prefixed "Fig. N."
- **3 tables** (Table I existing-approaches comparison, Table II model-comparison results,
  Table III Decision Engine configurations), each cited in text and each with its title above
  the table, in Roman numerals.
- **28 references**, numbered by first appearance. Every citation number `[1]`–`[28]` used in
  the body has exactly one matching reference entry, and every reference entry is cited at
  least once — verified by set comparison (cited set == reference-entry set == {1..28}), with
  zero orphaned citations and zero uncited references.
- No page numbers present.

## 8. Word Count

- Word's own document statistic: **3,782 words** (whole document, i.e. narrative text +
  table/figure labels + references).
- This sits close to the guideline's own recommended "≈3,000–3,400 words of narrative text
  excluding references," once the ~780-word reference list and table/figure label text are
  subtracted, consistent with the per-section targets used while drafting (Abstract 246,
  Introduction 441, Related Work 448, Methodology 378, System Design 535, Results and
  Discussion ≈650 narrative words plus tables, Conclusion 200).

## 9. Remaining Evidence Conflicts and Limitations (Preserved, Not Resolved)

Consistent with the thesis's own discipline, these are stated in the paper itself and are not
resolved here:

- **CodeBERT provenance conflict**: the authoritative `codebert/` artefact's figures are used in
  Table II, with the two conflicting artefacts' figures and the "not independently reproduced"
  caveat stated explicitly in the Results and Discussion text.
- **Decision Engine threshold instability** at the higher-coverage Balanced configuration,
  reported as measured cross-seed evidence, not smoothed into one figure.
- **Dataset generalisation**: the split is template-level, not application-level, stated as a
  limitation in Methodology and repeated in Discussion/Conclusion.
- **HTTP-only transport**, **two remaining NOT VALIDATED mobile items** (Splash; Search
  network-error), and **no human-observed IDE GUI validation** are all stated as open
  limitations in Results/Discussion and again in the Conclusion, matching the thesis exactly.

## 10. Confirmations

- The original `conference-template-a4.docx` in Downloads was not modified (file size/timestamp
  unchanged from before this task); a copy was used as the build target.
- No thesis chapter file, source code file, dataset file, trained model artefact, evaluation
  report, phase-validation report, CSV, or screenshot was modified, moved, or deleted. `git
  status` after this task shows only three new files added under
  `final_documentation/` (the `.docx`, `.md`, and `.pdf` listed in Section 1) plus this audit
  report — every other path shown as untracked was already untracked before this task began.
- No fabricated evidence was introduced anywhere in the paper; every numerical claim traces to
  the verified thesis chapters/audit report cited in Section 5.

This paper is **not** described as "100% complete" in an unqualified sense: it is
double-blind-compliant, IEEE-A4-template-faithful, within the 4–6 page limit (5 pages),
internally consistent with the verified thesis evidence, and free of the forbidden claims
checked above — but it inherits, and states plainly, every open limitation the underlying
research itself has not yet closed (Section 9).
