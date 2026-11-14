"""Simulation phases 1 and 2: everything that does not depend on how payments get allocated.

Phase 1 builds enrollments, invoices, invoice lines, eligibility decisions and awards. Phase 2 plans the
payments. Every choice comes from a named random stream keyed by (student, term), so a student's story does not
depend on how many other students exist or in which order they are processed.

Exact volumes without random outcomes (spec section 6):
  * awards: every application is judged by the rules; of the students whose application wins an award, exactly
    `scale.awards` are filed (a seeded subset), the rest never applied;
  * payments: each invoice gets a payment behaviour; the plan is then topped up to `scale.payments` by splitting
    seeded-chosen payments in two, which changes the count and not the money.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from app import ids
from app.datagen import catalog, people
from app.datagen.rand import stream, weighted
from app.datagen.scale import Scale
from app.domain import billing, scholarships
from app.domain.calendar import AS_OF, TERM_ORDER, TERMS, Term
from app.domain.latefees import late_fee
from app.money import pct

LEAVE_RATE = 0.03          # share of enrollments that end in a cancellation or withdrawal
CANCEL_SHARE = 0.25        # of those, the share that cancel before the term starts
APPLY_IF_ELIGIBLE = 0.92   # chance a student applies to a scheme they qualify for
APPLY_IF_NOT = 0.03        # chance they apply anyway (these become INELIGIBLE decisions)
ADVANCE_RATE = 0.05        # chance of an advance deposit before the next term (SPRING, SUMMER)
BEHAVIORS = ["FULL_ON_TIME", "INSTALMENTS", "PARTIAL", "LATE_FULL", "OVERPAY", "NONE"]
MIX = {"LOW": [40, 25, 10, 12, 3, 10], "OTHER": [54, 22, 7, 8, 5, 4]}
METHODS = ["UPI", "CARD", "NETBANKING", "BANK_TRANSFER", "CASH", "CHEQUE"]
METHOD_WEIGHTS = [45, 15, 20, 12, 3, 5]
MIN_SPLIT = 2_000 * 100    # payments below INR 2,000 are never split


@dataclass
class Item:
    """One enrollment, its invoice and what is known about it before any payment."""
    student: dict
    sno: int
    term: Term
    enrollment: dict
    invoice: dict
    lines: list[dict]
    leave: tuple[date, str] | None      # (left_on, CANCELLED | WITHDRAWN)
    outcome: scholarships.Outcome | None
    decided_off: int
    scholarship: dict | None = None


@dataclass
class World:
    programs: list[dict]
    terms: list[dict]
    schemes: list[dict]
    students: list[dict]
    fees: list[dict]
    fee_by_id: dict[str, dict]
    items: list[Item]
    eligibility: list[dict] = field(default_factory=list)
    scholarships: list[dict] = field(default_factory=list)
    payments: list[dict] = field(default_factory=list)


def _leave(r, term: Term) -> tuple[date, str] | None:
    if r.random() >= LEAVE_RATE:
        return None
    if r.random() < CANCEL_SHARE:
        return term.issue + timedelta(days=r.randint(1, (term.start - term.issue).days - 1)), "CANCELLED"
    limit = min(70, (term.end - term.start).days - 1, (AS_OF - term.start).days)
    band = r.random()
    lo, hi = (0, 14) if band < 0.40 else (15, 30) if band < 0.75 else (31, 70)
    return term.start + timedelta(days=r.randint(min(lo, limit), min(hi, limit))), "WITHDRAWN"


def build_world(scale: Scale, seed: int) -> World:
    programs = catalog.programs()
    fees = catalog.fee_schedules(stream(seed, "catalog"), programs)
    fee_by_id = {f["fee_schedule_id"]: f for f in fees}
    by_program_term: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for f in fees:
        by_program_term[(f["program_id"], f["term_id"])].append(f)
    students, late = people.students(stream(seed, "students"), scale.students, programs, scale.duplicates)

    items: list[Item] = []
    for term_name in TERM_ORDER:
        term = TERMS[term_name]
        for s in students:
            sno = ids.student_no(s["student_id"])
            if term_name == "SPRING" and sno in late:
                continue                                    # admitted after spring: no spring enrollment
            r = stream(seed, f"scenario:{sno}:{term_name}")
            enrolled_on = max(s["admitted_on"], term.issue - timedelta(days=r.randint(20, 60)))
            leave = _leave(r, term)
            invoice_id = ids.invoice_id(sno, len(items) + 1)
            lines = billing.build_invoice_lines(invoice_id, s, by_program_term[(s["program_id"], term.term_id)],
                                                term.issue)
            eligible = billing.eligible_fees(lines, fee_by_id)
            applied = [sc.code for sc in scholarships.SCHEMES
                       if r.random() < (APPLY_IF_ELIGIBLE if scholarships.judge(s, sc, True)[0] == "ELIGIBLE"
                                        else APPLY_IF_NOT)]
            outcome = scholarships.decide(s, eligible, applied) if applied else None
            status = ("CANCELLED" if leave and leave[1] == "CANCELLED" else "WITHDRAWN" if leave
                      else "COMPLETED" if term.end <= AS_OF else "ENROLLED")
            items.append(Item(
                student=s, sno=sno, term=term, leave=leave, outcome=outcome, decided_off=r.randint(2, 14),
                lines=lines,
                enrollment={"enrollment_id": ids.enrollment_id(sno, term_name), "student_id": s["student_id"],
                            "program_id": s["program_id"], "term_id": term.term_id, "enrolled_on": enrolled_on,
                            "status": status, "left_on": leave[0] if leave else None},
                invoice={"invoice_id": invoice_id, "student_id": s["student_id"],
                         "enrollment_id": ids.enrollment_id(sno, term_name), "term_id": term.term_id,
                         "issue_date": term.issue, "due_date": term.due, "status": "ISSUED", "total_paise": 0}))

    world = World(programs, catalog.terms(), catalog.schemes(), students, fees, fee_by_id, items)
    _select_awards(world, scale, seed)
    _record_decisions(world)
    return world


def _select_awards(world: World, scale: Scale, seed: int) -> None:
    """Of the applications that win an award, keep exactly `scale.awards`; the others never applied."""
    winners = [i for i, it in enumerate(world.items) if it.outcome and it.outcome.award]
    if len(winners) < scale.awards:
        raise ValueError(f"only {len(winners)} awards are possible, {scale.awards} needed: raise the GPA mean "
                         f"or the application rate")
    keep = set(stream(seed, "awards").sample(winners, scale.awards))
    for i in winners:
        if i not in keep:
            world.items[i].outcome = None


def _record_decisions(world: World) -> None:
    """Number eligibility and scholarship rows in invoice order and post the SCHOLARSHIP credit lines."""
    elg_no = sch_no = 0
    for it in world.items:
        if it.outcome is None:
            continue
        issue = it.term.issue
        decided_on = max(it.enrollment["enrolled_on"], issue - timedelta(days=it.decided_off))
        winner_elg = None
        for code, decision, reason in it.outcome.decisions:
            elg_no += 1
            eid = ids.eligibility_id(elg_no)
            world.eligibility.append({
                "eligibility_id": eid, "student_id": it.student["student_id"], "term_id": it.term.term_id,
                "scheme_code": code, "decision": decision, "reason_code": reason,
                "gpa_at_decision": it.student["gpa"], "income_band_at_decision": it.student["income_band"],
                "decided_on": decided_on})
            if decision == "ELIGIBLE":
                winner_elg = eid
        award = it.outcome.award
        if award:
            sch_no += 1
            sid = ids.scholarship_id(sch_no)
            it.lines += scholarships.credit_lines(it.invoice["invoice_id"], sid, award.amount_paise, it.lines,
                                                  world.fee_by_id, issue, len(it.lines) + 1)
            it.scholarship = {
                "scholarship_id": sid, "eligibility_id": winner_elg, "student_id": it.student["student_id"],
                "term_id": it.term.term_id, "scheme_code": award.scheme_code, "invoice_id": it.invoice["invoice_id"],
                "eligible_fees_paise": award.eligible_fees_paise, "amount_paise": award.amount_paise,
                "status": "REVOKED" if it.leave and it.leave[1] == "CANCELLED" else "APPLIED",
                "awarded_on": decided_on}
            world.scholarships.append(it.scholarship)


# ------------------------------------------------------------------------------------------ payments
def _intents(r, behavior: str, base: int, term: Term) -> list[tuple[date, int]]:
    """(date, amount) payments one behaviour makes against an invoice whose net payable is `base`."""
    issue, due = term.issue, term.due
    if behavior == "FULL_ON_TIME":
        return [(issue + timedelta(days=r.randint(1, 29)), base)]
    if behavior == "OVERPAY":
        return [(issue + timedelta(days=r.randint(1, 29)), base + pct(base, r.randint(300, 2500)))]
    if behavior == "PARTIAL":
        return [(issue + timedelta(days=r.randint(1, 39)), pct(base, r.randint(20, 80) * 100))]
    if behavior == "LATE_FULL":                              # pays after the late fee was posted
        return [(due + timedelta(days=r.randint(9, 45)), base + late_fee(base))]
    if behavior == "INSTALMENTS":
        parts = r.choice([2, 3, 4])
        cuts = [0, *sorted(r.sample(range(10, 91), parts - 1)), 100]
        out, day, paid = [], issue + timedelta(days=r.randint(1, 10)), 0
        for k in range(parts):
            amount = base - paid if k == parts - 1 else pct(base, (cuts[k + 1] - cuts[k]) * 100)
            out.append((day, amount))
            paid += amount
            day += timedelta(days=r.randint(10, 30))
        return out
    return []


def plan_payments(world: World, scale: Scale, seed: int) -> list[dict]:
    """Phase 2: payment rows with final ids, sorted by date. Returns them and stores them on the world."""
    pending: list[list] = []     # [date, student_no, seq, amount, last allowed date]
    for it in world.items:
        r = stream(seed, f"pay:{it.sno}:{it.term.name}")
        base = billing.invoice_total(it.lines)
        bound = min(AS_OF, it.leave[0]) if it.leave else AS_OF
        if it.leave and it.leave[1] == "CANCELLED":
            behavior = "EARLY_FULL" if r.random() < 0.55 else "NONE"
            intents = ([(it.term.issue + timedelta(days=r.randint(1, max(1, (it.leave[0] - it.term.issue).days))),
                         base)] if behavior == "EARLY_FULL" else [])
        else:
            behavior = weighted(r, BEHAVIORS, MIX["LOW" if it.student["income_band"] == "LOW" else "OTHER"])
            intents = _intents(r, behavior, base, it.term)
        for d, amount in intents:
            if amount > 0 and d <= bound:
                pending.append([d, it.sno, len(pending), amount, bound])
        if it.term.name != "FALL" and r.random() < ADVANCE_RATE:    # advance deposit before the next term
            nxt = TERMS[TERM_ORDER[TERM_ORDER.index(it.term.name) + 1]]
            d = nxt.issue - timedelta(days=r.randint(2, 25))
            pending.append([d, it.sno, len(pending), r.choice([5, 10, 15, 20]) * 1_000 * 100, AS_OF])
    _top_up(pending, scale, stream(seed, "topup"))
    pending.sort(key=lambda p: (p[0], p[1], p[2]))
    rr = stream(seed, "payref")
    payments = []
    for n, (d, sno, _, amount, _) in enumerate(pending, 1):
        method = weighted(rr, METHODS, METHOD_WEIGHTS)
        payments.append({"payment_id": ids.payment_id(n), "student_id": ids.student_id(sno), "received_on": d,
                         "amount_paise": amount, "method": method,
                         "reference": f"{method[:3]}{rr.randrange(10**9, 10**10)}", "status": "RECEIVED"})
    world.payments = payments
    return payments


def _top_up(pending: list[list], scale: Scale, r) -> None:
    """Split seeded-chosen payments in two until the planned count equals the target."""
    shortfall = scale.payments - len(pending)
    if shortfall < 0:
        raise ValueError(f"planned {len(pending)} payments, above the target {scale.payments}: lower the "
                         f"instalment share")
    candidates = [i for i, p in enumerate(pending) if p[3] >= MIN_SPLIT]
    if shortfall > len(candidates):
        raise ValueError(f"cannot split {shortfall} payments, only {len(candidates)} are large enough")
    for i in sorted(r.sample(candidates, shortfall)):
        d, sno, _, amount, bound = pending[i]
        first = amount // 2
        pending[i][3] = first
        pending.append([min(bound, d + timedelta(days=r.randint(0, 5))), sno, len(pending), amount - first, bound])
