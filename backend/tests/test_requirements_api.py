"""需求管理 API 契约测试 — 覆盖 ticket #13 AC。

覆盖：
- 需求 CRUD（项目+分支隔离、非成员 403）
- 级联删除（来源/评审/Story/用例/绑定 + 磁盘文件目录）
- 来源：链接记录、文件上传落盘 + 签名 URL 下载、类型白名单
- 各环节只读列表接口
"""
import os

import pytest
from sqlalchemy import select

from app.db.database import session_ctx
from app.db.models import (
    Requirement, RequirementSource, RequirementReview, Story,
    GeneratedCase, CaseBinding, LLMSettings, UserLarkBinding,
)


def _auth(user: dict) -> dict:
    return {'Authorization': f'Bearer {user["token"]}'}


async def _create_project_ctx(creator_id: int, *member_ids: int) -> int:
    """建一个新项目并把给定用户加为成员，返回 project_id。"""
    from app.db.database import session_ctx
    from app.db.models import Project, ProjectMember

    async with session_ctx() as session:
        p = Project(name=f'隔离项目{creator_id}', source_type='upload', creator_id=creator_id)
        session.add(p)
        await session.commit()
        await session.refresh(p)
        for uid in (creator_id, *member_ids):
            session.add(ProjectMember(project_id=p.id, user_id=uid))
        await session.commit()
        return p.id


async def _ensure_branch_ctx(project_id: int) -> int:
    from app.db.database import session_ctx
    from app.db.models import Branch

    async with session_ctx() as session:
        result = await session.execute(select(Branch).where(Branch.project_id == project_id).limit(1))
        b = result.scalar_one_or_none()
        if b is None:
            b = Branch(project_id=project_id, name='main', is_default=True)
            session.add(b)
            await session.commit()
            await session.refresh(b)
        return b.id


async def _create_req(client, user, project_id, branch_id, title='测试需求') -> int:
    resp = await client.post(
        '/api/requirements',
        json={'project_id': project_id, 'branch_id': branch_id, 'title': title, 'priority': 'P2'},
        headers=_auth(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 200, body
    return body['data']['id']


async def _insert_children(req_id: int) -> None:
    """直接向子表插入评审/Story/用例/绑定，验证级联删除契约。"""
    async with session_ctx() as session:
        review = RequirementReview(
            requirement_id=req_id, conclusion='通过', risks='[]', issues='[]',
            score=85, score_reason='ok', created_by=1,
        )
        story = Story(
            requirement_id=req_id, title='Story1', description='desc',
            acceptance_criteria='["c1"]', sort_order=1, score=80, score_reason='ok',
        )
        case = GeneratedCase(
            requirement_id=req_id, story_id=story.id, title='Case1',
            preconditions='pre', steps='[{"s":"1"}]', expected='exp',
            score=78, score_reason='ok',
        )
        session.add_all([review, story, case])
        await session.commit()
        await session.refresh(case)
        session.add(CaseBinding(
            generated_case_id=case.id, uid='auto_case_1',
            project_id=1, branch_id=1,
        ))
        await session.commit()


async def _count_rows(session, model, **filters) -> int:
    result = await session.execute(select(model.id).where(*[getattr(model, k) == v for k, v in filters.items()]))
    return len(result.scalars().all())


# ══════════════════════════════════════════════
# CRUD
# ══════════════════════════════════════════════


async def test_create_get_update_delete_requirement(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'], title='订单查询需求')

    # GET detail
    resp = await client.get(f'/api/requirements/{req_id}', headers=_auth(c['member']))
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['id'] == req_id
    assert data['title'] == '订单查询需求'
    assert data['status'] == 'pending_review'
    assert data['creator_name'] == '成员'
    assert data['branch_name'] == 'main'
    assert data['project_name'] == '测试项目'
    assert data['source_count'] == 0

    # PUT update
    resp = await client.put(
        f'/api/requirements/{req_id}',
        json={'title': '订单查询需求v2', 'priority': 'P1', 'status': 'review_passed'},
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 200
    resp = await client.get(f'/api/requirements/{req_id}', headers=_auth(c['member']))
    data = resp.json()['data']
    assert data['title'] == '订单查询需求v2'
    assert data['priority'] == 'P1'
    assert data['status'] == 'review_passed'

    # DELETE
    resp = await client.delete(f'/api/requirements/{req_id}', headers=_auth(c['member']))
    assert resp.json()['code'] == 200
    resp = await client.get(f'/api/requirements/{req_id}', headers=_auth(c['member']))
    assert resp.json()['code'] == 404


async def test_create_requirement_requires_title(client, ctx):
    resp = await client.post(
        '/api/requirements',
        json={'project_id': ctx['project_id'], 'branch_id': ctx['branch_id'], 'title': '   '},
        headers=_auth(ctx['member']),
    )
    assert resp.json()['code'] == 400


# ══════════════════════════════════════════════
# 隔离：项目 + 分支
# ══════════════════════════════════════════════


async def test_requirement_isolation_by_project(client, ctx):
    c = ctx
    # 第二个成员所属项目（无需求）
    project2 = await _create_project_ctx(c['member']['id'], c['other']['id'])
    branch2 = await _ensure_branch_ctx(project2)

    await _create_req(client, c['member'], c['project_id'], c['branch_id'])

    # 成员在另一个项目下看不到该需求
    resp = await client.get(
        f'/api/requirements?project_id={project2}&branch_id={branch2}',
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 200
    assert resp.json()['data'] == []

    resp = await client.get(
        f"/api/requirements?project_id={c['project_id']}&branch_id={c['branch_id']}",
        headers=_auth(c['member']),
    )
    assert len(resp.json()['data']) == 1


async def test_requirement_isolation_by_branch(client, ctx):
    c = ctx
    await _create_req(client, c['member'], c['project_id'], c['branch_id'])

    # 同项目不同分支（不存在的分支 id）看不到
    resp = await client.get(
        f'/api/requirements?project_id={c["project_id"]}&branch_id=99999',
        headers=_auth(c['member']),
    )
    assert resp.json()['data'] == []


# ══════════════════════════════════════════════
# 权限：非成员 403
# ══════════════════════════════════════════════


async def test_non_member_forbidden(client, ctx):
    c = ctx
    outsider = c['outsider']

    # list
    resp = await client.get(
        f"/api/requirements?project_id={c['project_id']}&branch_id={c['branch_id']}",
        headers=_auth(outsider),
    )
    assert resp.json()['code'] == 403

    # create
    resp = await client.post(
        '/api/requirements',
        json={'project_id': c['project_id'], 'branch_id': c['branch_id'], 'title': 'x'},
        headers=_auth(outsider),
    )
    assert resp.json()['code'] == 403

    # get / update / delete on an existing requirement
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])
    resp = await client.get(f'/api/requirements/{req_id}', headers=_auth(outsider))
    assert resp.json()['code'] == 403
    resp = await client.put(f'/api/requirements/{req_id}', json={'title': 'y'}, headers=_auth(outsider))
    assert resp.json()['code'] == 403
    resp = await client.delete(f'/api/requirements/{req_id}', headers=_auth(outsider))
    assert resp.json()['code'] == 403


# ══════════════════════════════════════════════
# 来源：链接 / 文件上传 / 签名下载
# ══════════════════════════════════════════════


async def test_add_and_list_link_source(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])

    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/xxx'},
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 200

    resp = await client.get(f'/api/requirements/{req_id}/sources', headers=_auth(c['member']))
    sources = resp.json()['data']
    assert len(sources) == 1
    assert sources[0]['type'] == 'lark_link'
    assert sources[0]['link'].startswith('https://asiainfo.feishu.cn')
    assert sources[0]['extracted'] is False
    assert sources[0]['created_by_name'] == '成员'

    # 空链接 400
    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': '   '},
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 400


async def test_upload_download_and_delete_file_source(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])

    # upload
    resp = await client.post(
        f'/api/requirements/{req_id}/sources/upload',
        files={'file': ('需求文档.md', '# 需求\n\n- 支持查询订单'.encode('utf-8'), 'text/markdown')},
        headers=_auth(c['member']),
    )
    assert resp.status_code == 200
    source_id = resp.json()['data']['id']

    # list → 文件来源带签名下载 URL
    resp = await client.get(f'/api/requirements/{req_id}/sources', headers=_auth(c['member']))
    sources = resp.json()['data']
    assert len(sources) == 1
    assert sources[0]['type'] == 'file'
    assert sources[0]['filename'] == '需求文档.md'
    assert sources[0]['download_url'].startswith(f'/api/requirements/sources/{source_id}/download')

    # download via signed URL
    resp = await client.get(sources[0]['download_url'])
    assert resp.status_code == 200
    assert resp.content == '# 需求\n\n- 支持查询订单'.encode('utf-8')

    # delete source → 文件从磁盘移除
    resp = await client.delete(f'/api/requirements/sources/{source_id}', headers=_auth(c['member']))
    assert resp.json()['code'] == 200
    resp = await client.get(f'/api/requirements/{req_id}/sources', headers=_auth(c['member']))
    assert resp.json()['data'] == []

    # 落盘目录应已被清理（源文件删除）
    from app.config import PROJECTS_DATA_DIR
    req_dir = PROJECTS_DATA_DIR / 'requirements' / str(req_id)
    assert not (req_dir / '需求文档.md').exists()


async def test_upload_unsupported_extension(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])
    resp = await client.post(
        f'/api/requirements/{req_id}/sources/upload',
        files={'file': ('virus.exe', b'MZ', 'application/octet-stream')},
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 400


async def test_source_requires_membership(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])
    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/yyy'},
        headers=_auth(c['outsider']),
    )
    assert resp.json()['code'] == 403


# ══════════════════════════════════════════════
# 级联删除
# ══════════════════════════════════════════════


async def test_cascade_delete_cleans_children_and_files(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])

    # 上传文件 + 添加链接
    resp = await client.post(
        f'/api/requirements/{req_id}/sources/upload',
        files={'file': ('需求.txt', b'content', 'text/plain')},
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 200
    resp = await client.post(
        f'/api/requirements/{req_id}/sources',
        json={'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/zzz'},
        headers=_auth(c['member']),
    )
    assert resp.json()['code'] == 200

    # 直插子表（评审/Story/用例/绑定）
    await _insert_children(req_id)

    async with session_ctx() as session:
        assert await _count_rows(session, RequirementSource, requirement_id=req_id) == 2
        assert await _count_rows(session, RequirementReview, requirement_id=req_id) == 1
        assert await _count_rows(session, Story, requirement_id=req_id) == 1
        assert await _count_rows(session, GeneratedCase, requirement_id=req_id) == 1

    # 删除需求
    resp = await client.delete(f'/api/requirements/{req_id}', headers=_auth(c['member']))
    assert resp.json()['code'] == 200

    # 需求与全部子表清空
    async with session_ctx() as session:
        assert await _count_rows(session, Requirement, id=req_id) == 0
        assert await _count_rows(session, RequirementSource, requirement_id=req_id) == 0
        assert await _count_rows(session, RequirementReview, requirement_id=req_id) == 0
        assert await _count_rows(session, Story, requirement_id=req_id) == 0
        assert await _count_rows(session, GeneratedCase, requirement_id=req_id) == 0
        # 用例绑定（用例 id 级联）也应清空
        result = await session.execute(select(CaseBinding.id))
        assert len(result.scalars().all()) == 0

    # 磁盘目录整体清理
    from app.config import PROJECTS_DATA_DIR
    assert not (PROJECTS_DATA_DIR / 'requirements' / str(req_id)).exists()


# ══════════════════════════════════════════════
# 只读环节列表
# ══════════════════════════════════════════════


async def test_readonly_stage_lists(client, ctx):
    c = ctx
    req_id = await _create_req(client, c['member'], c['project_id'], c['branch_id'])

    for path in ('reviews', 'stories', 'cases'):
        resp = await client.get(f'/api/requirements/{req_id}/{path}', headers=_auth(c['member']))
        assert resp.json()['code'] == 200
        assert resp.json()['data'] == []

    # 非成员 403
    resp = await client.get(f'/api/requirements/{req_id}/reviews', headers=_auth(c['outsider']))
    assert resp.json()['code'] == 403


# ══════════════════════════════════════════════
# LLM 设置与飞书绑定表（后续 ticket 使用，先验证可写读）
# ══════════════════════════════════════════════


async def test_llm_settings_and_lark_binding_crud(client, ctx):
    from app.db import crud

    await crud.save_llm_settings(
        {'provider': 'deepseek', 'api_base': 'https://api.deepseek.com', 'text_model': 'deepseek-chat'},
        user_id=ctx['member']['id'],
    )
    settings = await crud.get_llm_settings()
    assert settings['provider'] == 'deepseek'
    assert settings['text_model'] == 'deepseek-chat'

    await crud.upsert_user_lark_binding(ctx['member']['id'], 'cli_test', 'ou_123')
    binding = await crud.get_user_lark_binding(ctx['member']['id'])
    assert binding['lark_open_id'] == 'ou_123'
