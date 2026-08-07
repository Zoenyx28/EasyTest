"""Authentication API endpoints — register, login, token management."""
from __future__ import annotations

import base64
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import uuid

import jwt
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from passlib.hash import bcrypt

from app.api.common import ok, fail
from app.config import JWT_SECRET, PROJECTS_DATA_DIR
from app.db import crud

router = APIRouter(prefix='/api/auth', tags=['auth'])

# ── JWT helpers ──

JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_DAYS = 7


def create_token(user_id: int, username: str) -> str:
    """Create a JWT token with 7-day expiry."""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': int((datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
        'iat': int(datetime.utcnow().timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode a JWT token. Returns the payload dict or raises on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


async def get_current_user(request: Request) -> dict:
    """Extract authenticated user from the request's Authorization header.

    Returns the user dict (id, username, nickname, avatar_url) or raises 401.
    """
    user = getattr(request.state, 'user', None)
    if user is None:
        raise HTTPException(status_code=401, detail='未登录或登录已过期')
    return user


# ── Routes ──

@router.post('/register')
async def register(data: dict):
    """Register a new user."""
    username = data.get('username', '').strip()
    nickname = data.get('nickname', '').strip()
    password = data.get('password', '')
    avatar = data.get('avatar', data.get('avatar_url', ''))

    if not username or not nickname or not password:
        return fail(400, '用户名、昵称和密码不能为空')

    if len(username) < 2 or len(username) > 64:
        return fail(400, '用户名长度应在2-64个字符之间')

    if len(password) < 6:
        return fail(400, '密码长度不能少于6个字符')

    # Check if username already exists
    existing = await crud.get_user_by_username(username)
    if existing:
        return fail(409, '用户名已存在')

    try:
        user_id = await crud.create_user(username, nickname, password)
    except ValueError as e:
        return fail(400, str(e))

    # Set avatar URL
    avatar_url = ''
    if avatar and avatar.startswith('default:'):
        avatar_url = f'/avatars/{avatar.split(":")[1]}.svg'
    elif avatar and avatar.startswith('http'):
        avatar_url = avatar
    elif avatar and avatar.startswith('data:image'):
        # Handle base64 data URL — decode and save as file
        try:
            header, encoded = avatar.split(',', 1)
            ext_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/svg+xml': '.svg',
                'image/webp': '.webp',
            }
            # Extract mime type from header (e.g., "data:image/png;base64")
            mime = header.split(';')[0].split(':')[1] if ';' in header else header.split(':')[1].split(';')[0]
            ext = ext_map.get(mime, '.png')
            content = base64.b64decode(encoded)
            if len(content) > 5 * 1024 * 1024:
                return fail(400, '图片大小不能超过 5MB')
            avatar_dir = PROJECTS_DATA_DIR / 'static' / 'avatars' / str(user_id)
            avatar_dir.mkdir(parents=True, exist_ok=True)
            filename = f'{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}'
            file_path = avatar_dir / filename
            with open(file_path, 'wb') as f:
                f.write(content)
            avatar_url = f'/api/static/avatars/{user_id}/{filename}'
        except Exception:
            avatar_url = ''

    if avatar_url:
        await crud.update_user_avatar(user_id, avatar_url)

    token = create_token(user_id, username)
    user_info = {
        'id': user_id,
        'username': username,
        'nickname': nickname,
        'avatar_url': avatar_url,
        'created_at': crud.dt_iso(datetime.utcnow()),
    }
    return ok({'token': token, 'user': user_info}, msg='注册成功')


@router.post('/login')
async def login(data: dict):
    """Login with username and password."""
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return fail(400, '用户名和密码不能为空')

    user = await crud.get_user_by_username(username)
    if user is None:
        return fail(401, '用户名或密码错误')

    if not user.get('is_active', True):
        return fail(403, '账号已被禁用')

    if not bcrypt.verify(password, user['password_hash']):
        return fail(401, '用户名或密码错误')

    token = create_token(user['id'], user['username'])
    user_info = {
        'id': user['id'],
        'username': user['username'],
        'nickname': user['nickname'],
        'avatar_url': user.get('avatar_url', ''),
        'created_at': user.get('created_at', ''),
    }
    return ok({'token': token, 'user': user_info}, msg='登录成功')


@router.post('/change-password')
async def change_password(request: Request, data: dict):
    """Change password for the currently authenticated user."""
    user = await get_current_user(request)
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return fail(400, '旧密码和新密码不能为空')

    if len(new_password) < 6:
        return fail(400, '新密码长度不能少于6个字符')

    # Verify old password
    full_user = await crud.get_user_by_username(user['username'])
    if full_user is None:
        return fail(401, '用户不存在')

    if not bcrypt.verify(old_password, full_user['password_hash']):
        return fail(400, '旧密码错误')

    await crud.update_password(user['id'], new_password)
    return ok(None, msg='密码修改成功')


@router.get('/me')
async def me(request: Request):
    """Get current user info."""
    user = await get_current_user(request)
    full_user = await crud.get_user_by_id(user['id'])
    if full_user is None:
        return fail(401, '用户不存在')
    return ok({
        'id': full_user['id'],
        'username': full_user['username'],
        'nickname': full_user['nickname'],
        'avatar_url': full_user.get('avatar_url', ''),
        'created_at': full_user.get('created_at', ''),
    })


@router.put('/profile')
async def update_profile(request: Request):
    """Update current user profile (nickname, avatar_url)."""
    user = await get_current_user(request)
    data = await request.json()
    update_data = {}
    if 'nickname' in data:
        nickname = data['nickname'].strip()
        if not nickname:
            return fail(400, '昵称不能为空')
        update_data['nickname'] = nickname
    if 'avatar_url' in data:
        avatar_url = data['avatar_url']
        if avatar_url and avatar_url.startswith('default:'):
            update_data['avatar_url'] = f'/avatars/{avatar_url.split(":")[1]}.svg'
        else:
            update_data['avatar_url'] = avatar_url

    if not update_data:
        return fail(400, '没有需要更新的字段')

    success = await crud.update_user_profile(user['id'], **update_data)
    if not success:
        return fail(500, '更新失败')

    # Return updated user info
    full_user = await crud.get_user_by_id(user['id'])
    return ok({
        'id': full_user['id'],
        'username': full_user['username'],
        'nickname': full_user['nickname'],
        'avatar_url': full_user.get('avatar_url', ''),
        'created_at': full_user.get('created_at', ''),
    }, msg='个人资料更新成功')


@router.post('/avatar')
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    """Upload a custom avatar image."""
    user = await get_current_user(request)

    # Validate file type
    if file.content_type not in ('image/jpeg', 'image/png', 'image/gif', 'image/svg+xml', 'image/webp'):
        return fail(400, '仅支持 JPEG、PNG、GIF、SVG、WebP 格式的图片')

    # Read file content
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        return fail(400, '图片大小不能超过 5MB')

    # Determine extension
    ext_map = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/svg+xml': '.svg',
        'image/webp': '.webp',
    }
    ext = ext_map.get(file.content_type, '.png')

    # Save file under the static directory
    avatar_dir = PROJECTS_DATA_DIR / 'static' / 'avatars' / str(user['id'])
    avatar_dir.mkdir(parents=True, exist_ok=True)

    filename = f'{int(time.time())}{ext}'
    file_path = avatar_dir / filename
    with open(file_path, 'wb') as f:
        f.write(content)

    avatar_url = f'/api/static/avatars/{user["id"]}/{filename}'
    await crud.update_user_avatar(user['id'], avatar_url)
    return ok({'avatar_url': avatar_url}, msg='头像上传成功')


@router.get('/default-avatars')
async def list_default_avatars():
    """Return the list of 5 default avatar identifiers."""
    avatars = [
        {'id': 'default:1', 'url': '/avatars/1.svg'},
        {'id': 'default:2', 'url': '/avatars/2.svg'},
        {'id': 'default:3', 'url': '/avatars/3.svg'},
        {'id': 'default:4', 'url': '/avatars/4.svg'},
        {'id': 'default:5', 'url': '/avatars/5.svg'},
    ]
    return ok(avatars)