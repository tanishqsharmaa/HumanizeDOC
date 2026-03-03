"""
HumanizeDOC — Pipeline Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestrates the five-step document processing pipeline:

  1. **parser**       — Extract paragraphs + formatting from DOCX
  2. **classifier**   — Label blocks HUMANIZE or PRESERVE
  3. **chunker**      — Group HUMANIZE blocks into LLM-sized chunks
  4. **humanizer**    — Send each chunk through the selected LLM backend
  5. **reconstructor** — Rebuild the DOCX with original formatting
"""
