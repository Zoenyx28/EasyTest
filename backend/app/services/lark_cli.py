"""lark-cli 子进程封装 — 每用户 Device Flow 授权 + 飞书文档正文提取。

设计依据 ADR-0013：
- 鉴权采用每用户 token（Device Flow 两段式），token 生命周期由 lark-cli 管理；
- 提取正文时以当前用户身份 subprocess 调用 `lark-cli docs +fetch`；
- 鉴权过期/未授权/失败均降级处理，返回可读原因，不抛出异常。

所有命令均受超时与并发信号量约束，避免 CLI 卡死拖垮后端。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil

# CLI 可执行文件（可用 LARK_CLI_PATH 覆盖；测试中也可注入）
LARK_CLI = os.getenv('LARK_CLI_PATH', 'lark-cli')

# 并发信号量：控制同时进行的 CLI 调用（auth 与提取共用）
_cli_semaphore = asyncio.Semaphore(2)

# 默认超时
AUTH_TIMEOUT = 30          # 发起授权
AUTH_COMPLETE_TIMEOUT = 300  # 后台完成授权最长等待（匹配 device_code 有效期，用户在浏览器确认窗口）
FETCH_TIMEOUT = 60         # 文档提取（大文档较慢）
STATUS_TIMEOUT = 15        # 状态查询

# 提取错误分类（前端据此展示不同提示）
ERR_AUTH = 'auth'          # 鉴权过期 / 未授权
ERR_NOT_FOUND = 'not_found'  # 文档不存在 / 无访问权限
ERR_INVALID = 'invalid'    # 非飞书文档链接
ERR_TIMEOUT = 'timeout'    # CLI 超时
ERR_UNKNOWN = 'unknown'    # 其他失败


class LarkCliError(Exception):
    """lark-cli 调用失败的通用异常，携带面向用户的可读原因。"""

    def __init__(self, kind: str, message: str, *, exit_code: int | None = None,
                 raw: str = ''):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.exit_code = exit_code
        self.raw = raw

    def to_dict(self) -> dict:
        return {
            'kind': self.kind,
            'message': self.message,
            'exit_code': self.exit_code,
            'raw': self.raw[:2000],
        }


def _cli_available() -> bool:
    """检查 lark-cli 是否可用（PATH 或显式路径）。"""
    if os.path.isabs(LARK_CLI):
        return os.path.exists(LARK_CLI)
    return shutil.which(LARK_CLI) is not None


async def run_cli(args: list[str], timeout: float = 30, *, shared: bool = True) -> tuple[int, str, str]:
    """执行 lark-cli 命令，返回 (exit_code, stdout, stderr)。

    shared=True（默认）时受全局并发信号量约束，适用于快速命令；
    shared=False 跳过信号量，仅用于后台阻塞式授权（`auth login --device-code`
    会等待用户在浏览器确认，不能长期占用信号量拖慢 status / fetch 等命令）。
    """
    async def _exec() -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            LARK_CLI, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise LarkCliError(ERR_TIMEOUT, '飞书 CLI 调用超时，请稍后重试', raw=args_str(args))
        return proc.returncode, stdout.decode('utf-8', errors='replace'), \
            stderr.decode('utf-8', errors='replace')

    if shared:
        async with _cli_semaphore:
            return await _exec()
    return await _exec()


def args_str(args: list[str]) -> str:
    return ' '.join(args)


def _parse_json(text: str) -> dict | list | None:
    """宽容解析 CLI 输出的 JSON（可能混入日志/提示行）。

    lark-cli 输出为缩进多行 JSON 且尾部常附 `_notice` 等额外字段，
    因此截取首个 '{'/'[' 到末尾 '}'/']' 的区间后解析。
    """
    text = (text or '').strip()
    if not text:
        return None
    starts = [i for i in (text.find('{'), text.find('[')) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    end = max(text.rfind('}'), text.rfind(']'))
    if end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _extract_cli_error(text: str) -> str:
    """从 lark-cli 输出中提取 error.message（失败原因，英文原文）。"""
    data = _parse_json(text)
    if isinstance(data, dict):
        error = data.get('error') or {}
        if isinstance(error, dict) and error.get('message'):
            return str(error['message'])
    return ''


def _translate_auth_error(message: str) -> str:
    """将 lark-cli 的授权失败原因翻译为面向用户的中文提示。"""
    lower = (message or '').lower()
    if 'under review' in lower or 'pending' in lower:
        return '飞书授权申请正在审核中，请等待审核通过后重新发起授权（审核进度将通过「开发者小助手」推送）'
    if 'denied' in lower or 'rejected' in lower or 'not approved' in lower:
        return '飞书授权申请未通过审核，请联系企业管理员处理'
    if 'expired' in lower:
        return '授权链接已过期，请重新发起授权'
    if 'cancelled' in lower or 'canceled' in lower:
        return '授权已取消，请重新发起授权'
    return message.strip()


# ── 授权 ──


async def auth_initiate(domain: str = 'docs') -> dict:
    """发起 Device Flow 授权，返回验证信息 dict。

    lark-cli 输出示例：
    {"device_code": "...", "expires_in": 600, "verification_url": "https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=...&user_code=..."}
    """
    code, out, err = await run_cli(
        ['auth', 'login', '--no-wait', '--json', '--domain', domain],
        timeout=AUTH_TIMEOUT,
    )
    data = _parse_json(out) if isinstance(out, str) else None
    if code != 0 or not isinstance(data, dict) or not data.get('device_code'):
        raise LarkCliError(ERR_AUTH, '发起飞书授权失败', exit_code=code, raw=out + err)
    return {
        'verification_url': data.get('verification_url', ''),
        'device_code': data.get('device_code', ''),
        'expires_in': int(data.get('expires_in') or 600),
    }


async def auth_complete(device_code: str, *, timeout: float = AUTH_COMPLETE_TIMEOUT,
                        shared: bool = False) -> dict:
    """以 device_code 完成授权；成功后返回当前用户绑定信息。

    该命令会阻塞等待用户在浏览器完成确认（最长 timeout，默认 300s），
    因此默认 shared=False 跳过并发信号量，须由后台任务调用，避免阻塞
    status / fetch 等快速命令。返回 {app_id, lark_open_id, user_name, token_status}；
    失败抛 LarkCliError。
    """
    code, out, err = await run_cli(
        ['auth', 'login', '--device-code', device_code],
        timeout=timeout, shared=shared,
    )
    if code != 0:
        # 失败原因可能以 JSON 形式输出（如权限审核中/申请被拒等），优先翻译后展示
        cli_msg = _extract_cli_error((out or '') + (err or ''))
        message = _translate_auth_error(cli_msg) or '飞书授权未完成，请确认已在浏览器完成操作'
        raise LarkCliError(ERR_AUTH, message, exit_code=code, raw=(out or '') + (err or ''))

    # 授权完成后查询用户列表，取最后一个（最新绑定）用户
    identities = await auth_list()
    if not identities:
        raise LarkCliError(ERR_AUTH, '飞书授权完成，但未获取到用户信息', raw=out + err)
    user = identities[-1]
    return {
        'app_id': user.get('appId', ''),
        'lark_open_id': user.get('userOpenId', ''),
        'user_name': user.get('userName', ''),
        'token_status': user.get('tokenStatus', ''),
    }


async def auth_list() -> list[dict]:
    """列出 lark-cli 当前已授权用户。"""
    code, out, err = await run_cli(['auth', 'list', '--json'], timeout=AUTH_TIMEOUT)
    if code != 0:
        raise LarkCliError(ERR_AUTH, '查询飞书授权状态失败', exit_code=code, raw=out + err)
    data = _parse_json(out)
    if not isinstance(data, list):
        raise LarkCliError(ERR_AUTH, '查询飞书授权状态失败', raw=out + err)
    return data


async def auth_status() -> dict:
    """查询当前默认身份的 token 状态。

    返回 {user_open_id, user_name, token_status, bot_ready}。
    """
    code, out, err = await run_cli(['auth', 'status', '--json'], timeout=STATUS_TIMEOUT)
    if code != 0:
        raise LarkCliError(ERR_AUTH, '查询飞书授权状态失败', exit_code=code, raw=out + err)
    data = _parse_json(out)
    if not isinstance(data, dict):
        raise LarkCliError(ERR_AUTH, '查询飞书授权状态失败', raw=out + err)
    user = data.get('identities', {}).get('user', {}) or {}
    bot = data.get('identities', {}).get('bot', {}) or {}
    return {
        'app_id': data.get('appId', ''),
        'user_open_id': user.get('openId', ''),
        'user_name': user.get('userName', ''),
        'token_status': user.get('tokenStatus', ''),
        'bot_ready': bool(bot.get('ready', False)),
        'default_as': data.get('defaultAs', ''),
    }


# ── 文档提取 ──


def _classify_fetch_error(payload: dict, exit_code: int) -> tuple[str, str]:
    """将提取失败响应分类为 (kind, 可读 message)。

    lark-cli 错误示例：
    - 文档不存在/无权：{"ok": false, "error": {"type": "api", "code": 3380002, "message": "Invalid document_id ..."}}
    - 非文档链接：{"ok": false, "error": {"type": "validation", "subtype": "invalid_argument", "message": "unsupported --doc input ..."}}
    """
    error = payload.get('error', {}) or {}
    etype = str(error.get('type', '') or '').lower()
    subtype = str(error.get('subtype', '') or '').lower()
    code = error.get('code')
    message = error.get('message') or ''
    lower_msg = message.lower()

    # 非文档链接（validation 类，优先于其余判断）
    if etype == 'validation' or subtype == 'invalid_argument' or 'unsupported' in lower_msg:
        return ERR_INVALID, '仅支持飞书文档（docx/wiki）链接'
    # 鉴权类错误
    if etype in ('auth', 'auth_error', 'unauthorized') or 'auth' in etype or \
            'login' in subtype or 'token_status' in lower_msg or \
            'unauthorized' in lower_msg or 'expired' in lower_msg:
        return ERR_AUTH, '飞书授权已过期或未授权，请重新授权后重试'
    if exit_code != 0 and ('auth' in lower_msg or '401' in message or 'login' in lower_msg):
        return ERR_AUTH, '飞书授权已过期或未授权，请重新授权后重试'
    # 文档不存在/无权访问（api 3380002 等）
    if etype == 'api' or code:
        if str(code) in ('3380002', '3380001') or 'not found' in lower_msg or \
                'access' in lower_msg or 'permission' in lower_msg:
            return ERR_NOT_FOUND, '文档不存在或当前账号无访问权限'
        return ERR_UNKNOWN, message or '飞书文档读取失败'
    return ERR_UNKNOWN, message or '飞书文档读取失败'


async def fetch_doc(url: str, timeout: float = FETCH_TIMEOUT) -> dict:
    """提取飞书文档正文，返回 {extracted, text_content, error_kind, error_message}。

    任何失败都不抛异常，返回 extracted=False + 可读原因（供降级路径使用）。
    """
    if not _cli_available():
        return {'extracted': False, 'text_content': '',
                'error_kind': ERR_UNKNOWN, 'error_message': '服务器未安装 lark-cli，请手动粘贴文档内容'}
    try:
        code, out, err = await run_cli(
            ['docs', '+fetch', '--doc', url, '--doc-format', 'markdown', '--format', 'json'],
            timeout=timeout,
        )
    except LarkCliError as exc:  # 超时等
        return {'extracted': False, 'text_content': '',
                'error_kind': exc.kind, 'error_message': exc.message}

    data = _parse_json(f"{out}\n{err}")
    if not isinstance(data, dict):
        return {'extracted': False, 'text_content': '',
                'error_kind': ERR_UNKNOWN,
                'error_message': (err or out or '飞书文档读取失败').strip()[:500]}

    if data.get('ok') is True:
        content = ''
        try:
            content = data['data']['document']['content'] or ''
        except (KeyError, TypeError):
            content = ''
        if not content.strip():
            return {'extracted': False, 'text_content': '',
                    'error_kind': ERR_UNKNOWN, 'error_message': '文档正文为空'}
        return {'extracted': True, 'text_content': content,
                'error_kind': '', 'error_message': ''}

    # ok=false：分类错误
    kind, message = _classify_fetch_error(data, code)
    return {'extracted': False, 'text_content': '',
            'error_kind': kind, 'error_message': message}
