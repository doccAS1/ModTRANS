from ..core.models import Decision

W_A, W_B = 0.6, 0.4


def aggregate(a, b):
    """Matrice decisionale. A = veto forte, B = veto morbido, pesi 0.6/0.4."""
    if not a.ok:                                   # errori di A (anche con B ok o assente)
        return Decision.REPAIR
    score = W_A * a.score + W_B * b.score
    if abs(a.score - b.score) > 0.4:               # disaccordo marcato -> umano
        return Decision.REVISION
    if not b.ok:                                   # solo B contesta: veto morbido
        return Decision.PUBLISH_WITH_NOTE if score >= 0.75 else Decision.REVISION
    return Decision.PUBLISH if score >= 0.85 else Decision.PUBLISH_WITH_NOTE
