"""Protegge i codici di Stardew/Content Patcher durante la traduzione."""
import re

PATTERNS = [
    r"⟦\d+⟧",                       # un ⟦N⟧ già presente nel testo originale: va protetto come un codice
    r"\{\{[^{}]*\}\}",               # token Content Patcher {{Token}}
    r"\{\d+\}",                      # {0} stile format
    r"#\$[a-z]+(?:\s[^#]*)?#",       # #$b#  #$e#  #$c 0.5#
    r"\$[a-z]+(?:\s-?\d+)*",         # $h $s $q 1 2
    r"%[a-z]+\d?",                   # %adj %noun %name %spouse ...
    r"<[^<>]+>",                     # markup
    r"\[\s*\d[^\]]*\]",              # [388] [O 388]
    r"@", r"\^", r"#", r"\\n",
]
RX = re.compile("|".join(f"(?:{p})" for p in PATTERNS))
TOKEN_RX = re.compile(r"⟦\d+⟧")


def mask(text):
    tokens = []

    def sub(m):
        tokens.append(m.group(0))
        return f"⟦{len(tokens)}⟧"

    return RX.sub(sub, text), tokens


def unmask(text, tokens):
    """Un solo passaggio: un token che contiene a sua volta un ⟦N⟧ non viene espanso due volte."""
    def sub(m):
        i = int(m.group(0)[1:-1])
        return tokens[i - 1] if 1 <= i <= len(tokens) else m.group(0)
    return TOKEN_RX.sub(sub, text)


def token_ids(text):
    return sorted(TOKEN_RX.findall(text))


def strip_tokens(text):
    return TOKEN_RX.sub("", text)
