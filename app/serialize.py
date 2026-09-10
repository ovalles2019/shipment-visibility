from __future__ import annotations

from app.models import Shipment
from app.schemas import EventOut, NotificationOut, ShipmentDetail, ShipmentOut
from app.status_codes import bucket_for, status_label


def shipment_out(row: Shipment) -> ShipmentOut:
    return ShipmentOut(
        id=row.id,
        pro_number=row.pro_number,
        shipment_id=row.shipment_id,
        scac=row.scac,
        shipper_name=row.shipper_name,
        shipper_city=row.shipper_city,
        shipper_state=row.shipper_state,
        consignee_name=row.consignee_name,
        consignee_city=row.consignee_city,
        consignee_state=row.consignee_state,
        po_number=row.po_number,
        bill_of_lading=row.bill_of_lading,
        promised_delivery=row.promised_delivery,
        current_status=row.current_status,
        current_status_label=status_label(row.current_status),
        current_city=row.current_city,
        current_state=row.current_state,
        last_event_at=row.last_event_at,
        overdue=row.overdue,
        bucket=bucket_for(row.current_status, row.overdue),
        event_count=len(row.events),
    )


def shipment_detail(row: Shipment) -> ShipmentDetail:
    base = shipment_out(row)
    return ShipmentDetail(
        **base.model_dump(),
        events=[EventOut.model_validate(e) for e in row.events],
        notifications=[NotificationOut.model_validate(n) for n in row.notifications],
    )
