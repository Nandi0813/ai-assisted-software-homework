from collections.abc import Mapping, Sequence
from typing import Final

from app.domain.money import format_cents

PERCENT_SCALE: Final[int] = 10_000


class SplitError(ValueError):
    pass


def _require_positive_total(total_cents: int) -> None:
    if total_cents < 1:
        raise SplitError("total must be positive")


def split_equal(total_cents: int, participants: Sequence[int]) -> dict[int, int]:
    _require_positive_total(total_cents)
    if len(participants) == 0:
        raise SplitError("at least one participant is required")
    seen: set[int] = set()
    for p in participants:
        if p in seen:
            raise SplitError(f"duplicate participant: {p}")
        seen.add(p)
    base, remainder = divmod(total_cents, len(participants))
    return {p: base + (1 if i < remainder else 0) for i, p in enumerate(participants)}


def split_exact(total_cents: int, shares: Mapping[int, int]) -> dict[int, int]:
    _require_positive_total(total_cents)
    if len(shares) == 0:
        raise SplitError("at least one participant is required")
    for p, share in shares.items():
        if share < 1:
            raise SplitError(f"share must be positive for participant {p}")
    s = sum(shares.values())
    if s != total_cents:
        raise SplitError(
            f"exact shares sum to {format_cents(s)}, expected {format_cents(total_cents)}"
        )
    return dict(shares)


def split_percent(total_cents: int, percents: Mapping[int, int]) -> dict[int, int]:
    _require_positive_total(total_cents)
    if len(percents) == 0:
        raise SplitError("at least one participant is required")
    for p, pct in percents.items():
        if pct < 1:
            raise SplitError(f"percentage must be positive for participant {p}")
    s = sum(percents.values())
    if s != PERCENT_SCALE:
        raise SplitError(f"percentages sum to {format_cents(s)}%, expected 100.00%")
    base: dict[int, int] = {}
    rem: dict[int, int] = {}
    for p, pct in percents.items():
        base[p], rem[p] = divmod(total_cents * pct, PERCENT_SCALE)
    leftover = total_cents - sum(base.values())
    ranking = sorted(percents.keys(), key=lambda p: -rem[p])
    result = dict(base)
    for p in ranking[:leftover]:
        result[p] += 1
    return {p: result[p] for p in percents}
