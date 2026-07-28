"""Unit tests for app/services/date_rules.py.

Anchor date for all tests: Tuesday 2026-07-28 (matches the assignment's
sample data). Every resolution must be >= the anchor — a phrase can never
resolve into the past.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.date_rules import resolve_evidence_dates, resolve_relative_date

CALL_DATE = date(2026, 7, 28)  # a Tuesday


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("I can pay today", date(2026, 7, 28)),
        ("pago hoy mismo", date(2026, 7, 28)),
        ("I'll pay tomorrow", date(2026, 7, 29)),
        ("pagaré mañana", date(2026, 7, 29)),
        ("the day after tomorrow works", date(2026, 7, 30)),
        ("pasado mañana le pago", date(2026, 7, 30)),
        ("I get paid Friday", date(2026, 7, 31)),
        ("el viernes puedo pagar", date(2026, 7, 31)),
        ("by the end of the month", date(2026, 7, 31)),
        ("a fin de mes", date(2026, 7, 31)),
        ("I can do it on the 30th", date(2026, 7, 30)),
        ("el 30 le pago", date(2026, 7, 30)),
        # day-of-month already past this month -> rolls to next month
        ("I'll pay on the 5th", date(2026, 8, 5)),
        ("on August 8", date(2026, 8, 8)),
        ("el 8 de agosto", date(2026, 8, 8)),
        ("August 8th is fine", date(2026, 8, 8)),
    ],
)
def test_single_phrase_resolution(phrase: str, expected: date) -> None:
    assert resolve_relative_date(phrase, CALL_DATE) == expected


def test_next_weekday_yields_both_regional_candidates() -> None:
    # 2026-07-28 is a Tuesday; "next Friday" is ambiguous between
    # 2026-07-31 and 2026-08-07 depending on regional usage.
    candidates = resolve_evidence_dates("next Friday", CALL_DATE)
    assert candidates == {date(2026, 7, 31), date(2026, 8, 7)}


def test_next_week_is_a_window_not_a_day() -> None:
    candidates = resolve_evidence_dates("sometime next week", CALL_DATE)
    assert date(2026, 8, 4) in candidates  # +7 canonical
    assert min(candidates) == date(2026, 8, 2)  # +5
    assert max(candidates) == date(2026, 8, 6)  # +9


def test_day_after_tomorrow_does_not_also_match_tomorrow() -> None:
    candidates = resolve_evidence_dates("the day after tomorrow", CALL_DATE)
    assert candidates == {date(2026, 7, 30)}


def test_weekday_same_as_call_day_rolls_a_full_week() -> None:
    # "Tuesday" spoken on a Tuesday means NEXT Tuesday, never today.
    assert resolve_relative_date("I can pay Tuesday", CALL_DATE) == date(2026, 8, 4)


def test_no_date_phrase_returns_none_and_empty_set() -> None:
    assert resolve_relative_date("I'll try to arrange something soon", CALL_DATE) is None
    assert resolve_evidence_dates("no tengo dinero", CALL_DATE) == set()


def test_never_resolves_into_the_past() -> None:
    end_of_month_anchor = date(2026, 7, 31)
    for phrase in ("today", "tomorrow", "end of month", "the 30th", "Friday", "next week"):
        resolved = resolve_relative_date(phrase, end_of_month_anchor)
        assert resolved is not None
        assert resolved >= end_of_month_anchor


def test_end_of_month_on_last_day_offers_next_month_too() -> None:
    candidates = resolve_evidence_dates("fin de mes", date(2026, 7, 31))
    assert date(2026, 7, 31) in candidates
    assert date(2026, 8, 31) in candidates


def test_accent_insensitive_spanish() -> None:
    assert resolve_relative_date("MAÑANA", CALL_DATE) == date(2026, 7, 29)
    assert resolve_relative_date("el miércoles", CALL_DATE) == date(2026, 7, 29)
