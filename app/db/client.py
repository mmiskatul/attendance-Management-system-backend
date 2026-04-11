"""MongoDB client manager."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings


class DatabaseManager:
    """Manage MongoDB client lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    async def connect(self) -> AsyncIOMotorDatabase:
        """Connect to MongoDB and return the database handle."""

        self.client = AsyncIOMotorClient(
            self.settings.mongodb_uri,
            maxPoolSize=self.settings.mongo_max_pool_size,
            minPoolSize=self.settings.mongo_min_pool_size,
            uuidRepresentation="standard",
        )
        await self.client.admin.command("ping")
        self.database = self.client[self.settings.mongodb_database]
        return self.database

    async def disconnect(self) -> None:
        """Close the MongoDB client."""

        if self.client is not None:
            self.client.close()
        self.client = None
        self.database = None
