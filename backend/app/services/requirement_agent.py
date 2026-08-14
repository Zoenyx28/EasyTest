"""需求智能体 — 三步流程（评审→拆 Story→生成用例）+ 需求元信息生成。

依据 ADR-0011：
- 每步固定 JSON 输出；同一次调用附带环节整体评分（100 分制）+ 评分原因；
- 评分 < 60 由 API 层标记 low_score（建议重新评审），不自动触发；
- 重新评审携带人工 review_comment，覆盖重调当前步智能体。

所有函数为纯服务层：接收 LLMClient + 需求材料，返回结构化 dict，不直接读写 DB。
"""
from __future__ import annotations

import json
from typing import Any

from app.services.llm_client import LLMClient, parse_json_output


def _sources_to_text(sources: list[dict], max_len: int = 20000) -> str:
    """将需求来源（提取正文）拼接为给 LLM 的材料文本。"""
    parts = []
    used = 0
    for i, src in enumerate(sources, 1):
        content = (src.get('text_content') or '').strip()
        if not content:
            continue
        head = src.get('link') or src.get('filename') or f'来源{i}'
        budget = max_len - used
        if budget <= 0:
            break
        parts.append(f'【来源：{head}】\n{content[:budget]}')
        used += len(parts[-1])
    return '\n\n'.join(parts) if parts else '（无可用正文）'


def _require_fields(data: dict, fields: list[str]) -> dict:
    """兜底：解析结果缺字段时用空值补齐，避免流程中断。"""
    for f in fields:
        if f not in data or data[f] is None:
            data[f] = '' if isinstance(f, str) else ''
    return data


# ── 需求元信息（标题/摘要/优先级） ──


async def generate_requirement_meta(client: LLMClient, requirement: dict,
                                    sources: list[dict]) -> dict:
    prompt = f"""你是资深产品需求分析师。请根据以下需求材料，提炼需求元信息。

【原始标题】{requirement.get('title', '')}

【需求材料】
{_sources_to_text(sources)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"title": "简洁的需求标题", "summary": "2-3 句话的摘要", "priority": "P0"}}

priority 取 P0/P1/P2 之一：P0=紧急且重要，P1=重要，P2=一般。"""
    data = await client.chat_json(prompt, schema_hint='需求元信息')
    if not isinstance(data, dict):
        raise ValueError('需求元信息输出应为 JSON 对象')
    _require_fields(data, ['title', 'summary', 'priority'])
    if data['priority'] not in ('P0', 'P1', 'P2'):
        data['priority'] = 'P2'
    return data


# ── 第一步：需求评审 ──


async def review_requirement(client: LLMClient, requirement: dict, sources: list[dict],
                             review_comment: str = '') -> dict:
    extra = ''
    if review_comment.strip():
        extra = f'\n【人工补充评论（需重点回应并覆盖进评审结论）】\n{review_comment.strip()}'
    prompt = f"""你是资深测试需求评审专家。请评审以下需求文档，输出评审结论、风险与问题清单，并对需求可测性打分（100 分制，60 分以下说明需求不可测或缺陷多，需要重新评审）。

【需求标题】{requirement.get('title', '')}

【需求材料】
{_sources_to_text(sources)}
{extra}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"conclusion": "评审结论（是否可进入测试设计）", "risks": ["风险1", "风险2"], "issues": [{{"title": "问题标题", "detail": "问题说明"}}], "score": 0, "score_reason": "扣分原因说明"}}

score 为 0-100 的整数。"""
    data = await client.chat_json(prompt, schema_hint='评审结果')
    if not isinstance(data, dict):
        raise ValueError('评审输出应为 JSON 对象')
    _require_fields(data, ['conclusion', 'score', 'score_reason'])
    data.setdefault('risks', [])
    data.setdefault('issues', [])
    if not isinstance(data.get('risks'), list):
        data['risks'] = []
    if not isinstance(data.get('issues'), list):
        data['issues'] = []
    data['score'] = _as_score(data.get('score'))
    return data


# ── 第二步：拆解 Story ──


async def split_stories(client: LLMClient, requirement: dict, sources: list[dict],
                        latest_review: dict | None = None) -> dict:
    review_block = ''
    if latest_review and (latest_review.get('conclusion') or latest_review.get('issues')):
        review_block = (f"\n【历史评审结论】{latest_review.get('conclusion', '')}\n"
                        f"【评审问题】{json.dumps(latest_review.get('issues', []), ensure_ascii=False)}")
    prompt = f"""你是资深测试设计专家。请将以下需求拆解为用户故事（Story），每个 Story 需独立可测。

【需求标题】{requirement.get('title', '')}
【需求摘要】{requirement.get('summary', '')}
{review_block}

【需求材料】
{_sources_to_text(sources)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"stories": [{{"title": "Story 标题", "description": "Story 描述", "acceptance_criteria": ["验收标准1", "验收标准2"]}}], "score": 0, "score_reason": "拆解质量评分原因"}}

要求：
1. 每个 Story 覆盖一个独立功能/流程，可单独测试
2. 验收标准必须是可验证的、具体的
3. 数量 3-8 个
4. score 为 0-100 的整数"""
    data = await client.chat_json(prompt, schema_hint='Story 拆解')
    if not isinstance(data, dict):
        raise ValueError('Story 拆解输出应为 JSON 对象')
    stories = data.get('stories') or []
    if not isinstance(stories, list):
        stories = []
    for s in stories:
        _require_fields(s, ['title', 'description'])
        if not isinstance(s.get('acceptance_criteria'), list):
            s['acceptance_criteria'] = []
    data['stories'] = stories
    data.setdefault('score', 0)
    data.setdefault('score_reason', '')
    data['score'] = _as_score(data.get('score'))
    return data


# ── 第三步：生成用例 ──


async def generate_cases(client: LLMClient, requirement: dict, stories: list[dict]) -> dict:
    story_block = '\n'.join(
        f"Story{i + 1}: {s.get('title', '')}\n描述: {s.get('description', '')}\n"
        f"验收标准: {json.dumps(s.get('acceptance_criteria', []), ensure_ascii=False)}"
        for i, s in enumerate(stories)
    )
    prompt = f"""你是资深测试用例设计专家。请基于以下用户故事，为每个 Story 生成测试用例。

【需求标题】{requirement.get('title', '')}

【Story 清单】
{story_block}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"cases": [{{"story_index": 0, "title": "用例标题", "preconditions": "前置条件", "test_data": "测试数据", "steps": ["步骤1", "步骤2"], "expected": "预期结果", "test_type": "功能"}}], "score": 0, "score_reason": "用例质量评分原因"}}

要求：
1. story_index 对应上方 Story 序号（从 0 开始）
2. 每个 Story 至少 2 条用例，覆盖正常、边界、异常场景
3. 步骤用数组，每步可执行；预期结果明确
4. test_type 取「功能 / 接口 / UI / 安全 / 性能 / 兼容 / Manual」之一（按用例验证方式判断）
5. test_data 填写该用例需要准备的测试数据（无特殊数据可填空串）
6. score 为 0-100 的整数"""
    data = await client.chat_json(prompt, schema_hint='用例生成')
    if not isinstance(data, dict):
        raise ValueError('用例生成输出应为 JSON 对象')
    cases = data.get('cases') or []
    if not isinstance(cases, list):
        cases = []
    for c in cases:
        _require_fields(c, ['title', 'preconditions', 'expected'])
        if not isinstance(c.get('steps'), list):
            c['steps'] = []
        c.setdefault('story_index', 0)
        c.setdefault('test_type', '功能')
        c.setdefault('test_data', '')
    data['cases'] = cases
    data.setdefault('score', 0)
    data.setdefault('score_reason', '')
    data['score'] = _as_score(data.get('score'))
    return data


async def regenerate_single_case(client: LLMClient, requirement: dict,
                                 story: dict | None, case: dict) -> dict:
    story_block = ''
    if story:
        story_block = (f"【所属 Story】{story.get('title', '')}\n"
                       f"描述: {story.get('description', '')}\n"
                       f"验收标准: {json.dumps(story.get('acceptance_criteria', []), ensure_ascii=False)}")
    prompt = f"""你是资深测试用例设计专家。请重新设计下面这条测试用例（可参考其原内容进行优化）。

【需求标题】{requirement.get('title', '')}
{story_block}

【原用例】
标题: {case.get('title', '')}
前置: {case.get('preconditions', '')}
步骤: {json.dumps(case.get('steps', []), ensure_ascii=False)}
预期: {case.get('expected', '')}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"title": "用例标题", "preconditions": "前置条件", "test_data": "测试数据", "steps": ["步骤1", "步骤2"], "expected": "预期结果", "test_type": "功能", "score": 0, "score_reason": "本次用例质量评分原因"}}

score 为 0-100 的整数；test_type 取「功能 / 接口 / UI / 安全 / 性能 / 兼容 / Manual」之一。"""
    data = await client.chat_json(prompt, schema_hint='单用例重生成')
    if not isinstance(data, dict):
        raise ValueError('单用例重生成输出应为 JSON 对象')
    _require_fields(data, ['title', 'preconditions', 'expected'])
    if not isinstance(data.get('steps'), list):
        data['steps'] = []
    data.setdefault('test_type', '功能')
    data.setdefault('test_data', '')
    data['score'] = _as_score(data.get('score'))
    return data


def _as_score(value: Any) -> int:
    """安全转分数（0-100）。"""
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))
