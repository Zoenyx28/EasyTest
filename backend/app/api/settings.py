"""设置类 API — 飞书官方 OAuth（读阶段，替换 lark-cli Device Flow）。

依据 grilling 定案（共享单应用 + 每用户 user_access_token + DB 加密 + 自动刷新）：
- GET  /api/settings/feishu/auth-url  构造 OAuth 授权 URL
- POST /api/settings/feishu/token     用 authorization_code 换 token 并落库
- GET  /api/settings/feishu/status    查询绑定与 token 状态
- DELETE /api/settings/feishu         解除绑定
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Query, Request
from pydantic import BaseModel

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.db import crud
from app.services import feishu_client
from app.models.schemas import LLMSettingsUpdate

router = APIRouter(prefix='/api/settings', tags=['设置'])


def _mask_key(key: str) -> str:
    """打码 API key（保留前 4 后 4）。"""
    key = key or ''
    if len(key) <= 8:
        return '****'
    return f'{key[:4]}****{key[-4:]}'


@router.get('/llm')
async def get_llm_settings(request: Request):
    """获取全局 LLM 配置（返回不泄完整 key）。"""
    await get_current_user(request)
    s = await crud.get_llm_settings()
    if s is None:
        return ok({'provider': '', 'api_base': '', 'text_model': '',
                   'vision_model': '', 'has_key': False, 'api_key_masked': ''})
    return ok({
        'provider': s['provider'],
        'api_base': s['api_base'],
        'text_model': s['text_model'],
        'vision_model': s['vision_model'],
        'has_key': bool(s['api_key']),
        'api_key_masked': _mask_key(s['api_key']),
    })


@router.put('/llm')
async def update_llm_settings(request: Request, data: LLMSettingsUpdate = Body(...)):
    """保存全局 LLM 配置（任意登录用户可改；key 仅存后端）。"""
    user = await get_current_user(request)
    fields = {}
    for key in ('provider', 'api_base', 'text_model', 'vision_model', 'api_key'):
        value = getattr(data, key, None)
        if value is not None:
            stripped = value.strip() if isinstance(value, str) else value
            # api_key 留空表示不修改已保存的 key，避免误覆盖
            if key == 'api_key' and not stripped:
                continue
            fields[key] = stripped
    if not fields:
        return fail(400, '无有效配置项')
    await crud.save_llm_settings(fields, user['id'])
    return ok({}, msg='LLM 配置已保存')





class FeishuTokenBody(BaseModel):
    code: str


def _token_status(rec: dict) -> tuple[str, bool]:
    """返回 (token_status, auth_required)。access 过期但 refresh 有效 → 下次提取自动刷新。"""
    now = datetime.utcnow()

    def _parse(iso: str) -> datetime | None:
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            return None

    access_ok = True
    if rec.get('access_expires_at'):
        exp = _parse(rec['access_expires_at'])
        access_ok = exp is not None and exp > now
    refresh_ok = bool(rec.get('refresh_token_enc'))
    if refresh_ok and rec.get('refresh_expires_at'):
        rexp = _parse(rec['refresh_expires_at'])
        refresh_ok = rexp is not None and rexp > now
    if access_ok:
        return 'valid', False
    if refresh_ok:
        return 'needs_refresh', False
    return 'expired', True


@router.get('/feishu/auth-url')
async def feishu_auth_url(request: Request):
    """构造飞书网页 OAuth 授权 URL（前端在新窗口打开）。"""
    await get_current_user(request)
    return ok({'authorize_url': feishu_client.build_authorize_url()},
              msg='请在浏览器中打开链接完成授权')


@router.post('/feishu/token')
async def feishu_token(request: Request, data: FeishuTokenBody = Body(...)):
    """用 OAuth authorization_code 换 user_access_token + refresh_token 并落库。"""
    user = await get_current_user(request)
    code = (data.code or '').strip()
    if not code:
        return fail(400, 'code 不能为空')
    try:
        info = await feishu_client.exchange_code(code, user['id'])
    except feishu_client.FeishuError as exc:
        return fail(400, exc.message)
    return ok({'lark_open_id': info.get('open_id', '')}, msg='飞书授权成功')


@router.get('/feishu/status')
async def feishu_status(request: Request):
    """查询当前用户的飞书绑定与 token 状态。"""
    user = await get_current_user(request)
    rec = await crud.get_user_feishu_token(user['id'])
    if rec is None or not rec['access_token_enc']:
        return ok({'bound': False, 'lark_open_id': '', 'token_status': '',
                   'auth_required': True, 'auth_pending': False, 'auth_error': ''})
    token_status, auth_required = _token_status(rec)
    return ok({'bound': True, 'lark_open_id': rec['lark_open_id'],
               'token_status': token_status, 'auth_required': auth_required,
               'auth_pending': False, 'auth_error': ''})


@router.delete('/feishu')
async def feishu_unbind(request: Request):
    """解除当前用户的飞书绑定。"""
    user = await get_current_user(request)
    await crud.clear_user_feishu_token(user['id'])
    return ok(None, msg='已解除飞书绑定')


# ══════════════════════════════════════════════════════════
# 飞书文档预览（blocks→markdown） + 图片代理
# ══════════════════════════════════════════════════════════

feishu_router = APIRouter(prefix='/api/feishu', tags=['飞书'])


@feishu_router.get('/preview')
async def feishu_preview(request: Request, url: str = Query(...)):
    """按链接返回文档预览 markdown + 图片 token 列表（当前用户身份）。"""
    user = await get_current_user(request)
    result = await feishu_client.preview_doc(url, user['id'])
    if result.get('error_kind'):
        code = 401 if result['error_kind'] == 'no_auth' else 400
        return fail(code, result.get('error_message', '预览失败'))
    return ok({'markdown': result['markdown'], 'images': result['images']}, msg='预览成功')


@feishu_router.get('/media/{file_token}')
async def feishu_media(request: Request, file_token: str):
    """飞书图片代理：以当前用户身份下载图片字节返回给前端 <img>。"""
    from fastapi.responses import Response
    user = await get_current_user(request)
    try:
        content, content_type = await feishu_client.fetch_image(file_token, user['id'])
    except feishu_client.FeishuError as exc:
        return fail(400, exc.message)
    return Response(content=content, media_type=content_type)
