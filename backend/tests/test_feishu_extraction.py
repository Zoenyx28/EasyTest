"""飞书官方 API 读阶段测试（mock lark_oapi SDK + OAuth）。

覆盖：链接解析（parse_link）、fetch_doc（docx/wiki/不支持/未授权/权限错误）、
token 加密回环、OAuth token 落库与状态、需求来源提取降级。
"""
import json

import httpx
import pytest

from unittest.mock import AsyncMock

from app.db import crud
from app.services import feishu_client


@pytest.fixture(autouse=True)
async def _clear_tokens():
    yield
    from app.db.database import session_ctx
    from app.db.models import UserFeishuToken, UserLarkBinding
    from sqlalchemy import delete
    async with session_ctx() as session:
        await session.execute(delete(UserFeishuToken))
        await session.execute(delete(UserLarkBinding))
        await session.commit()


# ── 链接解析 ──


async def test_parse_link_valid_types():
    cases = [
        ('https://x.feishu.cn/docx/Abc123', 'docx', 'Abc123'),
        ('https://x.feishu.cn/wiki/WikiT9', 'wiki', 'WikiT9'),
        ('https://x.feishu.cn/sheets/ShToken', 'sheet', 'ShToken'),
        ('https://x.feishu.cn/base/BaToken', 'bitable', 'BaToken'),
        ('https://x.feishu.cn/docs/OldDoc1', 'doc', 'OldDoc1'),
    ]
    for url, dt, tok in cases:
        r = feishu_client.parse_link(url)
        assert r['valid'], url
        assert r['doc_type'] == dt
        assert r['token'] == tok


async def test_parse_link_invalid():
    for url in ('https://baidu.com/x', 'https://x.feishu.cn/unknown/xx',
                'not a url', 'https://x.feishu.cn/docx/'):
        r = feishu_client.parse_link(url)
        assert not r['valid']
        assert r['error_kind'] == feishu_client.ERR_INVALID_LINK


async def test_parse_link_unsupported_types_flagged():
    # file/slides/mindnotes 能解析但不在读取支持集
    r = feishu_client.parse_link('https://x.feishu.cn/file/FIleXx')
    assert r['valid'] and r['doc_type'] == 'file'
    assert r['doc_type'] not in feishu_client._SUPPORTED_READ


# ── token 加密 ──


async def test_token_encrypt_decrypt_roundtrip():
    enc = feishu_client.encrypt_token('ua_token_123')
    assert enc != 'ua_token_123'
    assert feishu_client.decrypt_token(enc) == 'ua_token_123'
    assert feishu_client.decrypt_token('garbage') == ''


# ── fetch_doc（mock httpx 客户端）──


class _FakeHttpResp:
    def __init__(self, data, status_code=200):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeHttp:
    """模拟 httpx.AsyncClient：按 URL 子串路由到固定响应，记录调用 URL。"""

    def __init__(self, routes):
        self.routes = routes  # {url_substring: data_dict}
        self.urls = []

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def get(self, url, **kw):
        self.urls.append(url)
        for sub, data in self.routes.items():
            if sub in url:
                return _FakeHttpResp(data)
        return _FakeHttpResp({'code': 0, 'data': {}})


async def test_fetch_doc_docx_success(client, ctx, monkeypatch):
    fake = _FakeHttp({'raw_content': {'code': 0, 'data': {'content': '订单支持 3 天无理由退款'}}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: fake)
    monkeypatch.setattr(feishu_client, '_get_tenant_token', AsyncMock(return_value='tenant_tok'))
    monkeypatch.setattr(feishu_client, '_get_user_token', AsyncMock(return_value=None))

    result = await feishu_client.fetch_doc('https://x.feishu.cn/docx/Doc1', ctx['member']['id'])
    assert result['extracted'] is True
    assert '无理由' in result['text_content']
    assert any('raw_content' in u and 'Doc1' in u for u in fake.urls)


async def test_fetch_doc_wiki_resolves(client, ctx, monkeypatch):
    fake = _FakeHttp({
        'get_node': {'code': 0, 'data': {'node': {'obj_token': 'RealDocTok', 'obj_type': 'docx'}}},
        'raw_content': {'code': 0, 'data': {'content': '知识库文档正文'}},
    })
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: fake)
    monkeypatch.setattr(feishu_client, '_get_tenant_token', AsyncMock(return_value='tenant_tok'))
    monkeypatch.setattr(feishu_client, '_get_user_token', AsyncMock(return_value=None))

    result = await feishu_client.fetch_doc('https://x.feishu.cn/wiki/WikiX', ctx['member']['id'])
    assert result['extracted'] is True
    assert '知识库' in result['text_content']
    assert any('get_node' in u for u in fake.urls)
    assert any('raw_content' in u and 'RealDocTok' in u for u in fake.urls)


async def test_fetch_doc_permission_error_mapped(client, ctx, monkeypatch):
    fake = _FakeHttp({'raw_content': {'code': 99991661, 'msg': 'permission denied'}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: fake)
    monkeypatch.setattr(feishu_client, '_get_tenant_token', AsyncMock(return_value='tt'))
    monkeypatch.setattr(feishu_client, '_get_user_token', AsyncMock(return_value=None))

    result = await feishu_client.fetch_doc('https://x.feishu.cn/docx/Doc1', ctx['member']['id'])
    assert result['extracted'] is False
    assert result['error_kind'] == feishu_client.ERR_PERMISSION
    assert '授权' in result['error_message']


async def test_get_tenant_token_async_path(monkeypatch):
    """回归：_get_tenant_token 必须走 httpx.AsyncClient（sync httpx.post 不可 await）。"""
    class FakeResp:
        status_code = 200
        def json(self):
            return {'code': 0, 'tenant_access_token': 'tt_abc', 'expire': 7200}
    class FakeAsyncClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None): return FakeResp()
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: FakeAsyncClient())
    monkeypatch.setattr(feishu_client, '_get_tenant_token', feishu_client._ORIG_GET_TENANT)

    token = await feishu_client._get_tenant_token()
    assert token == 'tt_abc'


async def test_oauth_post_async_path(monkeypatch):
    """回归：_oauth_post 必须走 AsyncClient（否则 exchange_code 在生产挂掉）。"""
    class FakeResp:
        status_code = 200
        def json(self):
            return {'access_token': 'ua_abc', 'refresh_token': 'rf_x',
                    'expires_in': 7200, 'open_id': 'ou_x'}
    class FakeAsyncClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None): return FakeResp()
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: FakeAsyncClient())

    data = await feishu_client._oauth_post({'grant_type': 'authorization_code'})
    assert data['access_token'] == 'ua_abc'


# ── OAuth token 落库 + 状态端点 ──


async def test_oauth_token_saved_and_status(client, ctx, monkeypatch):
    # mock 掉真实 HTTP：exchange_code 里的 _oauth_post 返回假 token
    async def fake_oauth_post(payload):
        assert 'redirect_uri' in payload  # 回归：token 交换必须带 redirect_uri 键
        return {
            'access_token': 'ua_abc', 'refresh_token': 'rf_xyz',
            'expires_in': 7200, 'refresh_token_expires_in': 2592000,
            'open_id': 'ou_member', 'scope': 'docx',
        }
    monkeypatch.setattr(feishu_client, '_oauth_post', fake_oauth_post)

    resp = await client.post('/api/settings/feishu/token', json={'code': 'auth_code_1'},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    assert resp.json()['code'] == 200, resp.text

    rec = await crud.get_user_feishu_token(ctx['member']['id'])
    assert rec and rec['lark_open_id'] == 'ou_member'
    assert feishu_client.decrypt_token(rec['access_token_enc']) == 'ua_abc'

    st = (await client.get('/api/settings/feishu/status',
                           headers={'Authorization': f"Bearer {ctx['member']['token']}"})).json()['data']
    assert st['bound'] is True
    assert st['token_status'] == 'valid'
    assert st['auth_required'] is False


async def test_feishu_status_unbound(client, ctx):
    st = (await client.get('/api/settings/feishu/status',
                           headers={'Authorization': f"Bearer {ctx['member']['token']}"})).json()['data']
    assert st['bound'] is False
    assert st['auth_required'] is True


async def test_feishu_auth_url(client, ctx):
    resp = await client.get('/api/settings/feishu/auth-url',
                            headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    url = resp.json()['data']['authorize_url']
    assert 'accounts.feishu.cn/open-apis/authen/v1/authorize' in url
    assert 'client_id=' in url and 'offline_access' in url


# ── 需求来源提取降级（无凭据 → 保存链接 + extracted=False）──


async def test_add_link_source_fails_gracefully(client, ctx, monkeypatch):
    """未授权时添加飞书链接 → 降级保存，不阻断。"""
    monkeypatch.setattr(feishu_client, '_get_tenant_token', AsyncMock(return_value=''))
    monkeypatch.setattr(feishu_client, '_get_user_token', AsyncMock(return_value=None))

    resp = await client.post('/api/requirements', json={
        'project_id': ctx['project_id'], 'branch_id': ctx['branch_id'], 'title': '需求',
    }, headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    req_id = resp.json()['data']['id']

    resp = await client.post(f'/api/requirements/{req_id}/sources', json={
        'type': 'lark_link', 'link': 'https://x.feishu.cn/docx/DocNoAuth',
    }, headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['extracted'] is False
    assert body['data']['extract_error']  # 可读失败原因

    srcs = (await client.get(f'/api/requirements/{req_id}/sources',
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})).json()['data']
    assert srcs[0]['type'] == 'lark_link'
    assert srcs[0]['extracted'] is False
