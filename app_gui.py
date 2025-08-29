import os, sys, subprocess, tkinter as tk
from tkinter import filedialog, messagebox

# CONFIG: percorso di default dove si trova main.py
DEFAULT_BOOKGEN_DIR = os.path.expanduser("~/Desktop/bookgen")

def pick_book_yaml():
    path = filedialog.askopenfilename(
        title="Select book.yaml",
        filetypes=[("YAML files","*.yaml"), ("All files","*.*")]
    )
    if path:
        yaml_var.set(path)

def pick_bookgen_dir():
    path = filedialog.askdirectory(
        title="Select folder that contains main.py (bookgen)"
    )
    if path:
        bookgen_dir_var.set(path)

def run_bookgen():
    yaml_path = yaml_var.get().strip()
    bookgen_dir = bookgen_dir_var.get().strip() or DEFAULT_BOOKGEN_DIR

    # Controlli base
    if not os.path.isfile(yaml_path):
        messagebox.showerror("Error", "Select a valid book.yaml.")
        return
    main_path = os.path.join(bookgen_dir, "main.py")
    if not os.path.isfile(main_path):
        messagebox.showerror("Error", f"main.py not found in:\n{bookgen_dir}\n\nPick the correct folder.")
        return

    # OPENAI_API_KEY
    api_key = os.getenv("OPENAI_API_KEY") or api_key_var.get().strip()
    if not api_key:
        messagebox.showerror("Error", "Set your OPENAI_API_KEY (field below) or as environment variable.")
        return

    # Env e cwd corretti:
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = api_key
    # facoltativo: passiamo il percorso YAML allo script (se supportato) oppure
    # eseguiamo con cwd nella cartella del YAML così che 'book.yaml' venga trovato.
    yaml_dir = os.path.dirname(yaml_path)

    try:
        run = subprocess.run(
            [sys.executable, main_path],  # esegui il file, NON come modulo
            cwd=yaml_dir,                 # così main.py troverà "book.yaml" nella cwd
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        messagebox.showinfo("Success", f"Book generated!\n\nSTDOUT:\n{run.stdout[-1000:]}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            "Error",
            f"Book generation failed.\n\nSTDOUT:\n{e.stdout[-1000:]}\n\nSTDERR:\n{e.stderr[-1000:]}"
        )

# --- GUI ---
root = tk.Tk()
root.title("Book Generator")

# Vars
yaml_var = tk.StringVar()
bookgen_dir_var = tk.StringVar(value=DEFAULT_BOOKGEN_DIR)
api_key_var = tk.StringVar(value=os.getenv("OPENAI_API_KEY",""))

tk.Label(root, text="📘 Book Generator", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=(10,8))

# YAML picker
tk.Label(root, text="book.yaml:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
tk.Entry(root, textvariable=yaml_var, width=60).grid(row=1, column=1, padx=6, pady=4)
tk.Button(root, text="Browse…", command=pick_book_yaml).grid(row=1, column=2, padx=6, pady=4)

# bookgen folder (contains main.py)
tk.Label(root, text="bookgen folder:").grid(row=2, column=0, sticky="e", padx=6, pady=4)
tk.Entry(root, textvariable=bookgen_dir_var, width=60).grid(row=2, column=1, padx=6, pady=4)
tk.Button(root, text="Browse…", command=pick_bookgen_dir).grid(row=2, column=2, padx=6, pady=4)

# API key
tk.Label(root, text="OPENAI_API_KEY:").grid(row=3, column=0, sticky="e", padx=6, pady=4)
tk.Entry(root, textvariable=api_key_var, width=60, show="•").grid(row=3, column=1, padx=6, pady=4)
tk.Label(root, text="(used only if env var not set)").grid(row=3, column=2, sticky="w", padx=6, pady=4)

# Run button
tk.Button(root, text="Run generator", width=20, height=2, command=run_bookgen).grid(row=4, column=0, columnspan=3, pady=12)

root.mainloop()