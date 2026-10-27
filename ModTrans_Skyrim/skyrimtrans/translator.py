"""Traduzione tramite Claude, a lotti, con cache e verifica dei segnaposto."""
from __future__ import annotations

import json
import re
import time
from typing import Callable

from .protect import Protected, ProtectionError, protect, restore
from .tables import KIND_HINTS

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """You translate text strings from video game mods (Skyrim) into {lang}.

Rules:
- Translate ONLY the natural-language text. Keep proper nouns, place names, and lore terms \
consistent with the official {lang} localization of the game when you know it.
- Markers like <x0/>, <x1/> stand for protected formatting (line breaks, tags, variables). \
Copy every marker EXACTLY as written, the same number of times, in a sensible position. \
Never translate, rename, add, remove or merge markers.
- Do not add quotes, notes or explanations. Do not change numbers.
- Keep the length close to the original when possible (UI space is limited).
- The user message is a JSON array of objects {{"id", "kind", "text"}}; "kind" tells you the \
type of text. Reply with ONLY a JSON array of {{"id", "text"}} with the translations.
{glossary}"""


class AnthropicBackend:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def __call__(self, system: str, user: str) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=8000, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


class OpenAICompatBackend:
    """Qualsiasi server compatibile OpenAI /chat/completions: OpenAI, OpenRouter,
    Ollama (http://localhost:11434/v1), LM Studio (http://localhost:1234/v1),
    llama.cpp server, vLLM... Solo libreria standard, nessuna dipendenza."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1",
                 api_key: str | None = None, timeout: float = 600, temperature: float = 0.0):
        self.model, self.timeout, self.temperature = model, timeout, temperature
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key

    def __call__(self, system: str, user: str) -> str:
        import urllib.error
        import urllib.request

        body = json.dumps({
            "model": self.model, "temperature": self.temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # i server locali spesso non richiedono chiave
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, body, headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}") from None
        text = data["choices"][0]["message"]["content"] or ""
        # alcuni modelli locali (reasoning) mettono il ragionamento in <think>...</think>
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def _parse_reply(reply: str) -> dict[int, str]:
    m = re.search(r"\[.*\]", reply, re.DOTALL)
    if not m:
        raise ValueError("risposta senza JSON")
    return {int(o["id"]): o["text"] for o in json.loads(m.group(0))}


class Translator:
    def __init__(self, backend: Callable[[str, str], str], language: str,
                 glossary: dict[str, str] | None = None, batch_chars: int = 6000,
                 batch_items: int = 40, retries: int = 2):
        gl = ""
        if glossary:
            gl = "\nGlossary (use these translations exactly):\n" + "\n".join(
                f"- {k} => {v}" for k, v in glossary.items())
        self.system = SYSTEM.format(lang=language, glossary=gl)
        self.backend = backend
        self.batch_chars, self.batch_items, self.retries = batch_chars, batch_items, retries
        self.cache: dict[tuple[str, str], str] = {}
        self.failed: dict[tuple[str, str], str] = {}

    def translate_all(self, items: list[tuple[str, str]], fit: Callable[[str], str] = lambda s: s,
                      progress: Callable[[int, int], None] | None = None) -> dict[tuple[str, str], str]:
        """items = [(kind, text)]. Ritorna {(kind, text): tradotto}; i falliti restano in self.failed."""
        todo: dict[tuple[str, str], Protected] = {}
        for key in dict.fromkeys(items):
            if key in self.cache or key in self.failed:
                continue
            p = protect(key[1])
            if p.skip_reason:
                self.failed[key] = p.skip_reason
            else:
                todo[key] = p
        keys = list(todo)
        done = 0
        i = 0
        while i < len(keys):
            batch, size = [], 0
            while i < len(keys) and len(batch) < self.batch_items and (not batch or size + len(todo[keys[i]].masked) < self.batch_chars):
                batch.append(keys[i])
                size += len(todo[keys[i]].masked)
                i += 1
            self._run_batch(batch, todo, fit)
            done += len(batch)
            if progress:
                progress(done, len(keys))
        return {k: v for k, v in self.cache.items() if k in set(items)}

    def _run_batch(self, batch, todo, fit):
        pending = list(batch)
        for attempt in range(self.retries + 1):
            if not pending:
                return
            payload = json.dumps(
                [{"id": n, "kind": KIND_HINTS.get(k[0], k[0]), "text": todo[k].masked}
                 for n, k in enumerate(pending)], ensure_ascii=False)
            try:
                got = _parse_reply(self.backend(self.system, payload))
            except Exception as e:  # rete, JSON, ecc.
                last = f"errore backend: {e}"
                time.sleep(min(2 ** attempt, 8)) if attempt < self.retries else None
                got = {}
            else:
                last = "traduzione mancante"
            still = []
            for n, k in enumerate(pending):
                try:
                    if n not in got:
                        raise ProtectionError(last)
                    out = fit(restore(todo[k], got[n]))
                    self.cache[k] = out
                except ProtectionError as e:
                    self.failed[k] = str(e)
                    still.append(k)
            pending = still
            for k in pending:
                if attempt < self.retries:
                    self.failed.pop(k, None)
        # rimasti falliti: restano in self.failed (originale intatto)
