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

    Identity-first: reveals only the org/bot names and the last 4 digits of
    the loan account (never the full account number, never the EMI amount or
    due date, never any phone number) and always closes with an
    identity-confirmation question, per the "no sensitive disclosure before
    identity confirmation" rule in the assignment brief. The EMI amount and
    due date are only spoken in stage S3, after identity confirmation, driven
    by the bot_variables injected below.
    """
    account_last4 = _last4(loan_account_number)
    bot_name = settings.BOT_NAME
    org_name = settings.ORG_NAME

    # COMPLIANCE (identity gate): the opening message is spoken BEFORE anyone
    # has confirmed their identity, so it must never contain the EMI amount,
    # due date, balance, or full account number. Only the org/bot names and
    # the loan's last-4 (a safe identifying hint per prompts/01) are allowed.
    # The amount and due date are disclosed by the bot in conversation stage
    # S3, strictly after identity confirmation (prompts/02, state S1 -> S3).
    # `emi_amount`, `currency`, and `emi_due_date` remain parameters because
    # they are injected into bot_variables for the post-verification stages —
    # they are intentionally NOT interpolated into this string.
    if language == Language.ES_ES:
        return (
            f"Hola, mi nombre es {bot_name} y le llamo de parte de {org_name} "
            f"en relación con la cuenta de préstamo que termina en {account_last4}. "
            f"¿Podría confirmarme si hablo con {customer_name}?"
        )

    # Default: en-US (also used as the fallback for languages without a template)
    return (
        f"Hello, this is {bot_name} calling from {org_name} regarding the loan "
        f"account ending in {account_last4}. May I confirm whether I am speaking "
        f"with {customer_name}?"
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
    # Key names below match the injected-variable list declared in
    # prompts/01-system-prompt.md verbatim (customer_name, loan_last4,
    # emi_amount, currency, emi_due_date, preferred_language, org_name,
    # bot_name, current_date, payment_link_hint, customer_id). The full
    # loan_account_number and the raw phone number are intentionally NEVER
    # transmitted to the console — the prompt only ever needs last-4.
    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_first_name": _first_name(customer_name),
        "loan_last4": _last4(loan_account_number),
        "emi_amount": round(emi_amount, 2),
        "currency": currency,
        "emi_due_date": emi_due_date.isoformat(),
        "emi_due_date_display": _format_date(emi_due_date, language),
        "preferred_language": language.value,
        "org_name": settings.ORG_NAME,
        "bot_name": settings.BOT_NAME,
        "current_date": date.today().isoformat(),
        "payment_link_hint": settings.PAYMENT_LINK_HINT,
        "initial_message": initial_message,
        "asr_engine": settings.GNANI_ASR_MODEL,
        "tts_engine": settings.GNANI_TTS_MODEL,
        "llm_engine": settings.GNANI_LLM_MODEL,
    }
