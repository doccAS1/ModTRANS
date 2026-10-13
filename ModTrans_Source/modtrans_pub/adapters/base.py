class Adapter:
    """Un adapter per gioco: estrae, e riscrive, le stringhe senza rompere la mod."""
    game = ""
    mod_id = ""
    mod_version = ""

    @classmethod
    def detect(cls, mod_dir) -> bool: ...
    def extract(self): ...                     # -> list[Unit]
    def read_output(self) -> dict: ...         # traduzioni già presenti nella mod
    def output_files(self) -> list: ...        # percorsi relativi che verranno scritti
    def write(self, mapping: dict): ...        # key -> testo tradotto
