"""Integration tests for GET /api/v1/calls (listing/filtering) and GET /api/v1/stats."""

from __future__ import annotations


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


async def test_sort_by_dashboard_alias_actually_sorts(client, api_headers, webhook_headers):
    """F-03 regression: the dashboard sends sort_by=call_initiated_time; it
    must map to call_initiated_at and genuinely order the rows."""
    for suffix in ("1001", "1002", "1003"):
        await _create_and_complete_call(
            client, api_headers, webhook_headers,
            customer_id=f"CUST{suffix}", stage_code="ALREADY_PAID", phone_suffix=suffix,
        )
    asc = await client.get(
        "/api/v1/calls?sort_by=call_initiated_time&sort_dir=asc", headers=api_headers
    )
    desc = await client.get(
        "/api/v1/calls?sort_by=call_initiated_time&sort_dir=desc", headers=api_headers
    )
    asc_ids = [row["call_id"] for row in asc.json()["items"]]
    desc_ids = [row["call_id"] for row in desc.json()["items"]]
    assert len(asc_ids) == 3
    assert asc_ids == list(reversed(desc_ids))
    asc_times = [row["call_initiated_time"] for row in asc.json()["items"]]
    assert asc_times == sorted(asc_times)


async def test_sort_by_unknown_field_is_422_not_silent_noop(client, api_headers):
    resp = await client.get("/api/v1/calls?sort_by=__proto__", headers=api_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_hindi_preferred_language_rejected_with_supported_list(client, api_headers):
    """F-23: the assignment's section 5.1 sample uses 'Hindi'; the alias is
    recognised but rejected by default with a clear, configurable message."""
    body = {
        "customer_id": "CUST5100",
        "customer_name": "Rahul Sharma",
        "phone_number": "9876543210",
        "country_code": "+91",
        "loan_account_number": "LAN123456",
        "emi_amount": 1200.0,
        "emi_due_date": "2026-07-25",
        "preferred_language": "Hindi",
        "currency": "USD",
    }
    resp = await client.post("/api/Initial_Message", json=body, headers=api_headers)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert "hi-IN" in err["message"]
    assert err["details"]["supported_languages"] == ["en-US", "es-ES"]
