import re

import pytest

from app.domain.splits import SplitError, split_equal, split_exact, split_percent


def test_ac1_split_equal_divides_evenly() -> None:
    assert split_equal(9000, [1, 2, 3]) == {1: 3000, 2: 3000, 3: 3000}


def test_ac2_split_equal_extra_cent_to_earliest_joiner() -> None:
    result = split_equal(10000, [1, 2, 3])
    assert result == {1: 3334, 2: 3333, 3: 3333}
    assert sum(result.values()) == 10000


def test_ac2_split_equal_remainder_follows_given_order() -> None:
    assert split_equal(10000, [3, 1, 2]) == {3: 3334, 1: 3333, 2: 3333}


def test_ac2_split_equal_two_cent_remainder() -> None:
    assert split_equal(1002, [1, 2, 3, 4]) == {1: 251, 2: 251, 3: 250, 4: 250}


def test_split_equal_total_smaller_than_participants() -> None:
    assert split_equal(2, [1, 2, 3]) == {1: 1, 2: 1, 3: 0}


def test_split_equal_single_participant() -> None:
    assert split_equal(1234, [7]) == {7: 1234}


@pytest.mark.parametrize("total", [1, 2, 3, 99, 100, 10001, 100_000_000])
@pytest.mark.parametrize("count", [1, 2, 3, 7])
def test_split_equal_shares_always_sum_to_total(total: int, count: int) -> None:
    result = split_equal(total, list(range(1, count + 1)))
    assert sum(result.values()) == total
    assert max(result.values()) - min(result.values()) <= 1


@pytest.mark.parametrize(
    ("total", "participants", "message"),
    [
        (0, [1], "total must be positive"),
        (-100, [1], "total must be positive"),
        (100, [], "at least one participant is required"),
        (100, [1, 2, 1], "duplicate participant: 1"),
    ],
)
def test_split_equal_rejects_invalid(total: int, participants: list[int], message: str) -> None:
    with pytest.raises(SplitError, match=re.escape(message)):
        split_equal(total, participants)


def test_ac3_split_exact_accepts_matching_sum() -> None:
    assert split_exact(10000, {1: 5000, 2: 3000, 3: 2000}) == {
        1: 5000,
        2: 3000,
        3: 2000,
    }


@pytest.mark.parametrize(
    ("shares", "message"),
    [
        ({1: 5000, 2: 4000}, "exact shares sum to 90.00, expected 100.00"),
        ({1: 6000, 2: 5000}, "exact shares sum to 110.00, expected 100.00"),
    ],
)
def test_ac3_split_exact_rejects_mismatched_sum(shares: dict[int, int], message: str) -> None:
    with pytest.raises(SplitError, match=re.escape(message)):
        split_exact(10000, shares)


@pytest.mark.parametrize(
    ("total", "shares", "message"),
    [
        (0, {1: 0}, "total must be positive"),
        (100, {}, "at least one participant is required"),
        (10000, {1: 10000, 2: 0}, "share must be positive for participant 2"),
        (10000, {1: 10100, 2: -100}, "share must be positive for participant 2"),
    ],
)
def test_split_exact_rejects_invalid(total: int, shares: dict[int, int], message: str) -> None:
    with pytest.raises(SplitError, match=re.escape(message)):
        split_exact(total, shares)


def test_ac3_split_percent_even() -> None:
    assert split_percent(10000, {1: 5000, 2: 5000}) == {1: 5000, 2: 5000}


def test_ac3_split_percent_largest_remainder() -> None:
    assert split_percent(1000, {1: 3333, 2: 3333, 3: 3334}) == {1: 333, 2: 333, 3: 334}


def test_split_percent_tie_goes_to_earliest_joiner() -> None:
    assert split_percent(1, {1: 5000, 2: 5000}) == {1: 1, 2: 0}
    assert split_percent(1, {2: 5000, 1: 5000}) == {2: 1, 1: 0}


@pytest.mark.parametrize("total", [1, 7, 999, 10000, 100_000_000])
def test_split_percent_shares_always_sum_to_total(total: int) -> None:
    assert sum(split_percent(total, {1: 3333, 2: 3333, 3: 3334}).values()) == total


def test_ac3_split_percent_rejects_bad_sum() -> None:
    with pytest.raises(SplitError, match=re.escape("percentages sum to 90.00%, expected 100.00%")):
        split_percent(10000, {1: 5000, 2: 4000})


@pytest.mark.parametrize(
    ("total", "percents", "message"),
    [
        (0, {1: 10000}, "total must be positive"),
        (100, {}, "at least one participant is required"),
        (100, {1: 10000, 2: 0}, "percentage must be positive for participant 2"),
    ],
)
def test_split_percent_rejects_invalid(total: int, percents: dict[int, int], message: str) -> None:
    with pytest.raises(SplitError, match=re.escape(message)):
        split_percent(total, percents)
