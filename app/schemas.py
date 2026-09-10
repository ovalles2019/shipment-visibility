from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    content: str = Field(min_length=10, description="Raw X12 EDI 214 text")
    filename: str = "paste.edi"


class EventOut(BaseModel):
    id: int
    status_code: str
    status_label: str
    reason_code: str
    city: str
    state: str
    country: str
    occurred_at: datetime | None
    raw_segment: str

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: int
    shipment_id: int
    kind: str
    channel: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ShipmentOut(BaseModel):
    id: int
    pro_number: str
    shipment_id: str
    scac: str
    shipper_name: str
    shipper_city: str
    shipper_state: str
    consignee_name: str
    consignee_city: str
    consignee_state: str
    po_number: str
    bill_of_lading: str
    promised_delivery: datetime | None
    current_status: str
    current_status_label: str
    current_city: str
    current_state: str
    last_event_at: datetime | None
    overdue: bool
    bucket: str
    event_count: int = 0

    model_config = {"from_attributes": True}


class ShipmentDetail(ShipmentOut):
    events: list[EventOut] = []
    notifications: list[NotificationOut] = []


class IngestResponse(BaseModel):
    shipment: ShipmentDetail
    events_added: int
    delay_alerts: int


class StatsOut(BaseModel):
    total: int
    in_transit: int
    delayed: int
    delivered: int
    exception: int
    notifications: int
