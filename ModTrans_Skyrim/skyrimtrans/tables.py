"""Quali sottorecord dei plugin di Skyrim contengono testo da tradurre.

Lista volutamente conservativa: (tipo record, tipo sottorecord) -> tipo di testo.
Tutto ciò che non è qui dentro non viene toccato, per nessun motivo.
Per aggiungere un campo basta una riga.
"""
from __future__ import annotations

_FULL = (
    "ACTI ALCH AMMO APPA ARMO AVIF BOOK CELL CLAS CLFM CONT DIAL DOOR ENCH EXPL FACT FLOR FURN "
    "HAZD HDPT INGR KEYM LCTN LIGH MESG MGEF MISC MSTT NPC_ PERK PROJ QUST RACE SCRL SHOU SLGM "
    "SPEL TACT TREE WEAP WOOP WRLD"
).split()

TABLE: dict[tuple[str, str], str] = {(r, "FULL"): "name" for r in _FULL}

for _r in "ARMO WEAP AMMO RACE PERK AVIF CLAS SHOU SCRL APPA QUST".split():
    TABLE[(_r, "DESC")] = "description"
TABLE[("MGEF", "DNAM")] = "description"
TABLE[("BOOK", "DESC")] = "book_text"
TABLE[("LSCR", "DESC")] = "loading_screen"
TABLE[("MESG", "DESC")] = "message"
TABLE[("MESG", "ITXT")] = "button"
TABLE[("PERK", "EPF2")] = "button"
TABLE[("INFO", "NAM1")] = "dialogue"
TABLE[("INFO", "RNAM")] = "dialogue_prompt"
TABLE[("QUST", "CNAM")] = "quest_log"
TABLE[("QUST", "NNAM")] = "quest_objective"
TABLE[("NPC_", "SHRT")] = "name"
TABLE[("FACT", "MNAM")] = "name"
TABLE[("FACT", "FNAM")] = "name"
TABLE[("WOOP", "TNAM")] = "name"
TABLE[("ACTI", "RNAM")] = "name"
TABLE[("FLOR", "RNAM")] = "name"
TABLE[("TES4", "SNAM")] = "plugin_description"

TABLE_RTYPES = {r for r, _ in TABLE}

RTYPE_NAMES = {
    "ACTI": "activator/object", "ALCH": "potion/food/drink", "AMMO": "ammunition", "APPA": "alchemy apparatus",
    "ARMO": "armor/clothing", "AVIF": "skill/attribute", "BOOK": "book/note", "CELL": "interior or exterior cell",
    "CLAS": "NPC class", "CLFM": "color", "CONT": "container", "DIAL": "dialogue topic", "DOOR": "door",
    "ENCH": "enchantment", "EXPL": "explosion", "FACT": "faction", "FLOR": "flora/plant", "FURN": "furniture",
    "HAZD": "hazard", "HDPT": "head part", "INFO": "dialogue line", "INGR": "ingredient", "KEYM": "key",
    "LCTN": "location", "LIGH": "light/torch", "LSCR": "loading screen", "MESG": "message box",
    "MGEF": "magic effect", "MISC": "miscellaneous item", "MSTT": "static object", "NPC_": "NPC",
    "PERK": "perk", "PROJ": "projectile", "QUST": "quest", "RACE": "race", "SCRL": "scroll", "SHOU": "shout",
    "SLGM": "soul gem", "SPEL": "spell", "TACT": "talking activator", "TREE": "tree", "WEAP": "weapon",
    "WOOP": "word of power", "WRLD": "worldspace", "TES4": "mod header",
}

KIND_HINTS = {
    "name": "short name or label of an item, spell, place, NPC or UI element; keep it concise",
    "description": "description text of an item, perk, spell or effect",
    "book_text": "in-world book text; literary register; keep the paragraph structure",
    "dialogue": "line spoken by a character; natural spoken register; similar length to the original",
    "dialogue_prompt": "short dialogue choice shown to the player; concise",
    "quest_log": "quest journal entry",
    "quest_objective": "short quest objective shown on the HUD",
    "button": "very short button label",
    "message": "message box text",
    "loading_screen": "loading screen tip or lore text",
    "ui_label": "mod configuration menu (MCM) label or description",
    "plugin_description": "description of the mod",
}
