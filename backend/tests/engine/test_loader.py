import copy

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import schema
from app.engine import detect, loader

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def loaded(db_engine, injected):
    ds, gt = injected
    exceptions = detect.run(ds)
    counts = loader.load(db_engine, ds, gt, exceptions)
    return db_engine, ds, gt, exceptions, counts


def test_every_table_holds_exactly_the_generated_rows(loaded):
    _, ds, gt, exceptions, counts = loaded
    for name in schema.DATA_TABLES:
        assert counts[name] == len(ds[name]), name
    assert counts["gt.ground_truth"] == len(gt) and counts["exception"] == len(exceptions)


def test_stored_values_equal_the_generated_values(loaded):
    engine, ds, *_ = loaded
    with engine.connect() as c:
        total = c.execute(text("SELECT sum(amount_paise) FROM payment")).scalar()
        first = ds["student"][0]
        gpa = c.execute(text("SELECT gpa FROM student WHERE student_id = :s"), {"s": first["student_id"]}).scalar()
        bal = c.execute(text("SELECT sum(balance_paise) FROM student_balance")).scalar()
    assert total == sum(p["amount_paise"] for p in ds["payment"])
    assert gpa == ds["student"][0]["gpa"]
    assert bal == sum(b["balance_paise"] for b in ds["student_balance"])


def test_ground_truth_lives_in_its_own_schema(loaded):
    engine, *_ = loaded
    with engine.connect() as c:
        rows = c.execute(text("SELECT table_schema || '.' || table_name FROM information_schema.tables"
                              " WHERE table_name = 'ground_truth'"))
        tables = {r[0] for r in rows}
    assert tables == {"gt.ground_truth"}


def test_the_database_rejects_an_orphan_row(loaded):
    engine, ds, *_ = loaded
    bad = copy.deepcopy(ds["payment"][0])
    with engine.connect() as c, pytest.raises(IntegrityError):
        c.execute(text("INSERT INTO payment (payment_id, student_id, received_on, amount_paise, method, reference,"
                       " status) VALUES ('PAY-2026-999999', 'STU-999999', :d, 100, 'UPI', 'x', 'RECEIVED')"),
                  {"d": bad["received_on"]})


def test_the_database_rejects_values_outside_the_allowed_set(loaded):
    engine, ds, *_ = loaded
    with engine.connect() as c, pytest.raises(IntegrityError):
        c.execute(text("UPDATE invoice SET status = 'LOST' WHERE invoice_id = :i"),
                  {"i": ds["invoice"][0]["invoice_id"]})


def test_the_database_rejects_a_credit_line_with_a_positive_amount(loaded):
    engine, ds, *_ = loaded
    line = next(ln for ln in ds["invoice_line"] if ln["line_type"] == "WAIVER")
    with engine.connect() as c, pytest.raises(IntegrityError):
        c.execute(text("UPDATE invoice_line SET amount_paise = 5 WHERE invoice_line_id = :i"),
                  {"i": line["invoice_line_id"]})


def test_loading_twice_replaces_rather_than_duplicates(loaded, injected):
    engine, ds, gt, exceptions, first = loaded
    again = loader.load(engine, ds, gt, exceptions)
    assert again == first


def test_a_failed_load_rolls_back_and_leaves_the_previous_data(loaded):
    engine, ds, gt, exceptions, first = loaded
    broken = copy.deepcopy(ds)
    broken["payment"][0]["student_id"] = "STU-999999"
    with pytest.raises(Exception):  # noqa: B017, PT011
        loader.load(engine, broken, gt, exceptions)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM payment")).scalar() == first["payment"]
