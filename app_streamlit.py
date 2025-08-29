# app_streamlit.py
import os
import re
import time
import json
import sys
import importlib
import pathlib
from pathlib import Path
import streamlit as st

APP_TITLE = "Book Generator (Streamlit)"
ROOT = pathlib.Path(__file__).parent

# ---------- Page ----------
st.set_page_config(page_title=APP_TITLE, page_icon="📘", layout="centered")
st.title(APP_TITLE)
st.caption("Paste Title, Buyer persona / Voice & Style, and Table of Contents. Click Generate to download the .docx.")

# ---------- Session guard ----------
if "running" not in st.session_state:
    st.session_state.running = False

# ---------- Helpers ----------
def safe_title_for_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '-', s).strip()

def parse_toc_lines(toc_text: str):
    """
    Convert simple pasted TOC to a chapters list usable by book.yaml.
    - ALL CAPS or 'Chapter/Day N' -> new chapter
    - following lines -> subsections
    """
    lines = [ln.strip(" \t-•").rstrip() for ln in toc_text.splitlines()]
    lines = [ln for ln in lines if ln]

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
                cur = {"title": "Introduction", "subs": []}
            cur["subs"].append(ln)

    if cur:
        chapters.append(cur)
    return chapters

def write_book_yaml_locally(title: str, persona: str, chapters_list: list) -> Path:
    """
    Write a minimal book.yaml expected by bookgen/main.py.
    (JSON syntax that yaml.safe_load can read.)
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
    safe = safe_title_for_filename(title)
    p = Path("output") / f"BOOK - {safe} - {run_id}.docx"
    return p if p.exists() else None

def import_bookgen_main():
    """Import bookgen.main after env + book.yaml are ready."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("bookgen.main")

# ---------- UI (FORM) ----------
with st.form("book_form", clear_on_submit=False):
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
    submitted = st.form_submit_button("🚀 Generate", use_container_width=True)

st.button("▶ Reset state", on_click=lambda: st.session_state.update(running=False))

# ---------- Action ----------
if submitted:
    if st.session_state.running:
        st.warning("A run is already in progress. Please wait.")
        st.stop()
    st.session_state.running = True

    try:
        # Validations
        if not title.strip():
            st.error("Please enter a Title / Inserisci un Titolo.")
            st.stop()
        if not persona.strip():
            st.error("Please paste the Buyer persona / Incolla la persona.")
            st.stop()
        if not toc_text.strip():
            st.error("Please paste the TOC / Incolla l'indice.")
            st.stop()

        # Secrets
        api_key = st.secrets.get("OPENAI_API_KEY", "")
        if not api_key:
            st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
            st.info("Streamlit Cloud → Manage app → Settings → Secrets.")
            st.stop()

        # Prepare env for backend (unchanged behaviour)
        os.environ["OPENAI_API_KEY"] = api_key
        model = st.secrets.get("BOOK_MODEL", "")
        if model:
            os.environ["BOOK_MODEL"] = model

        # RUN_ID + book.yaml
        run_id = time.strftime("%Y%m%d-%H%M%S")
        os.environ["BOOK_RUN_ID"] = run_id
        chapters_parsed = parse_toc_lines(toc_text)
        write_book_yaml_locally(title, persona, chapters_parsed)

        # Generate
        with st.spinner("Generating the .docx… this can take a bit for larger TOCs."):
            bookgen_main = import_bookgen_main()
            # Non tocchiamo MIN_SUBSECTION_WORDS / TOKENS / TRIES
            bookgen_main.main()

        # Serve .docx
        out_path = find_output_doc(title, run_id)
        if not out_path:
            st.error("Generation finished but output file was not found. Check logs.")
            st.stop()

        st.success("Done! Click below to download your book.")
        st.download_button(
            label="📥 Download .docx",
            data=out_path.read_bytes(),
            file_name=out_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        st.caption(f"Saved on server: `{out_path}`")

    except Exception as e:
        msg = str(e)
        if "insufficient_quota" in msg or "insufficient_quota" in repr(e):
            st.error("OpenAI quota exhausted. Please top up and try again.")
        else:
            st.error("Generation crashed. See logs (Manage app → Logs).")
            st.exception(e)
    finally:
        # rilascia sempre il flag (anche su errore)
        st.session_state.running = False
