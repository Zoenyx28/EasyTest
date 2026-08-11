"""#22 测试设计工作台冒烟 — 真实 DB 上验证 /layers 一屏聚合 + 工作台关键动作。"""
import asyncio
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend 根目录

BASE = 'http://127.0.0.1:8040'

# 环境可能已配置 LLM（真实调用会等待较久），错误路径验证前临时清空 api_key
from sqlalchemy import text as sa_text  # noqa: E402
from app.db.database import engine  # noqa: E402


async def _read_llm_key() -> str:
    async with engine.begin() as conn:
        res = await conn.exec_driver_sql('SELECT api_key FROM llm_settings LIMIT 1')
        row = res.first()
        return (row[0] if row else '') or ''


async def _write_llm_key(value: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(sa_text('UPDATE llm_settings SET api_key = :v'), {'v': value})


def req(method, path, data=None, token=None):
    url = BASE + path
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


async def run():
    # 注册新用户（避免依赖既有账号）
    uname = f'wbsmoke{int(time.time())}'
    try:
        auth = req('POST', '/api/auth/register', {'username': uname, 'password': 'wbsmoke123', 'nickname': '冒烟'})
    except Exception as e:
        print('[FATAL] register failed:', e)
        raise
    token = auth['data']['token']
    print('[OK] auth user:', uname)

    # 取项目（无则新建）
    projects = req('GET', '/api/projects', token=token)['data']
    if projects:
        pid = projects[0]['id']
    else:
        p = req('POST', '/api/projects',
                {'name': f'冒烟项目{int(time.time())}', 'source_type': 'upload'}, token=token)['data']
        pid = p['id']
    print('[OK] projects, use pid=', pid)

    # 取分支
    branches = req('GET', f'/api/projects/{pid}/branches', token=token)['data'] if pid else []
    bid = branches[0]['id'] if branches else None
    print('[OK] branches:', len(branches), 'use bid=', bid)

    # 建需求
    r = req('POST', '/api/requirements', {'project_id': pid, 'branch_id': bid, 'title': '工作台冒烟-订单退款'},
            token=token)['data']
    rid = r['id']
    print('[OK] created requirement', rid)

    # 工作台一屏聚合
    layers = req('GET', f'/api/requirements/{rid}/layers', token=token)['data']
    keys = ['requirement', 'analysis', 'information_gaps', 'test_points', 'test_point_review',
            'test_scenarios', 'scenario_review', 'case_review', 'strategy', 'coverage', 'test_gaps']
    missing = [k for k in keys if k not in layers]
    assert not missing, f'/layers 缺少 {missing}'
    print('[OK] /layers 一屏聚合含全部', len(keys), '个键')

    # 各层数据端点
    for path in [f'/api/requirements/{rid}/stories', f'/api/requirements/{rid}/cases',
                 f'/api/requirements/{rid}/ai-tasks', f'/api/requirements/{rid}/test-gaps',
                 f'/api/requirements/{rid}/review-audits']:
        raw = req('GET', path, token=token)
        data = raw['data']
        print('[OK]', path, '→', None if data is None else len(data), '条', raw.get('msg', ''))

    # 未配置 LLM 时 AI 动作应返回业务 400 且任务落 FAILED（错误路径，临时清空 api_key 验证）
    old_key = await _read_llm_key()
    try:
        await _write_llm_key('')
        body = req('POST', f'/api/requirements/{rid}/analysis/analyze', {}, token=token)
        assert body['code'] == 400, body
        assert 'LLM' in body.get('msg', ''), body
        print('[OK] analyze 未配置 LLM → 业务 400:', body['msg'])
    finally:
        await _write_llm_key(old_key)
    tasks = req('GET', f'/api/requirements/{rid}/ai-tasks', token=token)['data']
    failed = [t for t in tasks if t['status'] == 'FAILED']
    print('[OK] ai-tasks:', len(tasks), '条, FAILED:', len(failed))
    assert failed and failed[0]['error'], '未配置 LLM 场景应有 FAILED 任务及错误信息'
    print('[OK] FAILED 任务 error:', failed[0]['error'][:80])

    # 清理
    req('DELETE', f'/api/requirements/{rid}', token=token)
    print('[OK] 清理需求', rid)
    await engine.dispose()


def main():
    asyncio.run(run())


if __name__ == '__main__':
    main()
