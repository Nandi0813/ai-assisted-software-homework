import re

import pytest

from app.domain.money import MAX_AMOUNT_CENTS, MoneyError, format_cents, parse_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.01", 1),
        ("1", 100),
        ("1.5", 150),
        ("33.34", 3334),
        ("1000000", 100_000_000),
        ("1000000.00", 100_000_000),
    ],
)
def test_ac4_parse_amount_valid(text: str, expected: int) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        " 1.00",
        "1.00 ",
        "-1.00",
        "+1.00",
        "1.234",
        "1.",
        ".5",
        "01.00",
        "1e3",
        "1,00",
        "abc",
        "NaN",
        "\u0661.00",
    ],
)
def test_ac4_parse_amount_rejects_bad_format(text: str) -> None:
    with pytest.raises(MoneyError, match=re.escape(f"invalid amount format: {text!r}")):
        parse_amount(text)


@pytest.mark.parametrize("text", ["0", "0.0", "0.00"])
def test_ac4_parse_amount_rejects_zero(text: str) -> None:
    with pytest.raises(MoneyError, match=re.escape("amount must be at least 0.01")):
        parse_amount(text)


@pytest.mark.parametrize("text", ["1000000.01", "99999999999"])
def test_ac4_parse_amount_rejects_over_max(text: str) -> None:
    with pytest.raises(MoneyError, match=re.escape("amount must not exceed 1000000.00")):
        parse_amount(text)


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "0.00"),
        (5, "0.05"),
        (150, "1.50"),
        (3334, "33.34"),
        (-3000, "-30.00"),
        (-5, "-0.05"),
        (MAX_AMOUNT_CENTS, "1000000.00"),
    ],
)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


@pytest.mark.parametrize("cents", [1, 99, 100, 3334, MAX_AMOUNT_CENTS])
def test_parse_format_round_trip(cents: int) -> None:
    assert parse_amount(format_cents(cents)) == cents
