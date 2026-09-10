from pathlib import Path

import pytest

from app.edi214 import EDIParseError, parse_214

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_parse_enroute_sample():
    parsed = parse_214((SAMPLES / "01_enroute_ontime.edi").read_text())
    assert parsed.pro_number == "FLOCK8821"
    assert parsed.scac == "FLCK"
    assert parsed.shipper.name.startswith("NORTHWIND")
    assert parsed.consignee.city == "MILWAUKEE"
    assert parsed.po_number == "PO-88421"
    assert [e.status_code for e in parsed.events] == ["AF", "X6"]
    assert parsed.events[-1].city == "KENOSHA"


def test_parse_delay_code():
    parsed = parse_214((SAMPLES / "03_carrier_delay.edi").read_text())
    assert parsed.events[-1].status_code == "A9"
    assert parsed.events[-1].city == "ALBERT LEA"


def test_rejects_empty():
    with pytest.raises(EDIParseError):
        parse_214("   ")


def test_rejects_wrong_transaction():
    with pytest.raises(EDIParseError):
        parse_214("ST*210*0001~\nB10*P*S*SC~\nAT7*X6****20260910*0100~")
