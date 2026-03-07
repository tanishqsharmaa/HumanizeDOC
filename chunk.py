"""
chunk.py — DOCX → chunked text pipeline
========================================
Reads a .docx file, extracts each paragraph as an atomic "section",
and groups sections into chunks where each chunk is < 185 words.
No section is ever split across chunks (atomicity guaranteed).

Output:
  1. A .txt file with each chunk enclosed in  --- Entry N ---  delimiters
  2. A Python list that main.py can import directly
"""

import sys
from docx import Document


# ─── Section extraction ──────────────────────────────────────────────
def extract_sections(docx_path: str) -> list[str]:
    """
    Extract every non-empty paragraph from the .docx as an individual section.
    Each paragraph is treated as the smallest atomic unit — it will never
    be split across two chunks.
    """
    doc = Document(docx_path)
    sections: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            sections.append(text)
    return sections


# ─── Chunking logic ──────────────────────────────────────────────────
def chunk_sections(sections: list[str], max_words: int = 185) -> list[str]:
    """
    Group sections into chunks so that each chunk has fewer than
    `max_words` words.  Atomicity is maintained — a section is either
    fully included in a chunk or not included at all.

    Edge case: if a single section already exceeds `max_words`, it is
    placed alone in its own chunk (we never break a section apart).
    """
    chunks: list[str] = []
    current_parts: list[str] = []
    current_word_count = 0

    for section in sections:
        section_word_count = len(section.split())

        # Single section already exceeds the limit → send it solo
        if section_word_count >= max_words:
            # Flush whatever we've accumulated so far
            if current_parts:
                chunks.append(" ".join(current_parts))
                current_parts = []
                current_word_count = 0
            chunks.append(section)
            continue

        # Adding this section would breach the limit → flush first
        if current_word_count + section_word_count > max_words:
            chunks.append(" ".join(current_parts))
            current_parts = []
            current_word_count = 0

        current_parts.append(section)
        current_word_count += section_word_count

    # Flush the last accumulated chunk
    if current_parts:
        chunks.append(" ".join(current_parts))

    return chunks


# ─── TXT file output ─────────────────────────────────────────────────
def write_chunks_to_txt(chunks: list[str], output_path: str) -> None:
    """Write chunks to a .txt file with --- delimiters."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks, 1):
            f.write(f"--- Entry {i} ---\n")
            f.write(chunk + "\n")
            f.write("--- End ---\n\n")
    print(f"📄 Wrote {len(chunks)} chunk(s) → {output_path}")


# ─── Public API ───────────────────────────────────────────────────────
def process_docx(
    docx_path: str,
    output_txt: str = "chunked_output.txt",
    max_words: int = 185,
) -> list[str]:
    """
    Full pipeline:  DOCX → sections → chunks → .txt file + return list.
    Returns the list of chunk strings (ready for main.py's `texts`).
    """
    print(f"📂 Reading: {docx_path}")
    sections = extract_sections(docx_path)
    print(f"   Found {len(sections)} section(s)")

    chunks = chunk_sections(sections, max_words)
    print(f"   Grouped into {len(chunks)} chunk(s)  (max {max_words} words each)")

    write_chunks_to_txt(chunks, output_txt)

    # Print summary
    for i, chunk in enumerate(chunks, 1):
        wc = len(chunk.split())
        preview = chunk[:80].replace("\n", " ") + ("..." if len(chunk) > 80 else "")
        print(f"   Chunk {i}: {wc} words — {preview}")

    return chunks


# ─── CLI entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:  python chunk.py <path_to.docx> [output.txt] [max_words]")
        print("  path_to.docx   — input Word document")
        print("  output.txt     — output text file  (default: chunked_output.txt)")
        print("  max_words      — word limit per chunk  (default: 185)")
        sys.exit(1)

    docx_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else "chunked_output.txt"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 185

    process_docx(docx_file, out_file, limit)
