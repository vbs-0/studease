"""Deterministic identifiers. Counters are zero padded, ids are immutable and carry their parents, so an id
seen in a log or a CSV says what it is and where it belongs. Every table's primary key has a pattern here;
validation check 1 matches each key against it."""
import re

YEAR = 2026


def program_id(n: int) -> str:
    return f"PRG-{n:02d}"


def term_id(term_name: str, year: int = YEAR) -> str:
    return f"TERM-{year}-{term_name}"


def student_id(n: int) -> str:
    return f"STU-{n:06d}"


def student_no(sid: str) -> int:
    """STU-000042 -> 42"""
    return int(sid.split("-")[1])


def fee_schedule_id(prog: str, term_name: str, fee_type: str, version: int, year: int = YEAR) -> str:
    return f"FEE-{prog}-{year}-{term_name}-{fee_type}-V{version}"


def enrollment_id(sid_no: int, term_name: str, year: int = YEAR) -> str:
    return f"ENR-{sid_no:06d}-{year}-{term_name}"


def invoice_id(sid_no: int, seq: int, year: int = YEAR) -> str:
    return f"INV-STU-{sid_no:06d}-{year}-{seq:06d}"


def invoice_line_id(inv: str, n: int) -> str:
    return f"{inv}-L{n:02d}"


def eligibility_id(n: int, year: int = YEAR) -> str:
    return f"ELG-{year}-{n:06d}"


def scholarship_id(n: int, year: int = YEAR) -> str:
    return f"SCH-{year}-{n:06d}"


def payment_id(n: int, year: int = YEAR) -> str:
    return f"PAY-{year}-{n:06d}"


def allocation_id(pay: str, n: int) -> str:
    return f"ALLOC-{pay}-{n:02d}"


def refund_id(n: int, year: int = YEAR) -> str:
    return f"REF-{year}-{n:06d}"


def ledger_id(n: int) -> str:
    return f"LED-{n:07d}"


def event_id(n: int) -> str:
    return f"EVT-{n:07d}"


def exception_id(n: int) -> str:
    return f"EXC-{n:06d}"


def gt_id(n: int) -> str:
    return f"GT-{n:06d}"


def user_id(n: int) -> str:
    return f"USR-{n:06d}"


_TERM = "SPRING|SUMMER|FALL"
_INV = r"INV-STU-\d{6}-\d{4}-\d{6}"
PATTERNS: dict[str, re.Pattern] = {k: re.compile(v) for k, v in {
    "program": r"PRG-\d{2}",
    "term": rf"TERM-\d{{4}}-({_TERM})",
    "scholarship_scheme": r"[A-Z_]+",
    "student": r"STU-\d{6}",
    "fee_schedule": rf"FEE-PRG-\d{{2}}-\d{{4}}-({_TERM})-[A-Z_]+-V\d+",
    "enrollment": rf"ENR-\d{{6}}-\d{{4}}-({_TERM})",
    "invoice": _INV,
    "eligibility": r"ELG-\d{4}-\d{6}",
    "scholarship": r"SCH-\d{4}-\d{6}",
    "invoice_line": rf"{_INV}-L\d{{2,3}}",
    "payment": r"PAY-\d{4}-\d{6}",
    "payment_allocation": r"ALLOC-PAY-\d{4}-\d{6}-\d{2,3}",
    "refund": r"REF-\d{4}-\d{6}",
    "ledger_entry": r"LED-\d{7}",
    "student_balance": r"STU-\d{6}",
    "event": r"EVT-\d{7}",
    "app_user": r"USR-\d{6}",
    "exception": r"EXC-\d{6}",
    "ground_truth": r"GT-\d{6}",
}.items()}


def matches(table: str, value: str) -> bool:
    """True if `value` is a well-formed primary key for `table` (whole string must match)."""
    return PATTERNS[table].fullmatch(value) is not None
