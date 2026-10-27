import hashlib, json, re


_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


class Glossary:
    def __init__(self, terms=None, keep=None):
        self.terms = terms or {}   # "Stardrop": "Goccia stellare" | [forme accettate]
        self.keep = keep or []     # nomi da lasciare invariati

    @classmethod
    def load(cls, path):
        d = json.load(open(path, encoding="utf-8"))
        return cls(d.get("terms", {}), d.get("keep", []))

    def hash(self):
        blob = json.dumps([self.terms, self.keep], sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(blob.encode()).hexdigest()[:10]

    @staticmethod
    def _has(term, text):
        if _CJK.search(term):               # scritture senza spazi: niente confini di parola
            return term.lower() in text.lower()
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I) is not None

    def relevant(self, text):
        return {"terms": {t: v for t, v in self.terms.items() if self._has(t, text)},
                "keep": [k for k in self.keep if self._has(k, text)]}

    def check(self, src, dst):
        issues = []
        for t, v in self.terms.items():
            if self._has(t, src):
                forms = v if isinstance(v, list) else [v]
                if not any(f.lower() in dst.lower() for f in forms):
                    issues.append({"type": "glossary", "detail": f"'{t}' must be rendered as {forms}",
                                   "suggestion": forms[0]})
        for k in self.keep:
            if self._has(k, src) and k.lower() not in dst.lower():
                issues.append({"type": "glossary", "detail": f"'{k}' must be left unchanged",
                               "suggestion": k})
        return issues
