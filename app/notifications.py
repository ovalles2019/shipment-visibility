from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Notification, Shipment

log = logging.getLogger("shipvis.notify")


def already_sent(db: Session, shipment_id: int, kind: str) -> bool:
    return (
        db.query(Notification)
        .filter(Notification.shipment_id == shipment_id, Notification.kind == kind)
        .first()
        is not None
    )


def notify_delay(db: Session, shipment: Shipment, reason: str) -> Notification | None:
    """Idempotent delay alert. Log always; webhook/SMTP if configured."""
    kind = f"delay:{reason}"
    if already_sent(db, shipment.id, kind):
        return None

    message = (
        f"DELAY {shipment.pro_number} ({shipment.scac}) "
        f"{shipment.shipper_name} → {shipment.consignee_name} "
        f"status={shipment.current_status} promised={shipment.promised_delivery} "
        f"reason={reason}"
    )
    channel = "log"
    log.warning(message)

    if settings.notify_webhook_url:
        try:
            httpx.post(
                settings.notify_webhook_url,
                json={
                    "pro_number": shipment.pro_number,
                    "scac": shipment.scac,
                    "reason": reason,
                    "status": shipment.current_status,
                    "message": message,
                },
                timeout=5.0,
            )
            channel = "webhook"
        except httpx.HTTPError as exc:
            log.error("Webhook notify failed: %s", exc)

    if settings.smtp_host:
        try:
            _send_smtp(f"Delayed shipment {shipment.pro_number}", message)
            channel = "email"
        except OSError as exc:
            log.error("SMTP notify failed: %s", exc)

    row = Notification(shipment_id=shipment.id, kind=kind, channel=channel, message=message)
    db.add(row)
    db.flush()
    return row


def _send_smtp(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.smtp_to
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=8) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
