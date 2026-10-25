from ..core.models import Decision

W_A, W_B = 0.6, 0.4


def aggregate(a, b):
    """Matrice decisionale. A = veto forte, B = veto morbido, pesi 0.6/0.4.

    `a` o `b` possono essere None quando quel giudice non è configurato:
    in quel caso decide solo il giudice presente.
    """
    if a is not None and not a.ok:                 # errori di A (anche con B ok o assente)
        return Decision.REPAIR
    if a is None and b is None:
        return Decision.PUBLISH
    if b is None:                                  # solo A
        return Decision.PUBLISH if a.score >= 0.85 else Decision.PUBLISH_WITH_NOTE
    if a is None:                                  # solo B (veto morbido)
        if not b.ok:
            return Decision.PUBLISH_WITH_NOTE if b.score >= 0.75 else Decision.REVISION
        return Decision.PUBLISH if b.score >= 0.85 else Decision.PUBLISH_WITH_NOTE
    score = W_A * a.score + W_B * b.score
    if abs(a.score - b.score) > 0.4:               # disaccordo marcato -> umano
        return Decision.REVISION
    if not b.ok:                                   # solo B contesta: veto morbido
        return Decision.PUBLISH_WITH_NOTE if score >= 0.75 else Decision.REVISION
    return Decision.PUBLISH if score >= 0.85 else Decision.PUBLISH_WITH_NOTE
