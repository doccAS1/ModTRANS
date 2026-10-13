import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import zipfile
import shutil
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from . import pipeline
from .pipeline import pick_adapter
from .core.project import Project

class ReviewWindow(tk.Toplevel):
    # ... [MANTIENI IL CODICE DELLA REVIEW WINDOW ESATTAMENTE COM'ERA] ...
    # (Per brevità non lo riscrivo, è identico alla versione precedente in inglese che hai già)
    pass # Sostituisci questo blocco con la tua ReviewWindow completa

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
        self._build_ui()

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

    def log(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def browse_mod(self):
        if d := filedialog.askdirectory(title="Select the mod folder"): self.mod_dir.set(d)
        
    def browse_mods_folder(self):
        if d := filedialog.askdirectory(title="Select Stardew Valley 'Mods' folder"):
            self.mods_folder.set(d)
            self._save_settings()

    def browse_zip(self):
        # ... [MANTIENI IL TUO CODICE PER BROWSE ZIP] ...
        pass

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

    def start_translation(self):
        mod = self.mod_dir.get()
        if not mod:
            messagebox.showwarning("Warning", "Please select a mod folder.")
            return
            
        cfg = self._load_config()
        if not cfg: return

        # Inietta le lingue scelte dall'utente nel dizionario di configurazione per passarle al backend
        tgt_full = self.target_lang.get()
        cfg["target_lang_code"] = tgt_full[tgt_full.find("(")+1 : tgt_full.find(")")] if "(" in tgt_full else "it"
        cfg["target_lang_name"] = tgt_full.split("(")[0].strip()
        cfg["source_lang_name"] = self.source_lang.get()

        self.btn_translate.state(['disabled'])
        self.log(f"\n--- Starting translation for: {Path(mod).name} ---")
        threading.Thread(target=self._run_pipeline, args=(mod, cfg), daemon=True).start()

    def _run_pipeline(self, mod_dir, cfg):
        try:
            pipeline.run(mod_dir, cfg, dry_run=False, log=self.log)
            self.log("Translation completed.")
            
            # --- FASE DI DEPLOY AUTOMATICO ---
            export_dir = self.mods_folder.get().strip()
            if export_dir and Path(export_dir).exists():
                src_path = Path(mod_dir)
                dest_path = Path(export_dir) / src_path.name
                
                # Evita di copiare se la mod sorgente è GIÀ nella cartella Mods di destinazione
                if src_path.resolve() != dest_path.resolve():
                    self.log(f"Deploying mod to: {dest_path} ...")
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(src_path, dest_path)
                    self.log("Deployment successful! Mod is ready to play.")
        except Exception as e:
            self.log(f"CRITICAL ERROR: {str(e)}")
        finally:
            self.btn_translate.state(['!disabled'])
            
    def open_review(self):
        # ... [MANTIENI IL TUO CODICE DELLA REVIEW] ...
        pass
        
    def restore_backup(self):
        # ... [MANTIENI IL TUO CODICE DEL RESTORE] ...
        pass

if __name__ == "__main__":
    app = ModTransGUI()
    app.mainloop()