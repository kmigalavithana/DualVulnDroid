"""
Builds Chapter_01_Introduction_DualVulnDroid.docx from the companion
Markdown file in this same directory. Formatting only - no content
decisions are made here (the Markdown file is the single source of
truth for the actual thesis text).
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Cm, Mm, RGBColor

HERE = Path(__file__).parent
MD_PATH = HERE / "Chapter_01_Introduction_DualVulnDroid.md"
OUT_PATH = HERE / "Chapter_01_Introduction_DualVulnDroid.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(12)
LINE_SPACING = 1.5


def add_bold_runs(paragraph, text):
    """Splits **bold** markers in `text` into bold/normal runs on `paragraph`."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(part)
        run.font.name = BODY_FONT
        run.font.size = BODY_SIZE
        # Ensure east-asian font attribute doesn't silently override Times New Roman
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.append(rFonts)
        rFonts.set(qn('w:ascii'), BODY_FONT)
        rFonts.set(qn('w:hAnsi'), BODY_FONT)
        rFonts.set(qn('w:cs'), BODY_FONT)


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


def main():
    text = MD_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    doc = Document()

    # ---- Page setup: A4, professional margins ----
    section = doc.sections[0]
    section.page_height = Mm(297)
    section.page_width = Mm(210)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)

    # ---- Base "Normal" style: Times New Roman 12pt, 1.5 spacing ----
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

    # ---- Heading 1 (chapter title) / Heading 2 (section headings) ----
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

    # ---- Footer: centered page number ----
    footer = section.footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_number_field(footer_p)

    # ---- Title block (first two lines of the markdown source) ----
    title_line_1 = lines[0].strip()   # DUALVULNDROID
    title_line_2 = lines[1].strip()   # CHAPTER 01 - INTRODUCTION

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title_line_1)
    run.font.name = BODY_FONT
    run.font.size = Pt(16)
    run.bold = True
    p.paragraph_format.space_after = Pt(4)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(title_line_2)
    run2.font.name = BODY_FONT
    run2.font.size = Pt(16)
    run2.bold = True
    p2.paragraph_format.space_after = Pt(24)

    body_lines = lines[2:]

    numbered_list_buffer = []

    def flush_numbered_list():
        nonlocal numbered_list_buffer
        for item_text in numbered_list_buffer:
            lp = doc.add_paragraph(style="List Number")
            lp.paragraph_format.line_spacing = LINE_SPACING
            lp.paragraph_format.space_after = Pt(8)
            add_bold_runs(lp, item_text)
        numbered_list_buffer = []

    i = 0
    while i < len(body_lines):
        raw = body_lines[i]
        line = raw.strip()
        i += 1

        if not line:
            continue

        if line.startswith("## "):
            flush_numbered_list()
            heading_text = line[3:].strip()
            hp = doc.add_paragraph(style="Heading 2")
            hp.add_run(heading_text)
            continue

        # Numbered objective list items: "1. Text", "2. Text", ...
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m:
            numbered_list_buffer.append(m.group(2))
            continue
        else:
            flush_numbered_list()

        # Regular paragraph
        para = doc.add_paragraph()
        set_body_paragraph_format(para)
        add_bold_runs(para, line)

    flush_numbered_list()

    doc.save(str(OUT_PATH))
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
