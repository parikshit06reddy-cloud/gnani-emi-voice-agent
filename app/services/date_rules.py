"""Relative/absolute date-phrase resolution for evidence consistency checks.

The analytics prompt (prompts/03) is responsible for resolving spoken
relative dates ("day after tomorrow", "next Friday", "end of month",
"pasado mañana") into an ISO ``ptp_date``. This module gives the backend an
independent, deterministic resolver so the stage-code engine can VERIFY that
the LLM's ``ptp_date`` is consistent with the date phrase actually present
in the customer's evidence quote — and downgrade to UNCLEAR when it is not
(rule ``evidence_date_mismatch`` in ``stage_code.py``).

Design notes:

- Resolution is anchored on ``call_date`` (the calendar date of the call as
  derived from the tz-aware ``call_started_at``; see call_service.py). All
  outputs are >= call_date — a phrase can never resolve into the past.
- Ambiguous phrases yield MULTIPLE candidates rather than one guess. E.g.
  "next Friday" yields both the next occurrence and the one after (regional
  usage differs); the consistency check passes if the LLM's date matches ANY
  candidate. This keeps the verifier strict about fabrication but tolerant
  of legitimate ambiguity.
- Input text is folded (lowercased, accents stripped) before matching, so
  "mañana" and "manana" behave identically.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from app.models.util import normalise_text_for_match

_WEEKDAYS_EN = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_WEEKDAYS_ES = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
_WEEKDAYS = {**_WEEKDAYS_EN, **_WEEKDAYS_ES}
_WEEKDAY_ALT = "|".join(_WEEKDAYS)

_MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
_MONTHS = {**_MONTHS_EN, **_MONTHS_ES}
_MONTH_ALT = "|".join(_MONTHS)

# Ordered: more specific phrases first; each matched span is masked out so
# e.g. "day after tomorrow" cannot additionally fire the "tomorrow" rule.
_RE_DAY_AFTER_TOMORROW = re.compile(r"\b(the day after tomorrow|day after tomorrow|pasado manana)\b")
_RE_TOMORROW = re.compile(r"\b(tomorrow|manana)\b")
_RE_TODAY = re.compile(r"\b(today|tonight|this evening|this afternoon|hoy|esta noche|esta tarde)\b")
_RE_NEXT_WEEK = re.compile(r"\b(next week|la proxima semana|la semana que viene)\b")
_RE_END_OF_MONTH = re.compile(r"\b(end of (the )?month|month end|fin de(l)? mes|a fin de mes)\b")
_RE_NEXT_WEEKDAY = re.compile(rf"\b(next|el proximo|proximo)\s+({_WEEKDAY_ALT})\b")
_RE_BARE_WEEKDAY = re.compile(rf"\b(?:on\s+|el\s+|este\s+)?({_WEEKDAY_ALT})\b")
# "the 30th" / "on the 5th" / "el 30" / "el dia 30"
_RE_DAY_OF_MONTH = re.compile(r"\b(?:the|el(?: dia)?)\s+(\d{1,2})(?:st|nd|rd|th)?\b")
# "august 8" / "8 august" / "8 de agosto" / "august 8th"
_RE_MONTH_DAY = re.compile(
    rf"\b(?:({_MONTH_ALT})\s+(\d{{1,2}})(?:st|nd|rd|th)?|(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+|de\s+)?({_MONTH_ALT}))\b"
)


def _next_weekday(anchor: date, weekday: int) -> date:
    """Next occurrence of ``weekday`` strictly after ``anchor``."""
    delta = (weekday - anchor.weekday()) % 7
    return anchor + timedelta(days=delta or 7)


def _end_of_month(anchor: date) -> date:
    return date(anchor.year, anchor.month, calendar.monthrange(anchor.year, anchor.month)[1])


def _day_of_month_candidates(anchor: date, day_num: int) -> set[date]:
    """Resolve a bare day-of-month, rolling forward so it is never past."""
    out: set[date] = set()
    year, month = anchor.year, anchor.month
    for _ in range(2):  # this month if not past, else next month
        if day_num <= calendar.monthrange(year, month)[1]:
            candidate = date(year, month, day_num)
            if candidate >= anchor:
                out.add(candidate)
                break
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


def _month_day_candidate(anchor: date, month_num: int, day_num: int) -> date | None:
    """Resolve an explicit month+day, rolling to next year if already past."""
    for year in (anchor.year, anchor.year + 1):
        if day_num <= calendar.monthrange(year, month_num)[1]:
            candidate = date(year, month_num, day_num)
            if candidate >= anchor:
                return candidate
    return None


def resolve_evidence_dates(text: str, call_date: date) -> set[date]:
    """Return every candidate date the phrases in ``text`` can resolve to.

    Empty set means the text contains no recognisable date phrase — the
    consistency rule in ``stage_code.py`` then has nothing to verify against
    and stays silent (it never fabricates a constraint).
    """
    folded = normalise_text_for_match(text)
    candidates: set[date] = set()

    def consume(pattern: re.Pattern[str]) -> list[re.Match[str]]:
        nonlocal folded
        matches = list(pattern.finditer(folded))
        if matches:
            folded = pattern.sub(" ", folded)
        return matches

    # Specific-before-general, masking each matched span.
    if consume(_RE_DAY_AFTER_TOMORROW):
        candidates.add(call_date + timedelta(days=2))
    if consume(_RE_TOMORROW):
        candidates.add(call_date + timedelta(days=1))
    if consume(_RE_TODAY):
        candidates.add(call_date)
    if consume(_RE_NEXT_WEEK):
        # "next week" is a window, not a day: accept +5..+9 around the
        # canonical +7 so any date the LLM places within it verifies.
        for offset in range(5, 10):
            candidates.add(call_date + timedelta(days=offset))
    if consume(_RE_END_OF_MONTH):
        eom = _end_of_month(call_date)
        candidates.add(eom)
        if eom == call_date:  # spoken on the last day → next month's end too
            candidates.add(_end_of_month(call_date + timedelta(days=1)))
    for m in consume(_RE_MONTH_DAY):
        month_name = m.group(1) or m.group(4)
        day_str = m.group(2) or m.group(3)
        resolved = _month_day_candidate(call_date, _MONTHS[month_name], int(day_str))
        if resolved is not None:
            candidates.add(resolved)
    for m in consume(_RE_NEXT_WEEKDAY):
        nxt = _next_weekday(call_date, _WEEKDAYS[m.group(2)])
        candidates.add(nxt)
        candidates.add(nxt + timedelta(days=7))  # regional "next Friday" ambiguity
    for m in consume(_RE_BARE_WEEKDAY):
        candidates.add(_next_weekday(call_date, _WEEKDAYS[m.group(1)]))
    for m in consume(_RE_DAY_OF_MONTH):
        day_num = int(m.group(1))
        if 1 <= day_num <= 31:
            candidates.update(_day_of_month_candidates(call_date, day_num))

    return candidates


def resolve_relative_date(phrase: str, call_date: date) -> date | None:
    """Resolve a single phrase to its earliest candidate date (tests/tools).

    Returns None when the phrase contains no recognisable date expression.
    Guaranteed never to return a date before ``call_date``.
    """
    candidates = resolve_evidence_dates(phrase, call_date)
    return min(candidates) if candidates else None
