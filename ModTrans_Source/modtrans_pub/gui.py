import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import json
import shutil
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from . import pipeline
from .core.fsutil import safe_extract_zip
from .core.masking import mask

class ReviewWindow(tk.Toplevel):
    """Revisione manuale: mostra le stringhe REVISION / BLOCK / PUBLISH_WITH_NOTE,
    permette di correggerle o approvarle e poi riscrive i file della mod."""

    def __init__(self, parent, mod_dir, cfg, items, on_done=None):
        super().__init__(parent)
        self.title(f"Manual Review - {Path(mod_dir).name}")
        self.geometry("980x600")
        self.minsize(800, 480)
        self.mod_dir, self.cfg, self.items, self.on_done = mod_dir, cfg, items, on_done
        self.pending = {}          # key -> testo finale approvato/modificato
        self.current = None

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.Frame(paned)
        self.tree = ttk.Treeview(left, columns=("decision", "key"), show="headings", selectmode="browse")
        self.tree.heading("decision", text="Status")
        self.tree.heading("key", text="Key")
        self.tree.column("decision", width=130, stretch=False)
        self.tree.column("key", width=260)
        sb = ttk.Scrollbar(left, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("approved", foreground="#2e7d32")
        for k, v in items.items():
            self.tree.insert("", tk.END, iid=k, values=(v["decision"], k))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        paned.add(left, weight=1)

        right = ttk.Frame(paned, padding=(8, 0, 0, 0))
        ttk.Label(right, text="Original:").pack(anchor=tk.W)
        self.src_text = tk.Text(right, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self.src_text.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(right, text="Judges' notes:").pack(anchor=tk.W)
        self.issues_lbl = ttk.Label(right, text="", wraplength=520, justify=tk.LEFT)
        self.issues_lbl.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(right, text="Translation (editable):").pack(anchor=tk.W)
        self.dst_text = tk.Text(right, height=8, wrap=tk.WORD)
        self.dst_text.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        btns = ttk.Frame(right)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Approve / Save edit", command=self.approve).pack(side=tk.LEFT, padx=2)
        self.apply_btn = ttk.Button(btns, text="Apply to mod (0)", command=self.apply)
        self.apply_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Close", command=self.destroy).pack(side=tk.RIGHT, padx=2)
        paned.add(right, weight=3)

        if items:
            first = next(iter(items))
            self.tree.selection_set(first)

    def _set_text(self, widget, text, editable=False):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        if not editable:
            widget.configure(state=tk.DISABLED)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        self.current = key
        v = self.items[key]
        self._set_text(self.src_text, v["src"])
        notes = "; ".join(f"[{i.get('type', '?')}] {i.get('detail', '')}" for i in v.get("issues", [])) or "-"
        self.issues_lbl.configure(text=notes)
        self._set_text(self.dst_text, self.pending.get(key, v["dst"]), editable=True)

    def approve(self):
        if not self.current:
            return
        text = self.dst_text.get("1.0", tk.END).rstrip("\n")
        if not text.strip():
            messagebox.showwarning("Empty translation", "Write a translation before approving.", parent=self)
            return
        src = self.items[self.current]["src"]
        if sorted(mask(src)[1]) != sorted(mask(text)[1]):
            if not messagebox.askyesno(
                    "Game codes differ",
                    "The game codes (@, $h, {{Token}}, #$b# ...) in the translation do not match the original.\n"
                    "This can break the mod. Save anyway?", parent=self):
                return
        self.pending[self.current] = text
        self.tree.item(self.current, tags=("approved",), values=("approved", self.current))
        self.apply_btn.configure(text=f"Apply to mod ({len(self.pending)})")
        # passa automaticamente alla stringa successiva
        nxt = self.tree.next(self.current)
        if nxt:
            self.tree.selection_set(nxt)
            self.tree.see(nxt)

    def apply(self):
        if not self.pending:
            messagebox.showinfo("Nothing to apply", "Approve at least one string first.", parent=self)
            return
        try:
            n = pipeline.apply_review(self.mod_dir, self.cfg, self.pending)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Error", f"Could not apply the review:\n{e}", parent=self)
            return
        messagebox.showinfo("Done", f"{n} string(s) updated in the mod.", parent=self)
        if self.on_done:
            self.on_done(n)
        self.destroy()


class ModTransGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ModTrans - Universal Mod Translator")
        self.geometry("800x550")
        self.minsize(700, 450)
        
        self.mod_dir = tk.StringVar()
        self.mods_folder = tk.StringVar()
        self.source_lang = tk.StringVar(value="Auto")
        self.target_lang = tk.StringVar(value="Italian (it)")
        
        self.settings_file = Path.home() / ".modtrans_gui.json"
        last_config = "config.toml"
        if self.settings_file.exists():
            try:
                saved = json.loads(self.settings_file.read_text(encoding="utf-8"))
                last_config = saved.get("last_config", "config.toml")
                self.mods_folder.set(saved.get("mods_folder", ""))
                self.source_lang.set(saved.get("source_lang", "Auto"))
                self.target_lang.set(saved.get("target_lang", "Italian (it)"))
            except:
                pass
                
        self.config_path = tk.StringVar(value=last_config)
        self._ui_queue = queue.Queue()      # i thread di lavoro non toccano mai i widget: passano da qui
        self._build_ui()
        self.after(100, self._drain_ui_queue)

    def _build_ui(self):
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=tk.X)

        # Riga 0: Mod Folder
        ttk.Label(top_frame, text="Mod Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(top_frame, textvariable=self.mod_dir, width=45).grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        btn_mod_frame = ttk.Frame(top_frame)
        btn_mod_frame.grid(row=0, column=3, sticky=tk.W)
        ttk.Button(btn_mod_frame, text="Browse...", command=self.browse_mod, width=10).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_mod_frame, text="From ZIP...", command=self.browse_zip, width=10).pack(side=tk.LEFT, padx=1)

        # Riga 1: Lingue (Source -> Target)
        lang_frame = ttk.Frame(top_frame)
        lang_frame.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(lang_frame, text="From:").pack(side=tk.LEFT)
        src_langs = ["Auto", "English", "Chinese", "Japanese", "Russian", "Spanish", "French", "German"]
        ttk.Combobox(lang_frame, textvariable=self.source_lang, values=src_langs, width=12, state="readonly").pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(lang_frame, text="To:").pack(side=tk.LEFT)
        tgt_langs = ["Italian (it)", "French (fr)", "Spanish (es)", "German (de)", "Chinese (zh)", "Russian (ru)", "Japanese (ja)", "Portuguese (pt)"]
        ttk.Combobox(lang_frame, textvariable=self.target_lang, values=tgt_langs, width=15, state="readonly").pack(side=tk.LEFT, padx=(5, 0))

        # Riga 2: Config TOML
        ttk.Label(top_frame, text="Config TOML:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(top_frame, textvariable=self.config_path, width=45).grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        ttk.Button(top_frame, text="Browse...", command=self.browse_config, width=10).grid(row=2, column=3, sticky=tk.W, padx=1)

        # Riga 3: Deploy Folder (Opzionale)
        ttk.Label(top_frame, text="Export to 'Mods':").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(top_frame, textvariable=self.mods_folder, width=45).grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        ttk.Button(top_frame, text="Browse...", command=self.browse_mods_folder, width=10).grid(row=3, column=3, sticky=tk.W, padx=1)

        # Bottoni
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)
        
        self.btn_translate = ttk.Button(btn_frame, text="Translate Mod", command=self.start_translation)
        self.btn_translate.pack(side=tk.LEFT, padx=5)
        self.btn_review = ttk.Button(btn_frame, text="Manual Review", command=self.open_review)
        self.btn_review.pack(side=tk.LEFT, padx=5)
        self.btn_restore = ttk.Button(btn_frame, text="Restore Backup", command=self.restore_backup)
        self.btn_restore.pack(side=tk.LEFT, padx=5)

        # Log
        log_frame = ttk.LabelFrame(self, text="Execution Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set)

    def _write_log(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _ui(self, fn):
        """Esegue fn nel thread principale (Tkinter non è thread-safe)."""
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            self._ui_queue.put(fn)

    def log(self, message):
        self._ui(lambda: self._write_log(message))

    def _drain_ui_queue(self):
        try:
            while True:
                self._ui_queue.get_nowait()()
        except queue.Empty:
            pass
        self.after(100, self._drain_ui_queue)

    def browse_mod(self):
        if d := filedialog.askdirectory(title="Select the mod folder"): self.mod_dir.set(d)
        
    def browse_mods_folder(self):
        if d := filedialog.askdirectory(title="Select Stardew Valley 'Mods' folder"):
            self.mods_folder.set(d)
            self._save_settings()

    def browse_zip(self):
        f = filedialog.askopenfilename(title="Select the mod .zip", filetypes=[("ZIP archive", "*.zip")])
        if not f:
            return
        zpath = Path(f)
        dest = zpath.parent / f"{zpath.stem}_extracted"
        try:
            if dest.exists() and any(dest.iterdir()):
                if not messagebox.askyesno("Folder exists",
                                           f"'{dest.name}' already exists. Extract over it (files may be overwritten)?"):
                    return
            safe_extract_zip(zpath, dest)       # rifiuta percorsi ostili e zip bomb
            manifests = sorted(dest.rglob("manifest.json"), key=lambda p: len(p.parts))
            if not manifests:
                raise FileNotFoundError("no manifest.json found inside the archive (is it a SMAPI mod?)")
            self.mod_dir.set(str(manifests[0].parent))
            self.log(f"Extracted {zpath.name} -> {manifests[0].parent}")
        except Exception as e:
            messagebox.showerror("ZIP error", f"Unable to open the archive:\n{e}")

    def browse_config(self):
        if f := filedialog.askopenfilename(title="Select config.toml", filetypes=[("TOML", "*.toml")]):
            self.config_path.set(f)
            self._save_settings()

    def _save_settings(self):
        try:
            data = {
                "last_config": self.config_path.get(),
                "mods_folder": self.mods_folder.get(),
                "source_lang": self.source_lang.get(),
                "target_lang": self.target_lang.get()
            }
            self.settings_file.write_text(json.dumps(data), encoding="utf-8")
        except: pass

    def _load_config(self):
        try:
            cfg = tomllib.loads(Path(self.config_path.get()).read_text(encoding="utf-8"))
            self._save_settings() 
            return cfg
        except Exception as e:
            messagebox.showerror("Config Error", f"Unable to read config:\n{e}")
            return None

    def _prepare_cfg(self):
        """Carica il TOML e vi inietta le lingue scelte nella GUI."""
        cfg = self._load_config()
        if not cfg:
            return None
        tgt_full = self.target_lang.get()
        cfg["target_lang_code"] = tgt_full[tgt_full.find("(")+1 : tgt_full.find(")")] if "(" in tgt_full else "it"
        cfg["target_lang_name"] = tgt_full.split("(")[0].strip()
        cfg["source_lang_name"] = self.source_lang.get()
        return cfg

    def start_translation(self):
        mod = self.mod_dir.get()
        if not mod:
            messagebox.showwarning("Warning", "Please select a mod folder.")
            return

        cfg = self._prepare_cfg()
        if not cfg: return

        self.btn_translate.state(['disabled'])
        self.log(f"\n--- Starting translation for: {Path(mod).name} ---")
        export_dir = self.mods_folder.get().strip()      # letto qui, nel thread principale
        threading.Thread(target=self._run_pipeline, args=(mod, cfg, export_dir), daemon=True).start()

    def _run_pipeline(self, mod_dir, cfg, export_dir=""):
        try:
            result = pipeline.run(mod_dir, cfg, dry_run=False, log=self.log)
            if result is None:
                # mod bloccata dall'autore o senza file traducibili: niente da consegnare
                self.log("Nothing was translated, so nothing was deployed.")
                return
            self.log("Translation completed.")
            self._deploy(Path(mod_dir), export_dir)
        except (Exception, SystemExit) as e:
            self.log(f"CRITICAL ERROR: {str(e)}")
        finally:
            self._ui(lambda: self.btn_translate.state(['!disabled']))

    def _deploy(self, src_path, export_dir):
        """Copia la mod tradotta nella cartella Mods. Unisce i file senza cancellare nulla."""
        if not export_dir or not Path(export_dir).exists():
            return
        dest_path = Path(export_dir) / src_path.name
        src, dest = src_path.resolve(), dest_path.resolve()
        if src == dest:                     # la mod è già nella cartella Mods
            return
        if src in dest.parents or dest in src.parents:
            self.log(f"Deploy skipped: '{src_path.name}' and the Mods folder overlap.")
            return
        self.log(f"Deploying mod to: {dest_path} ...")
        shutil.copytree(src, dest, dirs_exist_ok=True)
        self.log("Deployment successful! Mod is ready to play.")

    def open_review(self):
        mod = self.mod_dir.get()
        if not mod:
            messagebox.showwarning("Warning", "Please select a mod folder.")
            return
        cfg = self._prepare_cfg()
        if not cfg: return
        try:
            items = pipeline.load_review(mod, cfg)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Error", f"Unable to load the review queue:\n{e}")
            return
        if not items:
            messagebox.showinfo("Manual Review", "No strings are waiting for review for this mod.")
            return
        ReviewWindow(self, mod, cfg, items,
                     on_done=lambda n: self.log(f"Manual review applied: {n} string(s) updated."))

    def restore_backup(self):
        mod = self.mod_dir.get()
        if not mod:
            messagebox.showwarning("Warning", "Please select a mod folder.")
            return
        cfg = self._prepare_cfg()
        if not cfg: return
        if not messagebox.askyesno("Restore backup",
                                   "Roll the mod back to the state before the last run?"):
            return
        try:
            ok = pipeline.restore(mod, cfg)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Error", f"Restore failed:\n{e}")
            return
        self.log("Backup restored." if ok else "No backup available for this mod.")


if __name__ == "__main__":
    app = ModTransGUI()
    app.mainloop()
