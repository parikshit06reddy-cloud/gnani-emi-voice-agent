"""Abstract repository interface for call records.

Both the Mongo and JSON-file backends implement this same interface so the
service layer (``call_service.py``) never needs to know which storage
backend is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.models.call import CallRecord


@dataclass
class CallFilters:
    """Filter parameters shared by ``GET /api/v1/calls`` and ``/stats``."""

    call_date: date | None = None
    date_from: date | None = None
    date_to: date | None = None
    call_status: str | None = None
    stage_code: list[str] = field(default_factory=list)
    stage_group: str | None = None
    customer_id: str | None = None
    loan_account_number: str | None = None
    language: str | None = None
    ptp_date: date | None = None
    q: str | None = None


@dataclass
class Page:
    """A page of :class:`CallRecord` results plus pagination metadata."""

    items: list[CallRecord]
    page: int
    page_size: int
    total: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return max(1, -(-self.total // self.page_size))


class CallRepository(ABC):
    """Storage-agnostic interface for persisting and querying call records."""

    @abstractmethod
    async def create(self, record: CallRecord) -> CallRecord:
        """Persist a brand-new call record."""

    @abstractmethod
    async def get(self, call_id: str) -> CallRecord | None:
        """Fetch a single call record by its ``call_id``, or ``None``."""

    @abstractmethod
    async def update_from_webhook(self, call_id: str, updates: dict[str, Any]) -> CallRecord | None:
        """Apply a partial update (from a post-call webhook) to a call record.

        Returns the updated record, or ``None`` if ``call_id`` was not found.
        """

    @abstractmethod
    async def list(
        self,
        filters: CallFilters,
        *,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> Page:
        """Return a filtered, sorted, paginated page of call records."""

    @abstractmethod
    async def stats(self, filters: CallFilters) -> dict[str, Any]:
        """Compute aggregate statistics over records matching ``filters``."""

    @abstractmethod
    async def try_claim_event_id(self, event_id: str) -> bool:
        """Atomically claim a webhook event id.

        Returns True if this call claimed the id (first delivery), False if
        it was already claimed (duplicate delivery). Claim-before-process
        closes the check-then-act race under concurrent duplicate deliveries.
        """
        raise NotImplementedError

    @abstractmethod
    async def release_event_id(self, event_id: str) -> None:
        """Release a previously claimed event id (used when processing fails
        after a successful claim, so a redelivery is not treated as a
        duplicate of a webhook that never actually took effect)."""
        raise NotImplementedError

    @abstractmethod
    async def event_id_seen(self, event_id: str) -> bool:
        """Return whether a webhook ``event_id`` has already been processed."""

    @abstractmethod
    async def mark_event_id_seen(self, event_id: str) -> None:
        """Record that a webhook ``event_id`` has been processed."""

    @abstractmethod
    async def next_daily_sequence(self, day: date) -> int:
        """Return the next collision-safe sequence number for ``day``."""
