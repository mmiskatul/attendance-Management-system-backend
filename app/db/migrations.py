"""Simple migration runner for MongoDB."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import IndexModel

from app.db.indexes import attendance_indexes, audit_indexes, face_embedding_indexes, student_indexes, user_indexes
from app.utils.time import utc_now

Migration = tuple[str, Callable[[AsyncIOMotorDatabase], Awaitable[None]]]


async def _ensure_collection_indexes(database: AsyncIOMotorDatabase, collection_name: str, indexes: list[IndexModel]) -> None:
    collection = database[collection_name]
    await collection.create_indexes(indexes)


async def migration_001_create_indexes(database: AsyncIOMotorDatabase) -> None:
    await _ensure_collection_indexes(database, "students", student_indexes())
    await _ensure_collection_indexes(database, "face_embeddings", face_embedding_indexes())
    await _ensure_collection_indexes(database, "attendance_records", attendance_indexes())
    await _ensure_collection_indexes(database, "users", user_indexes())
    await _ensure_collection_indexes(database, "audit_logs", audit_indexes())


MIGRATIONS: list[Migration] = [
    ("001_create_indexes", migration_001_create_indexes),
]


async def run_migrations(database: AsyncIOMotorDatabase) -> None:
    """Apply unapplied migrations in order."""

    migrations_collection = database["schema_migrations"]
    await migrations_collection.create_index("name", unique=True)

    applied = {
        document["name"]
        async for document in migrations_collection.find({}, projection={"name": True, "_id": False})
    }

    for name, migration in MIGRATIONS:
        if name in applied:
            continue
        await migration(database)
        await migrations_collection.insert_one({"name": name, "applied_at": utc_now()})
