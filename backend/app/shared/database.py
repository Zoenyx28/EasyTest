"""Shared database infrastructure — Base, engine, session factory.

This module is the single source of truth for the SQLAlchemy declarative
Base and async session management.  Domain models import from here so
that all tables share the same metadata and engine.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base shared by all domain models."""
    pass


async def get_session() -> AsyncSession:
    """Yield an async session for FastAPI dependency injection."""
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def session_ctx():
    """Context manager for direct session use in services and CRUD helpers."""
    async with async_session_factory() as session:
        yield session
