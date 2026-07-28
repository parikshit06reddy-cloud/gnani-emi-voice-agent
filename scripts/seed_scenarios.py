#!/usr/bin/env python3
"""Exercise all 12 mandatory demo scenarios end-to-end against the running app.

Usage:
    python scripts/seed_scenarios.py [--base-url http://localhost:8000]

If ``--base-url`` is omitted, the script talks to an in-process ASGI app via
``httpx.ASGITransport`` (no server needs to be running). If provided, it
issues real HTTP requests against a running uvicorn instance.

Also runs a couple of supplementary (non-mandatory) scenarios purely to give
the dashboard more stage-code variety on first load (PTP_PARTIAL, RNR/VM).
These are reported separately and never affect the mandatory 12/12 count.

Writes a PASS/FAIL summary table to stdout and machine-readable results to
``docs/test-results.json`` (the ONLY file this script writes under docs/).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API_KEY = os.environ.get("API_KEY", "dev-api-key")
WEBHOOK_API_KEY = os.environ.get("WEBHOOK_API_KEY", "dev-webhook-key")

TODAY = datetime.now(UTC).date()

RECORDINGS_DIR = PROJECT_ROOT / "samples" / "recordings"


def _recording_url_for(call_id: str, *, language: str = "en-US", tags: tuple[str, ...] = ()) -> str:
    """Point at a real file in samples/recordings/ if one matches by naming
    convention (CALL-<call_id>.wav|mp3) or by semantic tag/language keywords
    (e.g. CALL-SAMPLE-ES-RTP-FINANCIAL.mp3). Falls back to the standard
    ``/recordings/<call_id>.wav`` convention (another agent is expected to
    drop a matching file there later).
    """
    if not RECORDINGS_DIR.is_dir():
        return f"/recordings/{call_id}.wav"

    candidates = sorted(RECORDINGS_DIR.glob("*"))
    exact_names = {f"{call_id}.wav", f"{call_id}.mp3"}
    for candidate in candidates:
        if candidate.name in exact_names:
            return f"/recordings/{candidate.name}"

    # Only attempt a semantic tag match when explicit tags are supplied --
    # matching on language alone is too loose (e.g. any en-US scenario would
    # otherwise collide with the first EN-tagged file found).
    if tags:
        lang_key = {"en-US": "EN", "es-ES": "ES"}.get(language, "")
        search_tokens = [t.upper() for t in tags] + ([lang_key] if lang_key else [])
        for candidate in candidates:
            if candidate.suffix.lower() not in (".wav", ".mp3"):
                continue
            upper_name = candidate.name.upper()
            if all(tok in upper_name for tok in search_tokens if tok):
                return f"/recordings/{candidate.name}"

    return f"/recordings/{call_id}.wav"


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    detail: str
    call_id: str | None = None
    stage_code: str | None = None
    supplementary: bool = False


@dataclass
class ScenarioRunner:
    client: httpx.AsyncClient
    results: list[ScenarioResult] = field(default_factory=list)

    def _api_headers(self) -> dict[str, str]:
        return {"X-API-Key": API_KEY}

    def _webhook_headers(self) -> dict[str, str]:
        return {"X-Webhook-Key": WEBHOOK_API_KEY}

    async def _initiate(self, body: dict[str, Any]) -> httpx.Response:
        return await self.client.post("/api/Initial_Message", json=body, headers=self._api_headers())

    async def _webhook(self, payload: dict[str, Any]) -> httpx.Response:
        return await self.client.post(
            "/api/v1/webhooks/post-call", json=payload, headers=self._webhook_headers()
        )

    def record(
        self,
        name: str,
        passed: bool,
        detail: str,
        call_id: str | None = None,
        stage_code: str | None = None,
        supplementary: bool = False,
    ) -> None:
        self.results.append(
            ScenarioResult(
                name=name,
                passed=passed,
                detail=detail,
                call_id=call_id,
                stage_code=stage_code,
                supplementary=supplementary,
            )
        )
        status = "PASS" if passed else "FAIL"
        tag = "[SUPPLEMENTARY] " if supplementary else ""
        print(f"[{status}] {tag}{name}: {detail}")

    async def run_all(self) -> None:
        # --- 12 mandatory scenarios ----------------------------------------
        await self.scenario_1_ptp_today()
        await self.scenario_2_ptp_future()
        await self.scenario_3_already_paid()
        await self.scenario_4_callback_requested()
        await self.scenario_5_rtp_financial()
        await self.scenario_6_dispute_emi_amount()
        await self.scenario_7_third_party()
        await self.scenario_8_language_switch()
        await self.scenario_9_disconnect_unclear()
        await self.scenario_10_duplicate_webhook()
        await self.scenario_11_invalid_request()
        await self.scenario_12_gnani_failure_and_timeout()
        # --- supplementary (non-mandatory) scenarios ------------------------
        await self.scenario_13_ptp_partial_supplementary()
        await self.scenario_14_rnr_supplementary()

    # --- helpers -----------------------------------------------------------

    def _base_customer(
        self,
        customer_id: str,
        phone_suffix: str,
        *,
        customer_name: str = "Marcus Whitfield",
        loan_suffix: str | None = None,
        emi_amount: float = 1200.0,
        emi_due_date: str = "2026-07-25",
        preferred_language: str = "English (US)",
        **overrides: Any,
    ) -> dict[str, Any]:
        body = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "phone_number": f"98765{phone_suffix}",
            "country_code": "+1",
            "loan_account_number": f"LAN{loan_suffix or phone_suffix}",
            "emi_amount": emi_amount,
            "emi_due_date": emi_due_date,
            "preferred_language": preferred_language,
            "currency": "USD",
        }
        body.update(overrides)
        return body

    def _base_webhook(
        self,
        call_id: str,
        event_id: str,
        *,
        call_duration_seconds: int = 95,
        started_offset_minutes: int = 0,
        recording_tags: tuple[str, ...] = (),
        **overrides: Any,
    ) -> dict[str, Any]:
        started = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=started_offset_minutes)
        ended = started + timedelta(seconds=call_duration_seconds)
        recording_language = overrides.get("language_detected", "en-US")
        payload = {
            "event_id": event_id,
            "call_id": call_id,
            "gnani_call_reference": f"gnani-{event_id}",
            "call_status": "completed",
            "call_duration_seconds": call_duration_seconds,
            "call_started_at": started.isoformat(),
            "call_ended_at": ended.isoformat(),
            "recording_url": _recording_url_for(call_id, language=recording_language, tags=recording_tags),
            "language_detected": "en-US",
            "asr_engine": "gnani-prisma",
            "tts_engine": "gnani-timbre-2.5",
            "llm_engine": "gnani-evon",
            "disposition": {},
            "transcript": [],
        }
        payload.update(overrides)
        return payload

    # --- Scenario 1: PTP today ----------------------------------------------
    async def scenario_1_ptp_today(self) -> None:
        name = "1. PTP today"
        body = self._base_customer(
            "CUST-S01", "100001",
            customer_name="Elena Vargas",
            emi_amount=1200.0,
            emi_due_date="2026-07-25",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code} {resp.text}")
        call_id = resp.json()["call_id"]

        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Hello, may I confirm I'm speaking with Elena Vargas regarding your loan ending in 0001?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, this is Elena speaking.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "Thank you. Your EMI of 1200.00 USD was due on July 25, 2026. Are you able to make the payment?", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "Oh yes, I forgot. Let me pay it right now.", "language": "en-US"},
            {"turn": 5, "speaker": "bot", "text": "Great, so you will pay the full amount today?", "language": "en-US"},
            {"turn": 6, "speaker": "customer", "text": "Yes, I will pay it today, no problem.", "language": "en-US"},
            {"turn": 7, "speaker": "bot", "text": "Wonderful. Is there anything else I can help you with?", "language": "en-US"},
            {"turn": 8, "speaker": "customer", "text": "No, that's all. Thank you.", "language": "en-US"},
            {"turn": 9, "speaker": "bot", "text": "Thank you for your time, Elena. Have a great day.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s01",
            call_duration_seconds=101,
            started_offset_minutes=-40,
            disposition={
                "stage_code": "PTP_TODAY",
                "disposition_reason": "Customer explicitly committed to paying today.",
                "disposition_summary": "Customer confirmed identity and promised to pay the full EMI today.",
                "ptp_date": TODAY.isoformat(),
                "ptp_amount": 1200.0,
                "confidence": 0.95,
                "customer_verified": True,
                "sentiment": "positive",
                "evidence_quote": "I will pay it today, no problem",
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "PTP_TODAY"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id, wresp.json().get("stage_code") if wresp.status_code == 200 else None)

    # --- Scenario 2: future PTP (real recorded call: CALL-SAMPLE-EN-PTP-FUTURE) --
    async def scenario_2_ptp_future(self) -> None:
        name = "2. Future PTP"
        body = self._base_customer(
            "CUST-S02", "100002",
            customer_name="Marcus Whitfield",
            loan_suffix="4417",
            emi_amount=968.0,
            emi_due_date="2026-07-21",
            preferred_language="English (US)",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code} {resp.text}")
        call_id = resp.json()["call_id"]

        ptp_date = "2026-08-08"
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Hello, this is Aria calling from Apex Financial Services regarding the loan account ending in 4417. May I confirm I am speaking with Marcus Whitfield?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yeah, this is Marcus.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "Thank you for confirming, Marcus. I'm calling about your monthly installment of nine hundred sixty eight dollars, which was due on July twenty first. Are you able to take care of that today?", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "Not today, no. I just moved and things have been tight.", "language": "en-US"},
            {"turn": 5, "speaker": "bot", "text": "I understand. Is there a date in the next couple of weeks when you would be able to make the payment?", "language": "en-US"},
            {"turn": 6, "speaker": "customer", "text": "I get paid on the seventh, so... I could do it on the eighth of August.", "language": "en-US"},
            {"turn": 7, "speaker": "bot", "text": "August eighth. And would that be the full nine hundred sixty eight dollars?", "language": "en-US"},
            {"turn": 8, "speaker": "customer", "text": "Yes, the full amount.", "language": "en-US"},
            {"turn": 9, "speaker": "bot", "text": "Perfect. So just to confirm, you will pay nine hundred sixty eight dollars on August eighth. Is that correct?", "language": "en-US"},
            {"turn": 10, "speaker": "customer", "text": "That's correct.", "language": "en-US"},
            {"turn": 11, "speaker": "bot", "text": "Thank you, Marcus. I've noted that down. You'll receive a reminder before the date. Have a good day.", "language": "en-US"},
            {"turn": 12, "speaker": "customer", "text": "Thanks. Bye.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s02",
            call_duration_seconds=88,
            started_offset_minutes=-120,
            language_detected="en-US",
            disposition={
                "stage_code": "PTP_FUTURE",
                "disposition_reason": "Customer committed to a specific future payment date after his next payday.",
                "disposition_summary": "Customer cannot pay today but committed to paying the full EMI on August 8th once he gets paid.",
                "ptp_date": ptp_date,
                "ptp_amount": 968.0,
                "confidence": 0.9,
                "customer_verified": True,
                "sentiment": "neutral",
                "evidence_quote": "I could do it on the eighth of August",
            },
            transcript=transcript,
        )
        webhook["recording_url"] = "/recordings/CALL-SAMPLE-EN-PTP-FUTURE.mp3"
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "PTP_FUTURE"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 3: already paid -------------------------------------------
    async def scenario_3_already_paid(self) -> None:
        name = "3. Already paid"
        body = self._base_customer(
            "CUST-S03", "100003",
            customer_name="Priya Raghunathan",
            emi_amount=968.0,
            emi_due_date="2026-07-23",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "May I confirm I'm speaking with Priya Raghunathan about the loan ending in 0003?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, speaking.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "Your EMI of 968.00 USD was due on July 23. Have you made this payment?", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "Yes actually, I already paid this EMI two days ago online.", "language": "en-US"},
            {"turn": 5, "speaker": "bot", "text": "Thank you, I will note that. Do you have a reference number?", "language": "en-US"},
            {"turn": 6, "speaker": "customer", "text": "I don't have it handy but it went through, I checked my bank app.", "language": "en-US"},
            {"turn": 7, "speaker": "bot", "text": "No problem, we'll verify on our end. Thanks for confirming.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s03",
            call_duration_seconds=79,
            started_offset_minutes=-300,
            disposition={
                "stage_code": "ALREADY_PAID",
                "disposition_reason": "Customer states the EMI was already paid two days ago.",
                "disposition_summary": "Customer claims payment already made; pending verification.",
                "confidence": 0.85,
                "customer_verified": True,
                "sentiment": "neutral",
                "evidence_quote": "I already paid this EMI two days ago online",
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "ALREADY_PAID"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 4: callback requested -------------------------------------
    async def scenario_4_callback_requested(self) -> None:
        name = "4. Callback requested"
        body = self._base_customer(
            "CUST-S04", "100004",
            customer_name="Daniel O'Sullivan",
            emi_amount=1875.5,
            emi_due_date="2026-07-22",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        callback_dt = (datetime.now(UTC) + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Am I speaking with Daniel O'Sullivan about your EMI?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, but I'm in a meeting right now.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "I understand, this will be quick. Can I proceed?", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "No, I really can't talk now. Please call me back tomorrow at 5pm.", "language": "en-US"},
            {"turn": 5, "speaker": "bot", "text": "Sure, I will call you back tomorrow at 5pm. Thank you.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s04",
            call_duration_seconds=38,
            started_offset_minutes=-15,
            disposition={
                "stage_code": "CALLBACK_SCHEDULED",
                "disposition_reason": "Customer requested a callback at a specific time tomorrow.",
                "disposition_summary": "Customer busy, requested callback tomorrow at 5pm.",
                "callback_datetime": callback_dt.isoformat(),
                "confidence": 0.88,
                "customer_verified": True,
                "sentiment": "neutral",
                "evidence_quote": "Please call me back tomorrow at 5pm",
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "CALLBACK_SCHEDULED"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 5: RTP financial (real recorded call: CALL-SAMPLE-ES-RTP-FINANCIAL) --
    async def scenario_5_rtp_financial(self) -> None:
        name = "5. RTP financial"
        body = self._base_customer(
            "CUST-S05", "100005",
            customer_name="Carmen Delgado",
            loan_suffix="8302",
            emi_amount=519.99,
            emi_due_date="2026-07-24",
            preferred_language="Spanish",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Buenas tardes, le llama Aria de Apex Financial Services sobre la cuenta de préstamo que termina en 8302. ¿Hablo con Carmen Delgado?", "language": "es-ES"},
            {"turn": 2, "speaker": "customer", "text": "Sí, soy Carmen.", "language": "es-ES"},
            {"turn": 3, "speaker": "bot", "text": "Gracias por confirmar, Carmen. Le llamo por su cuota mensual de quinientos diecinueve dólares con noventa y nueve centavos, que venció el veinticuatro de julio. ¿Podría realizar el pago hoy?", "language": "es-ES"},
            {"turn": 4, "speaker": "customer", "text": "No puedo. Perdí mi trabajo el mes pasado y ahora mismo no tengo ese dinero.", "language": "es-ES"},
            {"turn": 5, "speaker": "bot", "text": "Lamento escuchar eso. ¿Tiene alguna idea de cuándo podría cambiar su situación?", "language": "es-ES"},
            {"turn": 6, "speaker": "customer", "text": "Estoy buscando trabajo, pero de verdad no puedo comprometerme a una fecha. No quiero prometer algo que no pueda cumplir.", "language": "es-ES"},
            {"turn": 7, "speaker": "bot", "text": "Entiendo, y le agradezco su honestidad. Voy a registrar que no puede pagar por dificultades económicas. ¿Le gustaría que le enviemos información sobre nuestras opciones de aplazamiento?", "language": "es-ES"},
            {"turn": 8, "speaker": "customer", "text": "Sí, por favor. Eso me ayudaría mucho.", "language": "es-ES"},
            {"turn": 9, "speaker": "bot", "text": "Perfecto. Nuestro equipo de servicio se pondrá en contacto con usted con esas opciones. Gracias por su tiempo, Carmen. Que tenga un buen día.", "language": "es-ES"},
            {"turn": 10, "speaker": "customer", "text": "Gracias a usted. Adiós.", "language": "es-ES"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s05",
            call_duration_seconds=112,
            started_offset_minutes=-200,
            language_detected="es-ES",
            disposition={
                "stage_code": "RTP_FINANCIAL",
                "disposition_reason": "Customer cites job loss and financial hardship.",
                "disposition_summary": "Customer lost her job last month and cannot commit to a payment date; requested deferral options.",
                "confidence": 0.9,
                "customer_verified": True,
                "sentiment": "negative",
                "evidence_quote": "Perdí mi trabajo el mes pasado y ahora mismo no tengo ese dinero",
            },
            transcript=transcript,
        )
        webhook["recording_url"] = "/recordings/CALL-SAMPLE-ES-RTP-FINANCIAL.mp3"
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "RTP_FINANCIAL"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 6: dispute EMI amount -------------------------------------
    async def scenario_6_dispute_emi_amount(self) -> None:
        name = "6. Dispute EMI amount"
        body = self._base_customer(
            "CUST-S06", "100006",
            customer_name="Tyrone Jackson",
            emi_amount=2150.0,
            emi_due_date="2026-07-19",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Am I speaking with Tyrone Jackson regarding your EMI ending in 0006?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, but I have an issue with this bill.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "Please tell me more, I'd like to help.", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "This is the wrong amount, you've charged me a penalty that shouldn't be there.", "language": "en-US"},
            {"turn": 5, "speaker": "bot", "text": "I understand, I'll flag this for review. Can you clarify what amount you expected?", "language": "en-US"},
            {"turn": 6, "speaker": "customer", "text": "My EMI should be 1950, not 2150, I dispute the extra charges.", "language": "en-US"},
            {"turn": 7, "speaker": "bot", "text": "Understood, I've logged your dispute for our billing team.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s06",
            call_duration_seconds=143,
            started_offset_minutes=-60,
            disposition={
                "stage_code": "DISPUTE_CHARGES",
                "disposition_reason": "Customer disputes penalty charges added to the EMI amount.",
                "disposition_summary": "Customer contests extra penalty charges on the EMI.",
                "confidence": 0.87,
                "customer_verified": True,
                "sentiment": "negative",
                "evidence_quote": "you've charged me a penalty that shouldn't be there",
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "DISPUTE_CHARGES"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 7: third party answers ------------------------------------
    async def scenario_7_third_party(self) -> None:
        name = "7. Third party answers"
        body = self._base_customer(
            "CUST-S07", "100007",
            customer_name="Rebecca Lindqvist",
            emi_amount=385.5,
            emi_due_date="2026-07-18",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "May I confirm I'm speaking with Rebecca Lindqvist?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "No, this is her brother. She's not here right now.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "I see, do you know when she'll be available?", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "She should be back this evening, I can pass a message.", "language": "en-US"},
            {"turn": 5, "speaker": "bot", "text": "Thank you, please ask her to call us back regarding her EMI.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s07",
            call_duration_seconds=24,
            started_offset_minutes=-500,
            disposition={
                "stage_code": "THIRD_PARTY",
                "disposition_reason": "Someone other than the borrower answered; borrower is reachable later.",
                "disposition_summary": "Borrower's brother answered, borrower reachable this evening.",
                "confidence": 0.82,
                "customer_verified": False,
                "sentiment": "neutral",
                "evidence_quote": "this is her brother. She's not here right now",
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "THIRD_PARTY"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 8: language switch mid-call (real recorded call: CALL-SAMPLE-SWITCH-PTP-TOMORROW) --
    async def scenario_8_language_switch(self) -> None:
        name = "8. Language switch mid-call (bilingual)"
        body = self._base_customer(
            "CUST-S08", "100008",
            customer_name="Miguel Santos",
            loan_suffix="6155",
            emi_amount=1200.0,
            emi_due_date="2026-07-25",
            preferred_language="English (US)",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Hello, this is Aria calling from Apex Financial Services regarding the loan account ending in 6155. May I confirm I am speaking with Miguel Santos?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Speaking, yes.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "Thank you. I'm calling about your installment of one thousand two hundred dollars, which was due on July twenty fifth.", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "Perdón, ¿podría continuar en español, por favor? Lo entiendo mucho mejor.", "language": "es-ES"},
            {"turn": 5, "speaker": "bot", "text": "Claro que sí, continuamos en español. Su cuota de mil doscientos dólares venció el veinticinco de julio. ¿Podría realizar el pago hoy?", "language": "es-ES"},
            {"turn": 6, "speaker": "customer", "text": "Hoy no, pero mañana sí. Voy a pagar mañana sin falta.", "language": "es-ES"},
            {"turn": 7, "speaker": "bot", "text": "Muy bien. ¿Sería el monto completo de mil doscientos dólares mañana, veintinueve de julio?", "language": "es-ES"},
            {"turn": 8, "speaker": "customer", "text": "Sí, el monto completo.", "language": "es-ES"},
            {"turn": 9, "speaker": "bot", "text": "Perfecto, lo anoto. Usted pagará mil doscientos dólares el veintinueve de julio. ¿Es correcto?", "language": "es-ES"},
            {"turn": 10, "speaker": "customer", "text": "Correcto. ¿Algo más?", "language": "es-ES"},
            {"turn": 11, "speaker": "bot", "text": "Eso es todo. Gracias por su tiempo, señor Santos. Que tenga un buen día.", "language": "es-ES"},
            {"turn": 12, "speaker": "customer", "text": "Igualmente, gracias. Adiós.", "language": "es-ES"},
        ]
        ptp_tomorrow = (TODAY + timedelta(days=1)).isoformat()
        webhook = self._base_webhook(
            call_id,
            "evt-s08",
            call_duration_seconds=133,
            started_offset_minutes=-80,
            language_detected="mixed",
            disposition={
                "stage_code": "PTP_TOMORROW",
                "disposition_reason": "Customer switched to Spanish and committed to paying the full EMI tomorrow.",
                "disposition_summary": "Customer requested to continue in Spanish and promised full payment on July 29th.",
                "ptp_date": ptp_tomorrow,
                "ptp_amount": 1200.0,
                "confidence": 0.9,
                "customer_verified": True,
                "sentiment": "positive",
                "evidence_quote": "Voy a pagar mañana sin falta",
            },
            transcript=transcript,
        )
        webhook["recording_url"] = "/recordings/CALL-SAMPLE-SWITCH-PTP-TOMORROW.mp3"
        wresp = await self._webhook(webhook)
        if wresp.status_code != 200:
            return self.record(name, False, f"webhook failed: {wresp.status_code} {wresp.text}", call_id)
        detail = await self.client.get(f"/api/v1/calls/{call_id}", headers=self._api_headers())
        detail_body = detail.json()
        ok = (
            wresp.json().get("stage_code") == "PTP_TOMORROW"
            and detail_body.get("language_switched") is True
            and detail_body.get("language_captured") == "mixed"
        )
        self.record(name, ok, f"stage_code={wresp.json().get('stage_code')} language_switched={detail_body.get('language_switched')} language_captured={detail_body.get('language_captured')}", call_id)

    # --- Scenario 9: disconnect, no clear disposition -----------------------
    async def scenario_9_disconnect_unclear(self) -> None:
        name = "9. Disconnect with no clear disposition"
        body = self._base_customer(
            "CUST-S09", "100009",
            customer_name="Aisha Bello",
            emi_amount=630.75,
            emi_due_date="2026-07-17",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Hello, may I confirm I'm speaking with Aisha Bello?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, this is—", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s09",
            call_status="failed",
            call_duration_seconds=7,
            started_offset_minutes=-10,
            disposition={
                "stage_code": None,
                "disposition_reason": "Call dropped shortly after connecting.",
                "disposition_summary": "The call was disconnected before any disposition could be captured.",
                "confidence": 0.0,
                "customer_verified": None,
                "sentiment": "unknown",
                "evidence_quote": None,
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "DSCN"
        self.record(name, ok, f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}", call_id)

    # --- Scenario 10: duplicate webhook replay ------------------------------
    async def scenario_10_duplicate_webhook(self) -> None:
        name = "10. Duplicate webhook replay"
        body = self._base_customer(
            "CUST-S10", "100010",
            customer_name="Jonathan Pike",
            emi_amount=1440.0,
            emi_due_date="2026-07-25",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code}")
        call_id = resp.json()["call_id"]
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "May I confirm I'm speaking with Jonathan Pike?", "language": "en-US"},
            {"turn": 2, "speaker": "customer", "text": "Yes, speaking.", "language": "en-US"},
            {"turn": 3, "speaker": "bot", "text": "Your EMI of 1440.00 USD was due on July 25. Can you pay today?", "language": "en-US"},
            {"turn": 4, "speaker": "customer", "text": "Yes, I will pay today.", "language": "en-US"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-s10-duplicate-test",
            call_duration_seconds=61,
            started_offset_minutes=-5,
            disposition={
                "stage_code": "PTP_TODAY",
                "disposition_reason": "Customer committed to paying today.",
                "ptp_date": TODAY.isoformat(),
                "confidence": 0.92,
                "customer_verified": True,
                "sentiment": "positive",
                "evidence_quote": "I will pay today",
            },
            transcript=transcript,
        )
        first = await self._webhook(webhook)
        second = await self._webhook(webhook)  # exact replay, same event_id
        ok = (
            first.status_code == 200
            and first.json().get("duplicate") is False
            and second.status_code == 200
            and second.json().get("duplicate") is True
        )
        self.record(
            name,
            ok,
            f"first.duplicate={first.json().get('duplicate') if first.status_code==200 else first.status_code} "
            f"second.duplicate={second.json().get('duplicate') if second.status_code==200 else second.status_code}",
            call_id,
        )

    # --- Scenario 11: invalid initial request (expect 422) ------------------
    async def scenario_11_invalid_request(self) -> None:
        name = "11. Invalid initial request (expect 422)"
        body = self._base_customer(
            "CUST-S11", "100011",
            customer_name="Lucia Herrera",
            emi_amount=1050.0,
            preferred_language="Spanish",
            phone_number="123",  # too short
        )
        resp = await self._initiate(body)
        ok = resp.status_code == 422 and resp.json().get("error", {}).get("code") == "VALIDATION_ERROR"
        self.record(name, ok, f"status={resp.status_code} code={resp.json().get('error', {}).get('code') if resp.headers.get('content-type','').startswith('application/json') else 'n/a'}")

    # --- Scenario 12: Gnani API failure + timeout ----------------------------
    async def scenario_12_gnani_failure_and_timeout(self) -> None:
        name = "12. Gnani API failure + timeout (injected)"
        timeout_body = self._base_customer(
            "CUST-S12A", "500000", customer_name="Nathan Brooks", emi_amount=1310.0
        )  # ends 0000 -> injected timeout
        timeout_resp = await self._initiate(timeout_body)
        timeout_ok = timeout_resp.status_code == 504 and timeout_resp.json().get("error", {}).get("code") == "GNANI_TIMEOUT"

        failure_body = self._base_customer(
            "CUST-S12B", "509999", customer_name="Nathan Brooks", emi_amount=1310.0
        )  # ends 9999 -> injected 5xx
        failure_resp = await self._initiate(failure_body)
        failure_ok = failure_resp.status_code == 502 and failure_resp.json().get("error", {}).get("code") == "GNANI_TRIGGER_FAILED"

        ok = timeout_ok and failure_ok
        self.record(
            name,
            ok,
            f"timeout_status={timeout_resp.status_code} failure_status={failure_resp.status_code}",
        )

    # =========================================================================
    # Supplementary (non-mandatory) scenarios — extra stage-code variety only.
    # =========================================================================

    # --- Supplementary A: PTP_PARTIAL ---------------------------------------
    async def scenario_13_ptp_partial_supplementary(self) -> None:
        name = "13. [Supplementary] PTP partial payment"
        body = self._base_customer(
            "CUST-SUP01", "200013",
            customer_name="Sofia Ramirez",
            emi_amount=1500.0,
            emi_due_date="2026-07-22",
            preferred_language="Spanish",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code} {resp.text}", supplementary=True)
        call_id = resp.json()["call_id"]
        partial_amount = 750.0  # genuinely less than emi_amount (1500.0)
        transcript = [
            {"turn": 1, "speaker": "bot", "text": "Hola, ¿hablo con Sofia Ramirez sobre su cuota vencida?", "language": "es-ES"},
            {"turn": 2, "speaker": "customer", "text": "Sí, soy yo.", "language": "es-ES"},
            {"turn": 3, "speaker": "bot", "text": "Su cuota de 1500.00 USD venció el 22 de julio. ¿Puede pagar el monto completo?", "language": "es-ES"},
            {"turn": 4, "speaker": "customer", "text": "Solo puedo pagar 750 ahora, el resto lo pago con la próxima cuota.", "language": "es-ES"},
            {"turn": 5, "speaker": "bot", "text": "De acuerdo, registramos un pago parcial de 750.00 USD. Gracias.", "language": "es-ES"},
        ]
        webhook = self._base_webhook(
            call_id,
            "evt-sup01",
            call_duration_seconds=97,
            started_offset_minutes=-25,
            language_detected="es-ES",
            disposition={
                "stage_code": "PTP_PARTIAL",
                "disposition_reason": "Customer can only pay half of the EMI now, remainder next cycle.",
                "disposition_summary": "Customer requested a partial payment arrangement of 750.00 now and the remainder with next month's EMI.",
                "ptp_date": TODAY.isoformat(),
                "ptp_amount": partial_amount,
                "confidence": 0.86,
                "customer_verified": True,
                "sentiment": "neutral",
                "evidence_quote": "Solo puedo pagar 750 ahora, el resto lo pago con la próxima cuota",
            },
            transcript=transcript,
        )
        wresp = await self._webhook(webhook)
        ok = (
            wresp.status_code == 200
            and wresp.json().get("stage_code") == "PTP_PARTIAL"
        )
        self.record(
            name, ok,
            f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text} ptp_amount={partial_amount} (< emi_amount=1500.0)",
            call_id, wresp.json().get("stage_code") if wresp.status_code == 200 else None,
            supplementary=True,
        )

    # --- Supplementary B: RNR (ring, no response) ---------------------------
    async def scenario_14_rnr_supplementary(self) -> None:
        name = "14. [Supplementary] RNR (ring, no response)"
        body = self._base_customer(
            "CUST-SUP02", "200014",
            customer_name="Derek Holloway",
            emi_amount=899.0,
            emi_due_date="2026-07-21",
        )
        resp = await self._initiate(body)
        if resp.status_code != 201:
            return self.record(name, False, f"initiate failed: {resp.status_code} {resp.text}", supplementary=True)
        call_id = resp.json()["call_id"]
        webhook = self._base_webhook(
            call_id,
            "evt-sup02",
            call_status="no_answer",
            call_duration_seconds=0,
            started_offset_minutes=-2,
            disposition={
                "stage_code": None,
                "disposition_reason": "Call rang out with no answer.",
                "disposition_summary": "No answer after multiple rings; recommend retry later.",
                "confidence": 0.0,
                "customer_verified": None,
                "sentiment": "unknown",
                "evidence_quote": None,
            },
            transcript=[],
        )
        wresp = await self._webhook(webhook)
        ok = wresp.status_code == 200 and wresp.json().get("stage_code") == "RNR"
        self.record(
            name, ok,
            f"webhook status={wresp.status_code} stage_code={wresp.json().get('stage_code') if wresp.status_code==200 else wresp.text}",
            call_id, wresp.json().get("stage_code") if wresp.status_code == 200 else None,
            supplementary=True,
        )


def _write_results(results: list[ScenarioResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mandatory = [r for r in results if not r.supplementary]
    supplementary = [r for r in results if r.supplementary]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mandatory": {
            "total": len(mandatory),
            "passed": sum(1 for r in mandatory if r.passed),
            "failed": sum(1 for r in mandatory if not r.passed),
            "scenarios": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "detail": r.detail,
                    "call_id": r.call_id,
                    "stage_code": r.stage_code,
                }
                for r in mandatory
            ],
        },
        "supplementary": {
            "total": len(supplementary),
            "passed": sum(1 for r in supplementary if r.passed),
            "failed": sum(1 for r in supplementary if not r.passed),
            "scenarios": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "detail": r.detail,
                    "call_id": r.call_id,
                    "stage_code": r.stage_code,
                }
                for r in supplementary
            ],
        },
        # Backwards-compatible top-level totals covering ALL scenarios run.
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "scenarios": [
            {
                "name": r.name,
                "passed": r.passed,
                "detail": r.detail,
                "call_id": r.call_id,
                "stage_code": r.stage_code,
                "supplementary": r.supplementary,
            }
            for r in results
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def _print_table(results: list[ScenarioResult]) -> None:
    mandatory = [r for r in results if not r.supplementary]
    supplementary = [r for r in results if r.supplementary]

    print("\n" + "=" * 90)
    print("MANDATORY SCENARIOS (12)")
    print("-" * 90)
    print(f"{'#':<3} {'Scenario':<45} {'Result':<6} Detail")
    print("-" * 90)
    for i, r in enumerate(mandatory, 1):
        status = "PASS" if r.passed else "FAIL"
        print(f"{i:<3} {r.name:<45} {status:<6} {r.detail[:80]}")
    print("=" * 90)
    m_passed = sum(1 for r in mandatory if r.passed)
    print(f"MANDATORY TOTAL: {m_passed}/{len(mandatory)} scenarios passed\n")

    if supplementary:
        print("=" * 90)
        print("SUPPLEMENTARY SCENARIOS (extra stage-code variety, non-mandatory)")
        print("-" * 90)
        print(f"{'#':<3} {'Scenario':<45} {'Result':<6} Detail")
        print("-" * 90)
        for i, r in enumerate(supplementary, 1):
            status = "PASS" if r.passed else "FAIL"
            print(f"{i:<3} {r.name:<45} {status:<6} {r.detail[:80]}")
        print("=" * 90)
        s_passed = sum(1 for r in supplementary if r.passed)
        print(f"SUPPLEMENTARY TOTAL: {s_passed}/{len(supplementary)} scenarios passed\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 12 mandatory demo scenarios (+ supplementary extras).")
    parser.add_argument("--base-url", default=None, help="Base URL of a running server; omit for in-process ASGI.")
    args = parser.parse_args()

    output_path = PROJECT_ROOT / "docs" / "test-results.json"

    if args.base_url:
        async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
            runner = ScenarioRunner(client=client)
            await runner.run_all()
    else:
        os.environ.setdefault("JSON_STORE_PATH", str(PROJECT_ROOT / "data" / "seed_scenarios_calls.json"))
        # Fresh store for a clean, reproducible run.
        store_path = Path(os.environ["JSON_STORE_PATH"])
        if store_path.exists():
            store_path.unlink()
        from app.main import create_app  # local import: env vars must be set first

        app = create_app()
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                runner = ScenarioRunner(client=client)
                await runner.run_all()

    _print_table(runner.results)
    _write_results(runner.results, output_path)
    print(f"Machine-readable results written to {output_path}")

    mandatory_ok = all(r.passed for r in runner.results if not r.supplementary)
    return 0 if mandatory_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
