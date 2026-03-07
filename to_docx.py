"""
to_docx.py — Convert humanized_outputs.txt → .docx
====================================================
Parses the humanized_outputs.txt file produced by main.py,
extracts only the OUTPUT sections (the humanized text),
and writes them into a formatted Word document.

Usage:
    python to_docx.py                              # defaults: humanized_outputs.txt → humanized_output.docx
    python to_docx.py my_outputs.txt               # custom input file
    python to_docx.py my_outputs.txt result.docx   # custom input + output files
"""

import sys
import re
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_LINE_SPACING


def parse_humanized_outputs(txt_path: str) -> list[str]:
    """
    Parse humanized_outputs.txt and extract only the OUTPUT text blocks.

    Expected format per entry:
        --- Entry N ---
        INPUT:
        <original text>

        OUTPUT:
        <humanized text>

        ==================================================
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        print("⚠️ The input file is empty.")
        return []

    # Split by entry delimiter
    entries = re.split(r"--- Entry \d+ ---", content)
    outputs = []

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Extract the OUTPUT section
        # Look for "OUTPUT:\n" and grab everything after it until the "====..." separator or end
        match = re.search(r"OUTPUT:\s*\n(.*?)(?:={10,}|$)", entry, re.DOTALL)
        if match:
            output_text = match.group(1).strip()
            if output_text:
                outputs.append(output_text)

    return outputs


def create_docx(outputs: list[str], docx_path: str) -> None:
    """
    Create a Word document from the list of humanized output texts.
    Each output chunk becomes one or more paragraphs in the document.
    """
    doc = Document()

    # ── Set default font for the document ──
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    font.color.rgb = RGBColor(0, 0, 0)

    # ── Set default paragraph spacing ──
    paragraph_format = style.paragraph_format
    paragraph_format.space_after = Pt(6)
    paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    paragraph_format.line_spacing = 1.15

    # ── Add each output chunk ──
    for i, output_text in enumerate(outputs):
        # Split the output into paragraphs (by double newlines or single newlines)
        paragraphs = output_text.split("\n")

        for para_text in paragraphs:
            para_text = para_text.strip()
            if para_text:
                doc.add_paragraph(para_text)

    doc.save(docx_path)
    print(f"✅ Created: {docx_path}")
    print(f"   {len(outputs)} chunk(s) → {docx_path}")


def main():
    # ── Parse CLI arguments ──
    txt_path = sys.argv[1] if len(sys.argv) > 1 else "humanized_outputs.txt"
    docx_path = sys.argv[2] if len(sys.argv) > 2 else "humanized_output.docx"

    print("=" * 50)
    print("📄 HUMANIZED TEXT → DOCX CONVERTER")
    print("=" * 50)
    print(f"   Input:  {txt_path}")
    print(f"   Output: {docx_path}")
    print()

    # ── Parse the text file ──
    outputs = parse_humanized_outputs(txt_path)

    if not outputs:
        print("⚠️ No output entries found in the file.")
        print("   Make sure you've run main.py first to generate humanized_outputs.txt")
        sys.exit(1)

    print(f"📦 Found {len(outputs)} humanized chunk(s)")
    for i, text in enumerate(outputs, 1):
        word_count = len(text.split())
        preview = text[:80].replace("\n", " ") + ("..." if len(text) > 80 else "")
        print(f"   Chunk {i}: {word_count} words — {preview}")
    print()

    # ── Create the docx ──
    create_docx(outputs, docx_path)

    print()
    print(f"🎉 Done! Open '{docx_path}' to see your humanized document.")


if __name__ == "__main__":
    main()
