"""Shared models — domain-agnostic entities used across all bounded contexts.

These models are owned by no single domain and are therefore kept in the
shared kernel (DDD parlance).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class User(Base):
    """System user for authentication and authorization."""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(512), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class LLMSettings(Base):
    """LLM global configuration (singleton row) — API key stored server-side only."""
    __tablename__ = 'llm_settings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), default='deepseek')
    api_base: Mapped[str] = mapped_column(String(512), default='')
    text_model: Mapped[str] = mapped_column(String(128), default='')
    vision_model: Mapped[str] = mapped_column(String(128), default='')
    api_key: Mapped[str] = mapped_column(String(512), default='')
    updated_by: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class UserLarkBinding(Base):
    """Per-user Lark (Feishu) OAuth binding — token lifecycle managed by lark-cli."""
    __tablename__ = 'user_lark_bindings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    app_id: Mapped[str] = mapped_column(String(64), default='')
    lark_open_id: Mapped[str] = mapped_column(String(128), default='')
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class UserFeishuToken(Base):
    """Per-user Feishu OAuth tokens — official API (replaces lark-cli keychain).

    user_access_token / refresh_token 以 Fernet 加密存储（密钥见 config.FEISHU_TOKEN_ENC_KEY）。
    refresh_token 单次使用；授权满 365 天需整重新 OAuth。
    """
    __tablename__ = 'user_feishu_tokens'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    lark_open_id: Mapped[str] = mapped_column(String(128), default='')
    access_token_enc: Mapped[str] = mapped_column(Text, default='')
    refresh_token_enc: Mapped[str] = mapped_column(Text, default='')
    access_expires_at: Mapped[datetime | None] = mapped_column(default=None)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
