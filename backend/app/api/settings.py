"""设置类 API — 飞书授权（每用户 Device Flow 两段式）。

依据 ADR-0013：
- POST /api/settings/lark/auth          发起授权，返回验证链接 + device_code
- POST /api/settings/lark/auth/complete 携带 device_code 完成授权并绑定 user_lark_bindings
- GET  /api/settings/lark/status        查询当前用户绑定状态与 token 有效性

绑定关系：系统 user_id ↔ (lark app_id, lark_open_id)；token 生命周期由 lark-cli 管理。

授权完成采用「发起即后台完成」：
lark-cli 的 `auth login --device-code` 会阻塞等待用户在浏览器确认（最长 AUTH_COMPLETE_TIMEOUT），
因此发起授权后由后台 task 执行该阻塞调用，前端仅轮询快速的 status 接口，
确认后自动绑定，避免前端每 3s 调用 complete 造成请求堆积。
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.db import crud
from app.services import lark_cli
from app.models.schemas import LLMSettingsUpdate

router = APIRouter(prefix='/api/settings', tags=['设置'])

# 进行中的后台授权：user_id -> {device_code, task, error}
_pending_auths: dict[int, dict] = {}


class LarkAuthCompleteRequest(BaseModel):
    device_code: str


async def _run_auth_completion(user_id: int, device_code: str) -> None:
    """后台执行阻塞式授权完成；成功后自动绑定 user_id ↔ 飞书身份。

    失败时不抛异常，把可读原因写入 _pending_auths 供 status 接口回报，
    避免 asyncio 记录未捕获的任务异常。
    """
    entry = _pending_auths.get(user_id)
    try:
        result = await lark_cli.auth_complete(device_code)
    except lark_cli.LarkCliError as exc:
        if entry and entry['device_code'] == device_code:
            entry['error'] = exc.message
        return
    await crud.upsert_user_lark_binding(user_id, result['app_id'], result['lark_open_id'])


def _auth_task_done(task: asyncio.Task) -> None:
    """消费后台授权任务的异常（CancelledError 或未预期异常），避免 asyncio 告警。"""
    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        pass


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


@router.post('/lark/auth')
async def lark_auth_initiate(request: Request):
    """发起飞书 Device Flow 授权，立即返回验证链接与 device_code。

    `auth login --device-code` 会阻塞等待用户在浏览器确认，因此由后台任务
    执行，本接口不阻塞；前端轮询 status 即可，确认后自动绑定。
    """
    user = await get_current_user(request)
    binding = await crud.get_user_lark_binding(user['id'])
    # 清理该用户旧的进行中授权
    old = _pending_auths.pop(user['id'], None)
    if old and old['task'] and not old['task'].done():
        old['task'].cancel()
    try:
        info = await lark_cli.auth_initiate()
    except lark_cli.LarkCliError as exc:
        return fail(500, exc.message)
    entry = {'device_code': info['device_code'], 'task': None, 'error': ''}
    _pending_auths[user['id']] = entry
    entry['task'] = asyncio.create_task(
        _run_auth_completion(user['id'], info['device_code'])
    )
    entry['task'].add_done_callback(_auth_task_done)
    return ok({
        'verification_url': info['verification_url'],
        'device_code': info['device_code'],
        'expires_in': info['expires_in'],
        'bound': binding is not None,
    }, msg='请在浏览器中打开链接完成授权')


@router.post('/lark/auth/complete')
async def lark_auth_complete(request: Request, data: LarkAuthCompleteRequest = Body(...)):
    """查询授权完成状态（后台任务已接管阻塞等待，本接口不再阻塞）。

    未完成返回 400 提示进行中；后台任务完成并自动绑定后返回 200 + 绑定信息。
    """
    user = await get_current_user(request)
    if not data.device_code.strip():
        return fail(400, 'device_code 不能为空')
    pending = _pending_auths.get(user['id'])
    if not pending or pending['device_code'] != data.device_code.strip():
        # 记录可能已被 status 清理：若用户已绑定则视为完成（幂等）
        binding = await crud.get_user_lark_binding(user['id'])
        if binding is not None:
            return ok({
                'lark_open_id': binding['lark_open_id'],
                'user_name': '',
                'token_status': '',
            }, msg='飞书授权成功')
        return fail(404, '未找到进行中的授权，请重新发起')
    if pending['error']:
        msg = pending['error'] or '飞书授权未完成，请确认已在浏览器完成操作'
        _pending_auths.pop(user['id'], None)
        return fail(400, msg)
    if not pending['task'] or not pending['task'].done():
        return fail(400, '飞书授权进行中，请在浏览器完成确认')
    # 任务已完成且无错误 → 后台已自动绑定
    binding = await crud.get_user_lark_binding(user['id'])
    if binding is None:
        _pending_auths.pop(user['id'], None)
        return fail(400, '飞书授权未完成，请确认已在浏览器完成操作')
    _pending_auths.pop(user['id'], None)
    return ok({
        'lark_open_id': binding['lark_open_id'],
        'user_name': '',
        'token_status': '',
    }, msg='飞书授权成功')


@router.get('/lark/status')
async def lark_auth_status(request: Request):
    """查询当前用户的飞书绑定状态。

    auth_required=True 表示需要发起授权（未绑定或 token 已失效）；
    auth_pending=True 表示后台授权进行中（期间跳过 CLI 状态查询，避免被阻塞）。
    """
    user = await get_current_user(request)
    binding = await crud.get_user_lark_binding(user['id'])
    pending = _pending_auths.get(user['id'])

    auth_pending = False
    auth_error = ''
    if pending:
        task = pending['task']
        if pending['error']:
            auth_error = pending['error']
            _pending_auths.pop(user['id'], None)
        elif task and not task.done():
            auth_pending = True
        else:
            # 任务已完成且无错误 → 后台已自动绑定，清理记录
            _pending_auths.pop(user['id'], None)

    if auth_pending:
        # 后台阻塞式授权运行中：跳过 CLI 查询（避免排队），由前端轮询等待
        return ok({
            'bound': binding is not None,
            'app_id': binding['app_id'] if binding else '',
            'lark_open_id': binding['lark_open_id'] if binding else '',
            'token_status': '',
            'auth_required': binding is None,
            'auth_pending': True,
            'auth_error': '',
            'cli_available': lark_cli._cli_available(),
        })

    cli_status = None
    try:
        cli_status = await lark_cli.auth_status()
    except lark_cli.LarkCliError:
        cli_status = None

    token_status = cli_status.get('token_status', '') if cli_status else ''
    # needs_refresh 表示即将过期但可用；invalid/expired 视为失效
    auth_required = binding is None or not token_status or token_status in ('invalid', 'expired', 'unknown')
    return ok({
        'bound': binding is not None,
        'app_id': binding['app_id'] if binding else '',
        'lark_open_id': binding['lark_open_id'] if binding else '',
        'token_status': token_status,
        'auth_required': auth_required,
        'auth_pending': False,
        'auth_error': auth_error,
        'cli_available': lark_cli._cli_available(),
    })
