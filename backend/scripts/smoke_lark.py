"""Ticket #14 冒烟测试 — 飞书授权状态 + 链接正文提取（真实 lark-cli）。

针对 8040 端口运行中的后端；使用用户提供的飞书 wiki 链接验证真实提取。
"""
import json
import time
import urllib.request

BASE = 'http://127.0.0.1:8040'
TEST_DOC = 'https://asiainfo.feishu.cn/wiki/FxbUwrLgOiFKUVkL72Wc49hJnAf'


def req(method, path, data=None, token=None):
    headers = {}
    body = None
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(f'{BASE}{path}', data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            raw = resp.read()
            try:
                return json.loads(raw.decode('utf-8'))
            except Exception:
                return {'raw': raw[:200]}
    except urllib.error.HTTPError as e:
        return {'http_error': e.code, 'body': e.read()[:300]}


def check(step, cond, detail=''):
    print(('PASS' if cond else 'FAIL') + f'  {step} {detail}')
    if not cond:
        raise SystemExit(f'冒烟测试失败: {step}')


# 1. 注册 + 登录
uname = f'smoke_lark_{int(time.time())}'
reg = req('POST', '/api/auth/register', {'username': uname, 'nickname': '飞书冒烟', 'password': 'Smoke1234'})
check('注册', reg.get('code') == 200, str(reg)[:120])
login = req('POST', '/api/auth/login', {'username': uname, 'password': 'Smoke1234'})
check('登录', login.get('code') == 200, str(login)[:120])
token = login['data']['token']

# 2. 飞书授权状态（新用户未绑定）
st = req('GET', '/api/settings/lark/status', None, token)
check('状态接口', st.get('code') == 200, str(st)[:200])
check('新用户未绑定', st['data'].get('bound') is False, str(st['data'])[:150])

# 3. 创建项目/分支/需求
proj = req('POST', '/api/projects', {'name': f'冒烟飞书项目{uname}', 'source_type': 'upload'}, token)
check('创建项目', proj.get('code') == 200, str(proj)[:150])
project_id = proj['data']['id']
branches = req('GET', f'/api/projects/{project_id}/branches', None, token)
branch_id = branches['data'][0]['id']
cr = req('POST', '/api/requirements', {'project_id': project_id, 'branch_id': branch_id, 'title': '冒烟需求：飞书提取'}, token)
check('创建需求', cr.get('code') == 200, str(cr)[:150])
req_id = cr['data']['id']

# 4. 真实飞书链接提取
link = req('POST', f'/api/requirements/{req_id}/sources', {'type': 'lark_link', 'link': TEST_DOC}, token)
check('真实提取', link.get('code') == 200 and link['data'].get('extracted') is True, str(link)[:200])
extract_error = link['data'].get('extract_error', '')
check('提取无错误', extract_error == '', extract_error[:200])

sources = req('GET', f'/api/requirements/{req_id}/sources', None, token)
src = sources['data'][0]
check('正文已落库', len(src.get('text_content', '')) > 100, f'text_content长度={len(src.get("text_content", ""))}')
check('正文含标题', '工具库 PRD' in src.get('text_content', '') or 'PRD' in src.get('text_content', ''), src.get('text_content', '')[:80])

# 5. 无效文档链接（降级）
bad = req('POST', f'/api/requirements/{req_id}/sources', {'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/INVALID_DOC_ID'}, token)
check('无效文档降级', bad.get('code') == 200 and bad['data'].get('extracted') is False, str(bad)[:200])
check('无效文档可读原因', len(bad['data'].get('extract_error', '')) > 0, bad['data'].get('extract_error', '')[:150])

# 6. 非文档链接（降级）
web = req('POST', f'/api/requirements/{req_id}/sources', {'type': 'lark_link', 'link': 'https://www.baidu.com'}, token)
check('非文档链接降级', web.get('code') == 200 and web['data'].get('extracted') is False, str(web)[:200])
check('非文档可读原因', '飞书文档' in web['data'].get('extract_error', ''), web['data'].get('extract_error', '')[:150])

# 7. 重试提取：对无效文档来源重试（仍失败但接口正常、原因可读）
bad_src_id = bad['data']['id']
retry = req('POST', f'/api/requirements/{req_id}/sources/{bad_src_id}/extract', None, token)
check('重试提取接口', retry.get('code') == 200 and retry['data'].get('extracted') is False, str(retry)[:200])
check('重试返回可读原因', len(retry['data'].get('extract_error', '')) > 0, retry['data'].get('extract_error', '')[:150])

# 8. 清理
delr = req('DELETE', f'/api/requirements/{req_id}', None, token)
check('删除需求', delr.get('code') == 200, str(delr)[:150])

print('\nTicket #14 冒烟测试通过 ✔')
