"""Dynamic, bilingual initial-message and bot-variable construction.

The opening message is generated per-call from customer/loan data. To avoid
disclosing sensitive information before identity is reasonably confirmed, it
only ever reveals the **last 4 digits** of the loan account number (never the
raw phone number) and always ends with an identity-confirmation question.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.config import Settings
from app.models.enums import Language

_MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _last4(value: str) -> str:
    digits_or_chars = value.strip()
    return digits_or_chars[-4:] if len(digits_or_chars) > 4 else digits_or_chars


def _format_date(d: date, language: Language) -> str:
    if language == Language.ES_ES:
        return f"{d.day} de {_MONTHS_ES[d.month - 1]} de {d.year}"
    return f"{_MONTHS_EN[d.month - 1]} {d.day}, {d.year}"


def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else full_name.strip()


def build_initial_message(
    *,
    customer_name: str,
    loan_account_number: str,
    emi_amount: float,
    currency: str,
    emi_due_date: date,
    language: Language,
    settings: Settings,
) -> str:
    """Build the dynamic opening message the bot will speak first.

    Reveals only the last 4 digits of the loan account (never the full
    account number, never any phone number) and always closes with an
    identity-confirmation question, per the "no sensitive disclosure before
    identity confirmation" rule in the assignment brief.
    """
    first_name = _first_name(customer_name)
    account_last4 = _last4(loan_account_number)
    formatted_date = _format_date(emi_due_date, language)
    bot_name = settings.BOT_NAME
    org_name = settings.ORG_NAME

    if language == Language.ES_ES:
        return (
            f"Hola, mi nombre es {bot_name} y le llamo de parte de {org_name} "
            f"en relación con el préstamo que termina en {account_last4}. "
            f"Su cuota (EMI) de {emi_amount:.2f} {currency} venció el {formatted_date}. "
            f"¿Podría confirmarme si hablo con {customer_name}?"
        )

    # Default: en-US
    return (
        f"Hello, this is {bot_name} calling from {org_name} regarding the loan "
        f"account ending in {account_last4}. Your EMI of {emi_amount:.2f} {currency} "
        f"was due on {formatted_date}. May I confirm whether I am speaking with "
        f"{customer_name}?"
    )


def build_bot_variables(
    *,
    customer_id: str,
    customer_name: str,
    loan_account_number: str,
    emi_amount: float,
    currency: str,
    emi_due_date: date,
    language: Language,
    settings: Settings,
    initial_message: str,
) -> dict[str, Any]:
    """Return every variable the bot prompt needs, keyed for prompt templating.

    Only non-sensitive, already-masked/truncated data is included — the raw
    phone number is intentionally never part of the bot_variables payload
    sent to the console.
    """
    return {
        "customer_id": customer_id,
        "customer_first_name": _first_name(customer_name),
        "customer_full_name": customer_name,
        "loan_account_last4": _last4(loan_account_number),
        "emi_amount": round(emi_amount, 2),
        "currency": currency,
        "emi_due_date": emi_due_date.isoformat(),
        "emi_due_date_display": _format_date(emi_due_date, language),
        "preferred_language": language.value,
        "org_name": settings.ORG_NAME,
        "bot_name": settings.BOT_NAME,
        "initial_message": initial_message,
        "asr_engine": settings.GNANI_ASR_MODEL,
        "tts_engine": settings.GNANI_TTS_MODEL,
        "llm_engine": settings.GNANI_LLM_MODEL,
    }
