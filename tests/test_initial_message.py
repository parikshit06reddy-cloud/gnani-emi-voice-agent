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
    assert "agosto" in msg


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
    required_keys = {
        "customer_id", "customer_first_name", "customer_full_name",
        "loan_account_last4", "emi_amount", "currency", "emi_due_date",
        "emi_due_date_display", "preferred_language", "org_name", "bot_name",
        "initial_message", "asr_engine", "tts_engine", "llm_engine",
    }
    assert required_keys.issubset(variables.keys())
    assert variables["loan_account_last4"] == "3456"
    assert "9876543210" not in str(variables)
