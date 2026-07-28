"""Small, dependency-free helpers shared by the model layer.

Kept separate from ``call.py``/``requests.py`` so they can be unit tested in
isolation and reused by services (e.g. ``initial_message.py``,
``stage_code.py``) without circular imports.
"""

from __future__ import annotations

import unicodedata

from app.models.enums import Language

# Maps every accepted alias (case-insensitive) to a normalised Language value.
_LANGUAGE_ALIASES: dict[str, Language] = {
    "en": Language.EN_US,
    "en-us": Language.EN_US,
    "en_us": Language.EN_US,
    "english": Language.EN_US,
    "english (us)": Language.EN_US,
    "english(us)": Language.EN_US,
    "en-gb": Language.EN_US,
    "es": Language.ES_ES,
    "es-es": Language.ES_ES,
    "es_es": Language.ES_ES,
    "spanish": Language.ES_ES,
    "español": Language.ES_ES,
    "espanol": Language.ES_ES,
    "mixed": Language.MIXED,
    "unknown": Language.UNKNOWN,
}


def normalise_language(value: str | None) -> Language:
    """Normalise a free-form language string/alias into a :class:`Language`.

    Unrecognised values fall back to :class:`Language.UNKNOWN` rather than
    raising, since language is best-effort metadata. Use
    :func:`normalise_language_strict` where an invalid value must be a
    validation error (e.g. ``preferred_language`` on the initial request).
    """
    if value is None:
        return Language.UNKNOWN
    key = _fold(value)
    return _LANGUAGE_ALIASES.get(key, Language.UNKNOWN)


def normalise_language_strict(value: str) -> Language | None:
    """Normalise a language alias, returning ``None`` if unrecognised.

    Only ``en-US`` and ``es-ES`` are valid outcomes for request-time
    ``preferred_language`` per CONTRACT (mixed/unknown are not acceptable
    customer preferences).
    """
    key = _fold(value)
    result = _LANGUAGE_ALIASES.get(key)
    if result in (Language.EN_US, Language.ES_ES):
        return result
    return None


def _fold(value: str) -> str:
    return value.strip().lower()


def mask_phone(phone_number: str) -> str:
    """Mask all but the last 4 digits of a phone number.

    Example:
        >>> mask_phone("9876543210")
        '******3210'

    Non-digit characters (spaces, dashes) are stripped before masking. If the
    number has 4 or fewer digits, only the digits themselves are shown with
    no leading mask (edge case, should not occur given validation rules).
    """
    digits = "".join(ch for ch in phone_number if ch.isdigit())
    if len(digits) <= 4:
        return digits
    last4 = digits[-4:]
    mask_len = len(digits) - 4
    return ("*" * mask_len) + last4


def normalise_text_for_match(text: str) -> str:
    """Fold a string for case/accent-insensitive substring comparisons.

    Strips accents (NFKD decomposition), lowercases, and collapses
    whitespace. Used by the stage-code evidence-matching rule so that, e.g.,
    "Sí, pagaré" matches "si, pagare".
    """
    normalised = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in normalised if not unicodedata.combining(ch))
    return " ".join(without_accents.lower().split())
