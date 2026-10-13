"""Motori LLM intercambiabili: cloud (Anthropic), qualsiasi endpoint OpenAI-compatibile (Ollama, LM Studio, llama.cpp, vLLM, OpenAI, OpenRouter...) e un mock per i test. Solo stdlib."""
import json, os, re, time, urllib.error, urllib.request

class Engine:
    name = "engine"
    def chat(self, system: str, user: str) -> str:
        raise NotImplementedError

def _post(url, headers, payload, timeout=30, retries=2):
    data = json.dumps(payload).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and i < retries - 1:
                time.sleep(2)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower() and i < retries - 1:
                continue
            raise RuntimeError(f"Connessione fallita o troppo lenta: {e}")

class AnthropicEngine(Engine):
    def __init__(self, model, api_key_env="ANTHROPIC_API_KEY", max_tokens=4096, **_):
        self.model, self.max_tokens = model, max_tokens
        self.key = os.environ.get(api_key_env, "")
        self.name = f"anthropic:{model}"

    def chat(self, system, user):
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"},
                  {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                   "messages": [{"role": "user", "content": user}]})
        if "error" in r:
            raise RuntimeError(f"Errore API Anthropic: {r['error']}")
        return "".join(b.get("text", "") for b in r["content"] if b.get("type") == "text")

class OpenAICompatEngine(Engine):
    def __init__(self, model, base_url="http://localhost:11434/v1", api_key_env=None,
                 max_tokens=4096, temperature=0.2, **_):
        self.model, self.base, self.max_tokens, self.temp = model, base_url.rstrip("/"), max_tokens, temperature
        self.key = os.environ.get(api_key_env, "") if api_key_env else ""
        self.name = f"openai_compat:{model}"

    def chat(self, system, user):
        h = {"content-type": "application/json"}
        if self.key:
            h["authorization"] = f"Bearer {self.key}"
            
        if "openrouter.ai" in self.base:
            h["HTTP-Referer"] = "https://github.com/modtrans-tool"
            h["X-Title"] = "ModTrans Automatic Translator"
            
        r = _post(f"{self.base}/chat/completions", h,
                  {"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temp,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]})
        
        if "error" in r:
            raise RuntimeError(f"Errore API OpenRouter: {json.dumps(r['error'])}")
            
        content = r["choices"][0]["message"].get("content")
        if content is None:
            raise RuntimeError("L'IA ha bloccato la risposta restituendo un testo vuoto (possibile filtro sicurezza).")
        return content

class MockEngine(Engine):
    name = "mock"
    def chat(self, system, user):
        if "ROLE: translator" in system:
            items = json.loads(user)["items"]
            return json.dumps({i: "[IT] " + v["text"] for i, v in items.items()}, ensure_ascii=False)
        if "ROLE: judge" in system:
            return json.dumps({"score": 0.92, "ok": True, "issues": []})
        if "ROLE: repair" in system:
            return json.dumps({"text": "[IT] " + json.loads(user)["source"]}, ensure_ascii=False)
        return "{}"

def extract_json(text):
    if not text:
        raise ValueError("L'IA non ha restituito alcun testo valido.")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("Nessun JSON valido trovato nella risposta.")
    return json.loads(text[a:b + 1])

def make_engine(cfg):
    kind = cfg.get("type", "mock")
    cls = {"anthropic": AnthropicEngine, "openai_compat": OpenAICompatEngine, "mock": MockEngine}[kind]
    c = {k: v for k, v in cfg.items() if k != "type"}
    return cls(**c) if kind != "mock" else cls()