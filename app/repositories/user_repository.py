"""User repository."""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import UserDocument
from app.repositories.base import MongoRepository


class UserRepository(MongoRepository):
    """MongoDB repository for users."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["users"]

    async def create(self, user: UserDocument) -> UserDocument:
        payload = self.serialize_document(user.model_dump(by_alias=True, exclude_none=True))
        result = await self.collection.insert_one(payload)
        payload["_id"] = str(result.inserted_id)
        return UserDocument.model_validate(payload)

    async def get_by_username(self, tenant_id: str, username: str) -> UserDocument | None:
        document = await self.collection.find_one({"tenant_id": tenant_id, "username": username})
        normalized = self.normalize_document(document)
        return UserDocument.model_validate(normalized) if normalized else None

    async def get_by_id(self, user_id: str) -> UserDocument | None:
        document = None
        try:
            document = await self.collection.find_one({"_id": ObjectId(user_id)})
        except InvalidId:
            document = None
        normalized = self.normalize_document(document)
        return UserDocument.model_validate(normalized) if normalized else None
