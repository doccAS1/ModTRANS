"""Protegge i codici di Stardew/Content Patcher durante la traduzione."""
import re

PATTERNS = [
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
    for i, t in enumerate(tokens, 1):
        text = text.replace(f"⟦{i}⟧", t)
    return text


def token_ids(text):
    return sorted(TOKEN_RX.findall(text))


def strip_tokens(text):
    return TOKEN_RX.sub("", text)
