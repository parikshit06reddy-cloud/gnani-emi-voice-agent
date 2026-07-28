"""Tests for the dynamic initial-message and bot-variable builder."""

from __future__ import annotations

from datetime import date

from app.core.config import Settings
from app.models.enums import Language
from app.services.initial_message import build_bot_variables, build_initial_message


def _settings() -> Settings:
    return Settings(ORG_NAME="Apex Financial Services", BOT_NAME="Aria")


def test_english_message_confirms_identity_and_masks_account():
    msg = build_initial_message(
        customer_name="Rahul Sharma",
        loan_account_number="LAN123456",
        emi_amount=1200.0,
        currency="USD",
        emi_due_date=date(2026, 7, 25),
        language=Language.EN_US,
        settings=_settings(),
    )
    assert "Rahul Sharma" in msg
    assert "3456" in msg
    assert "LAN123456" not in msg  # full account number must never be disclosed
    assert msg.strip().endswith("?")
    assert "Aria" in msg
    assert "Apex Financial Services" in msg
    # COMPLIANCE (identity gate): amount and due date must NOT be in the
    # pre-identity opener — they are disclosed only in stage S3 after the
    # customer confirms their identity.
    assert "1200" not in msg
    assert "July 25" not in msg and "2026" not in msg


def test_spanish_message_confirms_identity_and_masks_account():
    msg = build_initial_message(
        customer_name="Maria Lopez",
        loan_account_number="LAN987654",
        emi_amount=850.5,
        currency="USD",
        emi_due_date=date(2026, 8, 1),
        language=Language.ES_ES,
        settings=_settings(),
    )
    assert "Maria Lopez" in msg
    assert "7654" in msg
    assert "LAN987654" not in msg
    assert msg.strip().endswith("?")
    # COMPLIANCE (identity gate): no amount, no due date, pre-identity.
    assert "850" not in msg
    assert "agosto" not in msg and "2026" not in msg


def test_message_never_includes_phone_number():
    # Phone number is not even a parameter to build_initial_message —
    # this test documents that guarantee structurally.
    import inspect

    sig = inspect.signature(build_initial_message)
    assert "phone_number" not in sig.parameters


def test_build_bot_variables_contains_all_required_keys():
    settings = _settings()
    msg = build_initial_message(
        customer_name="Rahul Sharma",
        loan_account_number="LAN123456",
        emi_amount=1200.0,
        currency="USD",
        emi_due_date=date(2026, 7, 25),
        language=Language.EN_US,
        settings=settings,
    )
    variables = build_bot_variables(
        customer_id="CUST001",
        customer_name="Rahul Sharma",
        loan_account_number="LAN123456",
        emi_amount=1200.0,
        currency="USD",
        emi_due_date=date(2026, 7, 25),
        language=Language.EN_US,
        settings=settings,
        initial_message=msg,
    )
    # Keys must match the injected-variable names declared in
    # prompts/01-system-prompt.md verbatim, or the prompt is unwired.
    required_keys = {
        "customer_id", "customer_name", "customer_first_name",
        "loan_last4", "emi_amount", "currency", "emi_due_date",
        "emi_due_date_display", "preferred_language", "org_name", "bot_name",
        "current_date", "payment_link_hint",
        "initial_message", "asr_engine", "tts_engine", "llm_engine",
    }
    assert required_keys.issubset(variables.keys())
    assert variables["loan_last4"] == "3456"
    assert variables["customer_name"] == "Rahul Sharma"
    assert variables["payment_link_hint"]  # non-empty spoken-safe phrase
    # Full account number and raw phone must never reach the console.
    assert "LAN123456" not in str(variables.values())
    assert "9876543210" not in str(variables)
