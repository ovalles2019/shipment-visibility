from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Shipment
from app.notifications import notify_delay
from app.status_codes import DELAY_CODES, DELIVERED_CODES, TERMINAL_CODES


def evaluate_shipment(shipment: Shipment, now: datetime | None = None) -> list[str]:
    """Return delay reasons for one shipment. Does not write."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    reasons: list[str] = []
    code = (shipment.current_status or "").upper()

    if code in DELAY_CODES:
        reasons.append("carrier_delay_code")
    if (
        shipment.promised_delivery
        and shipment.promised_delivery < now
        and code not in TERMINAL_CODES
    ):
        reasons.append("missed_promised_delivery")
        shipment.overdue = True
    elif code in DELIVERED_CODES:
        shipment.overdue = False
    return reasons


def scan_and_notify(db: Session) -> int:
    created = 0
    for shipment in db.query(Shipment).all():
        for reason in evaluate_shipment(shipment):
            if notify_delay(db, shipment, reason):
                created += 1
    db.commit()
    return created
