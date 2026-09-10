from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.ingest import ingest_edi
from app.models import Shipment

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def seed_if_empty(db: Session) -> int:
    if db.query(Shipment).count():
        return 0
    return load_samples(db)


def load_samples(db: Session) -> int:
    loaded = 0
    if not SAMPLES.exists():
        return 0
    for path in sorted(SAMPLES.glob("*.edi")):
        ingest_edi(db, path.read_text(), filename=path.name)
        loaded += 1
    return loaded
