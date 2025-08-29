import os, io, time, tempfile, shutil
from pathlib import Path
from datetime import datetime

import streamlit as st

# Importa il tuo motore: bookgen/main.py (quello che già usi da terminale)
# NB: deve esistere bookweb/bookgen/main.py e bookweb/bookgen/__init__.py
from bookgen import main as bookgen_main

# ------------- UI -------------
st.set_page_config(page_title="Book Generator", page_icon="📘", layout="centered")
st.title("📘 Book Generator (Streamlit)")

st.markdown(
    "Carica il tuo **book.yaml** e inserisci la tua **OPENAI_API_KEY**. "
    "Clicca *Generate* e scarica il .docx."
)

col1, col2 = st.columns(2)
with col1:
    yaml_file = st.file_uploader("book.yaml", type=["yaml", "yml"])
with col2:
    api_key = st.text_input("OPENAI_API_KEY", type="password", placeholder="sk-...")

st.divider()

st.subheader("Opzioni (facoltative)")
run_id = st.text_input(
    "RUN_ID (per avere un nome file unico; vuoto = timestamp)",
    value=""
).strip()

mini_mode = st.selectbox(
    "Stile mini-headings (se il modello li crea)",
    options=["bullet", "bold"],
    index=0,
    help="bullet → • **Titolo** — testo | bold → **Titolo.** testo"
)

min_words = st.slider(
    "Lunghezza minima per sottosezione (parole)",
    min_value=400, max_value=800, value=550, step=50,
    help="Tu avevi chiesto 500–600 parole; qui imposti la soglia minima."
)

st.caption("Il resto (font, margini, spacing) lo imposta già il tuo main.py.")

# ------------- ACTION -------------
generate = st.button("🚀 Generate", type="primary", use_container_width=True)

if generate:
    if not yaml_file:
        st.error("Carica un file book.yaml.")
        st.stop()
    if not api_key:
        st.error("Inserisci la OPENAI_API_KEY.")
        st.stop()

    # 1) Prepara una cartella temporanea di lavoro
    with st.spinner("Preparazione ambiente..."):
        tmpdir = Path(tempfile.mkdtemp(prefix="bookweb-"))
        workdir = tmpdir
        # Scrivi il book.yaml caricato
        yaml_path = workdir / "book.yaml"
        yaml_path.write_bytes(yaml_file.read())

        # Copia la tua cartella bookgen nel tmp (così non tocchi i file originali)
        src = Path(__file__).parent / "bookgen"
        dst = workdir / "bookgen"
        shutil.copytree(src, dst)

    # 2) Configura variabili d’ambiente per il run
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["MINI_HEADING_MODE"] = mini_mode
    if run_id:
        os.environ["BOOK_RUN_ID"] = run_id
    else:
        os.environ["BOOK_RUN_ID"] = datetime.now().strftime("%Y%m%d-%H%M%S")

    # 3) Monkey-patch di alcuni parametri nel tuo main (solo per questa sessione)
    #    - Sposta il puntamento del BOOK_YAML sul file appena caricato
    #    - Imposta la soglia minima parole che vuoi (es. 500–600)
    #    - Resetta l’eventuale checkpoint
    try:
        bookgen_main.BOOK_YAML = yaml_path
    except Exception:
        pass

    try:
        bookgen_main.MIN_SUBSECTION_WORDS = int(min_words)
    except Exception:
        pass

    # 4) Esegui la generazione
    st.info("Generazione in corso. Può richiedere qualche minuto…")
    start = time.time()
    try:
        # È importante eseguire nel working dir temporaneo
        os.chdir(workdir)
        bookgen_main.main()
    except Exception as e:
        st.exception(e)
        st.stop()
    finally:
        os.chdir(Path(__file__).parent)

    elapsed = time.time() - start
    st.success(f"Fatto in {int(elapsed)}s.")

    # 5) Trova l’ultimo .docx generato e offri il download
    out_dir = workdir / "output"
    docx_files = sorted(out_dir.glob("*.docx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not docx_files:
        st.error("Nessun .docx trovato in output/ — qualcosa è andato storto.")
    else:
        latest = docx_files[0]
        st.write("File generato:")
        st.code(str(latest.name))
        with open(latest, "rb") as f:
            st.download_button(
                label="⬇️ Scarica DOCX",
                data=f.read(),
                file_name=latest.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    st.caption("La cartella temporanea verrà eliminata automaticamente dal sistema.")
