"""Small factories so each test states only what it cares about. Money helper: rs(1_000) is INR 1,000 in paise."""
from datetime import date
from decimal import Decimal

import pytest


def rs(rupees: int) -> int:
    return rupees * 100


def make_student(**kw) -> dict:
    base = {"student_id": "STU-000001", "program_id": "PRG-01", "residency": "DOMESTIC", "gpa": Decimal("7.00"),
            "income_band": "MID", "sports_quota": False, "hostel_resident": False, "waiver_type": None}
    return {**base, **kw}


def make_fee(fee_type: str, rupees: int, applies_to: str = "ALL", frm: date = date(2026, 1, 1),
             to: date | None = None, version: int = 1, eligible: bool | None = None) -> dict:
    return {"fee_schedule_id": f"FEE-PRG-01-2026-FALL-{fee_type}-V{version}", "fee_type": fee_type,
            "applies_to": applies_to, "amount_paise": rs(rupees), "effective_from": frm, "effective_to": to,
            "version": version, "scholarship_eligible": fee_type in ("TUITION", "LAB") if eligible is None
            else eligible}


@pytest.fixture
def student():
    return make_student


@pytest.fixture
def fee():
    return make_fee
