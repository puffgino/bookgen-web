# app_streamlit.py
import os
import re
import time
import json
import sys
import importlib
import pathlib
import traceback
from pathlib import Path

import streamlit as st

APP_TITLE = "Book Generator (Streamlit)"

# ---------- UI ----------
st.set_page_config(page_title=APP_TITLE, page_icon="📘", layout="centered")
st.title(APP_TITLE)
st.caption(
    "Paste **Title**, **Buyer persona / Voice & Style**, and **Table of Contents**. "
    "The app uses your Streamlit **Secrets** for the OpenAI API key and generates a .docx."
)

# --- Inputs (only what you asked) ---
title = st.text_input("Title", placeholder="Es. The EMDR Therapist’s Complete Blueprint")

persona = st.text_area(
    "Buyer persona / Voice & Style",
    height=220,
    placeholder="Incolla qui la persona (target, tono, must/avoid,...).",
)

toc_text = st.text_area(
    "Table of Contents (simple text paste)",
    height=320,
    placeholder=(
        "Esempio:\n"
        "INTRODUCTION\n"
        "How to Use This Book for Real Clinical Impact\n"
        "A Note on Ethics and Client Safety\n\n"
        "PART I – FOUNDATIONS OF TRAUMA & EMDR\n"
        "Chapter 1: Understanding the Roots of Emotional Wounds\n"
        "How trauma hides in plain sight\n"
        "The biology of stuck processing\n"
    ),
)

gen_btn = st.button("🚀 Generate", type="primary", use_container_width=True)

# ---------- Helpers ----------
def safe_title_for_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "-", s).strip()

def parse_toc_lines(toc_text: str):
    """
    Converte una TOC incollata (testo semplice) in una lista per book.yaml:
    - Linee in MAIUSCOLO (es. INTRODUCTION, PART I …) o che iniziano con 'Chapter'/'Day'
      => diventano capitoli.
    - Le linee successive, finché non arriva un nuovo capitolo, sono sottosezioni.
    - Le righe vuote vengono ignorate.
    """
    lines = [ln.strip(" \t-•").rstrip() for ln in toc_text.splitlines()]
    lines = [ln for ln in lines if ln]  # no vuoti

    chapters = []
    cur = None

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
                cur = {"title": "Chapter", "subs": []}
            cur["subs"].append(ln)

    if cur:
        chapters.append(cur)
    return chapters

def write_book_yaml_locally(title: str, persona: str, chapters_list: list) -> Path:
    """
    Scrive un book.yaml minimale per il backend esistente (bookgen.main).
    Nota: yaml.safe_load accetta perfettamente JSON, quindi scriviamo JSON valido.
    """
    data = {
        "title": title,
        "persona": persona,
        "toc": [{c["title"]: c["subs"]} if c["subs"] else c["title"] for c in chapters_list],
    }
    p = Path("book.yaml")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p

def find_output_doc(title: str, run_id: str) -> Path | None:
    safe_title = safe_title_for_filename(title)
    p = Path("output") / f"BOOK - {safe_title} - {run_id}.docx"
    return p if p.exists() else None

def import_bookgen_main():
    """
    Import robusto di bookgen.main, assicurando che la root del repo sia nel PYTHONPATH.
    """
    root = pathlib.Path(__file__).parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        return importlib.import_module("bookgen.main")
    except Exception:
        st.error("Import error: cannot load module `bookgen.main`. Check that `bookgen/main.py` exists.")
        st.code(traceback.format_exc())
        st.stop()

# ---------- Action ----------
if gen_btn:
    # Validazioni minime
    if not title.strip():
        st.error("Please enter a Title.")
        st.stop()
    if not persona.strip():
        st.error("Please paste the Buyer persona / Voice & Style.")
        st.stop()
    if not toc_text.strip():
        st.error("Please paste the Table of Contents.")
        st.stop()

    # Verifica OPENAI_API_KEY nei secrets
    if "OPENAI_API_KEY" not in st.secrets or not st.secrets["OPENAI_API_KEY"]:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()

    # Prepara env per il backend
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    if "BOOK_MODEL" in st.secrets and st.secrets["BOOK_MODEL"]:
        os.environ["BOOK_MODEL"] = st.secrets["BOOK_MODEL"]

    # Forziamo un RUN_ID riproducibile per recuperare il file
    run_id = time.strftime("%Y%m%d-%H%M%S")
    os.environ["BOOK_RUN_ID"] = run_id

    # Parsing TOC → book.yaml temporaneo
    chapters_parsed = parse_toc_lines(toc_text)
    write_book_yaml_locally(title, persona, chapters_parsed)

    with st.spinner("Generating the .docx… this can take a bit for larger TOCs."):
        # Import QUI (dopo che env e file sono pronti)
        bookgen_main = import_bookgen_main()

        # (opzionale) forza target parole 500–600
        try:
            bookgen_main.MIN_SUBSECTION_WORDS = 520
        except Exception:
            pass

        # Eseguo generazione
        bookgen_main.main()

    # Recupero file e offro il download
    out_path = find_output_doc(title, run_id)
    if not out_path:
        st.error("Generation finished but output file was not found. Check logs.")
        st.stop()

    data = out_path.read_bytes()
    st.success("Done! Click below to download your book.")
    st.download_button(
        label="📥 Download .docx",
        data=data,
        file_name=out_path.name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    st.caption(f"Saved also on server: `{out_path}`")
