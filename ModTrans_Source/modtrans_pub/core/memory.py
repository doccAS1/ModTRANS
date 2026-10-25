import sqlite3


class TranslationMemory:
    """TM esatta (testo sorgente + hash glossario). Salva solo output approvati."""
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS tm(game TEXT, src TEXT, gloss TEXT, dst TEXT,"
                        " PRIMARY KEY(game, src, gloss))")
        # Le voci create prima del supporto multilingua non avevano la lingua nella chiave
        # ("<hash>"): erano tutte italiane. Il formato nuovo è "<hash>.<lingua>".
        self.db.execute("UPDATE OR IGNORE tm SET gloss = gloss || '.it' WHERE instr(gloss, '.') = 0")
        self.db.commit()

    def get(self, game, src, gloss):
        r = self.db.execute("SELECT dst FROM tm WHERE game=? AND src=? AND gloss=?",
                            (game, src, gloss)).fetchone()
        return r[0] if r else None

    def put(self, game, src, gloss, dst):
        self.db.execute("INSERT OR REPLACE INTO tm VALUES(?,?,?,?)", (game, src, gloss, dst))
        self.db.commit()
