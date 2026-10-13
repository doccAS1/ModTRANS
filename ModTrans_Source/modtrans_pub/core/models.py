from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    PUBLISH = "PUBLISH"
    PUBLISH_WITH_NOTE = "PUBLISH_WITH_NOTE"
    REPAIR = "REPAIR"
    REVISION = "REVISION"   # revisione umana
    BLOCK = "BLOCK"


@dataclass
class Unit:
    key: str
    source: str
    file: str = ""
    masked: str = ""
    tokens: list = field(default_factory=list)


@dataclass
class Verdict:
    judge: str
    ok: bool
    score: float
    issues: list = field(default_factory=list)  # [{"type","detail","suggestion"}]
    hard: bool = False                          # errore strutturale (veto forte)
