"""Minimal X12 EDI 214 parser.

Teaching note: production EDI stacks (Cleo, Orderful, Stedi, custom maps)
handle ISA envelopes, partner-specific qualifiers, and 997 acknowledgements.
This parser is intentionally small so you can read every line and still
extract the shipment events a visibility platform cares about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


class EDIParseError(ValueError):
    pass


@dataclass
class Party:
    name: str = ""
    city: str = ""
    state: str = ""


@dataclass
class StatusEvent:
    status_code: str
    reason_code: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    occurred_at: datetime | None = None
    raw_segment: str = ""


@dataclass
class Parsed214:
    interchange_control: str = ""
    pro_number: str = ""
    shipment_id: str = ""
    scac: str = ""
    po_number: str = ""
    bill_of_lading: str = ""
    shipper: Party = field(default_factory=Party)
    consignee: Party = field(default_factory=Party)
    promised_delivery: datetime | None = None
    events: list[StatusEvent] = field(default_factory=list)
    transaction_set: str = ""
    raw: str = ""


def _split_segments(raw: str) -> list[str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise EDIParseError("Empty EDI payload")
    if "~" in text:
        parts = [p.strip() for p in text.split("~")]
    else:
        parts = [p.strip() for p in text.split("\n")]
    return [p for p in parts if p]


def _parse_dt(date_s: str, time_s: str = "") -> datetime | None:
    date_s = (date_s or "").strip()
    time_s = (time_s or "").strip()
    if not date_s:
        return None
    if len(date_s) == 6:
        date_s = "20" + date_s
    if len(date_s) != 8 or not date_s.isdigit():
        return None
    hour, minute = 0, 0
    if len(time_s) >= 4 and time_s[:4].isdigit():
        hour, minute = int(time_s[:2]), int(time_s[2:4])
    try:
        return datetime(int(date_s[:4]), int(date_s[4:6]), int(date_s[6:8]), hour, minute)
    except ValueError:
        return None


def parse_214(raw: str) -> Parsed214:
    segments = _split_segments(raw)
    parsed = Parsed214(raw=raw)
    saw_st = False
    current: StatusEvent | None = None
    last_n1: str | None = None

    for seg in segments:
        el = seg.split("*")
        tag = el[0].strip().upper()

        if tag == "ISA":
            parsed.interchange_control = el[13].strip() if len(el) > 13 else ""
        elif tag == "ST":
            parsed.transaction_set = el[1].strip() if len(el) > 1 else ""
            if parsed.transaction_set and parsed.transaction_set != "214":
                raise EDIParseError(f"Expected ST*214, got ST*{parsed.transaction_set}")
            saw_st = True
        elif tag == "B10":
            parsed.pro_number = el[1].strip() if len(el) > 1 else ""
            parsed.shipment_id = el[2].strip() if len(el) > 2 else ""
            parsed.scac = el[3].strip() if len(el) > 3 else ""
        elif tag == "L11" and len(el) > 2:
            value, qual = el[1].strip(), el[2].strip().upper()
            if qual == "PO":
                parsed.po_number = value
            elif qual in {"BM", "BOL"}:
                parsed.bill_of_lading = value
        elif tag == "N1" and len(el) > 2:
            last_n1 = el[1].strip().upper()
            name = el[2].strip()
            if last_n1 == "SH":
                parsed.shipper.name = name
            elif last_n1 == "CN":
                parsed.consignee.name = name
        elif tag == "N4" and last_n1 in {"SH", "CN"}:
            city = el[1].strip() if len(el) > 1 else ""
            state = el[2].strip() if len(el) > 2 else ""
            party = parsed.shipper if last_n1 == "SH" else parsed.consignee
            party.city, party.state = city, state
        elif tag == "G62" and len(el) > 2:
            qual = el[1].strip().upper()
            # 17 = estimated delivery, EP = promised, 68 = current scheduled
            if qual in {"17", "EP", "68", "70"}:
                parsed.promised_delivery = _parse_dt(el[2], el[3] if len(el) > 3 else "")
        elif tag == "AT7":
            if current:
                parsed.events.append(current)
            current = StatusEvent(
                status_code=el[1].strip().upper() if len(el) > 1 else "",
                reason_code=el[2].strip().upper() if len(el) > 2 else "",
                occurred_at=_parse_dt(el[5] if len(el) > 5 else "", el[6] if len(el) > 6 else ""),
                raw_segment=seg,
            )
        elif tag == "MS1" and current:
            current.city = el[1].strip() if len(el) > 1 else ""
            current.state = el[2].strip() if len(el) > 2 else ""
            current.country = el[3].strip() if len(el) > 3 else ""
            current.raw_segment = f"{current.raw_segment}~{seg}"

    if current:
        parsed.events.append(current)

    if not saw_st:
        raise EDIParseError("No ST (transaction set) segment found")
    if not parsed.pro_number:
        raise EDIParseError("B10 is missing a PRO number")
    if not parsed.events:
        raise EDIParseError("No AT7 status events found")
    return parsed
