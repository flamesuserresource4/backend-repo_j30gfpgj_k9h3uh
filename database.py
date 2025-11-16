"""
Database Helper Functions

MongoDB helper functions ready to use in your backend code.
Import and use these functions in your API endpoints for database operations.
"""

from pymongo import MongoClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import Union, Any
from pydantic import BaseModel, AnyUrl

# Load environment variables from .env file
load_dotenv()

_client = None
db = None

database_url = os.getenv("DATABASE_URL")
database_name = os.getenv("DATABASE_NAME")

if database_url and database_name:
    _client = MongoClient(database_url)
    db = _client[database_name]


def _to_plain(value: Any) -> Any:
    """Recursively convert Pydantic/BaseModel and special types (e.g., AnyUrl) to Mongo-storable primitives."""
    if isinstance(value, BaseModel):
        return {k: _to_plain(v) for k, v in value.model_dump().items()}
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    if isinstance(value, AnyUrl):
        return str(value)
    # Leave datetime, str, int, float, bool, None as-is
    return value

# Helper functions for common database operations
def create_document(collection_name: str, data: Union[BaseModel, dict]):
    """Insert a single document with timestamp"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")

    # Convert Pydantic model to dict if needed and coerce special types
    if isinstance(data, BaseModel):
        data_dict = _to_plain(data)
    else:
        data_dict = _to_plain(data.copy())

    data_dict['created_at'] = datetime.now(timezone.utc)
    data_dict['updated_at'] = datetime.now(timezone.utc)

    result = db[collection_name].insert_one(data_dict)
    return str(result.inserted_id)

def get_documents(collection_name: str, filter_dict: dict = None, limit: int = None):
    """Get documents from collection"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")
    
    cursor = db[collection_name].find(filter_dict or {})
    if limit:
        cursor = cursor.limit(limit)
    
    return list(cursor)
