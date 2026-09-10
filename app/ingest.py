from __future__ import annotations

from sqlalchemy.orm import Session

from app.delays import evaluate_shipment
from app.edi214 import Parsed214, parse_214
from app.models import IngestRecord, Shipment, ShipmentEvent
from app.notifications import notify_delay
from app.status_codes import status_label


def _upsert_shipment(db: Session, parsed: Parsed214) -> Shipment:
    row = (
        db.query(Shipment)
        .filter(Shipment.pro_number == parsed.pro_number, Shipment.scac == parsed.scac)
        .one_or_none()
    )
    if row is None:
        row = Shipment(pro_number=parsed.pro_number, scac=parsed.scac)
        db.add(row)

    row.shipment_id = parsed.shipment_id or row.shipment_id
    row.shipper_name = parsed.shipper.name or row.shipper_name
    row.shipper_city = parsed.shipper.city or row.shipper_city
    row.shipper_state = parsed.shipper.state or row.shipper_state
    row.consignee_name = parsed.consignee.name or row.consignee_name
    row.consignee_city = parsed.consignee.city or row.consignee_city
    row.consignee_state = parsed.consignee.state or row.consignee_state
    row.po_number = parsed.po_number or row.po_number
    row.bill_of_lading = parsed.bill_of_lading or row.bill_of_lading
    if parsed.promised_delivery:
        row.promised_delivery = parsed.promised_delivery
    db.flush()
    return row


def _add_events(db: Session, shipment: Shipment, parsed: Parsed214) -> int:
    added = 0
    for event in parsed.events:
        exists = (
            db.query(ShipmentEvent)
            .filter(
                ShipmentEvent.shipment_id == shipment.id,
                ShipmentEvent.status_code == event.status_code,
                ShipmentEvent.occurred_at == event.occurred_at,
                ShipmentEvent.city == event.city,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                status_code=event.status_code,
                status_label=status_label(event.status_code),
                reason_code=event.reason_code,
                city=event.city,
                state=event.state,
                country=event.country,
                occurred_at=event.occurred_at,
                raw_segment=event.raw_segment,
            )
        )
        added += 1
    db.flush()
    db.refresh(shipment)
    _refresh_current_status(shipment)
    return added


def _refresh_current_status(shipment: Shipment) -> None:
    if not shipment.events:
        return
    dated = [e for e in shipment.events if e.occurred_at]
    latest = max(dated, key=lambda e: e.occurred_at) if dated else shipment.events[-1]
    shipment.current_status = latest.status_code
    shipment.current_city = latest.city
    shipment.current_state = latest.state
    shipment.last_event_at = latest.occurred_at


def ingest_edi(db: Session, raw: str, filename: str = "paste.edi") -> tuple[Shipment, int, int]:
    parsed = parse_214(raw)
    shipment = _upsert_shipment(db, parsed)
    events_added = _add_events(db, shipment, parsed)

    archive = IngestRecord(
        filename=filename,
        payload=raw,
        control_number=parsed.interchange_control,
        shipment_id=shipment.id,
    )
    db.add(archive)

    alerts = 0
    for reason in evaluate_shipment(shipment):
        if notify_delay(db, shipment, reason):
            alerts += 1

    db.commit()
    db.refresh(shipment)
    return shipment, events_added, alerts
