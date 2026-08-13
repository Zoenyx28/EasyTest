"""Pytest 夹具 — 需求管理 API 测试（SQLite 内存后端）。

DATABASE_URL / PROJECTS_DATA_DIR 必须在导入 app 模块之前覆盖，
因此本模块（conftest 先于测试导入）在模块顶部设置环境变量。
引擎改为 NullPool，避免跨事件循环的池化连接问题。
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix='easytest_req_'))
os.environ['DATABASE_URL'] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ['PROJECTS_DATA_DIR'] = str(_TMP)
os.environ['JWT_SECRET'] = 'test-jwt-secret'
os.environ['FILE_SIGN_SECRET'] = 'test-file-sign-secret'

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# ── 用 NullPool 引擎替换默认引擎（避免跨事件循环复用连接） ──
# Engine and session factory are defined in app.shared.database.
# Patch at the source so all import paths (old + new) pick up the test engine.
import app.shared.database as shared_db

_engine = create_async_engine(os.environ['DATABASE_URL'], poolclass=NullPool)
shared_db.engine = _engine
shared_db.async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)

# Also patch app.db.database for backward-compat re-exports
import app.db.database as db

db.engine = _engine
db.async_session_factory = shared_db.async_session_factory

from app.db.database import init_db, session_ctx
from app.db.models import User, Project, ProjectMember, Branch
from app.main import app
from app.api.auth import create_token


@pytest.fixture(scope='session', autouse=True)
async def _init_db():
    """一次性建表并预置测试用户（成员/其他成员/非成员）。"""
    await init_db()

    async def _create_user(username: str, nickname: str) -> dict:
        async with session_ctx() as session:
            result = await session.execute(select(User).where(User.username == username))
            u = result.scalar_one_or_none()
            if u is None:
                u = User(username=username, nickname=nickname, password_hash='x')
                session.add(u)
                await session.commit()
                await session.refresh(u)
            return {'id': u.id, 'username': u.username, 'nickname': u.nickname}

    member = await _create_user('member', '成员')
    other = await _create_user('other', '其他成员')
    outsider = await _create_user('outsider', '外部用户')
    return {
        'member': {**member, 'token': create_token(member['id'], member['username'])},
        'other': {**other, 'token': create_token(other['id'], other['username'])},
        'outsider': {**outsider, 'token': create_token(outsider['id'], outsider['username'])},
    }


async def _create_project(name: str, creator_id: int) -> int:
    async with session_ctx() as session:
        p = Project(name=name, source_type='upload', creator_id=creator_id)
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p.id


async def _add_member(project_id: int, user_id: int) -> None:
    async with session_ctx() as session:
        session.add(ProjectMember(project_id=project_id, user_id=user_id))
        await session.commit()


async def _ensure_branch(project_id: int) -> int:
    async with session_ctx() as session:
        result = await session.execute(select(Branch).where(Branch.project_id == project_id).limit(1))
        b = result.scalar_one_or_none()
        if b is None:
            b = Branch(project_id=project_id, name='main', is_default=True)
            session.add(b)
            await session.commit()
            await session.refresh(b)
        return b.id


@pytest.fixture()
async def ctx(_init_db):
    """每个测试独立的新项目 + main 分支 + 成员关系。"""
    member = _init_db['member']
    other = _init_db['other']
    outsider = _init_db['outsider']

    project_id = await _create_project('测试项目', member['id'])
    await _add_member(project_id, member['id'])
    await _add_member(project_id, other['id'])
    branch_id = await _ensure_branch(project_id)

    return {
        'member': member,
        'other': other,
        'outsider': outsider,
        'project_id': project_id,
        'branch_id': branch_id,
    }


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c


@pytest.fixture(autouse=True)
async def _no_feishu_network(monkeypatch):
    """全局避免 fetch_doc 触发真实飞书网络调用（测试环境无凭据/网络不稳）。

    test_feishu_extraction 等需要特定返回的测试会自行 monkeypatch 覆盖本补丁。
    """
    from unittest.mock import AsyncMock
    from app.services import feishu_client
    # 保存原函数，供需要实测真实路径的测试恢复（如 _get_tenant_token_async_path）
    feishu_client._ORIG_GET_TENANT = feishu_client._get_tenant_token
    feishu_client._ORIG_GET_USER = feishu_client._get_user_token
    monkeypatch.setattr(feishu_client, '_get_tenant_token', AsyncMock(return_value=''))
    monkeypatch.setattr(feishu_client, '_get_user_token', AsyncMock(return_value=None))
    yield
