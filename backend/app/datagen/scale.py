"""Dataset sizes. One generator serves every scale; only these numbers change."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Scale:
    name: str
    students: int
    programs: int
    invoices: int       # after anomaly injection (baseline = invoices - duplicates)
    awards: int
    payments: int
    anomalies: dict[str, int]

    @property
    def duplicates(self) -> int:
        return self.anomalies["DUPLICATE_INVOICE"]

    def check(self) -> None:
        if self.invoices != self.students * 3:
            raise ValueError("every student enrolls in three terms, so invoices must be 3 x students")
        if self.duplicates > self.students:
            raise ValueError("more duplicate invoices than students")


SCALES = {
    "starter": Scale("starter", 500, 20, 1_500, 750, 2_500,
                     {"ALLOC_EXCEEDS_PAYMENT": 8, "SCHOLARSHIP_EXCEEDS_ELIGIBLE": 6, "DUPLICATE_INVOICE": 5,
                      "REFUND_EXCEEDS_NET_PAID": 4, "BALANCE_LEDGER_MISMATCH": 8}),
    "full": Scale("full", 10_000, 20, 30_000, 15_000, 50_000,
                  {"ALLOC_EXCEEDS_PAYMENT": 150, "SCHOLARSHIP_EXCEEDS_ELIGIBLE": 120, "DUPLICATE_INVOICE": 100,
                   "REFUND_EXCEEDS_NET_PAID": 80, "BALANCE_LEDGER_MISMATCH": 150}),
}
for _s in SCALES.values():
    _s.check()
