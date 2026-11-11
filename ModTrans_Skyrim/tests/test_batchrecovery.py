import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from skyrimtrans.translator import AbortRun, Translator, _parse_list  # noqa: E402

ITEMS = [("dialogue", f"This is line number {i} of the test.") for i in range(40)]


def ok_reply(items, mark="IT "):
    return json.dumps([{"id": it["id"], "text": mark + it["text"]} for it in items])


class Model:
    """Modello finto: `behave(items)` decide la risposta; registra le dimensioni delle richieste."""
    def __init__(self, behave):
        self.behave, self.sizes = behave, []

    def __call__(self, system, user):
        items = json.loads(user)
        self.sizes.append(len(items))
        return self.behave(items)


def run(model, items=ITEMS, **kw):
    tr = Translator(model, "Italian", sleep=lambda s: None, batch_items=40, **kw)
    return tr, tr.translate_all(items)


def all_translated(tr, res, items=ITEMS):
    return len(res) == len(items) and not tr.failed and all(res[k].startswith("IT ") for k in items)


def test_big_batch_the_model_cannot_handle_is_split(monkeypatch):
    """Oltre 10 stringhe il modello risponde fuori formato: dividendo il lotto si traducono tutte."""
    m = Model(lambda items: ok_reply(items) if len(items) <= 10 else "Certo! Ecco le traduzioni, buon lavoro.")
    tr, res = run(m)
    assert all_translated(tr, res)
    assert tr.stats["splits"] >= 2
    assert m.sizes == [40, 20, 10, 10, 20, 10, 10]       # 40 non regge: 20+20, e 20 non regge: 10+10 (7 richieste in tutto)


def test_truncated_reply_keeps_what_was_complete():
    def behave(items):
        text = ok_reply(items)
        if len(items) > 8:
            return text[: len(text) // 2]               # risposta tagliata a metà
        return text
    m = Model(behave)
    tr, res = run(m)
    assert all_translated(tr, res)
    assert m.sizes[1] < 40                              # il secondo giro chiede solo ciò che mancava (o meno)
    assert not tr.stats.get("splits")                   # risposta parziale: si richiede il resto, non si divide


def test_unescaped_quotes_in_one_item_are_recovered():
    def behave(items):
        out = []
        for it in items:
            t = "IT " + it["text"]
            out.append('{"id": %d, "text": "%s"}' % (it["id"], t.replace("line number 7 ", 'line "number" 7 ')))
        return "[" + ", ".join(out) + "]"
    tr, res = run(Model(behave))
    assert all_translated(tr, res)
    assert res[ITEMS[7]] == 'IT This is line "number" 7 of the test.'


def test_model_that_never_answers_still_stops_quickly():
    m = Model(lambda items: "Non posso aiutarti con questo.")
    tr = Translator(m, "Italian", sleep=lambda s: None, batch_items=40)
    with pytest.raises(AbortRun):
        tr.translate_all(ITEMS)
    assert len(m.sizes) < 40                             # l'interruttore di sicurezza scatta, niente richieste all'infinito


def test_good_replies_cost_one_request_per_batch_as_before():
    m = Model(ok_reply)
    tr, res = run(m)
    assert all_translated(tr, res) and m.sizes == [40] and not tr.stats.get("splits")


def test_single_bad_item_does_not_take_down_the_others():
    def behave(items):
        return json.dumps([{"id": it["id"], "text": "IT " + it["text"]} for it in items if "number 3 " not in it["text"]])
    tr, res = run(Model(behave))
    assert list(tr.failed) == [ITEMS[3]] and "mancante" in tr.failed[ITEMS[3]]
    assert len(res) == 39


def test_parse_list_variants():
    assert _parse_list('```json\n[{"id": 0, "text": "a"}]\n```') == [{"id": 0, "text": "a"}]
    assert _parse_list('Ecco: [{"id": 0, "text": "a"}, {"id": 1, "text": "b"') == [{"id": 0, "text": "a"}]
    assert [o["id"] for o in _parse_list('[{"id": 0, "ok": true}, {"id": 1, "ok": false, "fix": "x"}')] == [0, 1]
    with pytest.raises(ValueError):
        _parse_list("nessun json qui")
