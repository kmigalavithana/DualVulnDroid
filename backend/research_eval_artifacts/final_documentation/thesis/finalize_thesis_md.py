"""
Combines _front_matter.md + _assembled_chapters.md + _appendices.md +
_master_references.md into the single final combined thesis markdown file,
and separately extracts every Figure/Table caption into a List of
Figures / List of Tables. Reads only files already produced by
assemble_final_thesis.py plus the front-matter/appendix/reference files
written directly for this task; writes only the final combined .md.
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
OUT_PATH = HERE / "FINAL_DualVulnDroid_Complete_Thesis.md"


def extract_block(text, tag):
    m = re.search(rf"%%{tag}%%\n(.*?)\n%%END{tag}%%", text, re.DOTALL)
    return m.group(1).strip()


def main():
    front = (HERE / "_front_matter.md").read_text(encoding="utf-8")
    chapters = (HERE / "_assembled_chapters.md").read_text(encoding="utf-8")
    appendices = (HERE / "_appendices.md").read_text(encoding="utf-8")
    references = (HERE / "_master_references.md").read_text(encoding="utf-8")

    title_block = extract_block(front, "TITLEPAGE")
    abstract = extract_block(front, "ABSTRACT")
    keywords = extract_block(front, "KEYWORDS")
    abbreviations = extract_block(front, "ABBREVIATIONS")

    # Extract figure and table captions from the assembled chapters, in order
    fig_captions = re.findall(r"^\*\*Figure (\d+\.\d+)\. (.+?)\*\*$", chapters, re.MULTILINE)
    table_captions = re.findall(r"^\*\*Table (\d+\.\d+)\. (.+?)\*\*$", chapters, re.MULTILINE)

    lof_lines = "\n".join(f"Figure {num} — {cap.rstrip('.')}" for num, cap in fig_captions)
    lot_lines = "\n".join(f"Table {num} — {cap.rstrip('.')}" for num, cap in table_captions)

    parts = []

    parts.append("%%TITLEPAGEBLOCK%%\n" + title_block + "\n%%ENDTITLEPAGEBLOCK%%\n")

    parts.append("# ABSTRACT\n\n" + abstract + "\n")
    parts.append("# KEYWORDS\n\n" + keywords + "\n")
    parts.append("# TABLE OF CONTENTS\n\n%%TOCFIELD%%\n")
    parts.append("# LIST OF FIGURES\n\n" + lof_lines + "\n")
    parts.append("# LIST OF TABLES\n\n" + lot_lines + "\n")
    parts.append("# LIST OF ABBREVIATIONS\n\n" + abbreviations + "\n")

    parts.append(chapters.strip() + "\n")

    parts.append("# APPENDICES\n\n" + appendices.strip() + "\n")

    parts.append("# " + references.strip().split("\n", 1)[0].replace("## ", "") + "\n\n" +
                  references.strip().split("\n", 1)[1].strip() + "\n")

    final_text = "\n\n".join(parts)
    OUT_PATH.write_text(final_text, encoding="utf-8")
    print(f"Saved: {OUT_PATH}")
    print(f"Figures indexed: {len(fig_captions)}")
    print(f"Tables indexed: {len(table_captions)}")
    print(f"Total characters: {len(final_text)}")


if __name__ == "__main__":
    main()
