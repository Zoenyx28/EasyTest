"""后端 LLM 代理 — OpenAI 兼容 chat/completions，双模型，key 不落前端。

依据 ADR-0011：
- 配置存 DB（LLMSettings 单行），登录用户可改，API key 仅后端可见；
- provider=ollama 免鉴权（沿用 TitleGenerator 约定），其余带 Bearer；
- 通过 httpx 异步调用，transport 可注入（测试用 MockTransport，不发起真实请求）。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

# 默认配置（仅当 DB 无配置或字段为空时兜底，便于直连真实服务调试）
DEFAULT_PROVIDER = 'deepseek'
DEFAULT_API_BASE = 'https://opencode.ai/zen/go/v1'
DEFAULT_TEXT_MODEL = 'deepseek-v4-flash'


class LLMConfigError(Exception):
    """LLM 未配置或配置无效。"""


class LLMCallError(Exception):
    """调用 LLM 失败（网络/HTTP/解析）。"""


class LLMClient:
    """OpenAI 兼容 LLM 客户端。

    transport 注入示例（pytest）：
        from httpx import MockTransport
        transport = MockTransport(lambda request: httpx.Response(200, json={...}))
        client = LLMClient(settings, transport=transport)
    """

    def __init__(self, settings: dict, transport: httpx.AsyncBaseTransport | None = None,
                 timeout: float = 180.0, max_retries: int = 2, retry_delay: float = 0.6):
        self.provider = (settings.get('provider') or DEFAULT_PROVIDER).strip().lower()
        self.api_base = (settings.get('api_base') or DEFAULT_API_BASE).strip().rstrip('/')
        self.text_model = (settings.get('text_model') or DEFAULT_TEXT_MODEL).strip()
        self.vision_model = (settings.get('vision_model') or '').strip()
        self.api_key = (settings.get('api_key') or '').strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._transport = transport

        if self.provider != 'ollama' and not self.api_key:
            raise LLMConfigError('未配置 LLM API Key，请先在设置中配置')

    # ── 底层调用 ──

    async def _post(self, payload: dict) -> dict:
        headers = {'Content-Type': 'application/json'}
        if self.provider != 'ollama':
            headers['Authorization'] = f'Bearer {self.api_key}'
        # 外部 LLM 服务可能间歇性 429/5xx，做指数退避重试
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
                    resp = await client.post(f'{self.api_base}/chat/completions', headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                retryable = status == 429 or status >= 500
                if not retryable or attempt >= self.max_retries:
                    raise
                last_exc = exc
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        raise LLMCallError(f'LLM 调用失败: {last_exc}') from last_exc

    async def chat_json(self, prompt: str, *, model_kind: str = 'text',
                        temperature: float = 0.2, max_tokens: int = 8192,
                        schema_hint: str = 'JSON') -> Any:
        """调用 LLM 并返回解析后的 JSON（dict/list）。

        model_kind: 'text' 用 text_model；'vision' 用 vision_model（未配置则抛 LLMConfigError）。

        外部服务可能间歇性返回空/截断输出，对「网络/HTTP/解析失败」整体做指数退避重试。
        """
        if model_kind == 'vision' and not self.vision_model:
            raise LLMConfigError('未配置视觉模型（vision_model）')
        model = self.vision_model if model_kind == 'vision' else self.text_model
        payload = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                data = await self._post(payload)
                content = data['choices'][0]['message']['content']
                return parse_json_output(content)
            except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
                last_exc = LLMCallError(f'LLM 输出非合法 {schema_hint}: {exc}')
            except LLMCallError as exc:
                last_exc = exc
            except httpx.HTTPError as exc:
                last_exc = LLMCallError(f'LLM 调用失败: {exc}')
            if attempt >= self.max_retries:
                break
            await asyncio.sleep(self.retry_delay * (2 ** attempt))
        raise last_exc


    async def chat_vision(self, prompt: str, images: list[dict], *,
                          max_tokens: int = 8192, schema_hint: str = 'JSON') -> Any:
        """调用视觉模型分析图片并返回解析后的 JSON（#12）。

        images: [{'data': <base64>, 'mime_type': 'image/png'}]。多模态 content：
        ``[{type:text},{type:image_url,image_url:{url:data:...;base64,...}}]``。
        """
        if not self.vision_model:
            raise LLMConfigError('未配置视觉模型（vision_model）')
        content: list[dict] = [{'type': 'text', 'text': prompt}]
        for img in images:
            content.append({
                'type': 'image_url',
                'image_url': {
                    'url': f"data:{img.get('mime_type', 'image/png')};base64,{img['data']}",
                },
            })
        payload = {
            'model': self.vision_model,
            'messages': [{'role': 'user', 'content': content}],
            'max_tokens': max_tokens,
        }
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                data = await self._post(payload)
                content_text = data['choices'][0]['message']['content']
                return parse_json_output(content_text)
            except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
                last_exc = LLMCallError(f'LLM 输出非合法 {schema_hint}: {exc}')
            except LLMCallError as exc:
                last_exc = exc
            except httpx.HTTPError as exc:
                last_exc = LLMCallError(f'LLM 调用失败: {exc}')
            if attempt >= self.max_retries:
                break
            await asyncio.sleep(self.retry_delay * (2 ** attempt))
        raise last_exc


def _match_bracket(text: str, start: int) -> int:
    """从 start 处的左括号（{ 或 [）出发，返回配对的右括号下标；不匹配返回 -1。

    按字符串/转义感知扫描，避免文本内容里的 { } 干扰配对。
    """
    open_ch = text[start]
    close_ch = '}' if open_ch == '{' else ']'
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def parse_json_output(text: str) -> Any:
    """宽容解析 LLM 输出（剥离 markdown 代码块、多余文本）。

    用括号配对定位 JSON 边界，字段文本内的 { } 不会导致截取错位。
    """
    text = (text or '').strip()
    # 剥离 ```json ... ``` 代码块
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        text = m.group(1).strip()
    # 从首个 { 或 [ 开始，按括号配对截到匹配的右括号
    starts = [i for i in (text.find('{'), text.find('[')) if i >= 0]
    if starts:
        start = min(starts)
        end = _match_bracket(text, start)
        if end > start:
            text = text[start:end + 1]
    return json.loads(text)
