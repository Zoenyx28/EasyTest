"""Defect Tracking domain models — defects, modules, attachments, logs, comments."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class DefectModule(Base):
    """Defect module — project-level + branch-level module tree."""
    __tablename__ = 'defect_modules'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class Defect(Base):
    """Defect record."""
    __tablename__ = 'defects'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    steps: Mapped[str] = mapped_column(Text, default='')
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    module_id: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(16), default='P3')
    priority: Mapped[str] = mapped_column(String(16), default='P3')
    status: Mapped[str] = mapped_column(String(32), default='unconfirmed')
    resolution: Mapped[str] = mapped_column(String(64), default='')
    assignee_id: Mapped[int] = mapped_column(Integer, default=0)
    creator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    case_uid: Mapped[str] = mapped_column(String(256), default='')
    case_name: Mapped[str] = mapped_column(String(512), default='')
    # ADR-0016: defect → requirement traceability
    requirement_id: Mapped[int] = mapped_column(Integer, default=0)
    bug_type: Mapped[str] = mapped_column(String(32), default='code_error')
    deadline: Mapped[str] = mapped_column(String(32), default='')
    resolved_version: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_defect_id: Mapped[int] = mapped_column(Integer, default=0)
    resolved_date: Mapped[str] = mapped_column(String(32), default='')
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class DefectAttachment(Base):
    """Defect attachment."""
    __tablename__ = 'defect_attachments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    filepath: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), default='')
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class DefectLog(Base):
    """Defect audit log."""
    __tablename__ = 'defect_logs'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default='')
    new_value: Mapped[str] = mapped_column(Text, default='')
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class DefectComment(Base):
    """Defect comment."""
    __tablename__ = 'defect_comments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
