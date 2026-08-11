"""Ticket #15 冒烟测试 — LLM 配置 + 智能体三步流程 + AI 评分 + 绑定（真实 LLM + 真实飞书提取）。

针对 8040 端口运行中的后端。LLM 用 opencode.ai 兼容端点（与 title_generator 同源）。
"""
import json
import time
import urllib.request

BASE = 'http://127.0.0.1:8040'
TEST_DOC = 'https://asiainfo.feishu.cn/wiki/FxbUwrLgOiFKUVkL72Wc49hJnAf'

# 与 title_generator.py 同源的真实 LLM 配置
LLM_CFG = {
    'provider': 'deepseek',
    'api_base': 'https://opencode.ai/zen/go/v1',
    'text_model': 'deepseek-v4-flash',
    'vision_model': '',
    'api_key': 'sk-AcQ9AjnmqcJ8GLt49DmrNlrUvRQFcv55eoXEiHxFuOiQzxDAy1NT0SwwRu7zt89f',
}


def req(method, path, data=None, token=None, timeout=180):
    headers = {}
    body = None
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(f'{BASE}{path}', data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {'http_error': e.code, 'body': e.read()[:300]}


def check(step, cond, detail=''):
    print(('PASS' if cond else 'FAIL') + f'  {step} {detail}')
    if not cond:
        raise SystemExit(f'冒烟测试失败: {step}')


# 1. 注册 + 登录
uname = f'smoke_agent_{int(time.time())}'
reg = req('POST', '/api/auth/register', {'username': uname, 'nickname': '智能体冒烟', 'password': 'Smoke1234'})
check('注册', reg.get('code') == 200, str(reg)[:120])
login = req('POST', '/api/auth/login', {'username': uname, 'password': 'Smoke1234'})
check('登录', login.get('code') == 200, str(login)[:120])
token = login['data']['token']

# 2. LLM 配置保存 + 读取（不泄 key）
cfg = req('PUT', '/api/settings/llm', LLM_CFG, token)
check('保存LLM配置', cfg.get('code') == 200, str(cfg)[:150])
st = req('GET', '/api/settings/llm', None, token)
check('读取配置不泄key', st.get('code') == 200 and st['data']['has_key']
      and 'sk-AcQ9' not in json.dumps(st['data']), str(st['data'])[:200])

# 3. 建项目/分支/需求 + 真实飞书来源
proj = req('POST', '/api/projects', {'name': f'冒烟智能体项目{uname}', 'source_type': 'upload'}, token)
check('创建项目', proj.get('code') == 200, str(proj)[:150])
project_id = proj['data']['id']
branches = req('GET', f'/api/projects/{project_id}/branches', None, token)
branch_id = branches['data'][0]['id']
cr = req('POST', '/api/requirements', {'project_id': project_id, 'branch_id': branch_id, 'title': '冒烟需求：智能体三步'}, token)
check('创建需求', cr.get('code') == 200, str(cr)[:150])
req_id = cr['data']['id']
src = req('POST', f'/api/requirements/{req_id}/sources', {'type': 'lark_link', 'link': TEST_DOC}, token)
check('飞书来源提取', src.get('code') == 200 and src['data'].get('extracted') is True, str(src)[:150])

# 4. meta 生成
meta = req('POST', f'/api/requirements/{req_id}/meta/generate', {}, token)
check('元信息生成', meta.get('code') == 200 and meta['data'].get('title'), str(meta)[:250])

# 5. 评审（真实 LLM）
review = req('POST', f'/api/requirements/{req_id}/review', {}, token)
check('评审完成', review.get('code') == 200, str(review)[:250])
check('评审含评分', 0 <= review['data'].get('score', -1) <= 100, f"score={review['data'].get('score')}")
print(f"  评审结论: {review['data'].get('conclusion', '')[:120]}")
print(f"  评分: {review['data'].get('score')}/100 | {review['data'].get('score_reason', '')[:80]}")
check('评审低分标记', isinstance(review['data'].get('low_score'), bool), '')

# 6. Story 拆解
stories = req('POST', f'/api/requirements/{req_id}/stories/generate', {}, token)
check('Story拆解', stories.get('code') == 200 and len(stories['data'].get('stories', [])) >= 1, str(stories)[:250])
print(f"  Story数量: {len(stories['data'].get('stories', []))} | 评分: {stories['data'].get('score')}")
for s in stories['data'].get('stories', [])[:3]:
    print(f"    - {s.get('title', '')}")

# 7. 用例生成
cases = req('POST', f'/api/requirements/{req_id}/cases/generate', {}, token)
check('用例生成', cases.get('code') == 200 and len(cases['data'].get('cases', [])) >= 1, str(cases)[:250])
print(f"  用例数量: {len(cases['data'].get('cases', []))} | 评分: {cases['data'].get('score')}")
case_id = cases['data']['cases'][0]['id']
check('用例含id', case_id > 0, '')

# 8. 单用例重生成
regen = req('POST', f'/api/requirements/{req_id}/cases/{case_id}/regenerate', {}, token)
check('单用例重生成', regen.get('code') == 200 and regen['data'].get('title'), str(regen)[:200])

# 9. 状态机 + 完成
st_req = req('GET', f'/api/requirements/{req_id}', None, token)
check('状态=用例生成', st_req['data']['status'] == 'cases_generated', st_req['data']['status'])
done = req('POST', f'/api/requirements/{req_id}/complete', {}, token)
check('标记完成', done.get('code') == 200, '')
st_req = req('GET', f'/api/requirements/{req_id}', None, token)
check('状态=完成', st_req['data']['status'] == 'done', st_req['data']['status'])

# 10. 清理
delr = req('DELETE', f'/api/requirements/{req_id}', None, token)
check('删除需求', delr.get('code') == 200, str(delr)[:120])

print('\nTicket #15 冒烟测试通过 ✔')
