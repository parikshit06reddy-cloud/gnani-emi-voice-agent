"""Tests for phone masking and language alias normalisation (app/models/util.py)."""

from __future__ import annotations

import pytest

from app.models.enums import Language
from app.models.util import mask_phone, normalise_language, normalise_language_strict


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("9876543210", "******3210"),
        ("123-456-7890", "******7890"),
        ("15551234567", "*******4567"),
        ("1234", "1234"),
    ],
)
def test_mask_phone(raw, expected):
    assert mask_phone(raw) == expected


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("English", Language.EN_US),
        ("English (US)", Language.EN_US),
        ("en", Language.EN_US),
        ("en-US", Language.EN_US),
        ("EN-us", Language.EN_US),
        ("Spanish", Language.ES_ES),
        ("es", Language.ES_ES),
        ("es-ES", Language.ES_ES),
        ("Español", Language.ES_ES),
        ("Mixed", Language.MIXED),
    ],
)
def test_normalise_language_aliases(alias, expected):
    assert normalise_language(alias) == expected


def test_normalise_language_unknown_falls_back():
    assert normalise_language("Klingon") == Language.UNKNOWN
    assert normalise_language(None) == Language.UNKNOWN


def test_normalise_language_strict_rejects_mixed_and_unknown():
    assert normalise_language_strict("Mixed") is None
    assert normalise_language_strict("Klingon") is None
    assert normalise_language_strict("English") == Language.EN_US
    assert normalise_language_strict("es-ES") == Language.ES_ES
