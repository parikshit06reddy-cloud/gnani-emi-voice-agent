"""Integration tests for POST /api/Initial_Message (validation + happy path + auth)."""

from __future__ import annotations

import pytest

VALID_BODY = {
    "customer_id": "CUST001",
    "customer_name": "Rahul Sharma",
    "phone_number": "9876543210",
    "country_code": "+1",
    "loan_account_number": "LAN123456",
    "emi_amount": 1200.0,
    "emi_due_date": "2026-07-25",
    "preferred_language": "English (US)",
    "currency": "USD",
}


async def test_initiate_call_success(client, api_headers):
    resp = await client.post("/api/Initial_Message", json=VALID_BODY, headers=api_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["call_id"].startswith("CALL-")
    assert body["phone_number"] == "******3210"
    assert body["preferred_language"] == "en-US"
    assert body["call_status"] == "initiated"
    assert "9876543210" not in resp.text


async def test_initiate_call_requires_api_key(client):
    resp = await client.post("/api/Initial_Message", json=VALID_BODY)
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in body


async def test_initiate_call_wrong_api_key(client):
    resp = await client.post(
        "/api/Initial_Message", json=VALID_BODY, headers={"X-API-Key": "wrong-key"}
    )
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("phone_number", "123"),
        ("phone_number", "abcdefghij"),
        ("country_code", "1"),
        ("country_code", "+abc"),
        ("emi_amount", -5),
        ("emi_amount", 0),
        ("emi_due_date", "not-a-date"),
        ("customer_id", ""),
        ("loan_account_number", "   "),
        ("preferred_language", "Klingon"),
    ],
)
async def test_initiate_call_validation_errors(client, api_headers, field, bad_value):
    body = dict(VALID_BODY)
    body[field] = bad_value
    resp = await client.post("/api/Initial_Message", json=body, headers=api_headers)
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "field_errors" in payload["error"]["details"]


async def test_initiate_call_gnani_timeout_injection(client, api_headers):
    body = dict(VALID_BODY)
    body["phone_number"] = "5550000000"  # injected timeout suffix
    resp = await client.post("/api/Initial_Message", json=body, headers=api_headers)
    assert resp.status_code == 504
    payload = resp.json()
    assert payload["error"]["code"] == "GNANI_TIMEOUT"


async def test_initiate_call_gnani_trigger_failed_injection(client, api_headers):
    body = dict(VALID_BODY)
    body["phone_number"] = "5559999999"  # injected 5xx suffix
    resp = await client.post("/api/Initial_Message", json=body, headers=api_headers)
    assert resp.status_code == 502
    payload = resp.json()
    assert payload["error"]["code"] == "GNANI_TRIGGER_FAILED"


async def test_initiate_call_spanish_preference_generates_spanish_message(client, api_headers):
    body = dict(VALID_BODY)
    body["preferred_language"] = "Spanish"
    body["phone_number"] = "9876543211"
    resp = await client.post("/api/Initial_Message", json=body, headers=api_headers)
    assert resp.status_code == 201
    payload = resp.json()
    assert payload["preferred_language"] == "es-ES"
    assert "?" in payload["initial_message"]
