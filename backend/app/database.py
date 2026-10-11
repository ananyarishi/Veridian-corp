from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

_client = None
_db = None

async def connect_db():
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=2500)
    await _client.admin.command("ping")
    _db = _client[settings.mongodb_database]

async def close_db():
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None

def get_db():
    if _db is None:
        raise RuntimeError("Database is not connected. Check MONGODB_URI and MongoDB availability.")
    return _db
