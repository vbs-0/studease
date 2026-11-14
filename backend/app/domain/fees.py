"""Which fee schedule rows apply to a student on a given date (R-FEE-1, R-FEE-3)."""
from datetime import date

from app.enums import FEE_TYPES


def in_audience(student: dict, applies_to: str) -> bool:
    if applies_to == "ALL":
        return True
    if applies_to == "INTERNATIONAL":
        return student["residency"] == "INTERNATIONAL"
    if applies_to == "HOSTEL":
        return bool(student["hostel_resident"])
    raise ValueError(f"unknown audience {applies_to!r}")


def is_effective(row: dict, on: date) -> bool:
    """Effective range is inclusive on both ends; an empty `effective_to` is open ended."""
    return row["effective_from"] <= on and (row["effective_to"] is None or on <= row["effective_to"])


def eligible_fee_rows(student: dict, fee_rows: list[dict], issue_date: date) -> list[dict]:
    """Fee rows (already limited to the student's program and term) that produce a line, in fee-type order.

    Raises ValueError when two rows of one fee type are effective on the same date (R-FEE-2 is broken):
    charging both would double bill, so the data is rejected instead of guessed at.
    """
    chosen: dict[str, dict] = {}
    for row in fee_rows:
        if not in_audience(student, row["applies_to"]) or not is_effective(row, issue_date):
            continue
        if row["fee_type"] in chosen:
            raise ValueError(f"overlapping fee schedules for {row['fee_type']}: "
                             f"{chosen[row['fee_type']]['fee_schedule_id']} and {row['fee_schedule_id']}")
        chosen[row["fee_type"]] = row
    return [chosen[t] for t in FEE_TYPES if t in chosen]
