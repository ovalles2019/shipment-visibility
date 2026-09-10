from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    pro_number: Mapped[str] = mapped_column(String(64), index=True)
    shipment_id: Mapped[str] = mapped_column(String(64), index=True)
    scac: Mapped[str] = mapped_column(String(8), default="")
    shipper_name: Mapped[str] = mapped_column(String(200), default="")
    shipper_city: Mapped[str] = mapped_column(String(80), default="")
    shipper_state: Mapped[str] = mapped_column(String(8), default="")
    consignee_name: Mapped[str] = mapped_column(String(200), default="")
    consignee_city: Mapped[str] = mapped_column(String(80), default="")
    consignee_state: Mapped[str] = mapped_column(String(8), default="")
    po_number: Mapped[str] = mapped_column(String(64), default="")
    bill_of_lading: Mapped[str] = mapped_column(String(64), default="")
    promised_delivery: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_status: Mapped[str] = mapped_column(String(8), default="")
    current_city: Mapped[str] = mapped_column(String(80), default="")
    current_state: Mapped[str] = mapped_column(String(8), default="")
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    events: Mapped[list[ShipmentEvent]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", order_by="ShipmentEvent.occurred_at"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("pro_number", "scac", name="uq_pro_scac"),)


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    status_code: Mapped[str] = mapped_column(String(8))
    status_label: Mapped[str] = mapped_column(String(80))
    reason_code: Mapped[str] = mapped_column(String(8), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(8), default="")
    country: Mapped[str] = mapped_column(String(8), default="")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_segment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    shipment: Mapped[Shipment] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint(
            "shipment_id", "status_code", "occurred_at", "city",
            name="uq_event_fingerprint",
        ),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(20), default="log")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    shipment: Mapped[Shipment] = relationship(back_populates="notifications")


class IngestRecord(Base):
    """Raw payload archive — the 'immutable inbound bucket' in cloud terms."""

    __tablename__ = "ingest_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), default="paste.edi")
    payload: Mapped[str] = mapped_column(Text)
    control_number: Mapped[str] = mapped_column(String(32), default="")
    shipment_id: Mapped[int | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
