"""
Builds Chapter_05_System_Design_and_Architecture_DualVulnDroid.docx from the
companion Markdown file in this same directory. Formatting only - no
content decisions are made here. Merges Chapter 4's bullet-list/fenced-
code-block/Heading-3 support with Chapter 3's figure-embedding support
(a "**Figure X.Y. Caption.** *(file.png)*" line embeds the named image,
centered, with the caption placed below it).
"""
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Cm, Mm, RGBColor, Inches

HERE = Path(__file__).parent
MD_PATH = HERE / "Chapter_05_System_Design_and_Architecture_DualVulnDroid.md"
OUT_PATH = HERE / "Chapter_05_System_Design_and_Architecture_DualVulnDroid.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(12)
TABLE_SIZE = Pt(9)
LINE_SPACING = 1.5
BLACK = RGBColor(0, 0, 0)


def set_run_font(run, size=BODY_SIZE, bold=None, italic=None):
    run.font.name = BODY_FONT
    run.font.size = size
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    run.font.color.rgb = BLACK
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), BODY_FONT)
    rFonts.set(qn('w:hAnsi'), BODY_FONT)
    rFonts.set(qn('w:cs'), BODY_FONT)


def add_formatted_runs(paragraph, text, size=BODY_SIZE):
    tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            run = paragraph.add_run(tok[2:-2])
            set_run_font(run, size=size, bold=True)
        elif tok.startswith("`") and tok.endswith("`"):
            run = paragraph.add_run(tok[1:-1])
            set_run_font(run, size=size)
            run.font.name = "Consolas"
        elif tok.startswith("*") and tok.endswith("*"):
            run = paragraph.add_run(tok[1:-1])
            set_run_font(run, size=size, italic=True)
        else:
            run = paragraph.add_run(tok)
            set_run_font(run, size=size)


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


def set_cell_borders(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '808080')
        borders.append(el)
    tcPr.append(borders)


def add_table(doc, header, rows):
    table = doc.add_table(rows=1, cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    hdr_cells = table.rows[0].cells
    for i, h in enumerate(header):
        hdr_cells[i].text = ""
        p = hdr_cells[i].paragraphs[0]
        p.paragraph_format.line_spacing = 1.1
        run = p.add_run(h)
        set_run_font(run, size=TABLE_SIZE, bold=True)
        set_cell_borders(hdr_cells[i])
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:fill'), 'D9D9D9')
        hdr_cells[i]._tc.get_or_add_tcPr().append(shd)

    for row_data in rows:
        row_cells = table.add_row().cells
        for i, val in enumerate(row_data):
            row_cells[i].text = ""
            p = row_cells[i].paragraphs[0]
            p.paragraph_format.line_spacing = 1.1
            add_formatted_runs(p, val, size=TABLE_SIZE)
            set_cell_borders(row_cells[i])

    return table


def parse_md_table(body_lines, start_idx):
    header_line = body_lines[start_idx].strip()
    header = [c.strip() for c in header_line.strip('|').split('|')]
    idx = start_idx + 2
    rows = []
    while idx < len(body_lines) and body_lines[idx].strip().startswith('|'):
        row_line = body_lines[idx].strip()
        cells = [c.strip() for c in row_line.strip('|').split('|')]
        rows.append(cells)
        idx += 1
    return header, rows, idx


def main():
    text = MD_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

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

    h3 = doc.styles["Heading 3"]
    h3.font.name = BODY_FONT
    h3.font.size = Pt(12)
    h3.font.bold = True
    h3.font.color.rgb = BLACK
    h3.paragraph_format.space_before = Pt(12)
    h3.paragraph_format.space_after = Pt(8)
    h3.paragraph_format.line_spacing = LINE_SPACING

    list_num = doc.styles["List Number"]
    list_num.font.name = BODY_FONT
    list_num.font.size = BODY_SIZE
    list_num.font.color.rgb = BLACK
    list_num.paragraph_format.line_spacing = LINE_SPACING

    list_bullet = doc.styles["List Bullet"]
    list_bullet.font.name = BODY_FONT
    list_bullet.font.size = BODY_SIZE
    list_bullet.font.color.rgb = BLACK
    list_bullet.paragraph_format.line_spacing = LINE_SPACING

    footer = section.footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_number_field(footer_p)

    # ---- Title block: 3 lines (student name / thesis title / chapter title) ----
    title_lines = [lines[0].strip(), lines[1].strip(), lines[2].strip()]
    for idx, tline in enumerate(title_lines):
        tp = doc.add_paragraph()
        tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        size = Pt(13) if idx < 2 else Pt(16)
        run = tp.add_run(tline)
        set_run_font(run, size=size, bold=True)
        tp.paragraph_format.space_after = Pt(4) if idx < 2 else Pt(24)

    body_lines = lines[3:]

    numbered_list_buffer = []
    bullet_list_buffer = []

    def flush_numbered_list():
        nonlocal numbered_list_buffer
        for item_text in numbered_list_buffer:
            lp = doc.add_paragraph(style="List Number")
            lp.paragraph_format.line_spacing = LINE_SPACING
            lp.paragraph_format.space_after = Pt(8)
            add_formatted_runs(lp, item_text)
        numbered_list_buffer = []

    def flush_bullet_list():
        nonlocal bullet_list_buffer
        for item_text in bullet_list_buffer:
            lp = doc.add_paragraph(style="List Bullet")
            lp.paragraph_format.line_spacing = LINE_SPACING
            lp.paragraph_format.space_after = Pt(6)
            add_formatted_runs(lp, item_text)
        bullet_list_buffer = []

    def flush_lists():
        flush_numbered_list()
        flush_bullet_list()

    figure_count = 0
    table_count = 0

    i = 0
    in_references = False
    while i < len(body_lines):
        raw = body_lines[i]
        line = raw.strip()
        i += 1

        if not line:
            continue

        if line.startswith("```"):
            flush_lists()
            code_lines = []
            while i < len(body_lines) and not body_lines[i].strip().startswith("```"):
                code_lines.append(body_lines[i])
                i += 1
            i += 1
            for code_line in code_lines:
                cp = doc.add_paragraph()
                cp.paragraph_format.space_after = Pt(0)
                cp.paragraph_format.line_spacing = 1.0
                run = cp.add_run(code_line if code_line.strip() else " ")
                set_run_font(run, size=Pt(10.5))
                run.font.name = "Consolas"
            spacer = doc.add_paragraph()
            spacer.paragraph_format.space_after = Pt(12)
            continue

        if line.startswith("### "):
            flush_lists()
            heading_text = line[4:].strip()
            hp = doc.add_paragraph(style="Heading 3")
            hp.add_run(heading_text)
            continue

        if line.startswith("## "):
            flush_lists()
            heading_text = line[3:].strip()
            hp = doc.add_paragraph(style="Heading 2")
            hp.add_run(heading_text)
            in_references = heading_text.strip().lower().startswith("references")
            continue

        # Figure caption + inline image reference on one line:
        # "**Figure 5.1. Caption.** *(figure_5_1_x.png)*"
        fig_match = re.match(r"^\*\*(Figure [^*]+)\*\*\s+\*\(([^)]+\.png)\)\*$", line)
        if fig_match:
            flush_lists()
            figure_count += 1
            img_name = fig_match.group(2)
            img_path = HERE / img_name
            if img_path.exists():
                img_p = doc.add_paragraph()
                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                img_p.paragraph_format.space_before = Pt(6)
                run_img = img_p.add_run()
                run_img.add_picture(str(img_path), width=Inches(5.6))
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_before = Pt(4)
            cap.paragraph_format.space_after = Pt(14)
            run = cap.add_run(fig_match.group(1))
            set_run_font(run, size=Pt(11), bold=True)
            continue

        if line.startswith("**Table") and (i < len(body_lines) and body_lines[i].strip().startswith('|')):
            flush_lists()
            table_count += 1
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_before = Pt(6)
            cap.paragraph_format.space_after = Pt(6)
            add_formatted_runs(cap, line, size=Pt(11))
            continue

        if line.startswith('|'):
            flush_lists()
            header, rows, next_i = parse_md_table(body_lines, i - 1)
            add_table(doc, header, rows)
            spacer = doc.add_paragraph()
            spacer.paragraph_format.space_after = Pt(12)
            i = next_i
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m and not in_references:
            flush_bullet_list()
            numbered_list_buffer.append(m.group(2))
            continue

        bm = re.match(r"^-\s+(.*)$", line)
        if bm:
            flush_numbered_list()
            bullet_list_buffer.append(bm.group(1))
            continue

        flush_lists()

        if in_references:
            para = doc.add_paragraph()
            para.paragraph_format.line_spacing = 1.15
            para.paragraph_format.space_after = Pt(10)
            para.paragraph_format.left_indent = Inches(0.4)
            para.paragraph_format.first_line_indent = Inches(-0.4)
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_formatted_runs(para, line, size=Pt(11))
            continue

        para = doc.add_paragraph()
        set_body_paragraph_format(para)
        add_formatted_runs(para, line)

    flush_lists()

    doc.save(str(OUT_PATH))
    print(f"Saved: {OUT_PATH}")
    print(f"Figures embedded: {figure_count}")
    print(f"Tables embedded: {table_count}")


if __name__ == "__main__":
    main()
