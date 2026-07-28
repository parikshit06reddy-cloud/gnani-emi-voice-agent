"""Integration tests for GET /api/v1/calls (listing/filtering) and GET /api/v1/stats."""

from __future__ import annotations

import pytest


async def _create_and_complete_call(
    client, api_headers, webhook_headers, *, customer_id, stage_code, ptp_date=None, phone_suffix="0001"
):
    body = {
        "customer_id": customer_id,
        "customer_name": "Test Customer",
        "phone_number": f"555111{phone_suffix}",
        "country_code": "+1",
        "loan_account_number": f"LAN{phone_suffix}",
        "emi_amount": 100.0,
        "emi_due_date": "2026-07-20",
        "preferred_language": "en-US",
        "currency": "USD",
    }
    resp = await client.post("/api/Initial_Message", json=body, headers=api_headers)
    assert resp.status_code == 201
    call_id = resp.json()["call_id"]

    webhook = {
        "event_id": f"evt-{call_id}",
        "call_id": call_id,
        "call_status": "completed",
        "call_duration_seconds": 60,
        "call_started_at": "2026-07-20T12:00:00+00:00",
        "call_ended_at": "2026-07-20T12:01:00+00:00",
        "disposition": {
            "stage_code": stage_code,
            "confidence": 0.9,
            "customer_verified": True,
            "evidence_quote": "yes I confirm",
            "ptp_date": ptp_date,
        },
        "transcript": [
            {"turn": 1, "speaker": "bot", "text": "Hello?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes I confirm.", "language": "en-US"},
        ],
    }
    wresp = await client.post("/api/v1/webhooks/post-call", json=webhook, headers=webhook_headers)
    assert wresp.status_code == 200
    return call_id


async def test_list_calls_requires_api_key(client):
    resp = await client.get("/api/v1/calls")
    assert resp.status_code == 401


async def test_list_calls_pagination_and_shape(client, api_headers, webhook_headers):
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-A", stage_code="PTP_TODAY", ptp_date="2026-07-20", phone_suffix="0001"
    )
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-B", stage_code="RTP_FINANCIAL", phone_suffix="0002"
    )

    resp = await client.get("/api/v1/calls", headers=api_headers, params={"page": 1, "page_size": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] == 2
    assert body["total_pages"] == 2
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert "masked_phone_number" in row
    assert row["masked_phone_number"].startswith("*")


async def test_list_calls_filter_by_customer_id(client, api_headers, webhook_headers):
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-FILTER", stage_code="PTP_TODAY", ptp_date="2026-07-20", phone_suffix="0011"
    )
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-OTHER", stage_code="RTP_FINANCIAL", phone_suffix="0012"
    )
    resp = await client.get("/api/v1/calls", headers=api_headers, params={"customer_id": "CUST-FILTER"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["customer_id"] == "CUST-FILTER"


async def test_list_calls_filter_by_stage_code(client, api_headers, webhook_headers):
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-SC1", stage_code="PTP_TODAY", ptp_date="2026-07-20", phone_suffix="0021"
    )
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-SC2", stage_code="RTP_FINANCIAL", phone_suffix="0022"
    )
    resp = await client.get("/api/v1/calls", headers=api_headers, params={"stage_code": ["RTP_FINANCIAL"]})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["stage_code"] == "RTP_FINANCIAL"


async def test_get_call_detail_not_found(client, api_headers):
    resp = await client.get("/api/v1/calls/CALL-00000000-0000", headers=api_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CALL_NOT_FOUND"


async def test_stats_endpoint_shape_and_counts(client, api_headers, webhook_headers):
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-ST1", stage_code="PTP_TODAY", ptp_date="2026-07-20", phone_suffix="0031"
    )
    await _create_and_complete_call(
        client, api_headers, webhook_headers, customer_id="CUST-ST2", stage_code="RTP_FINANCIAL", phone_suffix="0032"
    )
    resp = await client.get("/api/v1/stats", headers=api_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_calls"] == 2
    assert body["ptp_calls"] == 1
    assert body["rtp_calls"] == 1
    assert 0.0 <= body["connect_rate"] <= 1.0
    assert "PTP_TODAY" in body["by_stage_code"]
    assert "en-US" in body["by_language"]
    assert isinstance(body["by_day"], list)


async def test_health_endpoint_no_auth_required(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["repository"] == "json"
    assert body["gnani_mode"] == "mock"


async def test_public_config_endpoint_never_exposes_key(client):
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    assert resp.json() == {"api_key_required": True}
    assert "dev-api-key" not in resp.text
