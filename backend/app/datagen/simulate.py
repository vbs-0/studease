"""Simulation phase 3: walk the calendar and apply the rules in date order.

On each day, in this order: invoices are issued (carried credit applied), payments arrive and are allocated, late
fees are posted, students leave (adjustment, de-allocation, refund), unused credit is refunded. Every state change
is also written as an event; ledger entries, balances and statuses are then derived from the source rows.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app import ids
from app.datagen.plan import Item, World, plan_payments
from app.datagen.scale import Scale
from app.domain import ledger, status
from app.domain.allocation import allocate, open_lines
from app.domain.billing import make_line, outstanding_by_line
from app.domain.calendar import AS_OF
from app.domain.latefees import late_fee, late_fee_date
from app.domain.withdrawal import adjustment_lines, excess_by_line, plan_reversals, refund_due, refund_share_bp
from app.enums import LEDGER_TYPES

STALE_DAYS = 30        # R-PAY-5
REFUND_PAY_DAYS = 3    # R-REF-3
LEDGER_ORDER = {t: i for i, t in enumerate(LEDGER_TYPES)}


class Student:
    """Mutable per-student state while the calendar is walked."""
    def __init__(self) -> None:
        self.issued: list[dict] = []        # invoices issued so far
        self.lines: list[dict] = []         # lines of issued invoices
        self.allocs: list[dict] = []
        self.payments: list[dict] = []
        self.refunds: list[dict] = []
        self.unapplied: dict[str, int] = {}


class Sim:
    def __init__(self, world: World) -> None:
        self.world = world
        self.state: dict[str, Student] = defaultdict(Student)
        self.alloc_count: dict[str, int] = defaultdict(int)
        self.allocations: list[dict] = []
        self.refunds: list[dict] = []
        self.items_by_invoice = {it.invoice["invoice_id"]: it for it in world.items}

    # ------------------------------------------------------------------------------ allocation
    def _alloc_row(self, pid: str, line_id: str, amount: int, on: date, st: Student) -> None:
        self.alloc_count[pid] += 1
        row = {"allocation_id": ids.allocation_id(pid, self.alloc_count[pid]), "payment_id": pid,
               "invoice_line_id": line_id, "amount_paise": amount, "allocated_on": on}
        st.allocs.append(row)
        self.allocations.append(row)

    def apply_credit(self, st: Student, pid: str, on: date) -> None:
        """Allocate a payment's unapplied money to the student's open charge lines (R-PAY-1 to R-PAY-3)."""
        left = st.unapplied.get(pid, 0)
        if left <= 0:
            return
        chosen, rest = allocate(left, open_lines(st.issued, st.lines, st.allocs))
        for line_id, amount in chosen:
            self._alloc_row(pid, line_id, amount, on, st)
        st.unapplied[pid] = rest

    def _add_line(self, it: Item, st: Student, line: dict) -> None:
        it.lines.append(line)
        st.lines.append(line)

    # ------------------------------------------------------------------------------ day events
    def issue(self, it: Item, day: date) -> None:
        st = self.state[it.invoice["student_id"]]
        st.issued.append(it.invoice)
        st.lines.extend(it.lines)
        for p in st.payments:                                  # carried credit, oldest payment first
            self.apply_credit(st, p["payment_id"], day)

    def receive(self, p: dict, day: date) -> None:
        st = self.state[p["student_id"]]
        st.payments.append(p)
        st.unapplied[p["payment_id"]] = p["amount_paise"]
        self.apply_credit(st, p["payment_id"], day)

    def late_fee(self, it: Item, day: date) -> None:
        if it.leave and it.leave[0] < day:                     # R-LATE-3
            return
        st = self.state[it.invoice["student_id"]]
        owed = sum(v for v in outstanding_by_line(it.lines, st.allocs).values() if v > 0)
        fee = late_fee(owed)
        if fee > 0:
            self._add_line(it, st, make_line(it.invoice["invoice_id"], len(it.lines) + 1, "LATE_FEE", fee, day,
                                             "Late fee"))

    def _refund(self, st: Student, student_id: str, invoice_id: str | None, pid: str, amount: int, reason: str,
                day: date) -> None:
        paid_on = day + timedelta(days=REFUND_PAY_DAYS)
        row = {"refund_id": ids.refund_id(len(self.refunds) + 1), "student_id": student_id,
               "invoice_id": invoice_id, "payment_id": pid, "amount_paise": amount, "reason": reason,
               "status": "PAID" if paid_on <= AS_OF else "APPROVED", "approved_on": day,
               "paid_on": paid_on if paid_on <= AS_OF else None}
        self.refunds.append(row)
        st.refunds.append(row)
        st.unapplied[pid] = st.unapplied.get(pid, 0) - amount

    def leave(self, it: Item, day: date) -> None:
        """R-WD, R-REF: adjust the invoice, de-allocate what is now overpaid, refund up to the net paid."""
        st = self.state[it.invoice["student_id"]]
        left_on, kind = it.leave
        for line in adjustment_lines(it.invoice["invoice_id"], it.lines, refund_share_bp(left_on, it.term),
                                     len(it.lines) + 1, day):
            self._add_line(it, st, line)
        returned: dict[str, int] = {}
        for pid, line_id, amount in plan_reversals(st.allocs, excess_by_line(it.lines, st.allocs)):
            self._alloc_row(pid, line_id, -amount, day, st)
            st.unapplied[pid] += amount
            returned[pid] = returned.get(pid, 0) + amount
        net_paid = sum(p["amount_paise"] for p in st.payments) - sum(r["amount_paise"] for r in st.refunds)
        budget = refund_due(sum(returned.values()), net_paid)  # R-REF-2
        for pid, amount in returned.items():
            give = min(amount, budget)
            if give > 0:
                self._refund(st, it.invoice["student_id"], it.invoice["invoice_id"], pid, give,
                             "CANCELLATION" if kind == "CANCELLED" else "WITHDRAWAL", day)
                budget -= give

    def stale(self, p: dict, day: date) -> None:
        """R-PAY-5: credit still unused 30 days after receipt, with no open invoice, goes back."""
        st = self.state[p["student_id"]]
        unused = st.unapplied.get(p["payment_id"], 0)
        if unused <= 0 or any(v > 0 for v in outstanding_by_line(st.lines, st.allocs).values()):
            return
        self._refund(st, p["student_id"], None, p["payment_id"], unused, "OVERPAYMENT", day)

    # ------------------------------------------------------------------------------ the calendar
    def run(self) -> None:
        issue_on, late_on, leave_on, pay_on, stale_on = (defaultdict(list) for _ in range(5))
        for it in self.world.items:
            issue_on[it.term.issue].append(it)
            late_on[late_fee_date(it.term.due)].append(it)
            if it.leave:
                leave_on[it.leave[0]].append(it)
        for p in self.world.payments:
            pay_on[p["received_on"]].append(p)
            stale_on[p["received_on"] + timedelta(days=STALE_DAYS)].append(p)
        days = sorted(d for d in {*issue_on, *late_on, *leave_on, *pay_on, *stale_on} if d <= AS_OF)
        for day in days:
            for it in issue_on[day]:
                self.issue(it, day)
            for p in pay_on[day]:
                self.receive(p, day)
            for it in late_on[day]:
                self.late_fee(it, day)
            for it in leave_on[day]:
                self.leave(it, day)
            for p in stale_on[day]:
                self.stale(p, day)


# ---------------------------------------------------------------------------------------------- derive
def _checkpoints(*groups) -> list[date]:
    return sorted({d for g in groups for d in g})


def build_dataset(world: World, scale: Scale, seed: int) -> dict[str, list[dict]]:
    """Run the simulation and return every table as a list of row dicts (parent first, sorted by key)."""
    plan_payments(world, scale, seed)
    sim = Sim(world)
    sim.run()

    events: list[tuple] = []     # (date, seq, entity_type, entity_id, from, to)

    def emit(on: date, etype: str, eid: str, frm: str | None, to: str) -> None:
        events.append((on, len(events), etype, eid, frm, to))

    allocs_by_line: dict[str, list[dict]] = defaultdict(list)
    for a in sim.allocations:
        allocs_by_line[a["invoice_line_id"]].append(a)
    refunds_by_payment: dict[str, list[dict]] = defaultdict(list)
    for rf in sim.refunds:
        refunds_by_payment[rf["payment_id"]].append(rf)
    allocs_by_payment: dict[str, list[dict]] = defaultdict(list)
    for a in sim.allocations:
        allocs_by_payment[a["payment_id"]].append(a)

    # invoices and enrollments, eligibility, scholarships
    for it in world.items:
        inv, enr = it.invoice, it.enrollment
        lines = it.lines
        mine = [a for ln in lines for a in allocs_by_line.get(ln["invoice_line_id"], [])]
        cancelled = bool(it.leave and it.leave[1] == "CANCELLED")
        owed = sum(outstanding_by_line(lines, mine).values())
        inv["total_paise"] = sum(ln["amount_paise"] for ln in lines)
        inv["status"] = status.invoice_status(False, cancelled, owed, sum(a["amount_paise"] for a in mine),
                                              inv["due_date"], AS_OF)
        # invoice history: replay the status at every date something changed
        marks = _checkpoints({inv["issue_date"], inv["due_date"] + timedelta(days=1), AS_OF},
                             (ln["posted_on"] for ln in lines), (a["allocated_on"] for a in mine),
                             [it.leave[0]] if cancelled else [])
        emit(inv["issue_date"], "invoice", inv["invoice_id"], None, "ISSUED")
        prev = "ISSUED"
        for d in marks:
            if d > AS_OF:
                continue
            seen = [ln for ln in lines if ln["posted_on"] <= d]
            got = [a for a in mine if a["allocated_on"] <= d]
            now = status.invoice_status(False, cancelled and d >= it.leave[0],
                                        sum(outstanding_by_line(seen, got).values()),
                                        sum(a["amount_paise"] for a in got), inv["due_date"], d)
            if now != prev:
                emit(d, "invoice", inv["invoice_id"], prev, now)
                prev = now
        emit(enr["enrolled_on"], "enrollment", enr["enrollment_id"], None, "ENROLLED")
        if it.leave:
            emit(it.leave[0], "enrollment", enr["enrollment_id"], "ENROLLED", it.leave[1])
        elif it.term.end <= AS_OF:
            emit(it.term.end, "enrollment", enr["enrollment_id"], "ENROLLED", "COMPLETED")
        if it.scholarship:
            s = it.scholarship
            emit(s["awarded_on"], "scholarship", s["scholarship_id"], None, "AWARDED")
            emit(it.term.issue, "scholarship", s["scholarship_id"], "AWARDED", "APPLIED")
            if cancelled:
                emit(it.leave[0], "scholarship", s["scholarship_id"], "APPLIED", "REVOKED")

    for e in world.eligibility:
        emit(e["decided_on"], "eligibility", e["eligibility_id"], None, e["decision"])

    for p in world.payments:
        pid = p["payment_id"]
        mine, refs = allocs_by_payment.get(pid, []), refunds_by_payment.get(pid, [])
        emit(p["received_on"], "payment", pid, None, "RECEIVED")
        prev = "RECEIVED"
        for d in _checkpoints({p["received_on"]}, (a["allocated_on"] for a in mine), (r["approved_on"] for r in refs)):
            applied = sum(a["amount_paise"] for a in mine if a["allocated_on"] <= d)
            returned = sum(r["amount_paise"] for r in refs if r["approved_on"] <= d)
            now = status.payment_status(p["amount_paise"], applied, returned)
            if now == "RECEIVED" and prev != "RECEIVED":
                now = "PARTIALLY_ALLOCATED"
            if now != prev:
                emit(d, "payment", pid, prev, now)
                prev = now
        p["status"] = prev

    for rf in sim.refunds:
        emit(rf["approved_on"], "refund", rf["refund_id"], None, "APPROVED")
        if rf["paid_on"]:
            emit(rf["paid_on"], "refund", rf["refund_id"], "APPROVED", "PAID")

    # ledger and balances (R-LED)
    entries: list[dict] = []
    for it in world.items:
        entries += [ledger.entry_for_line(it.invoice["student_id"], ln) for ln in it.lines]
    entries += [ledger.entry_for_payment(p) for p in world.payments]
    entries += [ledger.entry_for_refund(r) for r in sim.refunds]
    entries.sort(key=lambda e: (e["posted_on"], e["student_id"], LEDGER_ORDER[e["entry_type"]], e["source_id"]))
    for n, e in enumerate(entries, 1):
        e["entry_id"] = ids.ledger_id(n)
    by_student: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_student[e["student_id"]].append(e)
    balances = [{"student_id": s["student_id"], **ledger.summarise(by_student[s["student_id"]]), "as_of": AS_OF}
                for s in world.students]

    events.sort(key=lambda e: (e[0], e[1]))
    event_rows = [{"event_id": ids.event_id(n), "entity_type": et, "entity_id": eid, "from_status": f,
                   "to_status": t, "occurred_on": d, "actor": "SYSTEM"}
                  for n, (d, _, et, eid, f, t) in enumerate(events, 1)]

    lines = sorted((ln for it in world.items for ln in it.lines), key=lambda ln: ln["invoice_line_id"])
    alloc_rows = sorted(sim.allocations, key=lambda a: a["allocation_id"])
    return {
        "program": world.programs, "term": world.terms, "scholarship_scheme": world.schemes,
        "student": world.students, "fee_schedule": world.fees,
        "enrollment": sorted((it.enrollment for it in world.items), key=lambda e: e["enrollment_id"]),
        "invoice": sorted((it.invoice for it in world.items), key=lambda i: i["invoice_id"]),
        "eligibility": world.eligibility, "scholarship": world.scholarships, "invoice_line": lines,
        "payment": world.payments, "payment_allocation": alloc_rows, "refund": sim.refunds,
        "ledger_entry": entries, "student_balance": balances, "event": event_rows,
    }
