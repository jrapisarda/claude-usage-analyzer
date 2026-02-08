"""FastAPI dependency injection for database and config."""

import aiosqlite
from fastapi import Request


async def get_db(request: Request) -> aiosqlite.Connection:
    """Get the shared aiosqlite connection from app state."""
    return request.app.state.db


def get_config(request: Request) -> dict:
    """Get the loaded config from app state."""
    return request.app.state.config
