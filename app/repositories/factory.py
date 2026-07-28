"""Repository factory: selects JSON or Mongo backend based on settings."""

from __future__ import annotations

from app.core.config import Settings
from app.repositories.base import CallRepository
from app.repositories.json_repo import JsonCallRepository
from app.repositories.mongo_repo import MongoCallRepository


async def build_repository(settings: Settings) -> CallRepository:
    """Construct the appropriate :class:`CallRepository` for ``settings``.

    Uses Mongo when ``MONGODB_URI`` is set, otherwise falls back to the
    JSON-file repository (the zero-config default).
    """
    if settings.repository_kind == "mongo":
        repo = MongoCallRepository(settings.MONGODB_URI, settings.MONGODB_DB)
        await repo.ensure_indexes()
        return repo
    return JsonCallRepository(settings.JSON_STORE_PATH)
