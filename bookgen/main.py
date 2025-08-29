# bookgen/main.py
import os, json, re, sys
from datetime import datetime
from pathlib import Path
import yaml

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from openai import OpenAI

# ====================== CONFIG ======================
MODEL                = os.getenv("BOOK_MODEL", "gpt-4o")
SUBSECTION_TOKENS    = int(os.getenv("SUBSECTION_MAX_OUTPUT_TOKENS", "7000"))
CHAPTER_TOKENS       = int(os.getenv("CHAPTER_MAX_OUTPUT_TOKENS", "18000"))
MIN_SUBSECTION_WORDS = 450          # target acceptance
MIN_HARD_WORDS       = 200          # below this -> ALWAYS retry
MAX_TRIES_PER_SUB    = 5            # more chances to avoid empty/short sections

# Mini-headings normalization style: "bullet" or "bold"
MINI_MODE = os.getenv("MINI_HEADING_MODE", "bullet").strip().lower()

DOCS_DIR   = Path("output")
CHECKPOINT = Path("progress.json")
BOOK_YAML  = Path("book.yaml")

# Always create a NEW file
RUN_ID = os.getenv("BOOK_RUN_ID") or datetime.now().strftime("%Y%m%d-%H%M%S")

# ===== MASTER PROMPT (global, reused for all books) =====
MASTER_PROMPT = """
You are a book-writing assistant.
Your job is to generate high-quality book content that follows the provided Table of Contents.

Rules:
1) Follow the TOC exactly; do not invent extra chapters or headings.
2) For each subheading, write about 500-600 words of complete, on-topic content.
3) Avoid repetition; each sentence must add new value.
4) Stay strictly on-topic for each subheading.
5) Ensure smooth flow and coherence across paragraphs.
6) Never use placeholders or meta comments.
7) No decorative separators (---, ***, etc.).
8) Do not restate "Chapter/Day ..." or the subheading line inside the body.

Global quality:
- Each section must feel complete, rich, and useful.
- Maintain consistent length and depth across the entire book.
- The output must be copy-paste ready.
"""

# ====================================================

client = OpenAI()

# ---------------- File IO ----------------
def load_yaml(path=BOOK_YAML):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _set_mirror_margins(doc: Document):
    """Turn on mirror margins in document settings (best-effort; OK if it fails)."""
    try:
        settings_part = doc._part.package.settings_part
        s = settings_part.element
        node = s.find(qn('w:mirrorMargins'))
        if node is None:
            s.append(OxmlElement('w:mirrorMargins'))
    except Exception:
        pass  # not critical

def ensure_doc(title: str):
    """Always create a NEW .docx with RUN_ID and set page/margin/spacing defaults."""
    DOCS_DIR.mkdir(exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]+', '-', title).strip()
    doc_path = DOCS_DIR / f"BOOK - {safe_title} - {RUN_ID}.docx"

    doc = Document()

    # ---- Page size & margins ----
    section = doc.sections[0]
    section.page_width  = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin    = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin   = Inches(0.7)
    section.right_margin  = Inches(0.7)
    try:
        section.gutter = Inches(0.2)
    except Exception:
        pass
    _set_mirror_margins(doc)

    # ---- Base style (Normal) ----
    normal = doc.styles["Normal"]
    normal.font.name = "Cambria"
    normal.font.size = Pt(13)
    pf = normal.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after  = Pt(6)  # small visual gap
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.2

    # Apply same spacing rules to headings so Word doesn't add extra gaps
    for style_name in ("Heading 1", "Heading 2", "Title"):
        try:
            st = doc.styles[style_name]
            st.font.name = "Cambria"
            st.font.size = Pt(18 if style_name == "Title" else 16)
            sp = st.paragraph_format
            sp.space_before = Pt(0)
            sp.space_after  = Pt(0)
            sp.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            sp.line_spacing = 1.2
        except KeyError:
            pass

    h0 = doc.add_heading(title, level=0)
    h0.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.save(str(doc_path))
    return doc, doc_path

def save_doc(doc: Document, path: Path):
    doc.save(str(path))

# (… tutto il resto del file rimane identico alla tua versione …)
