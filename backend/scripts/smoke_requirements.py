"""需求管理 API 冒烟测试 — 针对 8040 端口运行中的后端。"""
import json
import time
import urllib.request

BASE = 'http://127.0.0.1:8040'


def req(method, path, data=None, token=None, files=None):
    headers = {}
    body = None
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if files is not None:
        # multipart/form-data
        boundary = '----smoke' + str(int(time.time() * 1000))
        parts = []
        for name, (filename, content, ctype) in files.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f'Content-Type: {ctype}\r\n\r\n'
            )
            parts.append(content.decode('utf-8') if isinstance(content, bytes) else content)
            parts.append('\r\n')
        parts.append(f'--{boundary}--\r\n')
        body = ''.join(parts).encode('utf-8')
        headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
    elif data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(f'{BASE}{path}', data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
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
uname = f'smoke_req_{int(time.time())}'
reg = req('POST', '/api/auth/register', {'username': uname, 'nickname': '冒烟用户', 'password': 'Smoke1234'})
check('注册', reg.get('code') == 200, str(reg)[:120])
login = req('POST', '/api/auth/login', {'username': uname, 'password': 'Smoke1234'})
check('登录', login.get('code') == 200, str(login)[:120])
token = login['data']['token']

# 2. 创建项目（自动建 main 分支 + 加入成员）
proj = req('POST', '/api/projects', {'name': f'冒烟需求项目{uname}', 'source_type': 'upload'}, token)
check('创建项目', proj.get('code') == 200, str(proj)[:150])
project_id = proj['data']['id']
branches = req('GET', f'/api/projects/{project_id}/branches', None, token)
check('获取分支', branches.get('code') == 200 and branches['data'], str(branches)[:150])
branch_id = branches['data'][0]['id']

# 3. 创建需求
cr = req('POST', '/api/requirements', {'project_id': project_id, 'branch_id': branch_id, 'title': '冒烟需求：订单查询', 'priority': 'P1'}, token)
check('创建需求', cr.get('code') == 200, str(cr)[:150])
req_id = cr['data']['id']

# 4. 列表 + 详情
lst = req('GET', f'/api/requirements?project_id={project_id}&branch_id={branch_id}', None, token)
check('列表', lst.get('code') == 200 and len(lst['data']) == 1, str(lst)[:200])
det = req('GET', f'/api/requirements/{req_id}', None, token)
check('详情', det.get('code') == 200 and det['data']['title'].startswith('冒烟需求'), str(det)[:200])

# 5. 添加链接来源 + 文件上传 + 下载
link = req('POST', f'/api/requirements/{req_id}/sources', {'type': 'lark_link', 'link': 'https://asiainfo.feishu.cn/wiki/FxbUwrLgOiFKUVkL72Wc49hJnAf'}, token)
check('添加链接来源', link.get('code') == 200, str(link)[:150])

up = req('POST', f'/api/requirements/{req_id}/sources/upload', token=token,
         files={'file': ('需求说明.md', '冒烟需求正文'.encode('utf-8'), 'text/markdown')})
check('上传文件来源', up.get('code') == 200, str(up)[:150])

sources = req('GET', f'/api/requirements/{req_id}/sources', None, token)
check('来源列表', sources.get('code') == 200 and len(sources['data']) == 2, str(sources)[:200])
file_src = [s for s in sources['data'] if s['type'] == 'file'][0]
dl = req('GET', file_src['download_url'])
check('签名下载', dl.get('raw', b'').find('冒烟需求正文'.encode('utf-8')) >= 0, str(dl)[:150])

# 6. 更新 + 只读环节列表
upd = req('PUT', f'/api/requirements/{req_id}', {'status': 'review_passed', 'priority': 'P0'}, token)
check('更新需求', upd.get('code') == 200, str(upd)[:150])
revs = req('GET', f'/api/requirements/{req_id}/reviews', None, token)
check('评审列表(空)', revs.get('code') == 200 and revs['data'] == [], str(revs)[:150])

# 7. 级联删除
delr = req('DELETE', f'/api/requirements/{req_id}', None, token)
check('删除需求', delr.get('code') == 200, str(delr)[:150])
det2 = req('GET', f'/api/requirements/{req_id}', None, token)
check('删除后 404', det2.get('code') == 404, str(det2)[:150])

# 8. 非成员 403
outsider_uname = f'smoke_out_{int(time.time())}'
req('POST', '/api/auth/register', {'username': outsider_uname, 'nickname': '外部', 'password': 'Smoke1234'})
out_login = req('POST', '/api/auth/login', {'username': outsider_uname, 'password': 'Smoke1234'})
out_token = out_login['data']['token']
forbid = req('GET', f'/api/requirements?project_id={project_id}&branch_id={branch_id}', None, out_token)
check('非成员 403', forbid.get('code') == 403, str(forbid)[:150])

print('\n全部冒烟测试通过 ✔')
