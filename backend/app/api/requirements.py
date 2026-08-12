"""需求管理 API 路由 — 需求 CRUD、来源（飞书链接/离线文件上传）、签名下载、
智能体流程（元信息/评审/拆 Story/生成用例 + AI 评分 + 绑定自动化用例）。

按 (project_id, branch_id) 隔离；仅项目成员可读写。
状态机：pending_review → review_passed → story_confirmed → cases_generated → done。
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Body, Query
from pydantic import BaseModel

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.config import PROJECTS_DATA_DIR
from app.db import crud
from app.models.schemas import (
    RequirementCreate,
    RequirementUpdate,
    RequirementSourceAdd,
    CaseBindingCreate,
)
from app.services import lark_cli, llm_client, requirement_agent
from app.services.file_signer import build_signed_url, verify_signature

router = APIRouter(prefix='/api/requirements', tags=['需求管理'])

# 允许上传的需求来源文件类型
ALLOWED_EXTENSIONS = {
    '.txt', '.json', '.md', '.doc', '.docx', '.pdf',
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
}


# ── Helper: 签名下载 ──


def _source_download_url(source_id: int, user_id: int) -> str:
    """生成需求来源文件的短时效签名 URL。"""
    return build_signed_url(
        f'/api/requirements/sources/{source_id}/download',
        f'req_src:{source_id}',
        user_id,
    )


def _resolve_signed_user(request: Request, resource: str) -> int | None:
    """从请求 query 中解析签名 URL，返回签名绑定的 user_id；无效返回 None。"""
    params = request.query_params
    uid = params.get('uid')
    if not uid:
        return None
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        return None
    if not verify_signature(resource, uid_int, params.get('expires'), params.get('sig')):
        return None
    return uid_int


# ── Helper: 需求目录 ──


def _req_dir(req_id: int) -> Path:
    """需求来源文件存储目录。"""
    return PROJECTS_DATA_DIR / 'requirements' / str(req_id)


# ── Helper: 详情富化 ──


async def _enrich_requirement(req: dict, user_id: int = 0) -> dict:
    """补充创建人/分支/项目名与各环节计数、最新评审。"""
    req_id = req['id']
    project_id = req['project_id']
    branch_id = req['branch_id']

    creator_name = ''
    if req.get('created_by'):
        try:
            user = await crud.get_user_by_id(req['created_by'])
            if user:
                creator_name = user.get('nickname', '') or user.get('username', '')
        except Exception:
            pass

    branch_name = ''
    try:
        branches = await crud.list_branches(project_id)
        for b in branches:
            if b['id'] == branch_id:
                branch_name = b['name']
                break
    except Exception:
        pass

    project_name = ''
    try:
        project = await crud.get_project(project_id)
        if project:
            project_name = project.get('name', '')
    except Exception:
        pass

    return {
        **req,
        'creator_name': creator_name,
        'branch_name': branch_name,
        'project_name': project_name,
        'source_count': await crud.count_requirement_sources(req_id),
        'review_count': await crud.count_requirement_reviews(req_id),
        'story_count': await crud.count_requirement_stories(req_id),
        'case_count': await crud.count_requirement_cases(req_id),
        'latest_review': await crud.get_latest_review(req_id),
    }


async def _enrich_source(src: dict, user_id: int = 0) -> dict:
    """补充来源上传者名称；文件来源附带签名下载 URL。"""
    created_by_name = ''
    if src.get('created_by'):
        try:
            user = await crud.get_user_by_id(src['created_by'])
            if user:
                created_by_name = user.get('nickname', '') or user.get('username', '')
        except Exception:
            pass

    result = {
        **src,
        'created_by_name': created_by_name,
        'download_url': '',
    }
    if src.get('type') == 'file' and src.get('id'):
        result['download_url'] = _source_download_url(src['id'], user_id)
    return result


# ══════════════════════════════════════════════
# Requirement Routes
# ══════════════════════════════════════════════


@router.get('')
async def list_requirements(request: Request, project_id: int, branch_id: int,
                            status: str = Query(default='')):
    """需求列表（按项目+版本隔离 + 可选状态筛选；仅项目成员可见）"""
    user = await get_current_user(request)
    if not await crud.is_project_member(project_id, user['id']):
        return fail(403, '无权访问该项目')
    items = await crud.list_requirements(project_id, branch_id, status=status)
    enriched = []
    for r in items:
        enriched.append(await _enrich_requirement(r, user['id']))
    return ok(enriched)


@router.post('')
async def create_requirement(request: Request, data: RequirementCreate = Body(...)):
    """新建需求（仅项目成员）"""
    user = await get_current_user(request)
    if not data.title or not data.title.strip():
        return fail(400, '需求标题不能为空')
    if not await crud.is_project_member(data.project_id, user['id']):
        return fail(403, '无权访问该项目')
    req_id = await crud.create_requirement(data, user['id'])
    return ok({'id': req_id}, msg='需求创建成功')


@router.get('/{req_id}')
async def get_requirement(request: Request, req_id: int):
    """需求详情"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    return ok(await _enrich_requirement(req, user['id']))


@router.put('/{req_id}')
async def update_requirement(request: Request, req_id: int, data: RequirementUpdate = Body(...)):
    """更新需求（标题/摘要/优先级/状态）"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')

    fields = {}
    if data.title.strip():
        fields['title'] = data.title
    if data.summary:
        fields['summary'] = data.summary
    if data.priority:
        fields['priority'] = data.priority
    if data.status:
        fields['status'] = data.status
    if fields:
        await crud.update_requirement(req_id, fields)
    return ok(None, msg='需求更新成功')


@router.delete('/{req_id}')
async def delete_requirement(request: Request, req_id: int):
    """删除需求 — 级联清理来源/评审/Story/用例/绑定及磁盘文件目录"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')

    await crud.delete_requirement(req_id)
    # 清理来源文件磁盘目录
    req_dir = _req_dir(req_id)
    if req_dir.exists():
        shutil.rmtree(req_dir, ignore_errors=True)
    return ok(None, msg='需求删除成功')


# ══════════════════════════════════════════════
# Source Routes
# ══════════════════════════════════════════════


@router.get('/{req_id}/sources')
async def list_sources(request: Request, req_id: int):
    """需求来源列表"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    sources = await crud.list_requirement_sources(req_id)
    enriched = []
    for s in sources:
        enriched.append(await _enrich_source(s, user['id']))
    return ok(enriched)


@router.post('/{req_id}/sources')
async def add_link_source(request: Request, req_id: int, data: RequirementSourceAdd = Body(...)):
    """添加链接来源（飞书文档链接等）；以当前用户身份提取正文（失败降级为仅保存链接）"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    if not data.link.strip():
        return fail(400, '链接不能为空')

    source_type = data.type if data.type in ('lark_link', 'file') else 'lark_link'
    link = data.link.strip()

    # 飞书链接：以当前用户身份同步提取正文（失败降级，不阻断添加来源）
    extracted = False
    text_content = data.text_content or ''
    extract_error = ''
    if source_type == 'lark_link':
        result = await lark_cli.fetch_doc(link)
        if result.get('extracted'):
            extracted = True
            text_content = result['text_content']
        else:
            extract_error = result.get('error_message', '') or '飞书文档读取失败'

    source_id = await crud.create_requirement_source(
        req_id,
        type=source_type,
        link=link,
        text_content=text_content,
        extracted=extracted,
        extract_error=extract_error,
        user_id=user['id'],
    )
    return ok({
        'id': source_id,
        'extracted': extracted,
        'extract_error': extract_error,
    }, msg='来源添加成功' if not extract_error else '来源已添加，正文提取失败')


@router.post('/{req_id}/sources/{source_id}/extract')
async def re_extract_source(request: Request, req_id: int, source_id: int):
    """重新提取飞书链接正文（授权后重试；仅 lark_link 来源）"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    src = await crud.get_requirement_source(source_id)
    if src is None or src['requirement_id'] != req_id:
        return fail(404, '来源不存在')
    if src['type'] != 'lark_link' or not src.get('link'):
        return fail(400, '仅飞书链接来源支持提取')

    result = await lark_cli.fetch_doc(src['link'])
    extracted = bool(result.get('extracted'))
    await crud.update_requirement_source(source_id, {
        'text_content': result.get('text_content', '') if extracted else '',
        'extracted': extracted,
        'extract_error': '' if extracted else result.get('error_message', '飞书文档读取失败'),
    })
    return ok({
        'id': source_id,
        'extracted': extracted,
        'extract_error': '' if extracted else result.get('error_message', ''),
    }, msg='正文提取成功' if extracted else '正文提取失败')


@router.post('/{req_id}/sources/upload')
async def upload_source_file(request: Request, req_id: int, file: UploadFile = File(...)):
    """上传来源文件（txt/json/md/doc/docx/pdf/图片）落盘并记录"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')

    filename = file.filename or 'unnamed'
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return fail(400, f'不支持的文件类型：{ext or "无扩展名"}')

    content = await file.read()
    if not content:
        return fail(400, '文件内容为空')

    upload_dir = _req_dir(req_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Handle duplicate filenames
    filepath = upload_dir / filename
    base, e = os.path.splitext(filename)
    counter = 1
    while os.path.exists(filepath):
        filename = f'{base}_{counter}{e}'
        filepath = upload_dir / filename
        counter += 1

    with open(filepath, 'wb') as f:
        f.write(content)

    source_id = await crud.create_requirement_source(
        req_id,
        type='file',
        filename=filename,
        filepath=str(filepath),
        file_size=len(content),
        mime_type=file.content_type or 'application/octet-stream',
        user_id=user['id'],
    )
    return ok({'id': source_id}, msg='文件上传成功')


@router.delete('/sources/{source_id}')
async def delete_source(request: Request, source_id: int):
    """删除需求来源（含磁盘文件）"""
    user = await get_current_user(request)
    src = await crud.get_requirement_source(source_id)
    if src is None:
        return fail(404, '来源不存在')
    req = await crud.get_requirement(src['requirement_id'])
    if req is None or not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')

    deleted = await crud.delete_requirement_source(source_id)
    if deleted and deleted.get('filepath'):
        try:
            if os.path.exists(deleted['filepath']):
                os.remove(deleted['filepath'])
        except OSError:
            pass
    return ok(None, msg='来源删除成功')


@router.get('/sources/{source_id}/download')
async def download_source(request: Request, source_id: int):
    """下载来源文件（需携带短时效签名 URL；需求所属项目成员可访问）"""
    from fastapi.responses import FileResponse

    uid = _resolve_signed_user(request, f'req_src:{source_id}')
    if uid is None:
        return fail(403, '无权访问或签名已过期')
    src = await crud.get_requirement_source(source_id)
    if src is None:
        return fail(404, '来源不存在')
    req = await crud.get_requirement(src['requirement_id'])
    if req is None or not await crud.is_project_member(req['project_id'], uid):
        return fail(403, '无权访问')
    filepath = src.get('filepath', '')
    if not filepath or not os.path.exists(filepath):
        return fail(404, '文件不存在')
    return FileResponse(
        filepath,
        filename=src.get('filename', 'download'),
        media_type=src.get('mime_type', 'application/octet-stream'),
    )


# ══════════════════════════════════════════════
# 智能体流程（ticket #15）：元信息 / 评审 / Story / 用例 + AI 评分 + 绑定
# ══════════════════════════════════════════════


async def _member_req(user: dict, req_id: int) -> tuple[dict | None, dict | None]:
    """校验成员身份，返回 (requirement, None) 或 (None, error_response)。"""
    req = await crud.get_requirement(req_id)
    if req is None:
        return None, fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return None, fail(403, '无权访问该项目')
    return req, None


async def _build_llm_client() -> llm_client.LLMClient:
    settings = await crud.get_llm_settings()
    if not settings:
        raise llm_client.LLMConfigError('尚未配置 LLM，请先在「设置」中填写')
    return llm_client.LLMClient(settings)


def _low_score(score: int) -> bool:
    """评分 < 60 标记「建议重新评审」。"""
    return score < 60


class ReviewRequestBody(BaseModel):
    review_comment: str = ''


@router.post('/{req_id}/meta/generate')
async def generate_meta(request: Request, req_id: int):
    """智能体提炼需求标题/摘要/优先级。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    sources = await crud.list_requirement_sources(req_id)
    try:
        client = await _build_llm_client()
        meta = await requirement_agent.generate_requirement_meta(client, req, sources)
    except (llm_client.LLMConfigError, llm_client.LLMCallError) as exc:
        return fail(400, str(exc))
    await crud.update_requirement(req_id, {
        'title': meta.get('title', ''),
        'summary': meta.get('summary', ''),
        'priority': meta.get('priority', 'P2'),
    })
    return ok(meta, msg='需求元信息已生成')


@router.post('/{req_id}/review')
async def review_requirement(request: Request, req_id: int,
                             data: ReviewRequestBody = Body(...)):
    """第一步：需求评审（携带 review_comment 可覆盖重审）。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    sources = await crud.list_requirement_sources(req_id)
    comment = (data.review_comment or '').strip()
    try:
        client = await _build_llm_client()
        result = await requirement_agent.review_requirement(
            client, req, sources, comment)
    except (llm_client.LLMConfigError, llm_client.LLMCallError) as exc:
        return fail(400, str(exc))

    await crud.create_requirement_review(
        req_id, result.get('conclusion', ''), result.get('risks', []),
        result.get('issues', []), result.get('score', 0),
        result.get('score_reason', ''), comment, user['id'],
    )
    # 状态机：评审完成进入 review_passed；若此前已进入后续阶段则回退
    await crud.update_requirement(req_id, {'status': 'review_passed'})
    return ok({**result, 'low_score': _low_score(result.get('score', 0))}, msg='评审完成')


@router.post('/{req_id}/stories/generate')
async def generate_stories(request: Request, req_id: int):
    """第二步：拆解 Story（基于最新评审结论）。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    sources = await crud.list_requirement_sources(req_id)
    latest_review = await crud.get_latest_review(req_id)
    try:
        client = await _build_llm_client()
        result = await requirement_agent.split_stories(
            client, req, sources, latest_review)
    except (llm_client.LLMConfigError, llm_client.LLMCallError) as exc:
        return fail(400, str(exc))

    stories = result.get('stories', [])
    # 环节整体评分内嵌到首条 Story
    score_items = []
    for i, s in enumerate(stories):
        score_items.append({
            **s,
            'score': result.get('score', 0) if i == 0 else 0,
            'score_reason': result.get('score_reason', '') if i == 0 else '',
        })
    await crud.replace_requirement_stories(req_id, score_items)
    await crud.update_requirement(req_id, {'status': 'story_confirmed'})
    saved = await crud.list_requirement_stories(req_id)
    return ok({'stories': saved, 'score': result.get('score', 0),
               'score_reason': result.get('score_reason', ''),
               'low_score': _low_score(result.get('score', 0))}, msg='Story 拆解完成')


@router.post('/{req_id}/cases/generate')
async def generate_cases(request: Request, req_id: int):
    """第三步：基于 Story 批量生成用例（覆盖旧用例，级联清理绑定）。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    stories = await crud.list_requirement_stories(req_id)
    if not stories:
        return fail(400, '请先完成 Story 拆解')
    try:
        client = await _build_llm_client()
        result = await requirement_agent.generate_cases(client, req, stories)
    except (llm_client.LLMConfigError, llm_client.LLMCallError) as exc:
        return fail(400, str(exc))

    cases = result.get('cases', [])
    # story_index → story_id 映射；整体评分内嵌到首条用例
    items = []
    for i, c in enumerate(cases):
        sidx = int(c.get('story_index') or 0)
        story_id = stories[sidx]['id'] if 0 <= sidx < len(stories) else 0
        items.append({
            **c,
            'story_id': story_id,
            'score': result.get('score', 0) if i == 0 else 0,
            'score_reason': result.get('score_reason', '') if i == 0 else '',
        })
    await crud.replace_generated_cases(req_id, items)
    await crud.update_requirement(req_id, {'status': 'cases_generated'})
    saved_cases = await crud.list_requirement_cases(req_id)
    return ok({'cases': saved_cases, 'score': result.get('score', 0),
               'score_reason': result.get('score_reason', ''),
               'low_score': _low_score(result.get('score', 0))}, msg='用例生成完成')


@router.post('/{req_id}/cases/{case_id}/regenerate')
async def regenerate_case(request: Request, req_id: int, case_id: int):
    """单个生成用例重新生成（覆盖该用例）。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    case = await crud.get_generated_case(case_id)
    if case is None or case['requirement_id'] != req_id:
        return fail(404, '用例不存在')
    story = None
    if case.get('story_id'):
        stories = await crud.list_requirement_stories(req_id)
        story = next((s for s in stories if s['id'] == case['story_id']), None)
    try:
        client = await _build_llm_client()
        result = await requirement_agent.regenerate_single_case(
            client, req, story, case)
    except (llm_client.LLMConfigError, llm_client.LLMCallError) as exc:
        return fail(400, str(exc))

    await crud.update_generated_case(case_id, {
        'title': result.get('title', ''),
        'preconditions': result.get('preconditions', ''),
        'steps': json.dumps(result.get('steps', []), ensure_ascii=False),
        'expected': result.get('expected', ''),
        'score': result.get('score', 0),
        'score_reason': result.get('score_reason', ''),
    })
    return ok({**result, 'low_score': _low_score(result.get('score', 0))}, msg='用例已重新生成')


@router.post('/{req_id}/cases/{case_id}/bindings')
async def add_case_binding(request: Request, req_id: int, case_id: int,
                           data: CaseBindingCreate = Body(...)):
    """生成用例绑定自动化用例（0..N）。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    case = await crud.get_generated_case(case_id)
    if case is None or case['requirement_id'] != req_id:
        return fail(404, '用例不存在')
    tcd = await crud.get_test_case_definition(data.uid, data.project_id, data.branch_id)
    if tcd is None:
        return fail(400, '自动化用例不存在（请选择当前项目+分支下的用例）')
    bid = await crud.create_case_binding(case_id, data.uid, data.project_id, data.branch_id)
    if bid == -1:
        return ok({'id': -1}, msg='该自动化用例已绑定')
    return ok({'id': bid, 'case_name': tcd.get('name', '')}, msg='绑定成功')


@router.get('/{req_id}/cases/{case_id}/bindings')
async def list_case_bindings(request: Request, req_id: int, case_id: int):
    """查看生成用例已绑定的自动化用例。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    case = await crud.get_generated_case(case_id)
    if case is None or case['requirement_id'] != req_id:
        return fail(404, '用例不存在')
    return ok(await crud.list_case_bindings(case_id))


@router.delete('/cases/{case_id}/bindings/{binding_id}')
async def delete_case_binding(request: Request, case_id: int, binding_id: int):
    """取消绑定。"""
    user = await get_current_user(request)
    case = await crud.get_generated_case(case_id)
    if case is None:
        return fail(404, '用例不存在')
    req, err = await _member_req(user, case['requirement_id'])
    if err:
        return err
    binding = await crud.get_case_binding(binding_id)
    if binding is None or binding['generated_case_id'] != case_id:
        return fail(404, '绑定不存在')
    await crud.delete_case_binding(binding_id)
    return ok({}, msg='已取消绑定')


@router.post('/{req_id}/complete')
async def complete_requirement(request: Request, req_id: int):
    """需求流程完成（进入 done 状态）。"""
    user = await get_current_user(request)
    req, err = await _member_req(user, req_id)
    if err:
        return err
    await crud.update_requirement(req_id, {'status': 'done'})
    return ok({}, msg='需求已标记完成')


@router.get('/{req_id}/reviews')
async def list_reviews(request: Request, req_id: int):
    """需求评审记录列表"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    reviews = await crud.list_requirement_reviews(req_id)
    enriched = []
    for rev in reviews:
        creator_name = ''
        if rev.get('created_by'):
            try:
                u = await crud.get_user_by_id(rev['created_by'])
                if u:
                    creator_name = u.get('nickname', '') or u.get('username', '')
            except Exception:
                pass
        enriched.append({**rev, 'created_by_name': creator_name})
    return ok(enriched)


@router.get('/{req_id}/stories')
async def list_stories(request: Request, req_id: int):
    """Story 列表"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    return ok(await crud.list_requirement_stories(req_id))


@router.get('/{req_id}/cases')
async def list_cases(request: Request, req_id: int):
    """生成用例列表"""
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return fail(404, '需求不存在')
    if not await crud.is_project_member(req['project_id'], user['id']):
        return fail(403, '无权访问该项目')
    return ok(await crud.list_requirement_cases(req_id))
