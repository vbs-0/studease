"""Money helpers. Everything is integer paise; there is no float in any money path."""


def pct(amount: int, bp: int) -> int:
    """`bp` basis points of `amount`, rounded half up to the paise (R-SCH-4, R-LATE-2)."""
    if amount < 0:
        return -pct(-amount, bp)
    return (amount * bp + 5000) // 10000


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def inr(paise: int) -> str:
    """Format as rupees with Indian digit grouping: 123456789 -> '₹12,34,567.89'."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join([*groups, tail])
    return f"{sign}₹{s}.{p:02d}"
