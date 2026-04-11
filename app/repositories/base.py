"""Shared repository helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any


class MongoRepository:
    """Base repository with BSON-safe serialization helpers."""

    @staticmethod
    def serialize_document(payload: dict[str, Any]) -> dict[str, Any]:
        """Convert Python-native values into BSON-safe values."""

        serialized = deepcopy(payload)
        for key, value in list(serialized.items()):
            if isinstance(value, date):
                serialized[key] = value.isoformat()
        if serialized.get("_id") is None:
            serialized.pop("_id", None)
        return serialized

    @staticmethod
    def normalize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert MongoDB-native values into Pydantic-friendly payloads."""

        if document is None:
            return None
        normalized = dict(document)
        if "_id" in normalized:
            normalized["_id"] = str(normalized["_id"])
        return normalized
