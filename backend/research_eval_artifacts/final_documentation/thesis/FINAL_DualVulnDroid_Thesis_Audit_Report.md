# DualVulnDroid Final Complete Thesis — Assembly Audit Report

This report documents how the eight individually-rebuilt DualVulnDroid thesis chapters were combined, cross-checked, and corrected into `FINAL_DualVulnDroid_Complete_Thesis.docx` / `.md`. It is a build/audit record, not a ninth thesis chapter, and is not part of the thesis document itself.

## 1. Files Inspected

**Source chapter files (read in full, not modified):**
- `Chapter_01_Introduction_and_Research_Problem_DualVulnDroid.md`
- `Chapter_02_Critical_Literature_Review_and_Research_Gap_DualVulnDroid_v2.md`
- `Chapter_03_Research_and_Development_Methodology_DualVulnDroid_v2.md`
- `Chapter_04_Requirements_Analysis_and_System_Model_Design_DualVulnDroid_v2.md`
- `Chapter_05_Artefact_Design_Realisation_and_Implementation_DualVulnDroid_v2.md`
- `Chapter_06_Experimental_Results_and_Model_Evaluation_DualVulnDroid_v2.md`
- `Chapter_07_System_Testing_and_Live_Validation_DualVulnDroid_v2.md`
- `Chapter_08_Discussion_Conclusions_and_Future_Work_DualVulnDroid_v2.md`

**Other materials consulted:** `Software_Research_Thesis_Writing_Guidelines.docx` (`backend/ml/data/`); `thesis_chapter_structure.md`; the project's own `final_mobile_validation.csv`, `REMAINING_VALIDATION_ITEMS.md`, and `final_documentation/final_project_report.md`, all re-referenced only to confirm the figures already verified when each source chapter was originally written (no new project evidence was gathered for this assembly task, consistent with "synthesise, do not re-investigate").

No declaration, supervisor-approval, or acknowledgements content was found anywhere in the project. Per the instruction not to invent university-specific wording, these front-matter sections were **omitted** from the final document rather than fabricated.

## 2. Chapters Included

All eight chapters were included, in order, each starting on a new page under its own Heading-1-level chapter title. No chapter was renumbered, dropped, or merged with another.

## 3. Cross-Chapter Consistency Checks Performed

Each of the eight chapters was re-read in full (not from memory) immediately before assembly. The following checks were performed:

- **Research question:** Confirmed byte-identical between Chapter 1 (§1.5) and Chapter 8 (§8.4); Chapters 2, 3, and 6 paraphrase it consistently without altering its meaning. Verified in the final document (2 verbatim occurrences, both intentional).
- **Research aim:** Consistent single-sentence aim in Chapter 1 (§1.6), referenced consistently elsewhere.
- **Five research objectives:** Confirmed the same five objectives, in the same order and with consistent meaning, are used in Chapter 1 (§1.7), traced in Chapter 2 (Table 2.2), Chapter 3 (Table 3.1, 3.8), Chapter 4 (Table 4.6), Chapter 5 (Table 5.3), Chapter 6 (Table 6.9), and Chapter 8 (Table 8.1). No objective was reworded or renumbered between chapters.
- **Research gap:** The five gaps derived in Chapter 2 §2.14 (integration, vulnerability coverage, explainability, remediation/decision support, developer-to-end-user) are referenced consistently in Chapters 1, 3, and 8.
- **Numeric values:** Dataset (1,687 raw / 559 excluded / 1,128 clean; split 791/169/168, seed 42), feature dimensionality (7,610 = 7,587 text + 23 security), classical-model results, LSTM results, the CodeBERT provenance table, Decision Engine figures (32.74% coverage / 3.03% FNR / 94.12% precision deployed; 88.69% / 20.24% Balanced candidate; the five-seed robustness table), latency figures, and test-suite totals (323 backend / 55 Kotlin / 59 Flutter) were checked for exact-match consistency everywhere they recur. No numeric discrepancy was found among Chapters 3, 5, 6, 7, and 8 (the chapters that state these figures). All figures were verified as present, in their corrected form, in the final assembled document (Section 5 confirms this programmatically).
- **Citation consistency:** All eight chapters already used APA 7 uniformly (the pre-existing, un-rebuilt chapters in this project use a mixed APA/IEEE convention across different files, but none of those were used as a source for this assembly — only the eight rebuilt v2/final chapters were used, and all eight were already APA 7, so no re-normalisation across styles was required).

## 4. Corrections Made

Fifteen specific, exact-text corrections were applied during assembly (none alter any factual claim; all reconcile a chapter-numbering or citation-disambiguation mismatch that arose because Chapter 1 was drafted before Chapters 4–8's final titles were settled, and because Chapters 4 and 5 were drafted before Chapter 6's final content placement was settled). Each was verified present-before and absent-after in the assembled document.

1. **Chapter 1, §1.1:** "covered fully in Chapters 4–6" → "covered fully in Chapters 4–5" (implementation detail is in Ch4–5; Ch6 is experimental results, not implementation).
2. **Chapter 1, §1.7, Objective 4:** chapter cross-reference "(Chapters 5, 6)" → "(Chapters 5, 7)" (the plugin/Flutter artefact is built in Ch5 and system-tested/live-validated in Ch7, not Ch6).
3. **Chapter 1, §1.12 "Thesis Organization":** the entire paragraph was rewritten. The original text (drafted before Chapters 4–8 existed in final form) described chapters titled "System Analysis and Requirements," "System Design and Architecture," "System Implementation," and "Results and Discussion" — none of which match the actual final chapter titles ("Requirements, Analysis and System/Model Design"; "Artefact Design Realisation and Implementation"; "Experimental Results and Model Evaluation"; "Discussion, Conclusions and Future Work"). The corrected paragraph names and describes the eight chapters exactly as they were finally written.
4–5. **Chapter 1, §1.2:** two citation-author corrections, "(Android Open Source Project, n.d.)" → "(Android Developers, n.d.-a)", and "(OWASP Foundation, n.d.)" → "(OWASP Foundation, n.d.-a)", to align with the author name and disambiguation suffix used consistently in Chapters 2 and 4.
6. **Chapter 3, §3.13:** "Phase 14B through Phase 34" → "Phase 14B through Phase 33". Chapter 3 was drafted referencing a hypothetical Phase 34; Chapter 7's own direct investigation later confirmed no Phase 34 report exists anywhere in the project. Chapter 3's table (Table 3.6) already only went up to Phase 33; only the introductory prose sentence was inconsistent, and is now corrected to match.
7–10. **Chapter 4** (Table 4.1 FR-03; Table 4.2 NFR-01; §4.11 prose; Table 4.6 row 3): four instances of "Chapter 7" corrected to "Chapter 6" for the Hybrid Decision Engine's quantitative coverage/reliability results and the measured inference-latency figures. These results were ultimately written into Chapter 6 ("Experimental Results and Model Evaluation"), not Chapter 7 ("System Testing and Live Validation"); Chapters 6 and 8 already consistently cite "Chapter 6" for this content, confirming Chapter 4 (drafted earlier) was the outlier.
11–12. **Chapter 5** (Table 5.2 FR-03; Table 5.3 row 3): the same "Chapter 7" → "Chapter 6" correction, for the same reason. Notably, Chapter 5's own §5.7 prose already correctly said "Chapter 6" for this content — only its later summary tables (§5.17) had drifted to "Chapter 7," confirming this was a localised slip rather than a chapter-wide misunderstanding.
13. **Chapter 7, §7.2:** citation disambiguation, "(Android Developers, n.d.)" for the "Test apps on Android" page → "(Android Developers, n.d.-c)", since two other, different Android Developers pages are also cited elsewhere in the thesis under the same author-year key.
14–15. **Master reference list:** the three distinct Android Developers pages cited across the thesis (network security configuration; security checklist; test apps on Android) were consolidated into one master list with `n.d.-a`/`n.d.-b`/`n.d.-c` suffixes, replacing the per-chapter reference lists (which, taken individually, each cited a subset of these under an ambiguous, unsuffixed "n.d." or, in Chapter 1's case, a different author name for the same publisher).

No other textual changes were made. No number, claim, or conclusion was altered — only chapter cross-references and citation-author disambiguation.

## 5. Programmatic Verification of the Assembled Document

The generated `FINAL_DualVulnDroid_Complete_Thesis.docx` was opened and inspected with `python-docx` after generation (not merely assumed correct from the build script's exit code):

- 16 Heading-1 sections in the correct order (Abstract, Keywords, Table of Contents, List of Figures, List of Tables, List of Abbreviations, Chapters 1–8, Appendices, References).
- 137 Heading-2 subsections across the chapters and appendices.
- 51 tables, 20 embedded figures (all pre-existing, project-generated architecture diagrams and genuine device screenshots reused from the individual chapters — none newly fabricated for this assembly).
- 40 reference entries in the master list (deduplicated from the ~30–35 entries repeated with overlap across the eight individual chapters' own reference lists).
- A4 page size, 2.54 cm margins, Times New Roman 12 pt body text, 1.5 line spacing — confirmed programmatically, not assumed.
- A genuine Word `TOC` field (updates automatically or via F9/"Update Field" when opened in Word — this is standard Word behaviour, not a defect) and a `PAGE` field in the footer, both confirmed present in the underlying XML.
- Searched the full assembled text (body paragraphs and every table cell) for nine specific forbidden/obsolete phrases: "Chapter 9" (0), "12 chapters" (0), "58/61" (1 — used only inside a sentence explicitly stating this figure is *not* found in the actual evidence), "61 validation rows" / "61 rows" (0), "100% validation" (0), "100% live validation" (3 — all three are negated: "does not claim 100% live validation"), "HTTPS" (12 — all are either explicit HTTP-not-HTTPS statements or explicit future-work/recommendation language; none claim HTTPS is implemented), "fully validated" (0), "production-ready" (1 — negated: "does not claim the system is production-ready").
- Confirmed by direct text search that the CodeBERT provenance conflict, the Splash and Search-network-error NOT VALIDATED statuses, the "no human-observed IDE GUI validation" statement, the "no universal winner" model-comparison finding, and the exact verified numeric figures (dataset counts, feature dimensionality, Decision Engine coverage/FNR, test-suite totals, screenshot count, live-validation row/PASS counts) all survive intact in the assembled document.

## 6. Evidence Conflicts (Preserved, Not Resolved)

- **CodeBERT provenance conflict** (Chapter 6, §6.7; referenced in Chapters 3, 8): three project artefact directories report materially different CodeBERT metrics from an identical nominal configuration. The project's own documented resolution (treating the CPU-run `codebert/` artefact as authoritative, based on a cross-check this thesis could not itself independently re-derive) is reported, with the conflicting figures shown in full, not silently resolved or hidden. This assembly did not attempt to resolve it further.
- **Decision Engine threshold instability** (Chapter 6, Table 6.11): the Balanced candidate's cross-seed instability is reported as direct evidence, not smoothed into a single recommended figure.

## 7. Remaining Limitations (Carried Forward Unchanged)

Dataset representativeness and size; the absence of a true application-level train/test split; LSTM/CodeBERT methodological differences from the classical models; the unresolved CodeBERT provenance conflict; Decision Engine threshold instability at higher coverage; HTTP-only (not HTTPS) API transport; unavailable mobile APK upload; and the automated-test-only construct limitation are all restated, unchanged, in Chapter 8 (§8.14) and are not revisited or softened by this assembly.

## 8. Remaining NOT VALIDATED Items

Exactly two live-validation items and one structurally separate validation dimension remain open, carried forward unchanged from Chapter 7:

1. **UI-01 Splash screen** — automated-test coverage only; not observed live.
2. **Search — network-error state** — automated-test coverage only; attempted once, blocked by an unrelated emulator failure, not re-attempted.
3. **Plugin real-time annotation / Quick Fix / Scan Project — human-observed, on-screen IDE GUI validation** — no session in this research's documented history includes a person directly observing the plugin's UI inside a visible IDE window; only headless integration-test coverage exists.

## 9. Confirmation: No Source Files Modified

`git status --short` was run after assembly and confirms that only new files were created (the final combined `.md`/`.docx`, this audit report, and the intermediate build/assembly scripts and staging files listed below). No existing chapter file, source code file, dataset file, trained model file, evaluation artefact, phase report, CSV file, or screenshot was modified, moved, or deleted.

**New files created by this task:**
- `FINAL_DualVulnDroid_Complete_Thesis.md`
- `FINAL_DualVulnDroid_Complete_Thesis.docx`
- `FINAL_DualVulnDroid_Thesis_Audit_Report.md` (this file)
- `assemble_final_thesis.py`, `finalize_thesis_md.py`, `build_final_thesis_docx.py` (build scripts)
- `_front_matter.md`, `_appendices.md`, `_master_references.md`, `_assembled_chapters.md` (intermediate staging files, retained for build transparency/reproducibility)
