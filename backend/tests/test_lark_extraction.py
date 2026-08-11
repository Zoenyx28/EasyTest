"""Ticket #14 测试 — 飞书授权（Device Flow）+ 链接正文提取。

通过 mock `app.services.lark_cli` 的授权/提取函数覆盖：
- 授权发起：发起后后台任务自动完成绑定，status/complete 反映状态
- 授权进行中 / 失败：status 返回 auth_pending / auth_error
- 提取成功：text_content + extracted=true
- 鉴权失败 / 非文档链接：extracted=false + 可读原因（降级）
"""
import asyncio
import json

import pytest
from sqlalchemy import delete

from app.db.database import session_ctx
from app.db.models import UserLarkBinding
from app.services import lark_cli
from app.api import settings as settings_api


async def _clear_binding(user_id: int) -> None:
    """清理用户的飞书绑定（测试间隔离，避免 session 级 DB 残留）。"""
    async with session_ctx() as session:
        await session.execute(delete(UserLarkBinding).where(UserLarkBinding.user_id == user_id))
        await session.commit()

_DEVICE_FLOW_JSON = json.dumps({
    'device_code': 'DC-TEST-001',
    'expires_in': 600,
    'verification_url': 'https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=f&user_code=uc',
})


# ── 授权接口 ──
async def test_lark_status_unbound(client, ctx):
    """未绑定时 auth_required=True。"""
    await _clear_binding(ctx['member']['id'])
    resp = await client.get('/api/settings/lark/status',
                            headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['bound'] is False
    assert body['data']['auth_required'] is True


async def test_lark_auth_initiate(client, ctx, monkeypatch):
    """发起授权返回验证链接与 device_code。"""
    await _clear_binding(ctx['member']['id'])

    async def fake_run_cli(args, timeout=30):
        assert 'login' in args and '--no-wait' in args
        return 0, _DEVICE_FLOW_JSON, ''
    monkeypatch.setattr(lark_cli, 'run_cli', fake_run_cli)

    resp = await client.post('/api/settings/lark/auth',
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    data = body['data']
    assert data['device_code'] == 'DC-TEST-001'
    assert 'verification_url' in data
    assert data['expires_in'] == 600
    assert data['bound'] is False


async def _fake_auth_status():
    return {
        'app_id': 'cli_test_app',
        'user_open_id': 'ou_test_openid',
        'user_name': '测试用户',
        'token_status': 'valid',
        'bot_ready': True,
        'default_as': 'auto',
    }


async def test_lark_auth_success_auto_binds(client, ctx, monkeypatch):
    """发起授权后后台自动完成绑定：status 反映 bound，complete 返回成功。"""
    await _clear_binding(ctx['member']['id'])

    async def fake_auth_initiate(domain='docs'):
        return {'verification_url': 'https://verify', 'device_code': 'DC-TEST-001', 'expires_in': 600}
    async def fake_auth_complete(device_code, *, timeout=300, shared=False):
        assert shared is False  # 阻塞式授权须跳过共享信号量
        return {'app_id': 'cli_test_app', 'lark_open_id': 'ou_test_openid',
                'user_name': '测试用户', 'token_status': 'valid'}
    monkeypatch.setattr(lark_cli, 'auth_initiate', fake_auth_initiate)
    monkeypatch.setattr(lark_cli, 'auth_complete', fake_auth_complete)
    monkeypatch.setattr(lark_cli, 'auth_status', _fake_auth_status)

    resp = await client.post('/api/settings/lark/auth',
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['device_code'] == 'DC-TEST-001'

    # 等待后台授权任务完成（自动绑定）
    entry = settings_api._pending_auths[ctx['member']['id']]
    await entry['task']
    assert entry['error'] == ''

    # status：已绑定
    resp = await client.get('/api/settings/lark/status',
                            headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['bound'] is True
    assert body['data']['lark_open_id'] == 'ou_test_openid'
    assert body['data']['token_status'] == 'valid'
    assert body['data']['auth_required'] is False
    assert body['data']['auth_pending'] is False

    # complete：返回成功
    resp = await client.post('/api/settings/lark/auth/complete',
                             json={'device_code': 'DC-TEST-001'},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['lark_open_id'] == 'ou_test_openid'


async def test_lark_auth_pending_state(client, ctx, monkeypatch):
    """后台任务尚未完成时：status 返回 auth_pending，complete 提示进行中。"""
    await _clear_binding(ctx['member']['id'])

    async def fake_auth_initiate(domain='docs'):
        return {'verification_url': 'https://verify', 'device_code': 'DC-TEST-001', 'expires_in': 600}
    async def fake_auth_complete(device_code, *, timeout=300, shared=False):
        await asyncio.sleep(30)  # 模拟阻塞等待用户在浏览器确认
        return {'app_id': 'cli_test_app', 'lark_open_id': 'ou_test_openid',
                'user_name': '测试用户', 'token_status': 'valid'}
    monkeypatch.setattr(lark_cli, 'auth_initiate', fake_auth_initiate)
    monkeypatch.setattr(lark_cli, 'auth_complete', fake_auth_complete)

    await client.post('/api/settings/lark/auth',
                      headers={'Authorization': f"Bearer {ctx['member']['token']}"})

    # status：进行中
    resp = await client.get('/api/settings/lark/status',
                            headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['auth_pending'] is True
    assert body['data']['bound'] is False

    # complete：进行中提示
    resp = await client.post('/api/settings/lark/auth/complete',
                             json={'device_code': 'DC-TEST-001'},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 400
    assert '进行中' in body['msg']

    # 清理：取消后台任务并移除记录
    entry = settings_api._pending_auths.pop(ctx['member']['id'], None)
    if entry and entry['task'] and not entry['task'].done():
        entry['task'].cancel()
        try:
            await entry['task']
        except asyncio.CancelledError:
            pass


async def test_lark_auth_failed_reports_error(client, ctx, monkeypatch):
    """后台任务失败（用户未确认）：status 返回 auth_error 并清理记录。"""
    await _clear_binding(ctx['member']['id'])

    async def fake_auth_initiate(domain='docs'):
        return {'verification_url': 'https://verify', 'device_code': 'DC-TEST-001', 'expires_in': 600}
    async def fake_auth_complete(device_code, *, timeout=300, shared=False):
        raise lark_cli.LarkCliError(lark_cli.ERR_AUTH, '飞书授权未完成，请确认已在浏览器完成操作')
    monkeypatch.setattr(lark_cli, 'auth_initiate', fake_auth_initiate)
    monkeypatch.setattr(lark_cli, 'auth_complete', fake_auth_complete)

    await client.post('/api/settings/lark/auth',
                      headers={'Authorization': f"Bearer {ctx['member']['token']}"})

    # 等待后台任务结束（记录失败原因，不抛出）
    entry = settings_api._pending_auths[ctx['member']['id']]
    await entry['task']
    assert entry['error'] != ''

    # status：返回 auth_error
    resp = await client.get('/api/settings/lark/status',
                            headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['auth_pending'] is False
    assert '飞书授权未完成' in body['data']['auth_error']
    assert ctx['member']['id'] not in settings_api._pending_auths


async def test_auth_complete_reports_review_pending(client, ctx, monkeypatch):
    """权限审核中：auth_complete 抛出翻译后的中文提示。"""
    _under_review = ('{"ok": false, "error": {"type": "authentication", "subtype": "unknown",'
                     ' "message": "authorization failed: The requested permissions are already'
                     ' under review. Please wait for approval."}}')

    async def fake_run_cli(args, timeout=300, shared=False):
        return 3, _under_review, ''
    monkeypatch.setattr(lark_cli, 'run_cli', fake_run_cli)

    with pytest.raises(lark_cli.LarkCliError) as exc_info:
        await lark_cli.auth_complete('DC-TEST-001')
    assert '审核中' in exc_info.value.message


async def test_translate_auth_error():
    """失败原因翻译：审核中/被拒/过期/取消/默认。"""
    assert '审核中' in lark_cli._translate_auth_error(
        'The requested permissions are already under review. Please wait for approval.')
    assert '未通过审核' in lark_cli._translate_auth_error('request denied by admin')
    assert '已过期' in lark_cli._translate_auth_error('device code expired')
    assert '已取消' in lark_cli._translate_auth_error('authorization cancelled')
    assert lark_cli._translate_auth_error('other reason') == 'other reason'
    assert lark_cli._translate_auth_error('') == ''


# ── 提取（来源添加/重试） ──


async def _make_requirement(client, ctx) -> int:
    resp = await client.post('/api/requirements',
                             json={'project_id': ctx['project_id'],
                                   'branch_id': ctx['branch_id'],
                                   'title': '提取测试需求'},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    return resp.json()['data']['id']


async def test_add_link_source_extracted(client, ctx, monkeypatch):
    """提取成功：text_content 落库，extracted=true。"""
    req_id = await _make_requirement(client, ctx)
    content = '# 需求\n\n- 支持查询订单'.encode('utf-8').decode('utf-8')

    async def fake_fetch_doc(url, timeout=60):
        return {'extracted': True, 'text_content': content, 'error_kind': '', 'error_message': ''}
    monkeypatch.setattr(lark_cli, 'fetch_doc', fake_fetch_doc)

    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/FxbUwrLgOiFKUVkL72Wc49hJnAf'},
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['extracted'] is True
    assert body['data']['extract_error'] == ''

    sources = (await client.get(f'/api/requirements/{req_id}/sources',
                                headers={'Authorization': f"Bearer {ctx['member']['token']}"})).json()['data']
    assert len(sources) == 1
    assert sources[0]['extracted'] is True
    assert sources[0]['text_content'] == content


async def test_add_link_source_auth_failed(client, ctx, monkeypatch):
    """鉴权过期：extracted=false，返回可读原因，来源仍保存。"""
    req_id = await _make_requirement(client, ctx)

    async def fake_fetch_doc(url, timeout=60):
        return {'extracted': False, 'text_content': '',
                'error_kind': lark_cli.ERR_AUTH,
                'error_message': '飞书授权已过期或未授权，请重新授权后重试'}
    monkeypatch.setattr(lark_cli, 'fetch_doc', fake_fetch_doc)

    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/XXXX'},
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['extracted'] is False
    assert '重新授权' in body['data']['extract_error']

    sources = (await client.get(f'/api/requirements/{req_id}/sources',
                                headers={'Authorization': f"Bearer {ctx['member']['token']}"})).json()['data']
    assert len(sources) == 1
    assert sources[0]['extracted'] is False
    assert '重新授权' in sources[0]['extract_error']


async def test_add_link_source_invalid_link(client, ctx, monkeypatch):
    """非飞书文档链接：extracted=false + 可读提示。"""
    req_id = await _make_requirement(client, ctx)

    async def fake_fetch_doc(url, timeout=60):
        return {'extracted': False, 'text_content': '',
                'error_kind': lark_cli.ERR_INVALID,
                'error_message': '仅支持飞书文档（docx/wiki）链接'}
    monkeypatch.setattr(lark_cli, 'fetch_doc', fake_fetch_doc)

    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://www.baidu.com'},
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['extracted'] is False
    assert '飞书文档' in body['data']['extract_error']


async def test_re_extract_source_after_auth(client, ctx, monkeypatch):
    """授权后重试提取成功并回写来源。"""
    req_id = await _make_requirement(client, ctx)

    # 第一次：鉴权失败
    async def fake_fetch_fail(url, timeout=60):
        return {'extracted': False, 'text_content': '',
                'error_kind': lark_cli.ERR_AUTH, 'error_message': '飞书授权已过期或未授权'}
    monkeypatch.setattr(lark_cli, 'fetch_doc', fake_fetch_fail)
    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/FxbUwrLgOiFKUVkL72Wc49hJnAf'},
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    source_id = resp.json()['data']['id']

    # 第二次：授权后提取成功
    content = '# 工具库 PRD\n\n| 优先级 | P0 |'
    async def fake_fetch_ok(url, timeout=60):
        return {'extracted': True, 'text_content': content, 'error_kind': '', 'error_message': ''}
    monkeypatch.setattr(lark_cli, 'fetch_doc', fake_fetch_ok)
    resp = await client.post(
        f'/api/requirements/{req_id}/sources/{source_id}/extract',
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['extracted'] is True

    sources = (await client.get(f'/api/requirements/{req_id}/sources',
                                headers={'Authorization': f"Bearer {ctx['member']['token']}"})).json()['data']
    assert sources[0]['extracted'] is True
    assert sources[0]['text_content'] == content
    assert sources[0]['extract_error'] == ''


async def test_re_extract_non_lark_source_rejected(client, ctx, monkeypatch):
    """文件来源不支持提取。"""
    req_id = await _make_requirement(client, ctx)

    async def fake_fetch(url, timeout=60):
        return {'extracted': False, 'text_content': '',
                'error_kind': lark_cli.ERR_INVALID, 'error_message': 'x'}
    monkeypatch.setattr(lark_cli, 'fetch_doc', fake_fetch)
    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://www.baidu.com'},
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    source_id = resp.json()['data']['id']

    # 将来源改为 file 类型（绕过接口，直接走 crud）
    from app.db import crud
    await crud.update_requirement_source(source_id, {'type': 'file'})

    resp = await client.post(
        f'/api/requirements/{req_id}/sources/{source_id}/extract',
        headers={'Authorization': f"Bearer {ctx['member']['token']}"},
    )
    body = resp.json()
    assert body['code'] == 400
    assert '仅飞书链接来源' in body['msg']
