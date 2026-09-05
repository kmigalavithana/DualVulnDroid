"""
Builds FINAL_DualVulnDroid_Complete_Thesis.docx from
FINAL_DualVulnDroid_Complete_Thesis.md (itself produced by
assemble_final_thesis.py + finalize_thesis_md.py). Formatting only - no
content decisions are made here; the markdown file is the single source
of truth. This script creates a NEW file and does not modify any of the
eight individual rebuilt chapter files, their own docx renderings, or
any project source/data/model/evaluation artefact.

Adapted from build_chapter07_new_docx.py, extended with:
  - a dedicated title page
  - a real Word TOC field (updates on open/F9 in Word, standard behaviour)
  - List of Figures / List of Tables / List of Abbreviations as plain,
    left-aligned, non-justified line lists
  - a page break before every top-level ("# ") heading
  - "## APPENDIX X" sub-headings inside the Appendices section
"""
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Cm, Mm, RGBColor

HERE = Path(__file__).parent
MD_PATH = HERE / "FINAL_DualVulnDroid_Complete_Thesis.md"
OUT_PATH = HERE / "FINAL_DualVulnDroid_Complete_Thesis.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(12)
LINE_SPACING = 1.5


def _set_run_font(run, font_name=BODY_FONT):
    run.font.name = font_name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)


def add_rich_runs(paragraph, text, size=BODY_SIZE):
    tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            run = paragraph.add_run(tok[2:-2])
            run.bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            run = paragraph.add_run(tok[1:-1])
            _set_run_font(run, "Courier New")
            run.font.size = size
            continue
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            run = paragraph.add_run(tok[1:-1])
            run.italic = True
        else:
            run = paragraph.add_run(tok)
        run.font.size = size
        _set_run_font(run)


def set_body_paragraph_format(paragraph, space_after=Pt(12), justify=True):
    paragraph.paragraph_format.line_spacing = LINE_SPACING
    paragraph.paragraph_format.space_after = space_after
    paragraph.paragraph_format.space_before = Pt(0)
    if justify:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def add_page_number_field(paragraph):
    run = paragraph.add_run()
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = 'PAGE'
    fld_sep = OxmlElement('w:fldChar')
    fld_sep.set(qn('w:fldCharType'), 'separate')
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(fld_end)


def add_toc_field(paragraph):
    run = paragraph.add_run()
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = 'TOC \\o "1-2" \\h \\z \\u'
    fld_sep = OxmlElement('w:fldChar')
    fld_sep.set(qn('w:fldCharType'), 'separate')
    placeholder = OxmlElement('w:t')
    placeholder.text = "Right-click and choose “Update Field” (or press F9) to generate the Table of Contents."
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    r2 = paragraph.add_run()
    r2._r.append(placeholder)
    run2 = paragraph.add_run()
    run2._r.append(fld_end)


def set_cell_shading(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def is_caption_line(line):
    return bool(re.match(r"^\*\*(Table|Figure|Code Snippet) [A-Z]?\.?\d*\.?\d+\.", line))


IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")


def add_page_break(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    br = OxmlElement('w:br')
    br.set(qn('w:type'), 'page')
    run._r.append(br)


def main():
    text = MD_PATH.read_text(encoding="utf-8")

    doc = Document()

    section = doc.sections[0]
    section.page_height = Mm(297)
    section.page_width = Mm(210)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = BODY_SIZE
    normal.paragraph_format.line_spacing = LINE_SPACING
    normal.paragraph_format.space_after = Pt(12)
    rPr = normal.element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), BODY_FONT)
    rFonts.set(qn('w:hAnsi'), BODY_FONT)
    rFonts.set(qn('w:cs'), BODY_FONT)

    BLACK = RGBColor(0, 0, 0)

    h1 = doc.styles["Heading 1"]
    h1.font.name = BODY_FONT
    h1.font.size = Pt(16)
    h1.font.bold = True
    h1.font.color.rgb = BLACK
    h1.paragraph_format.space_before = Pt(0)
    h1.paragraph_format.space_after = Pt(18)
    h1.paragraph_format.line_spacing = LINE_SPACING

    h2 = doc.styles["Heading 2"]
    h2.font.name = BODY_FONT
    h2.font.size = Pt(14)
    h2.font.bold = True
    h2.font.color.rgb = BLACK
    h2.paragraph_format.space_before = Pt(18)
    h2.paragraph_format.space_after = Pt(10)
    h2.paragraph_format.line_spacing = LINE_SPACING

    list_num = doc.styles["List Number"]
    list_num.font.name = BODY_FONT
    list_num.font.size = BODY_SIZE
    list_num.font.color.rgb = BLACK
    list_num.paragraph_format.line_spacing = LINE_SPACING

    footer = section.footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_number_field(footer_p)

    # ---- Title page ----
    tp_match = re.search(r"%%TITLEPAGEBLOCK%%\n(.*?)\n%%ENDTITLEPAGEBLOCK%%", text, re.DOTALL)
    title_lines = [l for l in tp_match.group(1).split("\n") if l.strip()]
    text = text[:tp_match.start()] + text[tp_match.end():]

    # title_lines[0]=full title, [1]=subtitle, [2]=system name, [3]=author,
    # [4]=degree statement, [5]=year
    spacers_before = [Pt(40), Pt(6), Pt(30), Pt(60), Pt(30), Pt(60)]
    sizes = [Pt(18), Pt(14), Pt(15), Pt(14), Pt(12), Pt(13)]
    bolds = [True, False, True, True, False, True]
    for idx, line_text in enumerate(title_lines):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = spacers_before[idx] if idx < len(spacers_before) else Pt(12)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.2
        run = p.add_run(line_text)
        run.font.size = sizes[idx] if idx < len(sizes) else Pt(12)
        run.bold = bolds[idx] if idx < len(bolds) else False
        _set_run_font(run)
    add_page_break(doc)

    body_lines = text.strip("\n").splitlines()

    numbered_list_buffer = []

    def flush_numbered_list():
        nonlocal numbered_list_buffer
        for item_text in numbered_list_buffer:
            lp = doc.add_paragraph(style="List Number")
            lp.paragraph_format.line_spacing = LINE_SPACING
            lp.paragraph_format.space_after = Pt(8)
            lp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_rich_runs(lp, item_text)
        numbered_list_buffer = []

    def is_table_row(s):
        return s.startswith("|") and s.endswith("|")

    def is_table_separator(s):
        return bool(re.match(r"^\|[\s\-:|]+\|$", s))

    def add_code_block(code_lines):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"
        cell = table.rows[0].cells[0]
        set_cell_shading(cell, "F2F2F2")
        cell.paragraphs[0].text = ""
        for idx, code_line in enumerate(code_lines):
            p = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(code_line if code_line else " ")
            run.font.size = Pt(9.5)
            _set_run_font(run, "Courier New")
        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(10)

    plain_list_mode = False  # for List of Figures/Tables/Abbreviations
    in_references = False
    first_h1_seen = False

    i = 0
    while i < len(body_lines):
        raw = body_lines[i]
        line = raw.strip()
        i += 1

        if line == "%%TOCFIELD%%":
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = LINE_SPACING
            add_toc_field(p)
            continue

        if line.startswith("```"):
            flush_numbered_list()
            code_lines = []
            while i < len(body_lines) and not body_lines[i].strip().startswith("```"):
                code_lines.append(body_lines[i])
                i += 1
            i += 1
            add_code_block(code_lines)
            continue

        if not line:
            continue

        if line.startswith("# "):
            flush_numbered_list()
            heading_text = line[2:].strip()
            if first_h1_seen:
                add_page_break(doc)
            first_h1_seen = True
            hp = doc.add_paragraph(style="Heading 1")
            hp.add_run(heading_text)
            lower = heading_text.lower()
            in_references = lower.startswith("references")
            plain_list_mode = lower.startswith("list of figures") or \
                lower.startswith("list of tables") or \
                lower.startswith("list of abbreviations") or \
                lower.startswith("keywords")
            continue

        if line.startswith("## "):
            flush_numbered_list()
            heading_text = line[3:].strip()
            hp = doc.add_paragraph(style="Heading 2")
            hp.add_run(heading_text)
            continue

        if is_caption_line(line):
            flush_numbered_list()
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cp.paragraph_format.space_after = Pt(6)
            cp.paragraph_format.space_before = Pt(4)
            run = cp.add_run(line.strip("*"))
            run.italic = True
            run.bold = True
            run.font.size = Pt(11)
            _set_run_font(run)
            continue

        img_match = IMAGE_RE.match(line)
        if img_match:
            flush_numbered_list()
            img_path = HERE / img_match.group(2)
            ip = doc.add_paragraph()
            ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
            ip.paragraph_format.space_after = Pt(14)
            run = ip.add_run()
            # Portrait phone screenshots (Ch7) need a narrower width than
            # landscape architecture diagrams (Ch4-6); detect by filename.
            width = Cm(7.2) if "phase3" in img_match.group(2) else Cm(14.5)
            run.add_picture(str(img_path), width=width)
            continue

        if is_table_row(line):
            flush_numbered_list()
            table_lines = [line]
            while i < len(body_lines) and is_table_row(body_lines[i].strip()):
                table_lines.append(body_lines[i].strip())
                i += 1
            header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
            data_rows = []
            for tl in table_lines[1:]:
                if is_table_separator(tl):
                    continue
                data_rows.append([c.strip() for c in tl.strip("|").split("|")])

            table = doc.add_table(rows=1 + len(data_rows), cols=len(header_cells))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.style = "Table Grid"
            table.autofit = True

            for c_idx, htext in enumerate(header_cells):
                cell = table.rows[0].cells[c_idx]
                cell.paragraphs[0].text = ""
                p = cell.paragraphs[0]
                run = p.add_run(htext)
                run.bold = True
                run.font.size = Pt(9.5)
                _set_run_font(run)
                p.paragraph_format.line_spacing = 1.1
                set_cell_shading(cell, "D9D9D9")

            for r_idx, row_vals in enumerate(data_rows, start=1):
                for c_idx, val in enumerate(row_vals):
                    cell = table.rows[r_idx].cells[c_idx]
                    cell.paragraphs[0].text = ""
                    p = cell.paragraphs[0]
                    add_rich_runs(p, val, size=Pt(9.5))
                    p.paragraph_format.line_spacing = 1.1

            spacer = doc.add_paragraph()
            spacer.paragraph_format.space_after = Pt(10)
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m and not plain_list_mode:
            numbered_list_buffer.append(m.group(2))
            continue
        else:
            flush_numbered_list()

        para = doc.add_paragraph()
        if plain_list_mode:
            para.paragraph_format.line_spacing = 1.3
            para.paragraph_format.space_after = Pt(4)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_rich_runs(para, line)
        elif in_references:
            set_body_paragraph_format(para, space_after=Pt(12), justify=False)
            para.paragraph_format.first_line_indent = Cm(-1.27)
            para.paragraph_format.left_indent = Cm(1.27)
            add_rich_runs(para, line)
        else:
            set_body_paragraph_format(para)
            add_rich_runs(para, line)

    flush_numbered_list()

    doc.save(str(OUT_PATH))
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
