"""
Assembles the eight rebuilt DualVulnDroid thesis chapters into ONE combined
markdown file (FINAL_DualVulnDroid_Complete_Thesis.md), with front matter,
appendices, and a single deduplicated master reference list.

This script only READS the existing Chapter_0X_..._v2.md (and Chapter_01's
unversioned) files and WRITES two new files in this same directory:
  - FINAL_DualVulnDroid_Complete_Thesis.md
  - FINAL_DualVulnDroid_Thesis_Audit_Report.md (corrections log only; the
    full audit report is written separately, see build notes)

No existing chapter file, source code, dataset, model, or evaluation
artefact is modified by this script.

CROSS-CHAPTER CORRECTIONS APPLIED (see audit report for full rationale):
  - Chapter 1: chapter-title mismatches in the old "Thesis Organization"
    section (written before Chapters 4-8's final titles existed);
    Objective 4's chapter cross-reference; one "Chapters 4-6" -> "4-5" scope
    reference; citation-author normalisation ("Android Open Source
    Project" -> "Android Developers", with -a/-b/-c disambiguation for
    three distinct Android Developers pages cited across the thesis;
    "OWASP Foundation, n.d." -> "n.d.-a" to match Chapter 2/4's suffixing).
  - Chapter 3: "Phase 14B through Phase 34" -> "Phase 14B through Phase 33"
    (no Phase 34 report exists anywhere in the project; Chapter 7
    confirms this directly).
  - Chapter 4 & 5: several "Chapter 7" cross-references to the Decision
    Engine's quantitative coverage/reliability results corrected to
    "Chapter 6" (the Decision Engine's numeric evaluation was ultimately
    written into Chapter 6, not Chapter 7, and Chapters 6 and 8 already
    consistently use "Chapter 6" for this - Chapters 4 and 5 were drafted
    earlier and had not been updated to match).
  - Chapter 7: "(Android Developers, n.d.)" for the distinct "Test apps on
    Android" page disambiguated to "n.d.-c".
"""
import re
from pathlib import Path

HERE = Path(__file__).parent

CHAPTER_FILES = [
    ("Chapter_01_Introduction_and_Research_Problem_DualVulnDroid.md", 1,
     "INTRODUCTION AND RESEARCH PROBLEM"),
    ("Chapter_02_Critical_Literature_Review_and_Research_Gap_DualVulnDroid_v2.md", 2,
     "CRITICAL LITERATURE REVIEW AND RESEARCH GAP"),
    ("Chapter_03_Research_and_Development_Methodology_DualVulnDroid_v2.md", 3,
     "RESEARCH AND DEVELOPMENT METHODOLOGY"),
    ("Chapter_04_Requirements_Analysis_and_System_Model_Design_DualVulnDroid_v2.md", 4,
     "REQUIREMENTS, ANALYSIS AND SYSTEM/MODEL DESIGN"),
    ("Chapter_05_Artefact_Design_Realisation_and_Implementation_DualVulnDroid_v2.md", 5,
     "ARTEFACT DESIGN REALISATION AND IMPLEMENTATION"),
    ("Chapter_06_Experimental_Results_and_Model_Evaluation_DualVulnDroid_v2.md", 6,
     "EXPERIMENTAL RESULTS AND MODEL EVALUATION"),
    ("Chapter_07_System_Testing_and_Live_Validation_DualVulnDroid_v2.md", 7,
     "SYSTEM TESTING AND LIVE VALIDATION"),
    ("Chapter_08_Discussion_Conclusions_and_Future_Work_DualVulnDroid_v2.md", 8,
     "DISCUSSION, CONCLUSIONS AND FUTURE WORK"),
]

# (chapter_number, old_substring, new_substring) - exact-match corrections
CORRECTIONS = [
    (1, "covered fully in Chapters 4–6.", "covered fully in Chapters 4–5."),
    (1, "a data-grounded security chatbot) (Chapters 5, 6).",
        "a data-grounded security chatbot) (Chapters 5, 7)."),
    (1,
     "The remainder of this thesis comprises seven further chapters. Chapter 2 (Critical Literature Review and Research Gap) reviews Android security, static/data-flow analysis, ML/DL vulnerability detection, and explainability literature to substantiate the gap above. Chapter 3 (Methodology) describes the end-to-end method, from dataset preparation through feature engineering, model comparison, and Decision Engine design, to production integration. Chapter 4 (System Analysis and Requirements) derives requirements for each component from the stated problem. Chapter 5 (System Design and Architecture) presents the resulting system, database, and pipeline architecture. Chapter 6 (System Implementation) describes how the plugin, backend, and Flutter application were built. Chapter 7 (Testing and Evaluation) reports the automated test suites and ML/Decision-Engine evaluation. Chapter 8 (Results and Discussion) synthesises these against the research questions, discusses the production model decision and limitations, and closes the thesis.",
     "The remainder of this thesis comprises seven further chapters. Chapter 2 (Critical Literature Review and Research Gap) reviews Android security, static/data-flow analysis, ML/DL vulnerability detection, and explainability literature to substantiate the gap above. Chapter 3 (Research and Development Methodology) describes the end-to-end method, from dataset preparation through feature engineering, model comparison, and Decision Engine design, to production integration. Chapter 4 (Requirements, Analysis and System/Model Design) derives requirements and a conceptual design for each component from the stated problem. Chapter 5 (Artefact Design Realisation and Implementation) traces this design into the actual, verified implementation. Chapter 6 (Experimental Results and Model Evaluation) reports the ML model comparison, Decision Engine evaluation, explainability evidence, and measured performance. Chapter 7 (System Testing and Live Validation) reports the automated test suites and the phase-by-phase live-device validation record. Chapter 8 (Discussion, Conclusions and Future Work) synthesises these results, answers the research question, evaluates the five objectives, and closes the thesis."),
    (1, "(Android Open Source Project, n.d.)", "(Android Developers, n.d.-a)"),
    (1, "(OWASP Foundation, n.d.)", "(OWASP Foundation, n.d.-a)"),
    (3, "Phase 14B through Phase 34", "Phase 14B through Phase 33"),
    (4, "Validated — Chapter 7 coverage/reliability analysis |",
        "Validated — Chapter 6 coverage/reliability analysis |"),
    (4, "sub-100ms `predict_code()` latency observed in development-machine measurements (Chapter 5) |",
        "sub-100ms `predict_code()` latency observed in development-machine measurements (Chapter 6) |"),
    (4, "those are experimental evaluation results and belong to, and are reported in full in, Chapter 7.",
        "those are experimental evaluation results and belong to, and are reported in full in, Chapter 6."),
    (4, "Decision Engine (Section 4.11) | `decision_engine.py`, `predictor.py` (SHAP) | Chapter 7 coverage/reliability analysis |",
        "Decision Engine (Section 4.11) | `decision_engine.py`, `predictor.py` (SHAP) | Chapter 6 coverage/reliability analysis |"),
    (5, "Implemented; Automated Tested; evaluated quantitatively in Chapter 7 |",
        "Implemented; Automated Tested; evaluated quantitatively in Chapter 6 |"),
    (5, "This chapter (Sections 5.7–5.8); Chapter 7 quantitative results |",
        "This chapter (Sections 5.7–5.8); Chapter 6 quantitative results |"),
    (7, "instrumented, platform-hosted tests; Android Developers, n.d.), (4)",
        "instrumented, platform-hosted tests; Android Developers, n.d.-c), (4)"),
]


def load_chapter(filename, num):
    text = (HERE / filename).read_text(encoding="utf-8")
    lines = text.splitlines()
    # Drop the 3-line title block (author / thesis title / chapter title)
    body_start = 3
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    body = "\n".join(lines[body_start:])
    # Split off the references section
    if "## References" in body:
        body, _refs = body.split("## References", 1)
    body = body.rstrip() + "\n"
    for (cnum, old, new) in CORRECTIONS:
        if cnum == num:
            if old not in body:
                raise RuntimeError(f"Correction not found in Ch{num}: {old[:60]!r}")
            body = body.replace(old, new)
    return body


def main():
    chapters_out = []
    for filename, num, title in CHAPTER_FILES:
        body = load_chapter(filename, num)
        chapters_out.append((num, title, body))
        print(f"Loaded and corrected Chapter {num} ({len(body.split())} words incl. tables)")

    out_path = HERE / "_assembled_chapters.md"
    with open(out_path, "w", encoding="utf-8") as f:
        for num, title, body in chapters_out:
            f.write(f"\n\n# CHAPTER {num:02d} – {title}\n\n")
            f.write(body)
            f.write("\n")
    print(f"Saved intermediate assembled chapters: {out_path}")


if __name__ == "__main__":
    main()
