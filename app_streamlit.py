# app_streamlit.py
import os, re, yaml
from datetime import datetime
from pathlib import Path
import streamlit as st

from bookgen import main as bookgen_main  # your generator

# ---------- UTIL ----------
def safe_title(t: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '-', t).strip()

def parse_toc_text(toc_text: str):
    """
    Simple parser: 
    - Lines without indentation = Chapter
    - Lines with 2+ spaces = Subsections
    """
    chapters = []
    current = None
    for raw in toc_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if re.match(r"^\s{2,}", line):  # subheading
            if current is None:
                continue
            sub = line.strip()
            if isinstance(chapters[-1], dict):
                key = next(iter(chapters[-1].keys()))
                chapters[-1][key].append(sub)
            else:
                prev = chapters.pop()
                chapters.append({prev: [sub]})
        else:
            chapters.append(line.strip())
            current = line.strip()
    return chapters

def build_yaml_dict(title: str, persona: str, toc_list):
    return {
        "title": title.strip(),
        "persona": persona.strip(),
        "toc": toc_list
    }

# ---------- UI ----------
st.set_page_config(page_title="Book Generator", page_icon="📘", layout="centered")

st.title("📘 Book Generator")

st.caption("Paste the **Buyer Persona / Voice & Style** and the **Table of Contents**. "
           "The app will use the configured API key in Streamlit Secrets automatically.")

persona = st.text_area(
    "Buyer Persona / Voice & Style",
    height=220,
    placeholder="Paste here the persona details: target reader, tone, style instructions, must/avoid, etc."
)

toc_text = st.text_area(
    "Table of Contents (paste as plain text)",
    height=280,
    placeholder=("Example:\n"
                 "INTRODUCTION\n"
                 "  How to Use This Book for Real Clinical Impact\n"
                 "  A Note on Ethics and Client Safety\n\n"
                 "PART I – FOUNDATIONS OF TRAUMA & EMDR\n"
                 "  Chapter 1: Understanding the Roots of Emotional Wounds\n"
                 "    How trauma hides in plain sight\n"
                 "    The biology of stuck processing\n")
)

generate = st.button("🚀 Generate", use_container_width=True)

# ---------- ACTION ----------
if generate:
    if not persona.strip() or not toc_text.strip():
        st.error("Please fill in both Persona and TOC.")
        st.stop()

    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    os.environ["BOOK_RUN_ID"] = run_id

    # Default title (since we removed the Title field)
    title = "Generated Book"

    toc_list = parse_toc_text(toc_text)
    cfg = build_yaml_dict(title, persona, toc_list)

    with open("book.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    with st.spinner("Generating .docx..."):
        try:
            bookgen_main.main()
        except Exception as e:
            st.exception(e)
            st.stop()

    out_dir = Path("output")
    expected = out_dir / f"BOOK - {safe_title(title)} - {run_id}.docx"
    if expected.exists():
        with open(expected, "rb") as f:
            st.success("✅ Document generated!")
            st.download_button(
                label="⬇️ Download .docx",
                data=f.read(),
                file_name=expected.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
    else:
        st.error("No .docx file was generated.")
