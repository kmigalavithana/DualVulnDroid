from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path

OUT = Path(r"F:\vibe cording\backend\research_eval_artifacts\final_documentation\thesis\MASTER_THESIS_CONSOLIDATION_REPORT_DualVulnDroid.docx")

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)

def set_cell(cell, text, bold=False):
    cell.text = ''
    p = cell.paragraphs[0]; r = p.add_run(str(text)); r.bold = bold; r.font.size = Pt(9)

def heading(doc, text, level=1):
    p = doc.add_heading(text, level); p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(4); return p

def para(doc, text, bold_lead=None):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(5); p.paragraph_format.line_spacing = 1.15
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold = True; p.add_run(text[len(bold_lead):])
    else: p.add_run(text)
    return p

def bullets(doc, rows):
    for text in rows:
        p = doc.add_paragraph(style='List Bullet'); p.paragraph_format.space_after = Pt(2); p.paragraph_format.line_spacing = 1.08; p.add_run(text)

def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Table Grid'
    for c, h in zip(t.rows[0].cells, headers): set_cell(c, h, True); shade(c, '1F4E78')
    for row in rows:
        cells = t.add_row().cells
        for c, value in zip(cells, row): set_cell(c, value)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t

doc = Document()
sec = doc.sections[0]; sec.top_margin = Inches(.75); sec.bottom_margin = Inches(.75); sec.left_margin = Inches(.8); sec.right_margin = Inches(.8)
styles = doc.styles
styles['Normal'].font.name = 'Aptos'; styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), 'Aptos'); styles['Normal'].font.size = Pt(10.5)
for name in ['Title','Heading 1','Heading 2','Heading 3']:
    styles[name].font.name = 'Aptos Display'; styles[name]._element.rPr.rFonts.set(qn('w:eastAsia'), 'Aptos Display')
styles['Heading 1'].font.color.rgb = RGBColor(31,78,120); styles['Heading 2'].font.color.rgb = RGBColor(31,78,120)

p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(80)
r=p.add_run('MASTER THESIS CONSOLIDATION REPORT'); r.bold=True; r.font.size=Pt(22); r.font.color.rgb=RGBColor(31,78,120)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('DualVulnDroid'); r.bold=True; r.font.size=Pt(16)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('Evidence-led thesis revision baseline'); r.italic=True; r.font.size=Pt(12)
doc.add_paragraph()
for label, value in [('Scope', 'Consolidation report only; Chapters 1–8 were not modified.'), ('Evidence basis', 'Existing thesis drafts, source inspection, stored research artifacts, and Phase 33 live-validation evidence.'), ('Status', 'Prepared for controlled thesis revision.')]:
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run(label + ': ').bold=True; p.add_run(value)
doc.add_page_break()

heading(doc, 'Executive Summary', 1)
para(doc, 'This report consolidates the verified thesis-state findings for DualVulnDroid before any chapter revision. The existing thesis package contains Chapters 1–8 and two competing Chapter 2 drafts, while the prior structure document incorrectly presents a proposed 12-chapter thesis as though it were the active final structure. The actual delivered chapter set ends at Chapter 8; Chapters 9–12 are absent. This report therefore distinguishes the current document state from the recommended final structure and records the evidence and wording constraints required for an academically defensible revision.')
para(doc, 'The system is a hybrid Android-security research prototype for SQL Injection (CWE-89) and Improper Certificate Validation (CWE-295). Its deployed classifier is XGBoost, supported by deterministic rule/data-flow evidence and SHAP-based explanation; SVM, Random Forest, LSTM and CodeBERT are research comparisons rather than production components. The Flutter application is an end-user client for account, findings, application lookup, compatibility and chatbot workflows; it is not evidence that the client performs local source-code analysis.')

heading(doc, '1. Document Inventory and Structural Reconciliation', 1)
table(doc, ['Observed item', 'Verified state', 'Consolidation implication'], [
('Current thesis chapters', 'Chapter 01 through Chapter 08 DOCX/Markdown files exist.', 'The actual delivered thesis structure is eight chapters, not twelve.'),
('Chapter 1 structure statement', 'Chapter 1 describes a 12-chapter structure.', 'Incorrect/stale relative to the present thesis package; revise only after this report is accepted.'),
('Chapter 2 drafts', 'Both “Chapter_02_Literature_Review” and “Chapter_02_Critical_Literature_Review_and_Research_Gap” exist.', 'Select the critical literature/research-gap draft as the successor, reconcile any unique material, and remove ambiguity in the final thesis manuscript.'),
('Missing Chapter 9 problem', 'No Chapter 09 testing/validation chapter file exists; no Chapters 10–12 exist.', 'Create the missing testing/validation chapter and the remaining final chapters before claiming a final 12-chapter thesis.'),
])
para(doc, 'Recommended final structure: (1) Introduction; (2) Critical Literature Review and Research Gap; (3) Methodology; (4) System Analysis and Requirements; (5) System Design and Architecture; (6) System Implementation; (7) Testing and Evaluation; (8) Results and Discussion; (9) Testing and Validation; (10) Results and Discussion synthesis; (11) Limitations and Future Work; and (12) Conclusion. This is a proposed target structure, not a statement that Chapters 9–12 already exist.')

heading(doc, '2. Literature and Research-Gap Consolidation', 1)
bullets(doc, [
'The literature review must distinguish developer-facing static-analysis/IDE work from end-user mobile-security support. The mobile/end-user literature gap is currently underdeveloped: the thesis should not imply that a Flutter interface alone closes it without a critical comparison to end-user-facing Android security assessment and decision support.',
'Chapter 2 has competing drafts. The critical-review/research-gap version better matches the required analytic purpose, but a single authoritative Chapter 2 must be declared before final pagination, references and cross-references are stabilized.',
'The contribution is best classified as an applied, evaluated systems-and-method integration contribution: leakage-conscious data preparation; a five-model comparison; a hybrid decision engine; and integration into developer and end-user interfaces. It is not evidence of a novel universally superior classifier, a general Android vulnerability detector, or completed field deployment.'
])

heading(doc, '3. Chapter-Level Staleness and Required Corrections', 1)
table(doc, ['Location', 'Finding', 'Required correction'], [
('Chapter 4', 'Mobile description is stale relative to the delivered Flutter flows and manifest-level APK compatibility/security workflow.', 'Describe the actual client/server scope and remove claims of on-device code analysis or unimplemented mobile capability.'),
('Chapter 6', 'Flutter implementation coverage is stale/incomplete.', 'Document only implemented screens and backend-mediated operations; distinguish client UX from analysis execution.'),
('Chapter 7', 'Testing numbers are stale.', 'Replace with the evidence-recorded counts and identify their phase/source rather than presenting one undifferentiated total.'),
('Phase 21 references', 'Earlier live-validation references are superseded in breadth by Phase 33.', 'Retain Phase 21 only as historical evidence and cite Phase 33 as the most comprehensive current live-validation session.'),
('All chapters', 'Several claims risk being broader than the evaluation supports.', 'Use qualified language: prototype, evaluated on the frozen 168-row test set, and limited to CWE-89/CWE-295 within the stated pipeline.')
])

heading(doc, '4. System Scope, Security Boundaries and Honest Capability Claims', 1)
para(doc, 'Transport finding: the IntelliJ plugin source uses HTTP loopback/default endpoints (including http://127.0.0.1:8000/predict and a localhost scan-line URI), not HTTPS. Thesis text must state this accurately and must not claim encrypted transport for the demonstrated plugin-to-local-backend configuration. Any deployment HTTPS statement must be framed as a requirement/future deployment control, not a validated current property.')
para(doc, 'Actual Flutter mobile application scope: the Flutter app provides JWT-backed account/session flows, dashboard and findings views, application search and details, compatibility presentation, security-chat interaction/history, settings, and backend-mediated actions. It does not itself host the production ML model or perform general local code scanning. Phase 33 validates real app/back-end/database interactions for the recorded flows, not universal device/network coverage.')
para(doc, 'APK upload scope: “Not Available” is a truthful output state where required metadata or hardware facts cannot be verified. The APK upload/scan route must be described as a backend-mediated APK manifest/permission metadata and compatibility workflow. It does not establish binary decompilation, full data-flow analysis of arbitrary APK bytecode, runtime dynamic analysis, or CWE-89/CWE-295 source-code detection within uploaded APKs.')
para(doc, 'apk_scanner.py scope: its findings are manifest-level/metadata-oriented, including permissions and Android manifest properties such as SDK and declared features. Its persisted findings are explicitly not CWE-89/295 code findings. This limitation is material and must be explicit in the thesis.')
para(doc, 'Plugin components: implemented components that can reach the configured backend are reachable only when the backend is running and accessible; live integration tests state this dependency. Components requiring the IntelliJ IDE sandbox or unavailable external runtime conditions remain unvalidated/unreachable in the recorded environment. Do not convert component existence or unit-test coverage into a claim of completed live IDE validation.')

heading(doc, '5. Research Evidence and Model Interpretation', 1)
table(doc, ['Model', 'Frozen test-set result', 'Consolidated interpretation'], [
('SVM', 'Accuracy 0.8036; Macro F1 0.7789; FNR 0.1828.', 'Strong comparison baseline; higher accuracy and lower FNR than XGBoost in this evaluation.'),
('Random Forest', 'Accuracy 0.7738; Macro F1 0.7519; FNR 0.2366.', 'Research comparator; not deployed.'),
('XGBoost', 'Accuracy 0.7917; Macro F1 0.7874; FPR 0.1467; FNR 0.2581.', 'Production model selected for the verified hybrid feature pipeline and decision-engine integration; it is not the winner of every metric.'),
('LSTM', 'Accuracy 0.7798; Macro F1 0.7448; FNR 0.1613.', 'Research-only deep-learning comparison. It has a different input representation, so comparison requires the stated fairness caveat.'),
('CodeBERT', 'Stored result variants contain a provenance conflict.', 'Research-only comparison. Resolve and document the exact artifact lineage before using one CodeBERT result as the authoritative thesis value.')
])
para(doc, 'The production distinction is mandatory: XGBoost is deployed with the 7,610-dimensional hybrid feature pipeline (7,587 text features plus 23 deterministic security/data-flow features), selected early-stopping cutoff, and current Decision Engine thresholds. The Balanced threshold configuration is a research candidate and is not deployed. SHAP explanation and deterministic rule/data-flow evidence should be described separately rather than as interchangeable explanations.')
para(doc, 'The CodeBERT provenance conflict must not be silently normalized. Multiple CodeBERT result/artifact locations exist, and the final project report identifies a resolved provenance ambiguity. The final thesis must cite one verified, reproducible artifact directory, report the associated configuration and test metrics, and label all other variants as superseded or exploratory.')

heading(doc, '6. Validation Evidence: Phase 33 as Current Live Baseline', 1)
para(doc, 'Phase 33 is the most comprehensive recorded genuine live-validation session. It reports a recovered, unmodified emulator session of approximately 1 hour 45 minutes, successful real backend/database interaction, 20 Current Live PASS items, 44 screenshots, zero application defects found/fixed, zero FAIL and one explicitly NOT VALIDATED item (Search network-error). It also records 59 Flutter tests passed / 0 failed and clean flutter analyze as unchanged historical results; these were not re-run in Phase 33 and must be cited as such.')
bullets(doc, [
'Live evidence includes re-login, vulnerability details, security-chat navigation and multi-turn use, chat-history persistence, settings, unknown-app search, compatibility outputs (NOT_AVAILABLE and INCOMPATIBLE), scrolling, keyboard use and visual overflow checks.',
'Phase 33 replaces stale summary language with item-level, screenshot-backed current evidence. Earlier Phase 14B/21/32 results remain historical evidence; they should not be double-counted into an unsupported aggregate.',
'Remaining limitation: the Search network-error path was not validated in Phase 33. Intermittent emulator/host instability remains an environment qualification rather than an application defect proven by this session.'
])

heading(doc, '7. Unsupported or Overstated Claims to Remove or Qualify', 1)
bullets(doc, [
'“Final 12-chapter thesis” — unsupported until Chapters 9–12 are created and the Chapter 1 structure is aligned.',
'“The mobile app scans Android applications/code locally” — unsupported; the implemented mobile scope is a backend-mediated end-user client, while APK scanning is manifest/metadata-level on the backend.',
'“APK upload detects CWE-89/CWE-295 in arbitrary APKs” — unsupported; manifest/permission findings are not code-level CWE findings.',
'“XGBoost is the best model” — overstated; it leads the recorded Macro F1 and lowest FPR but SVM leads accuracy and has a lower FNR.',
'“The Decision Engine improves all end-to-end detection” — unsupported; quality is better on the auto-decided subset, while deferred items materially affect all-case surfaced results.',
'“CodeBERT result is definitive” — unsupported until provenance is reconciled.',
'“HTTPS-secured plugin transport” — false for the demonstrated HTTP loopback/default configuration.',
'“Complete live validation” — unsupported; describe the exact Phase 33 scope and named not-validated item.'
])

heading(doc, '8. Exact Final Thesis Revision Order', 1)
for i, text in enumerate([
'Freeze this consolidation report as the evidence baseline; do not alter source code or Chapters 1–8 during this step.',
'Declare the authoritative Chapter 2 draft: Critical Literature Review and Research Gap; inventory/reconcile unique material from the legacy Chapter 2 draft.',
'Correct Chapter 1’s thesis-structure statement to match the actual target structure and explicitly distinguish current delivered files from planned chapters.',
'Revise Chapter 2 to strengthen the mobile/end-user literature gap and classify the contribution as evaluated applied integration, not universal novelty.',
'Revise Chapter 4 system analysis/requirements to replace the stale mobile description; add the HTTP, APK-upload and manifest-level scope boundaries.',
'Revise Chapter 5 architecture/design material as necessary for consistent pipeline scope, without inflating plugin/mobile capabilities.',
'Revise Chapter 6 implementation to document the actual Flutter application scope and reachable versus unvalidated plugin components.',
'Revise Chapter 7 testing/evaluation numbers and references: retain historical Phase 21 evidence, elevate Phase 33 as current live evidence, and preserve source/phase labels.',
'Revise Chapter 8 results/discussion to use the five-model comparison, the XGBoost-production distinction, LSTM caveat, CodeBERT provenance resolution, and qualified Decision Engine claims.',
'Create Chapter 9 Testing and Validation from the item-level evidence, including explicit NOT VALIDATED conditions and the no-double-counting rule.',
'Create Chapters 10–12 (synthesis/discussion, limitations/future work, conclusion), then perform a final cross-reference, table/figure, bibliography, numbering and claim-audit pass.'
], 1):
    p=doc.add_paragraph(style='List Number'); p.add_run(text); p.paragraph_format.space_after=Pt(3)

heading(doc, '9. Evidence Sources Consulted', 1)
bullets(doc, [
'Thesis package: Chapter_01 through Chapter_08 DOCX/Markdown documents, including both Chapter 2 variants.',
'final_documentation/thesis_chapter_structure.md; final_project_report.md; research_conclusion.md; limitations.md; testing_summary.csv; final_mobile_validation.csv.',
'final_documentation/phase21_lightweight_emulator_live_validation.md and phase33_final_live_validation.md.',
'Stored comparison, XGBoost, LSTM, CodeBERT and security-selection artifacts under backend/research_eval_artifacts/.',
'Read-only source inspection of the backend, Flutter app and IntelliJ plugin, including app.py, apk_scanner.py, compatibility.py and plugin API configuration.'
])

heading(doc, 'Conclusion', 1)
para(doc, 'The thesis should now be revised against this report as a controlled, evidence-led baseline. The priority is structural truthfulness, scope accuracy, reproducible model provenance, and phase-labelled validation evidence. No claim should be retained merely because it appeared in an earlier draft when the final artifacts demonstrate a narrower or different reality.')

section = doc.sections[0]
footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
doc.core_properties.title = 'Master Thesis Consolidation Report — DualVulnDroid'
doc.core_properties.subject = 'Evidence-led thesis revision baseline'
doc.core_properties.author = 'DualVulnDroid Research Project'
doc.save(OUT)
print(OUT)
