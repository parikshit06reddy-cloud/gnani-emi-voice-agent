"""JSON-file backed implementation of :class:`CallRepository`.

Used whenever ``MONGODB_URI`` is unset (the zero-config default). All writes
are made atomic via an ``asyncio.Lock`` (serialising concurrent writers
within this process) plus a temp-file-then-rename pattern (avoiding partial
writes even under a crash).
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.models.call import CallRecord
from app.repositories.base import CallFilters, CallRepository, Page


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)} is not JSON serialisable")


class JsonCallRepository(CallRepository):
    """Stores all call records as a single JSON document on disk."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        if not self._path.exists():
            self._write_state_sync({"calls": {}, "event_ids": [], "sequences": {}})

    # --- low-level state I/O ------------------------------------------------
    def _read_state_sync(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"calls": {}, "event_ids": [], "sequences": {}}
        with open(self._path, "r", encoding="utf-8") as fh:
            content = fh.read().strip()
            if not content:
                return {"calls": {}, "event_ids": [], "sequences": {}}
            return json.loads(content)

    def _write_state_sync(self, state: dict[str, Any]) -> None:
        """Atomic write: write to a temp file in the same dir, then rename."""
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=".tmp_calls_", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh, default=_json_default, indent=2)
            os.replace(tmp_path, self._path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    # --- CallRepository interface -------------------------------------------
    async def create(self, record: CallRecord) -> CallRecord:
        async with self._lock:
            state = self._read_state_sync()
            state["calls"][record.call_id] = json.loads(record.model_dump_json())
            self._write_state_sync(state)
            return record

    async def get(self, call_id: str) -> CallRecord | None:
        async with self._lock:
            state = self._read_state_sync()
            raw = state["calls"].get(call_id)
            return CallRecord.model_validate(raw) if raw else None

    async def update_from_webhook(self, call_id: str, updates: dict[str, Any]) -> CallRecord | None:
        async with self._lock:
            state = self._read_state_sync()
            raw = state["calls"].get(call_id)
            if raw is None:
                return None
            record = CallRecord.model_validate(raw)
            merged = json.loads(record.model_dump_json())
            merged.update(updates)
            updated = CallRecord.model_validate(merged)
            state["calls"][call_id] = json.loads(updated.model_dump_json())
            self._write_state_sync(state)
            return updated

    async def list(
        self,
        filters: CallFilters,
        *,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> Page:
        async with self._lock:
            state = self._read_state_sync()
            records = [CallRecord.model_validate(raw) for raw in state["calls"].values()]

        filtered = [r for r in records if _matches(r, filters)]
        reverse = sort_dir.lower() != "asc"
        filtered.sort(key=lambda r: _sort_key(r, sort_by), reverse=reverse)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return Page(items=filtered[start:end], page=page, page_size=page_size, total=total)

    async def stats(self, filters: CallFilters) -> dict[str, Any]:
        async with self._lock:
            state = self._read_state_sync()
            records = [CallRecord.model_validate(raw) for raw in state["calls"].values()]
        filtered = [r for r in records if _matches(r, filters)]
        return _compute_stats(filtered)

    async def event_id_seen(self, event_id: str) -> bool:
        async with self._lock:
            state = self._read_state_sync()
            return event_id in state.get("event_ids", [])

    async def mark_event_id_seen(self, event_id: str) -> None:
        async with self._lock:
            state = self._read_state_sync()
            event_ids = state.setdefault("event_ids", [])
            if event_id not in event_ids:
                event_ids.append(event_id)
            self._write_state_sync(state)

    async def next_daily_sequence(self, day: date) -> int:
        async with self._lock:
            state = self._read_state_sync()
            sequences = state.setdefault("sequences", {})
            key = day.isoformat()
            next_seq = sequences.get(key, 0) + 1
            sequences[key] = next_seq
            self._write_state_sync(state)
            return next_seq


def _matches(record: CallRecord, filters: CallFilters) -> bool:
    if filters.call_date is not None:
        if record.call_initiated_at is None or record.call_initiated_at.date() != filters.call_date:
            return False
    if filters.date_from is not None:
        if record.created_at.date() < filters.date_from:
            return False
    if filters.date_to is not None:
        if record.created_at.date() > filters.date_to:
            return False
    if filters.call_status is not None and record.call_status.value != filters.call_status:
        return False
    if filters.stage_code:
        if record.stage_code is None or record.stage_code.value not in filters.stage_code:
            return False
    if filters.stage_group is not None and record.stage_group != filters.stage_group:
        return False
    if filters.customer_id is not None and record.customer.customer_id != filters.customer_id:
        return False
    if filters.loan_account_number is not None:
        if record.emi_details.loan_account_number != filters.loan_account_number:
            return False
    if filters.language is not None:
        lang = record.language_captured.value if record.language_captured else record.preferred_language.value
        if lang != filters.language:
            return False
    if filters.ptp_date is not None and record.ptp_date != filters.ptp_date:
        return False
    if filters.q:
        needle = filters.q.lower()
        haystacks = [record.disposition_summary or "", record.disposition_reason or ""]
        haystacks.extend(turn.text for turn in record.conversation_transcript)
        if not any(needle in h.lower() for h in haystacks):
            return False
    return True


def _sort_key(record: CallRecord, sort_by: str) -> Any:
    value = getattr(record, sort_by, None)
    if value is None:
        return datetime.min.replace(tzinfo=None)
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return value


def _compute_stats(records: list[CallRecord]) -> dict[str, Any]:
    total = len(records)
    completed = sum(1 for r in records if r.call_status.value == "completed")
    connected = sum(1 for r in records if r.call_status.value in ("connected", "completed"))
    ptp = sum(1 for r in records if r.stage_group == "ptp")
    already_paid = sum(1 for r in records if r.stage_group == "already_paid")
    rtp = sum(1 for r in records if r.stage_group == "rtp")
    dispute = sum(1 for r in records if r.stage_group == "dispute")
    non_connect = sum(1 for r in records if r.stage_group == "non_connect")
    callback = sum(1 for r in records if r.stage_group == "callback")

    by_stage_code = Counter(r.stage_code.value for r in records if r.stage_code is not None)
    by_language = Counter(
        (r.language_captured.value if r.language_captured else r.preferred_language.value) for r in records
    )
    by_day_counter: Counter[str] = Counter()
    for r in records:
        if r.call_initiated_at is not None:
            by_day_counter[r.call_initiated_at.date().isoformat()] += 1
        else:
            by_day_counter[r.created_at.date().isoformat()] += 1
    by_day = [{"date": d, "calls": c} for d, c in sorted(by_day_counter.items())]

    return {
        "total_calls": total,
        "completed_calls": completed,
        "connected_calls": connected,
        "ptp_calls": ptp,
        "already_paid_calls": already_paid,
        "rtp_calls": rtp,
        "dispute_calls": dispute,
        "non_connect_calls": non_connect,
        "callback_calls": callback,
        "connect_rate": round(connected / total, 4) if total else 0.0,
        "ptp_rate": round(ptp / total, 4) if total else 0.0,
        "by_stage_code": dict(by_stage_code),
        "by_language": dict(by_language),
        "by_day": by_day,
    }
