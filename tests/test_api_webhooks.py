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


async def test_webhook_downgraded_disposition_never_persists_ptp_date(client, api_headers, webhook_headers):
    """F-04 regression: if the engine downgrades a PTP proposal (missing
    evidence), the LLM's ptp_date must NOT survive to the stored record."""
    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id, event_id="evt-downgrade-1")
    payload["disposition"]["evidence_quote"] = "totally fabricated quote never spoken"
    resp = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert resp.status_code == 200
    assert resp.json()["stage_code"] == "UNCLEAR"
    assert resp.json()["ptp_date"] is None

    detail = await client.get(f"/api/v1/calls/{call_id}", headers=api_headers)
    body = detail.json()
    assert body["stage_code"] == "UNCLEAR"
    assert body["ptp_date"] is None
    assert body["ptp_amount"] is None


async def test_webhook_failed_processing_releases_claim_for_redelivery(client, api_headers, webhook_headers, monkeypatch):
    """F-08 regression: a claim taken for a webhook whose processing then
    fails must be released, so the redelivery is processed (not treated as
    a duplicate of an update that never happened)."""
    from app.services.call_service import CallService

    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id, event_id="evt-crash-once")

    original = CallService._apply_webhook
    crashed = {"done": False}

    async def crash_once(self, *args, **kwargs):
        if not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("simulated storage failure mid-processing")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(CallService, "_apply_webhook", crash_once)

    # The ASGI test transport re-raises unhandled app exceptions rather than
    # rendering the generic 500 envelope; either way the claim must have been
    # released before the exception left process_webhook.
    with pytest.raises(RuntimeError, match="simulated storage failure"):
        await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)

    second = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert second.status_code == 200
    assert second.json()["duplicate"] is False  # redelivery processed, not swallowed
    assert second.json()["stage_code"] == "PTP_TODAY"


async def test_webhook_vague_commitment_never_becomes_ptp_end_to_end(client, api_headers, webhook_headers):
    """F-06 golden case at the API layer: 'arrange something soon' with a
    fabricated ptp_date must land as UNCLEAR with no ptp_date stored."""
    call_id = await _create_call(client, api_headers)
    payload = _webhook_payload(call_id, event_id="evt-vague-1")
    payload["disposition"]["stage_code"] = "PTP_FUTURE"
    payload["disposition"]["ptp_date"] = "2026-08-04"
    payload["disposition"]["evidence_quote"] = "I'll try to arrange something soon"
    payload["transcript"][1]["text"] = "I'll try to arrange something soon."
    resp = await client.post("/api/v1/webhooks/post-call", json=payload, headers=webhook_headers)
    assert resp.status_code == 200
    assert resp.json()["stage_code"] == "UNCLEAR"
    assert resp.json()["ptp_date"] is None
