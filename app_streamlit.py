# app_streamlit.py
import os
import re
import time
import json
import sys
import importlib
from pathlib import Path

import streamlit as st

APP_TITLE = "Book Generator (Streamlit)"
ROOT = Path(__file__).parent


# ======================= UI =======================
st.set_page_config(page_title=APP_TITLE, page_icon="📘", layout="centered")
st.title(APP_TITLE)
st.caption(
    "Paste **Title**, **Buyer persona / Voice & Style**, and **Table of Contents**. "
    "Click **Generate** to download the .docx."
)

# Session flags
if "running" not in st.session_state:
    st.session_state.running = False
if "last_file" not in st.session_state:
    st.session_state.last_file = None

# Inputs
title = st.text_input(
    "Title / Titolo",
    placeholder="e.g., Super Easy Options Trading for Absolute Beginners",
)

persona = st.text_area(
    "Buyer persona / Voice & Style",
    height=220,
    placeholder=(
        "Paste the persona (target, tone, must/avoid...).\n\n"
        "Incolla qui la persona (target, tono, must/avoid,...)."
    ),
)

toc_text = st.text_area(
    "Table of Contents (simple text paste) / Indice (incolla testo semplice)",
    height=320,
    placeholder=(
        "Example / Esempio:\n"
        "INTRODUCTION\n"
        "How to Use This Book for Real Impact\n"
        "A Note on Ethics and Client Safety\n\n"
        "PART I – FOUNDATIONS\n"
        "Chapter 1: Understanding the Basics\n"
        "How X hides in plain sight\n"
        "The biology of Y\n"
    ),
)

colA, colB = st.columns([1, 1])
gen_clicked = colA.button("🚀 Generate", type="primary", use_container_width=True)
reset_clicked = colB.button("↩️ Reset state", use_container_width=True)


# =================== Helpers ===================
def safe_title_for_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "-", s).strip()


def parse_toc_lines(toc_text: str):
    """
    Convert simple pasted TOC to chapters usable by book.yaml.

    Rules:
    - Lines in ALL CAPS (INTRODUCTION, PART I …) or starting with 'Chapter/Day N'
      -> start a new chapter.
    - Following lines until the next chapter -> subsections.
    - Empty lines ignored.
    """
    lines = [ln.strip(" \t-•").rstrip() for ln in toc_text.splitlines()]
    lines = [ln for ln in lines if ln]  # drop empties

    chapters, cur = [], None

    def is_chapter(ln: str) -> bool:
        if re.match(r"^(chapter|day)\s+\d+[:\- ]", ln, flags=re.I):
            return True
        letters = re.sub(r"[^A-Za-z]+", "", ln)
        if letters and ln == ln.upper() and len(ln) >= 4:
            return True
        if ln.upper().startswith("PART "):
            return True
        return False

    for ln in lines:
        if is_chapter(ln):
            if cur:
                chapters.append(cur)
            cur = {"title": ln, "subs": []}
        else:
            if not cur:
                cur = {"title": "Introduction", "subs": []}
            cur["subs"].append(ln)

    if cur:
        chapters.append(cur)

    return chapters


def write_book_yaml_locally(title: str, persona: str, chapters_list: list) -> Path:
    """Write a minimal book.yaml expected by bookgen/main.py (JSON is OK for yaml.safe_load)."""
    data = {
        "title": title,
        "persona": persona,
        "toc": [{c["title"]: c["subs"]} if c["subs"] else c["title"] for c in chapters_list],
    }
    p = Path("book.yaml")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def find_output_doc(title: str, run_id: str) -> Path | None:
    safe = safe_title_for_filename(title)
    p = Path("output") / f"BOOK - {safe} - {run_id}.docx"
    return p if p.exists() else None


def import_bookgen_main():
    """Import bookgen.main only after env + book.yaml are ready."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("bookgen.main")


# =================== Actions ===================
if reset_clicked and not st.session_state.running:
    st.session_state.last_file = None
    st.success("State reset.")
    st.rerun()

if gen_clicked and not st.session_state.running:
    st.session_state.running = True
    try:
        # ---- Validations
        if not title.strip():
            st.error("Please enter a Title / Inserisci un Titolo.")
            st.session_state.running = False
            st.stop()

        if not persona.strip():
            st.error("Please paste the Buyer persona / Incolla la persona.")
            st.session_state.running = False
            st.stop()

        if not toc_text.strip():
            st.error("Please paste the TOC / Incolla l'indice.")
            st.session_state.running = False
            st.stop()

        # ---- Secrets
        api_key = st.secrets.get("OPENAI_API_KEY", "")
        if not api_key:
            st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
            st.info("In Streamlit Cloud: Manage app → Settings → Secrets.")
            st.session_state.running = False
            st.stop()

        # Prepare env for backend
        os.environ["OPENAI_API_KEY"] = api_key
        model = st.secrets.get("BOOK_MODEL", "")
        if model:
            os.environ["BOOK_MODEL"] = model

        # Unique RUN_ID for filename
        run_id = time.strftime("%Y%m%d-%H%M%S")
        os.environ["BOOK_RUN_ID"] = run_id

        # Build book.yaml
        chapters_parsed = parse_toc_lines(toc_text)
        write_book_yaml_locally(title, persona, chapters_parsed)

        # Generate
        with st.spinner("Generating the .docx… this can take a bit for larger TOCs."):
            try:
                bookgen_main = import_bookgen_main()
                # Optional clamp to ~500–600 words per subsection
                try:
                    bookgen_main.MIN_SUBSECTION_WORDS = 520
                except Exception:
                    pass
                bookgen_main.main()
            except Exception as e:
                st.error("Generation crashed. See logs on the right (or Manage app → Logs).")
                st.exception(e)
                st.session_state.running = False
                st.stop()

        # Serve .docx
        out_path = find_output_doc(title, run_id)
        if not out_path:
            st.error("Generation finished but output file was not found. Check logs.")
            st.session_state.running = False
            st.stop()

        data = out_path.read_bytes()
        st.session_state.last_file = out_path.name  # remember last file

        st.success("Done! Click below to download your book.")
        st.download_button(
            label="📥 Download .docx",
            data=data,
            file_name=out_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        st.caption(f"Saved on server: `{out_path}`")

    finally:
        # release the lock so user can run again
        st.session_state.running = False

# If a file was already produced in this session, show download again
if st.session_state.last_file:
    hint = Path("output") / st.session_state.last_file
    if hint.exists():
        st.info("Last generated file:")
        st.download_button(
            label="📥 Re-download last .docx",
            data=hint.read_bytes(),
            file_name=hint.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
