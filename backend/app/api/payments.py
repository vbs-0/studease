"""Record a payment and allocate it (R-PAY), idempotently (S-9), in one transaction (S-15)."""
import hashlib
import json
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Header, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app import ids, mail
from app.api import txn
from app.api.deps import Conn, CurrentUser, require_role
from app.api.errors import ApiError
from app.domain import ledger, status
from app.domain.allocation import allocate, open_lines
from app.domain.billing import outstanding_by_line
from app.domain.calendar import AS_OF
from app.money import inr

router = APIRouter(tags=["payments"])
KEY = Annotated[str | None, Header(alias="Idempotency-Key")]


class NewPayment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str = Field(pattern=r"^STU-\d{6}$")
    amount_paise: int = Field(ge=1, le=1_000_000_000)          # up to Rs 1,00,00,000
    method: Literal["UPI", "CARD", "NETBANKING", "BANK_TRANSFER", "CASH", "CHEQUE"]
    reference: str = Field(min_length=1, max_length=40)


def _receipt(student_id: str, email: str | None, payment_id: str, amount: int, unapplied: int) -> None:
    if email:
        mail.send(email, f"Payment received: {payment_id}",
                  f"We received {inr(amount)} ({payment_id}).\n"
                  + (f"{inr(unapplied)} is held as credit for your next invoice.\n" if unapplied else "")
                  + f"Account: {student_id}")


class OwnPayment(BaseModel):
    """A learner paying their own bill: the student comes from the token, never from the request."""
    model_config = ConfigDict(extra="forbid")
    amount_paise: int = Field(ge=1, le=1_000_000_000)
    method: Literal["UPI", "CARD", "NETBANKING"]
    reference: str = Field(min_length=1, max_length=40)


@router.post("/payments", status_code=201, dependencies=[require_role("SUPPORT", "PLATFORM_ADMIN")])
def record_payment(body: NewPayment, conn: Conn, user: CurrentUser, tasks: BackgroundTasks, response: Response,
                   idempotency_key: KEY = None):
    return record(body, conn, user, tasks, response, idempotency_key)


@router.post("/me/payments", status_code=201, dependencies=[require_role("LEARNER")])
def pay_own_bill(body: OwnPayment, conn: Conn, user: CurrentUser, tasks: BackgroundTasks, response: Response,
                 idempotency_key: KEY = None):
    return record(NewPayment(student_id=user.student_id, **body.model_dump()), conn, user, tasks, response,
                  idempotency_key)


def record(body: NewPayment, conn, user, tasks: BackgroundTasks, response: Response, idempotency_key: str | None):
    if not idempotency_key or not (8 <= len(idempotency_key) <= 80) or not idempotency_key.replace(
            "-", "").replace("_", "").replace(":", "").replace(".", "").isalnum():
        raise ApiError(422, "IDEMPOTENCY_KEY", "Send an Idempotency-Key header of 8 to 80 letters, digits, - _ : .")
    if not txn.lock_student(conn, body.student_id):
        raise ApiError(404, "NOT_FOUND", "No such student.")
    counters = txn.begin_write(conn)
    request_hash = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()

    seen = conn.execute(text("SELECT request_hash, response_json FROM idempotency_key"
                             " WHERE app_user_id = :u AND key = :k"),
                        {"u": user.app_user_id, "k": idempotency_key}).mappings().first()
    if seen:                                                      # S-9: scoped to this caller
        if seen["request_hash"] != request_hash:
            raise ApiError(422, "IDEMPOTENCY_MISMATCH", "That Idempotency-Key was used for a different request.")
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
        return seen["response_json"]

    invoices, lines, allocs = txn.student_documents(conn, body.student_id)
    chosen, unapplied = allocate(body.amount_paise, open_lines(invoices, lines, allocs))   # R-PAY-1..3
    applied = body.amount_paise - unapplied
    pay_id = ids.payment_id(counters.take("payment"))
    pay_status = status.payment_status(body.amount_paise, applied, 0)
    payment = {"payment_id": pay_id, "student_id": body.student_id, "received_on": AS_OF,
               "amount_paise": body.amount_paise, "method": body.method, "reference": body.reference,
               "status": pay_status}
    txn.insert_row(conn, "payment", payment)
    txn.add_event(conn, counters, "payment", pay_id, None, "RECEIVED", AS_OF, user.app_user_id)
    if pay_status != "RECEIVED":
        txn.add_event(conn, counters, "payment", pay_id, "RECEIVED", pay_status, AS_OF, user.app_user_id)
    new_allocs = []
    for n, (line_id, amount) in enumerate(chosen, 1):
        row = {"allocation_id": ids.allocation_id(pay_id, n), "payment_id": pay_id, "invoice_line_id": line_id,
               "amount_paise": amount, "allocated_on": AS_OF}
        txn.insert_row(conn, "payment_allocation", row)
        new_allocs.append(row)
    txn.add_ledger(conn, counters, ledger.entry_for_payment(payment))

    for inv in invoices:                                         # re-derive the status of every invoice touched
        inv_lines = [ln for ln in lines if ln["invoice_id"] == inv["invoice_id"]]
        line_ids = {ln["invoice_line_id"] for ln in inv_lines}
        mine = [a for a in allocs + new_allocs if a["invoice_line_id"] in line_ids]
        if not any(a["invoice_line_id"] in line_ids for a in new_allocs):
            continue
        now = status.invoice_status(False, False, sum(outstanding_by_line(inv_lines, mine).values()),
                                    sum(a["amount_paise"] for a in mine), inv["due_date"], AS_OF)
        if now != inv["status"] and status.is_allowed("invoice", inv["status"], now):
            conn.execute(text("UPDATE invoice SET status = :s WHERE invoice_id = :i"),
                         {"s": now, "i": inv["invoice_id"]})
            txn.add_event(conn, counters, "invoice", inv["invoice_id"], inv["status"], now, AS_OF, user.app_user_id)

    balance = txn.refresh_balance(conn, body.student_id, AS_OF)
    result = jsonable_encoder({"payment": payment, "allocations": new_allocs, "unapplied_paise": unapplied,
                               "balance": balance})
    conn.execute(text("INSERT INTO idempotency_key (app_user_id, key, request_hash, response_json, created_at)"
                      " VALUES (:u, :k, :h, CAST(:r AS jsonb), now())"),
                 {"u": user.app_user_id, "k": idempotency_key, "h": request_hash, "r": json.dumps(result)})
    email = conn.execute(text("SELECT email FROM app_user WHERE student_id = :s AND enabled LIMIT 1"),
                         {"s": body.student_id}).scalar()
    conn.commit()
    tasks.add_task(_receipt, body.student_id, email, pay_id, body.amount_paise, unapplied)   # after commit (S-22)
    return result
