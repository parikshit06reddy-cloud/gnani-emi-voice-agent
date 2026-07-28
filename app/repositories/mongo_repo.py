"""MongoDB (motor) backed implementation of :class:`CallRepository`.

Used whenever ``MONGODB_URI`` is set. Indexes are created lazily on first
use via :meth:`ensure_indexes` (called once at application startup).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, time, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.models.call import CallRecord
from app.repositories.base import CallFilters, CallRepository, Page


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    return start, end


class MongoCallRepository(CallRepository):
    """Motor-based repository storing one document per call in ``calls``."""

    def __init__(self, uri: str, db_name: str) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self._db = self._client[db_name]
        self._calls: AsyncIOMotorCollection = self._db["calls"]
        self._events: AsyncIOMotorCollection = self._db["webhook_events"]
        self._sequences: AsyncIOMotorCollection = self._db["daily_sequences"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create all required indexes. Safe to call repeatedly (idempotent)."""
        if self._indexes_ready:
            return
        await self._calls.create_index("call_id", unique=True)
        await self._calls.create_index("customer.customer_id")
        await self._calls.create_index("stage_code")
        await self._calls.create_index("created_at")
        await self._calls.create_index("ptp_date")
        await self._calls.create_index("webhook_event_ids")
        await self._calls.create_index(
            [("disposition_summary", "text"), ("disposition_reason", "text")]
        )
        await self._events.create_index("event_id", unique=True)
        await self._sequences.create_index("day", unique=True)
        self._indexes_ready = True

    async def close(self) -> None:
        """Close the underlying Mongo client connection."""
        self._client.close()

    @staticmethod
    def _to_doc(record: CallRecord) -> dict[str, Any]:
        return json.loads(record.model_dump_json())

    async def create(self, record: CallRecord) -> CallRecord:
        await self._calls.insert_one(self._to_doc(record))
        return record

    async def get(self, call_id: str) -> CallRecord | None:
        doc = await self._calls.find_one({"call_id": call_id}, {"_id": 0})
        return CallRecord.model_validate(doc) if doc else None

    async def update_from_webhook(self, call_id: str, updates: dict[str, Any]) -> CallRecord | None:
        existing = await self.get(call_id)
        if existing is None:
            return None
        merged = json.loads(existing.model_dump_json())
        merged.update(updates)
        updated = CallRecord.model_validate(merged)
        await self._calls.replace_one({"call_id": call_id}, self._to_doc(updated))
        return updated

    def _build_query(self, filters: CallFilters) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if filters.call_date is not None:
            start, end = _day_bounds(filters.call_date)
            query["call_initiated_at"] = {"$gte": start.isoformat(), "$lte": end.isoformat()}
        if filters.date_from is not None or filters.date_to is not None:
            rng: dict[str, Any] = {}
            if filters.date_from is not None:
                rng["$gte"] = _day_bounds(filters.date_from)[0].isoformat()
            if filters.date_to is not None:
                rng["$lte"] = _day_bounds(filters.date_to)[1].isoformat()
            query["created_at"] = rng
        if filters.call_status is not None:
            query["call_status"] = filters.call_status
        if filters.stage_code:
            query["stage_code"] = {"$in": filters.stage_code}
        if filters.stage_group is not None:
            query["stage_group"] = filters.stage_group
        if filters.customer_id is not None:
            query["customer.customer_id"] = filters.customer_id
        if filters.loan_account_number is not None:
            query["emi_details.loan_account_number"] = filters.loan_account_number
        if filters.language is not None:
            query["$or"] = [
                {"language_captured": filters.language},
                {"language_captured": None, "preferred_language": filters.language},
            ]
        if filters.ptp_date is not None:
            query["ptp_date"] = filters.ptp_date.isoformat()
        if filters.q:
            query["$text"] = {"$search": filters.q}
        return query

    async def list(
        self,
        filters: CallFilters,
        *,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> Page:
        query = self._build_query(filters)
        direction = -1 if sort_dir.lower() != "asc" else 1
        total = await self._calls.count_documents(query)
        cursor = (
            self._calls.find(query, {"_id": 0})
            .sort(sort_by, direction)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        docs = [doc async for doc in cursor]
        # Text search fallback for records lacking indexed text fields.
        items = [CallRecord.model_validate(doc) for doc in docs]
        return Page(items=items, page=page, page_size=page_size, total=total)

    async def stats(self, filters: CallFilters) -> dict[str, Any]:
        query = self._build_query(filters)
        docs = [doc async for doc in self._calls.find(query, {"_id": 0})]
        records = [CallRecord.model_validate(doc) for doc in docs]
        return _compute_stats(records)

    async def event_id_seen(self, event_id: str) -> bool:
        doc = await self._events.find_one({"event_id": event_id})
        return doc is not None

    async def mark_event_id_seen(self, event_id: str) -> None:
        await self._events.update_one(
            {"event_id": event_id}, {"$setOnInsert": {"event_id": event_id}}, upsert=True
        )

    async def next_daily_sequence(self, day: date) -> int:
        doc = await self._sequences.find_one_and_update(
            {"day": day.isoformat()},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        return int(doc["seq"])


def _compute_stats(records: list[CallRecord]) -> dict[str, Any]:
    """Shared aggregation logic (kept identical to the JSON repo's version)."""
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
