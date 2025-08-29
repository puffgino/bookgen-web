# app_streamlit.py
import os, re, yaml, io
from datetime import datetime
from pathlib import Path
import streamlit as st

# importa il tuo generatore
from bookgen import main as bookgen_main  # usa bookgen/main.py del tuo repo

# ---------- UTIL ----------
def safe_title(t: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '-', t).strip()

def parse_toc_text(toc_text: str):
    """
    Accetta TOC incollata a righe:
    - Riga senza indentazione = Capitolo
    - Righe con 2+ spazi davanti = Sottosezioni del capitolo precedente
    Righe vuote/whitespace ignorate.
    Ritorna la struttura che si aspetta book.yaml:
      [{'Chapter': ['Sub1','Sub2']}, 'Chapter without subs', ...]
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
                # se l'ultimo era stringa, converti a dict
                prev = chapters.pop()
                chapters.append({prev: [sub]})
        else:
            # chapter
            if current and isinstance(chapters[-1], dict):
                pass
            chapters.append(line.strip())
            current = line.strip()
    return chapters

def build_yaml_dict(title: str, persona: str, toc_list):
    return {
        "title": title.strip(),
        "persona": persona.strip(),
        # NB: il MASTER PROMPT ora è dentro main.py; non serve nel YAML
        "toc": toc_list
    }

# ---------- UI ----------
st.set_page_config(page_title="Book Generator", page_icon="📘", layout="centered")

st.title("📘 Book Generator (Streamlit)")

st.caption("Incolla **Titolo**, **Persona** e **TOC**. L’app userà le tue **Streamlit Secrets** per l’OpenAI API Key.")

# Stato segreti
has_key = "OPENAI_API_KEY" in st.secrets
st.info("OPENAI_API_KEY configurata nei *Secrets* ✅" if has_key else "⚠️ Aggiungi OPENAI_API_KEY nei *Secrets* dell’app.")

col1, col2 = st.columns([1,1])
with col1:
    title = st.text_input("Title", placeholder="Es. The EMDR Therapist’s Complete Blueprint", max_chars=250)
with col2:
    st.text_input("Model (opzionale, da Secrets BOOK_MODEL)", value=st.secrets.get("BOOK_MODEL", ""), disabled=True)

persona = st.text_area(
    "Buyer persona / Voice & Style",
    height=220,
    placeholder="Incolla qui la persona (target, tono, must/avoid,...)."
)

toc_text = st.text_area(
    "Table of Contents (incolla semplice testo)",
    height=280,
    placeholder=("Esempio:\n"
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
    # Validazioni minime
    if not has_key:
        st.error("Configura l’OPENAI_API_KEY nei *Secrets* (Settings → Secrets).")
        st.stop()
    if not title.strip():
        st.error("Inserisci il Title.")
        st.stop()
    if not toc_text.strip():
        st.error("Incolla la TOC.")
        st.stop()

    # Prepara env: API key + opzionale BOOK_MODEL
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    if "BOOK_MODEL" in st.secrets and st.secrets["BOOK_MODEL"]:
        os.environ["BOOK_MODEL"] = st.secrets["BOOK_MODEL"]

    # RUN_ID automatico (timestamp) per nome file univoco
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    os.environ["BOOK_RUN_ID"] = run_id

    # Opzioni interne: niente UI per mini-headings o word count
    # (si usano i default già messi nel tuo main.py)
    # Se vuoi forzarli qui via secrets, decommenta:
    # os.environ["MINI_HEADING_MODE"] = st.secrets.get("MINI_HEADING_MODE", "bullet")
    # os.environ["SUBSECTION_MIN_WORDS"] = st.secrets.get("SUBSECTION_MIN_WORDS", "550")

    # Costruisci YAML temporaneo per compat con bookgen.main
    toc_list = parse_toc_text(toc_text)
    cfg = build_yaml_dict(title, persona, toc_list)

    # Scrivi book.yaml nella working dir (bookgen/main.py lo legge da Path('book.yaml'))
    with open("book.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    st.write("✅ TOC parsata:", toc_list)

    with st.spinner("Generating .docx..."):
        # esegui il generatore
        try:
            bookgen_main.main()
        except Exception as e:
            st.exception(e)
            st.stop()

    # Trova il file .docx generato
    out_dir = Path("output")
    expected = out_dir / f"BOOK - {safe_title(title)} - {run_id}.docx"
    if expected.exists():
        with open(expected, "rb") as f:
            st.success("✅ Documento generato!")
            st.download_button(
                label="⬇️ Download .docx",
                data=f.read(),
                file_name=expected.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
    else:
        # fallback: mostra lista dei docx presenti
        st.warning("File atteso non trovato. Mostro i .docx presenti in /output.")
        files = list(out_dir.glob("*.docx"))
        if files:
            for p in files:
                with open(p, "rb") as f:
                    st.download_button(f"Scarica {p.name}", f.read(), file_name=p.name)
        else:
            st.error("Nessun .docx trovato.")
