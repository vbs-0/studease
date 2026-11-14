"""Helpers shared by the write endpoints: serialised id allocation, events, ledger rows, balance refresh.

Every write runs in one transaction and starts with `begin_write`, which takes a transaction-scoped advisory
lock. That one lock serialises id allocation (LED-, EVT-, PAY-, REF- numbers are max+1) across all writers, so two
requests can never be handed the same id. It also makes writes strictly sequential: fine for a demo and a
back-office tool, and the documented ceiling (docs/decisions.md): per-sequence database sequences would lift it."""
from datetime import date

from sqlalchemy import Connection, text

from app import ids
from app.domain import ledger

_LOCK = 20261022          # arbitrary application-wide advisory lock key


class Counters:
    """Next free number per id kind, read once under the lock and then counted up in memory."""

    def __init__(self, conn: Connection):
        def top(sql: str) -> int:
            return conn.execute(text(sql)).scalar() + 1
        self._next = {
            "ledger": top("SELECT coalesce(max(substr(entry_id, 5)::int), 0) FROM ledger_entry"),
            "event": top("SELECT coalesce(max(substr(event_id, 5)::int), 0) FROM event"),
            "payment": top("SELECT coalesce(max(substr(payment_id, 10)::int), 0) FROM payment"),
            "refund": top("SELECT coalesce(max(substr(refund_id, 10)::int), 0) FROM refund"),
            "student": top("SELECT coalesce(max(substr(student_id, 5)::int), 0) FROM student"),
            "user": top("SELECT coalesce(max(substr(app_user_id, 5)::int), 0) FROM app_user"),
            "eligibility": top("SELECT coalesce(max(substr(eligibility_id, 10)::int), 0) FROM eligibility"),
            "scholarship": top("SELECT coalesce(max(substr(scholarship_id, 10)::int), 0) FROM scholarship"),
        }

    def take(self, kind: str) -> int:
        n = self._next[kind]
        self._next[kind] = n + 1
        return n


def begin_write(conn: Connection) -> Counters:
    conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK})
    return Counters(conn)


def lock_student(conn: Connection, student_id: str) -> bool:
    """S-15: lock the student row so two writes for one student queue up. False if there is no such student."""
    return conn.execute(text("SELECT 1 FROM student WHERE student_id = :s FOR UPDATE"),
                        {"s": student_id}).first() is not None


def add_event(conn: Connection, c: Counters, entity_type: str, entity_id: str, frm: str | None, to: str,
              on: date, actor: str) -> None:
    conn.execute(text("INSERT INTO event (event_id, entity_type, entity_id, from_status, to_status, occurred_on, actor)"
                      " VALUES (:i, :t, :e, :f, :to, :d, :a)"),
                 {"i": ids.event_id(c.take("event")), "t": entity_type, "e": entity_id, "f": frm, "to": to, "d": on,
                  "a": actor})


def add_ledger(conn: Connection, c: Counters, entry: dict) -> None:
    conn.execute(text("INSERT INTO ledger_entry (entry_id, student_id, entry_type, amount_paise, posted_on,"
                      " source_type, source_id) VALUES (:entry_id, :student_id, :entry_type, :amount_paise, :posted_on,"
                      " :source_type, :source_id)"), {"entry_id": ids.ledger_id(c.take("ledger")), **entry})


def refresh_balance(conn: Connection, student_id: str, as_of: date) -> dict:
    """Re-state the student's balance from the ledger (R-LED-2) and return it."""
    entries = [dict(r) for r in conn.execute(text(
        "SELECT entry_type, amount_paise FROM ledger_entry WHERE student_id = :s"), {"s": student_id}).mappings()]
    s = ledger.summarise(entries)
    conn.execute(text("UPDATE student_balance SET charged_paise = :charged_paise, credits_paise = :credits_paise,"
                      " paid_paise = :paid_paise, refunded_paise = :refunded_paise, balance_paise = :balance_paise,"
                      " as_of = :d WHERE student_id = :s"), {**s, "d": as_of, "s": student_id})
    return s


def student_documents(conn: Connection, student_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    """The student's live invoices, their lines and every allocation on those lines."""
    invoices = [dict(r) for r in conn.execute(text(
        "SELECT * FROM invoice WHERE student_id = :s AND status NOT IN ('VOID', 'CANCELLED')"),
        {"s": student_id}).mappings()]
    lines = [dict(r) for r in conn.execute(text(
        "SELECT l.* FROM invoice_line l JOIN invoice i USING (invoice_id) WHERE i.student_id = :s"),
        {"s": student_id}).mappings()]
    allocs = [dict(r) for r in conn.execute(text(
        "SELECT a.* FROM payment_allocation a JOIN payment p USING (payment_id) WHERE p.student_id = :s"),
        {"s": student_id}).mappings()]
    return invoices, lines, allocs


def insert_row(conn: Connection, table: str, row: dict) -> None:
    """INSERT one row through SQLAlchemy Core: column names come from the schema, values are bound."""
    from app import schema
    conn.execute(schema.TABLES[table].insert(), {c: row.get(c) for c in schema.columns(table)})
