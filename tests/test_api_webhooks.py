"""Integration tests for POST /api/v1/webhooks/post-call: idempotency, auth, 404, resolution."""

from __future__ import annotations

import pytest

INITIAL_BODY = {
    "customer_id": "CUST100",
    "customer_name": "Ana Torres",
    "phone_number": "5551112222",
    "country_code": "+1",
    "loan_account_number": "LAN555000",
    "emi_amount": 500.0,
    "emi_due_date": "2026-07-20",
    "preferred_language": "en-US",
    "currency": "USD",
}


async def _create_call(client, api_headers) -> str:
    resp = await client.post("/api/Initial_Message", json=INITIAL_BODY, headers=api_headers)
    assert resp.status_code == 201
    return resp.json()["call_id"]


def _webhook_payload(call_id: str, event_id: str = "evt-001") -> dict:
    return {
        "event_id": event_id,
        "call_id": call_id,
        "gnani_call_reference": "gnani-test-ref",
        "call_status": "completed",
        "call_duration_seconds": 90,
        "call_started_at": "2026-07-20T12:00:00+00:00",
        "call_ended_at": "2026-07-20T12:01:30+00:00",
        "recording_url": f"https://example.com/recordings/{call_id}.wav",
        "language_detected": "en-US",
        "asr_engine": "gnani-prisma",
        "tts_engine": "gnani-timbre-2.5",
        "llm_engine": "gnani-evon",
        "disposition": {
            "stage_code": "PTP_TODAY",
            "disposition_reason": "Customer promised to pay today.",
            "disposition_summary": "Customer confirmed identity and promised payment today.",
            "ptp_date": "2026-07-20",
            "ptp_amount": 500.0,
            "confidence": 0.9,
            "customer_verified": True,
            "sentiment": "neutral",
            "evidence_quote": "I will pay today",
        },
        "transcript": [
            {"turn": 1, "speaker": "bot", "text": "May I confirm I'm speaking with Ana Torres?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, this is Ana. I will pay today.", "language": "en-US"},
        ],
    }


async def test_webhook_requires_webhook_key(client, api_headers):
    call_id = await _create_call(client, api_headers)
    resp = await client.post("/api/v1/webhooks/post-call", json=_webhook_payload(call_id))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_webhook_unknown_call_id_returns_404(client, webhook_headers):
    resp = await client.post(
        "/api/v1/webhooks/post-call",
        json=_webhook_payload("CALL-99999999-9999"),
        headers=webhook_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CALL_NOT_FOUND"


async def test_webhook_processes_and_resolves_stage_code(client, api_headers, webhook_headers):
    call_id = await _create_call(client, api_headers)
    resp = await client.post(
        "/api/v1/webhooks/post-call", json=_webhook_payload(call_id), headers=webhook_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["duplicate"] is False
    assert body["call_id"] == call_id
    assert body["stage_code"] == "PTP_TODAY"
    assert body["ptp_date"] == "2026-07-20"


async def test_webhook_duplicate_replay_no_state_change(client, api_headers, webhook_headers):
    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id)

    first = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False

    second = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert second.status_code == 200
    body = second.json()
    assert body["success"] is True
    assert body["duplicate"] is True
    assert body["call_id"] == call_id

    detail = await client.get(f"/api/v1/calls/{call_id}", headers=api_headers)
    assert detail.status_code == 200
    # Only one webhook_event_id recorded despite two deliveries.
    assert detail.json()["webhook_event_ids"].count("evt-001") == 1


async def test_webhook_fallback_idempotency_key_without_event_id(client, api_headers, webhook_headers):
    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id)
    payload.pop("event_id")

    first = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False

    second = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


async def test_webhook_missing_evidence_resolves_to_unclear(client, api_headers, webhook_headers):
    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id, event_id="evt-002")
    payload["disposition"]["evidence_quote"] = None
    resp = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert resp.status_code == 200
    assert resp.json()["stage_code"] == "UNCLEAR"

    detail = await client.get(f"/api/v1/calls/{call_id}", headers=api_headers)
    assert detail.json()["stage_code_source"] == "derived"


async def test_webhook_language_switch_detected(client, api_headers, webhook_headers):
    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id, event_id="evt-003")
    payload["transcript"] = [
        {"turn": 1, "speaker": "bot", "text": "May I confirm your identity?", "language": "en-US"},
        {"turn": 2, "speaker": "customer", "text": "Yes, this is Ana.", "language": "en-US"},
        {"turn": 3, "speaker": "bot", "text": "Great, thank you.", "language": "en-US"},
        {"turn": 4, "speaker": "customer", "text": "Sí, pagaré hoy mismo.", "language": "es-ES"},
    ]
    payload["disposition"]["evidence_quote"] = "pagaré hoy mismo"
    resp = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert resp.status_code == 200

    detail = await client.get(f"/api/v1/calls/{call_id}", headers=api_headers)
    detail_body = detail.json()
    assert detail_body["language_switched"] is True
    assert detail_body["language_captured"] == "mixed"
