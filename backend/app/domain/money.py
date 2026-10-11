import re
from typing import Final

MAX_AMOUNT_CENTS: Final[int] = 100_000_000


class MoneyError(ValueError):
    pass


_AMOUNT_RE = re.compile(r"([0-9]+)(?:\.([0-9]{1,2}))?")


def parse_amount(text: str) -> int:
    m = _AMOUNT_RE.fullmatch(text)
    if m is None:
        raise MoneyError(f"invalid amount format: {text!r}")
    whole_text = m.group(1)
    if len(whole_text) > 1 and whole_text.startswith("0"):
        raise MoneyError(f"invalid amount format: {text!r}")
    cents = int(whole_text) * 100 + int((m.group(2) or "").ljust(2, "0"))
    if cents < 1:
        raise MoneyError("amount must be at least 0.01")
    if cents > MAX_AMOUNT_CENTS:
        raise MoneyError("amount must not exceed 1000000.00")
    return cents


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"
