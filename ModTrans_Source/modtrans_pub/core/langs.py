"""Nomi delle lingue da dare ai prompt quando il config indica solo il codice."""

LANG_NAMES = {
    "en": "English", "it": "Italian", "fr": "French", "es": "Spanish", "de": "German",
    "pt": "Portuguese", "ru": "Russian", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "tr": "Turkish", "hu": "Hungarian", "pl": "Polish", "uk": "Ukrainian", "nl": "Dutch",
    "cs": "Czech", "sv": "Swedish", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian",
}


def lang_name(code):
    """'fr' -> 'French', 'pt-BR' -> 'Portuguese (BR)'; un codice sconosciuto resta com'e'."""
    code = (code or "").strip()
    base, _, region = code.replace("_", "-").partition("-")
    name = LANG_NAMES.get(base.lower())
    if not name:
        return code
    return f"{name} ({region.upper()})" if region else name
