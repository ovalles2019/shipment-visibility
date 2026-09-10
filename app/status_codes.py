"""EDI 214 AT7 shipment-status codes used in this demo.

A real carrier 214 catalog is longer. This subset is enough to teach
extraction, normalization, and delay rules without drowning in X12.
"""

from __future__ import annotations

STATUS_CODES: dict[str, str] = {
    "AF": "Departed pickup",
    "X1": "Arrived at pickup",
    "X3": "Arrived at delivery",
    "X4": "Arrived at terminal",
    "X6": "En route",
    "X8": "Attempted delivery",
    "AM": "Loaded on equipment",
    "CP": "Completed loading",
    "D1": "Completed unloading at delivery",
    "CD": "Completed unloading",
    "AV": "Available for delivery",
    "AG": "Estimated delivery",
    "AA": "Pickup appointment",
    "AB": "Delivery appointment",
    "AJ": "Tendered to carrier",
    "A9": "Shipment delayed",
    "SD": "Shipment delayed",
    "AP": "Delivery not completed",
    "A7": "Refused by consignee",
    "A3": "Returned to shipper",
    "P1": "Departed terminal",
    "OA": "Outgated",
}

DELIVERED_CODES = frozenset({"D1", "CD"})
DELAY_CODES = frozenset({"A9", "SD", "AP", "A7"})
TERMINAL_CODES = DELIVERED_CODES | frozenset({"A3", "A7"})


def status_label(code: str | None) -> str:
    if not code:
        return "Unknown"
    return STATUS_CODES.get(code.upper(), f"Unmapped status ({code})")


def bucket_for(code: str | None, overdue: bool = False) -> str:
    """Coarse dashboard bucket: delivered | delayed | in_transit | exception."""
    if not code:
        return "in_transit"
    code = code.upper()
    if code in DELIVERED_CODES:
        return "delivered"
    if code in DELAY_CODES or overdue:
        return "delayed"
    if code in {"A3", "A7"}:
        return "exception"
    return "in_transit"
