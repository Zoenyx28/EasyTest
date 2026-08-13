"""#25 需求评审闭环 API 测试（System B：/api/req）。

覆盖：问题卡片 评论（AI 回复线程）/ 忽略 / 确定（AI 改文档 + 快照）/
重新评审 reconcile（旧问题 已修复/不涉及/已确定不动 + 新问题追加）+ 提取正文自动写 content。
fake LLM 用 httpx.MockTransport 按 prompt 关键词返回固定输出。
"""
import json

import httpx
import pytest
from httpx import MockTransport

from app.db import crud_requirements
from app.services import llm_client
from app.domains.requirement_design import api as req_api


def _auth(user: dict) -> dict:
    return {'Authorization': f'Bearer {user["token"]}'}


async def _create_req(client, user, project_id, branch_id, content='订单支持 3 天无理由退款'):
    resp = await client.post('/api/req', json={
        'project_id': project_id, 'branch_id': branch_id,
        'title': '订单退款', 'content': content, 'source_type': 'text',
    }, headers=_auth(user))
    body = resp.json()
    assert body['code'] == 200, body
    return body['data']['id']


async def _seed_gap(client, user, req_id, content=None, status='pending'):
    gap_content = content or {
        'gap_type': 'BUSINESS_RULE_MISSING', 'severity': 'CRITICAL',
        'description': '退款时限未定义', 'question': '退款需在多少天内完成？',
        'thread': [],
    }
    await crud_requirements.upsert_assets(req_id, 'gap', [{
        'title': 'BUSINESS_RULE_MISSING', 'description': '退款时限未定义',
        'content': json.dumps(gap_content, ensure_ascii=False),
        'gate_status': 'CRITICAL', 'status': status,
    }], created_by=user['id'])
    gaps = await crud_requirements.get_assets(req_id, 'gap')
    return gaps[0]


def _review_transport() -> MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)['messages'][0]['content']
        # 确定问题 → 更新文档
        if '确定以下评审问题' in prompt:
            data = {'doc_changed': True,
                    'updated_content': '更新后的需求文档：退款 3 天内完成，超时自动重试。',
                    'note': '已补充退款时限规则'}
        # 重新评审 reconcile
        elif '重新核对' in prompt:
            data = {
                'elements': {'business_goal': '支持退款', 'roles': [], 'entities': [],
                             'flows': [], 'rules': [], 'states': [], 'inputs_outputs': [],
                             'exceptions': [], 'permissions': [], 'dependencies': [], 'risks': []},
                'reconciled': [
                    {'index': 0, 'new_status': 'fixed', 'note': '文档已补充时限规则'},
                    {'index': 1, 'new_status': 'not_applicable', 'note': '需求不再涉及'},
                ],
                'information_gaps': [
                    {'gap_type': 'SCENARIO_MISSING', 'severity': 'HIGH',
                     'description': '缺少超时场景', 'question': '超时如何处理？'},
                ],
                'score': 92, 'score_reason': '核对完成',
            }
        # 评论/忽略 → 纯文本回复
        else:
            return httpx.Response(200, json={
                'choices': [{'message': {'content': 'AI 已记录您的意见'}}],
            })
        return httpx.Response(200, json={
            'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}],
        })
    return MockTransport(handler)


@pytest.fixture
async def _enable_fake_llm(monkeypatch):
    real_llm = llm_client.LLMClient
    monkeypatch.setattr(
        req_api.llm_client, 'LLMClient',
        lambda *a, **k: real_llm(
            {'provider': 'deepseek', 'api_base': 'http://fake',
             'text_model': 'fake-model', 'vision_model': '', 'api_key': 'k'},
            transport=_review_transport()))


# ══════════════════════════════════════════════════════════
# 1. 评论 → AI 回复线程
# ══════════════════════════════════════════════════════════


async def test_gap_comment_appends_thread(client, ctx, _enable_fake_llm):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    gap = await _seed_gap(client, ctx['member'], req_id)

    resp = await client.post(f'/api/req/{req_id}/gaps/{gap["id"]}/comment',
                             json={'comment': '请补充时限规则'}, headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    thread = body['data']['thread']
    assert len(thread) == 2
    assert thread[0]['role'] == 'user' and thread[0]['text'] == '请补充时限规则'
    assert thread[1]['role'] == 'ai' and '记录' in thread[1]['text']

    # 落库确认
    gap2 = await crud_requirements.get_assets(req_id, 'gap')
    c = json.loads(gap2[0]['content'])
    assert len(c['thread']) == 2
    assert gap2[0]['status'] == 'pending'  # 评论不改状态


async def test_gap_comment_requires_text(client, ctx, _enable_fake_llm):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    gap = await _seed_gap(client, ctx['member'], req_id)
    resp = await client.post(f'/api/req/{req_id}/gaps/{gap["id"]}/comment',
                             json={'comment': '   '}, headers=_auth(ctx['member']))
    assert resp.json()['code'] == 400


# ══════════════════════════════════════════════════════════
# 2. 忽略 → 状态 ignored + AI 回复
# ══════════════════════════════════════════════════════════


async def test_gap_ignore_sets_status_and_reply(client, ctx, _enable_fake_llm):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    gap = await _seed_gap(client, ctx['member'], req_id)

    resp = await client.post(f'/api/req/{req_id}/gaps/{gap["id"]}/ignore',
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['status'] == 'ignored'

    gap2 = (await crud_requirements.get_assets(req_id, 'gap'))[0]
    assert gap2['status'] == 'ignored'
    assert len(json.loads(gap2['content'])['thread']) == 1  # 仅 AI 回复


# ══════════════════════════════════════════════════════════
# 3. 确定 → confirmed + AI 改文档 + 快照
# ══════════════════════════════════════════════════════════


async def test_gap_confirm_updates_doc_with_snapshot(client, ctx, _enable_fake_llm):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'],
                               content='订单支持 3 天无理由退款')
    gap = await _seed_gap(client, ctx['member'], req_id)

    resp = await client.post(f'/api/req/{req_id}/gaps/{gap["id"]}/confirm',
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['doc_changed'] is True
    assert body['data']['status'] == 'confirmed'

    # 文档被覆盖 + 快照
    req = await crud_requirements.get_requirement_with_stats(req_id)
    assert '3 天内完成' in req['content']
    meta = json.loads(req['source_meta'] or '{}')
    assert 'prev_content' in meta and '无理由退款' in meta['prev_content']

    gap2 = (await crud_requirements.get_assets(req_id, 'gap'))[0]
    assert gap2['status'] == 'confirmed'
    c = json.loads(gap2['content'])
    assert c['resolved_doc_change'] is True


# ══════════════════════════════════════════════════════════
# 4. 重新评审 reconcile
# ══════════════════════════════════════════════════════════


async def test_re_review_reconciles_and_appends(client, ctx, _enable_fake_llm):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    # 一次建两张卡片：g1 pending（会被 reconcile），g2 confirmed（不动）
    await crud_requirements.upsert_assets(req_id, 'gap', [
        {'title': 'BUSINESS_RULE_MISSING', 'description': '退款时限未定义',
         'content': json.dumps({'gap_type': 'BUSINESS_RULE_MISSING', 'severity': 'CRITICAL',
                                'description': '退款时限未定义', 'question': '多少天？',
                                'thread': []}, ensure_ascii=False),
         'gate_status': 'CRITICAL', 'status': 'pending'},
        {'title': 'RISK_UNSPECIFIED', 'description': '已确认的风险',
         'content': json.dumps({'gap_type': 'RISK_UNSPECIFIED', 'severity': 'LOW',
                                'description': '已确认的风险', 'question': 'x',
                                'thread': []}, ensure_ascii=False),
         'gate_status': 'LOW', 'status': 'confirmed'},
    ], created_by=ctx['member']['id'])
    gaps_before = await crud_requirements.get_assets(req_id, 'gap')
    g1 = gaps_before[0]
    g2 = gaps_before[1]

    resp = await client.post(f'/api/req/{req_id}/analysis/re-review', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body

    # 后台任务完成后再断言（re-review 为后台任务 + AITask）
    import asyncio
    for _ in range(40):
        wb = (await client.get(f'/api/requirements/{req_id}/workbench',
                               headers=_auth(ctx['member']))).json()['data']
        rrt = [t for t in wb.get('ai_tasks') or [] if t['stage'] == 're_review']
        if rrt and rrt[0]['status'] in ('REVIEW', 'CONFIRMED', 'FAILED'):
            break
        await asyncio.sleep(0.3)

    gaps = await crud_requirements.get_assets(req_id, 'gap')
    by_id = {g['id']: g for g in gaps}
    assert by_id[g1['id']]['status'] == 'fixed'            # g1 已修复
    assert json.loads(by_id[g1['id']]['content']).get('resolution_note')
    assert by_id[g2['id']]['status'] == 'confirmed'         # g2 未被改动
    # 新问题追加（3 张卡片）
    assert len(gaps) == 3
    assert any('缺少超时场景' in g['description'] for g in gaps)


# ══════════════════════════════════════════════════════════
# 5. 提取正文自动写 content（#25）
# ══════════════════════════════════════════════════════════


async def test_extract_writes_doc_content(client, ctx, monkeypatch):
    """飞书链接提取成功 → 正文自动写入 requirement.content。"""
    from app.services import feishu_client
    from unittest.mock import AsyncMock

    async def fake_fetch(url, user_id=0):
        return {'extracted': True, 'text_content': '提取后的需求文档正文', 'title': '',
                'doc_type': 'docx', 'error_kind': '', 'error_message': ''}
    monkeypatch.setattr(feishu_client, 'fetch_doc', fake_fetch)

    resp = await client.post('/api/requirements', json={
        'project_id': ctx['project_id'], 'branch_id': ctx['branch_id'], 'title': '需求',
    }, headers=_auth(ctx['member']))
    req_id = resp.json()['data']['id']

    resp = await client.post(f'/api/requirements/{req_id}/sources', json={
        'type': 'lark_link', 'link': 'https://x.feishu.cn/docx/DocX',
    }, headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    assert resp.json()['data']['extracted'] is True

    from app.db.database import session_ctx
    from app.db.models import Requirement
    async with session_ctx() as session:
        r = await session.get(Requirement, req_id)
        assert '提取后的需求文档正文' in (r.content or '')
