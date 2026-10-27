"""Motori LLM intercambiabili: cloud (Anthropic), qualsiasi endpoint OpenAI-compatibile (Ollama, LM Studio, llama.cpp, vLLM, OpenAI, OpenRouter...) e un mock per i test. Solo stdlib."""
import ipaddress, json, os, re, time, urllib.error, urllib.parse, urllib.request

class Engine:
    name = "engine"
    def chat(self, system: str, user: str) -> str:
        raise NotImplementedError

DEFAULT_TIMEOUT = 120


def _post(url, headers, payload, timeout=DEFAULT_TIMEOUT, retries=3):
    data = json.dumps(payload).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and i < retries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            # include il timeout di lettura (TimeoutError/socket.timeout non e' un URLError)
            last = e
            if i < retries - 1:
                time.sleep(2 * (i + 1))
                continue
    raise RuntimeError(f"Connection failed or too slow after {retries} attempts "
                       f"(timeout {timeout}s): {last}")


def _is_local_host(host):
    host = (host or "").lower()
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


class AnthropicEngine(Engine):
    def __init__(self, model, api_key_env="ANTHROPIC_API_KEY", max_tokens=4096, timeout=DEFAULT_TIMEOUT, **_):
        self.model, self.max_tokens, self.timeout = model, max_tokens, timeout
        self.key = os.environ.get(api_key_env, "")
        self.name = f"anthropic:{model}"

    def chat(self, system, user):
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"},
                  {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                   "messages": [{"role": "user", "content": user}]}, timeout=self.timeout)
        if "error" in r:
            raise RuntimeError(f"Anthropic API error: {r['error']}")
        return "".join(b.get("text", "") for b in r["content"] if b.get("type") == "text")

class OpenAICompatEngine(Engine):
    def __init__(self, model, base_url="http://localhost:11434/v1", api_key_env=None,
                 max_tokens=4096, temperature=0.2, timeout=DEFAULT_TIMEOUT, **_):
        self.model, self.base, self.max_tokens, self.temp = model, base_url.rstrip("/"), max_tokens, temperature
        self.timeout = timeout
        self.key = os.environ.get(api_key_env, "") if api_key_env else ""
        if self.key and self.base.startswith("http://"):
            host = urllib.parse.urlparse(self.base).hostname
            if not _is_local_host(host):
                raise ValueError(f"Refusing to send the API key over unencrypted HTTP to '{host}'. "
                                 "Use an https:// base_url (plain http is only allowed for local/LAN servers).")
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
                                {"role": "user", "content": user}]}, timeout=self.timeout)
        
        if "error" in r:
            raise RuntimeError(f"API error ({self.base}): {json.dumps(r['error'])}")
            
        content = r["choices"][0]["message"].get("content")
        if content is None:
            raise RuntimeError("The AI blocked the reply and returned empty text (possible safety filter).")
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
    """Estrae il primo oggetto JSON valido dalla risposta, anche con note o graffe attorno."""
    if not text:
        raise ValueError("The AI returned no usable text.")
    dec = json.JSONDecoder()
    # prima i blocchi ```json ... ```, poi il testo intero
    chunks = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S | re.I) + [text]
    for chunk in chunks:
        pos = chunk.find("{")
        while pos >= 0:
            try:
                obj, _ = dec.raw_decode(chunk, pos)
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                pass
            pos = chunk.find("{", pos + 1)
    raise ValueError("No valid JSON found in the reply.")

def make_engine(cfg):
    kind = cfg.get("type", "mock")
    cls = {"anthropic": AnthropicEngine, "openai_compat": OpenAICompatEngine, "mock": MockEngine}[kind]
    c = {k: v for k, v in cfg.items() if k != "type"}
    return cls(**c) if kind != "mock" else cls()