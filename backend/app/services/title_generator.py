"""AI-powered Chinese title generator (integrated into the system, no pytest plugin).

Generates natural Chinese titles for test functions using LLM APIs
(DeepSeek / Ollama / OpenAI compatible), with automatic local caching
so AI is only called once per function name.

Design notes:
- ``name`` here may carry parametrize parameters, e.g. ``test_login[admin]``.
  The AI is fed the full name (base function + parametrize suffix) so the
  generated title can reflect the specific parameter values.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class TitleGenerator:
    """AI title generator supporting multiple providers + caching + fallback."""

    DEFAULTS = {
        "provider": os.getenv("TITLE_PROVIDER", "deepseek"),
        "api_key": os.getenv(
            "TITLE_API_KEY",
            "sk-AcQ9AjnmqcJ8GLt49DmrNlrUvRQFcv55eoXEiHxFuOiQzxDAy1NT0SwwRu7zt89f",
        ),
        "api_base": os.getenv("TITLE_API_BASE", "https://opencode.ai/zen/go/v1").rstrip("/"),
        "model": os.getenv("TITLE_MODEL", "deepseek-v4-flash"),
    }

    def __init__(self, cache_path: Path | str | None = None, **overrides):
        cfg = dict(self.DEFAULTS)
        cfg.update(overrides)
        self.provider = cfg["provider"]
        self.api_key = cfg["api_key"]
        self.api_base = cfg["api_base"].rstrip("/")
        self.model = cfg["model"]
        if cache_path is None:
            cache_path = Path(".pytest-title-cache.json")
        self.cache_path = Path(cache_path)
        self.cache: Dict[str, str] = self._load_cache()
        self._dirty = False

    def generate_titles(self, names: List[str]) -> Dict[str, str]:
        """Batch-generate titles, returning {name: title} mapping.

        ``names`` may include parametrize suffixes, e.g. ``test_login[admin]``;
        each distinct full name gets its own title.
        """
        result: Dict[str, str] = {}
        need_ai: List[str] = []

        # 1. Read from cache
        for name in names:
            if name in self.cache:
                result[name] = self.cache[name]
            else:
                need_ai.append(name)

        # 2. Call AI for missing entries (in chunks to keep prompts reasonable)
        if need_ai:
            logger.info(
                "AI title generator: %d new names need titles, calling %s...",
                len(need_ai), self.provider,
            )
            for start in range(0, len(need_ai), 100):
                chunk = need_ai[start:start + 100]
                ai_titles = self._batch_call_ai(chunk)
                for name, title in ai_titles.items():
                    self.cache[name] = title
                    result[name] = title
                    self._dirty = True

                # Fallback for any remaining (AI failed to return) — do NOT
                # cache these so a later run can retry the AI.
                for name in chunk:
                    if name not in result:
                        result[name] = self._fallback(name)

        # 3. Save cache if changed
        if self._dirty:
            self._save_cache()

        return result

    def _batch_call_ai(self, names: List[str]) -> Dict[str, str]:
        """Call AI API to generate titles for the given names."""
        if self.provider == "disabled":
            return {name: self._fallback(name) for name in names}

        prompt = self._build_prompt(names)
        try:
            response_text = self._call_api(prompt)
            return self._parse_response(response_text, names)
        except Exception as e:
            logger.warning("AI title generation failed: %s, falling back", e)
            # Return empty dict so failed names are NOT cached: a later run
            # will retry the AI instead of being stuck with an English fallback.
            return {}

    def _build_prompt(self, names: List[str]) -> str:
        name_list = "\n".join(f"- {name}" for name in names)
        return f"""你是一个测试用例命名专家。请将以下 Python 测试函数名翻译成简洁的中文用例标题。

要求：
1. 去掉 test_ 前缀，按语义拆分单词
2. 标题简洁自然，不超过 20 个字
3. 表意清晰，不需要额外解释
4. 使用测试领域的规范术语
5. 函数名中 [参数] 后缀是 pytest 参数化产生的参数值，翻译时要把参数值融入标题，例如 test_login[admin] -> "使用admin账号登录"

函数名列表：
{name_list}

请按以下 JSON 格式返回：
{{"test_login[admin]": "使用admin账号登录", ...}}
直接返回 JSON，不要返回其他内容。"""

    def _call_api(self, prompt: str) -> str:
        """Call the AI API via OpenAI-compatible chat completions endpoint."""
        if self.provider == "ollama":
            headers = {"Content-Type": "application/json"}
        else:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

        import httpx

        response = httpx.post(
            f"{self.api_base}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 18000,
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _parse_response(
        self, text: str, expected_names: List[str]
    ) -> Dict[str, str]:
        """Parse the JSON response from AI, extracting only expected keys."""
        # Try to extract JSON from markdown code blocks
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1)

        text = text.strip()
        result = json.loads(text)
        return {k: v for k, v in result.items() if k in expected_names}

    def _fallback(self, name: str) -> str:
        """Fallback: strip test_ prefix and parametrize suffix keep, underscores to spaces."""
        # Keep parametrize suffix visible: test_login[admin] -> login[admin]
        if "[" in name:
            base, suffix = name.split("[", 1)
            base = base[5:] if base.startswith("test_") else base
            return f"{base.replace('_', ' ')}[{suffix.rstrip(']')}]"
        name = name[5:] if name.startswith("test_") else name
        return name.replace("_", " ")

    def _load_cache(self) -> Dict[str, str]:
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                return data.get("titles", {})
            except Exception as e:
                logger.warning("Failed to load title cache: %s", e)
                return {}
        return {}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "generated_at": datetime.now().isoformat(),
                    "titles": self.cache,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def clear_cache(self):
        """Clear the title cache, forcing re-generation on next run."""
        self.cache.clear()
        self._dirty = True
        if self.cache_path.exists():
            self.cache_path.unlink()
        logger.info("Title cache cleared.")
