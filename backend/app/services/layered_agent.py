"""分层智能体服务（#21）— QA Orchestrator 模式的 9 个专业 Agent。

在 ADR-0011 三步智能体（评审→Story→用例）基础上扩展：
- Requirement Analyzer：需求分析（业务要素 11 项）+ 信息缺口识别
- Story Reviewer 升级：7 维评分 + Issues/Suggestions + QualityGate
- TestPoint Designer / Reviewer：测试点树（11 类分类）与 11 维评审
- Scenario Designer / Reviewer：业务场景生成与评审
- Case Reviewer：用例 9 维检查
- Strategy Advisor：自动化策略推荐
- Coverage Analyzer：逐层覆盖率 + TestGap（P0/P1）识别 + AI 补测建议

约定（延续 ADR-0011 / ADR-0015）：
- 所有函数为纯服务层：接收 LLMClient + 需求材料，返回结构化 dict，不直接读写 DB；
- 每次生成/评审同次调用附带评分（100 分制）+ QualityGate（PASS/WARNING/BLOCKED）；
- 覆盖式重生成：API 层负责删旧写新。
"""
from __future__ import annotations

import json
from typing import Any

from app.services.llm_client import LLMClient
from app.services.requirement_agent import _as_score, _require_fields, _sources_to_text

PROMPT_VERSION = 'layered-v1'

# 测试维度 11 类（PRD 第 65 节）
TEST_DIMENSIONS = [
    'Functional', 'Boundary', 'Exception', 'State', 'Permission',
    'Security', 'Data', 'Concurrency', 'Performance', 'Compatibility', 'Dependency',
]

# Story 评审 7 维权重（PRD 第 47 节 Story Reviewer）
STORY_REVIEW_DIMENSIONS = {
    '需求覆盖度': 25, '业务完整性': 20, '独立性': 15, '可测试性': 15,
    '粒度合理性': 10, '业务规则完整性': 10, '依赖完整性': 5,
}

# 测试点评审 11 维（PRD 第 47 节 TestPoint Reviewer）
TEST_POINT_REVIEW_DIMENSIONS = [
    'Story覆盖', '业务规则覆盖', '正常', '异常', '边界',
    '状态', '权限', '数据', '并发', '风险', '重复度',
]

# 用例评审 9 维（PRD 第 47 节 TestCase Reviewer / #21）
CASE_REVIEW_CHECKS = [
    '步骤', '预期', '数据', '业务规则', '测试点',
    '场景', '重复', '优先级', '自动化可行性',
]


def _stories_to_text(stories: list[dict]) -> str:
    """Story 清单 → 文本（含 id 供 LLM 引用索引）。"""
    lines = []
    for i, s in enumerate(stories):
        lines.append(
            f'Story{i}: {s.get("title", "")}\n'
            f'描述: {s.get("description", "")}\n'
            f'验收标准: {json.dumps(s.get("acceptance_criteria") or [], ensure_ascii=False)}'
        )
    return '\n\n'.join(lines) if lines else '（无 Story）'


def _test_points_to_text(test_points: list[dict]) -> str:
    """测试点 → 文本（含树形层级信息）。"""
    lines = []
    for i, t in enumerate(test_points):
        lines.append(
            f'TP{i}: [{t.get("category", "")}] {t.get("title", "")}'
            f'（story={t.get("story_index", 0)}, parent={t.get("parent_index", -1)}）\n'
            f'说明: {t.get("description", "")}'
        )
    return '\n\n'.join(lines) if lines else '（无测试点）'


def _scenarios_to_text(scenarios: list[dict]) -> str:
    lines = []
    for i, s in enumerate(scenarios):
        lines.append(
            f'SC{i}: [{s.get("coverage_dim", "")}] {s.get("title", "")}'
            f'（tp={s.get("test_point_index", 0)}）\n说明: {s.get("description", "")}'
        )
    return '\n\n'.join(lines) if lines else '（无场景）'


def _cases_to_text(cases: list[dict]) -> str:
    lines = []
    for i, c in enumerate(cases):
        lines.append(
            f'CASE{i}: {c.get("title", "")}（story={c.get("story_id", 0)}）\n'
            f'前置: {c.get("preconditions", "")}\n'
            f'步骤: {json.dumps(c.get("steps") or [], ensure_ascii=False)}\n'
            f'预期: {c.get("expected", "")}'
        )
    return '\n\n'.join(lines) if lines else '（无用例）'


def _extra_comment(review_comment: str) -> str:
    if review_comment.strip():
        return f'\n【人工补充评论（需重点回应并覆盖进结果）】\n{review_comment.strip()}'
    return ''


def _gate(score: int, *, blocked: bool = False) -> str:
    """按评分与强制条件判定 QualityGate：BLOCKED / WARNING / PASS。"""
    if blocked:
        return 'BLOCKED'
    if score < 60:
        return 'BLOCKED'
    if score < 80:
        return 'WARNING'
    return 'PASS'


# ══════════════════════════════════════════════════════════
# 1. Requirement Analyzer
# ══════════════════════════════════════════════════════════


async def analyze_requirement(client: LLMClient, requirement: dict, sources: list[dict],
                              review_comment: str = '', images: list[dict] | None = None) -> dict:
    """需求分析：理解业务要素（11 项）+ 识别信息缺口 + 需求可测性评分。

    images 非空时走视觉模型（#12：截图/图片需求文档），否则文本模型。
    """
    prompt = f"""你是资深测试需求分析师（Requirement Analyzer）。请先理解需求，再输出结构化业务要素与信息缺口。

【需求标题】{requirement.get('title', '')}
【需求摘要】{requirement.get('summary', '')}

【需求材料】
{_sources_to_text(sources)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"elements": {{"business_goal": "业务目标", "roles": ["角色"], "entities": ["业务实体"], "flows": ["关键流程"], "rules": ["业务规则"], "states": ["状态"], "inputs_outputs": ["输入输出"], "exceptions": ["异常场景"], "permissions": ["权限"], "dependencies": ["外部依赖"], "risks": ["风险"]}}, "information_gaps": [{{"gap_type": "BUSINESS_RULE_MISSING", "severity": "HIGH", "description": "缺口描述", "question": "需产品确认的问题"}}], "score": 0, "score_reason": "需求清晰度评分原因"}}

约束：
1. elements 每项尽量具体；无信息时用空数组，不要编造
2. information_gaps 类型取 AMBIGUOUS_DESCRIPTION / BUSINESS_RULE_MISSING / SCENARIO_MISSING / DATA_DEFINITION_MISSING / ACCEPTANCE_CRITERIA_MISSING / DEPENDENCY_UNKNOWN / RISK_UNSPECIFIED；严重度取 CRITICAL/HIGH/MEDIUM/LOW
3. 存在重大歧义或关键规则缺失时 severity=CRITICAL
4. score 为 0-100 的整数"""
    if images:
        data = await client.chat_vision(prompt, images, schema_hint='需求分析')
    else:
        data = await client.chat_json(prompt, schema_hint='需求分析')
    if not isinstance(data, dict):
        raise ValueError('需求分析输出应为 JSON 对象')
    _require_fields(data, ['elements', 'score', 'score_reason'])
    if not isinstance(data.get('elements'), dict):
        data['elements'] = {}
    for k in ('roles', 'entities', 'flows', 'rules', 'states', 'inputs_outputs',
              'exceptions', 'permissions', 'dependencies', 'risks'):
        if not isinstance(data['elements'].get(k), list):
            data['elements'][k] = []
    gaps = data.get('information_gaps') or []
    if not isinstance(gaps, list):
        gaps = []
    for g in gaps:
        _require_fields(g, ['gap_type', 'severity', 'description', 'question'])
    data['information_gaps'] = gaps
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 2. Story Reviewer（7 维升级）
# ══════════════════════════════════════════════════════════


async def review_stories(client: LLMClient, requirement: dict, sources: list[dict],
                         stories: list[dict], review_comment: str = '') -> dict:
    """Story 评审：每条 Story 7 维评分 + Issues/Suggestions + 组级 QualityGate。

    存在 CRITICAL 信息缺口时，API 层会强制 gate=BLOCKED（本函数仅按评分判定）。
    """
    dims = ', '.join(f'{k}(权重{v}%)' for k, v in STORY_REVIEW_DIMENSIONS.items())
    prompt = f"""你是资深测试设计评审专家（Story Reviewer）。请评审以下用户故事的可测性与完整性。

【需求标题】{requirement.get('title', '')}
【需求摘要】{requirement.get('summary', '')}

【需求材料】
{_sources_to_text(sources)}

【Story 清单】
{_stories_to_text(stories)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"reviews": [{{"story_index": 0, "dimension_scores": {{"需求覆盖度": 0}}, "score": 0, "issues": [{{"title": "问题", "detail": "说明"}}], "suggestions": ["建议"], "gate_status": "PASS"}}], "score": 0, "score_reason": "整体评分原因"}}

约束：
1. 对每条 Story 输出一组 7 维评分：{dims}，每维 0-100
2. story_index 对应上方 Story 序号（从 0 开始）
3. 单条 gate_status 取 PASS/WARNING/BLOCKED（总分≥80 PASS，60-79 WARNING，<60 BLOCKED）
4. 整体 score 为 0-100 的整数"""
    data = await client.chat_json(prompt, schema_hint='Story 评审')
    if not isinstance(data, dict):
        raise ValueError('Story 评审输出应为 JSON 对象')
    reviews = data.get('reviews') or []
    if not isinstance(reviews, list):
        reviews = []
    for r in reviews:
        _require_fields(r, ['story_index', 'score', 'gate_status'])
        if not isinstance(r.get('dimension_scores'), dict):
            r['dimension_scores'] = {}
        if not isinstance(r.get('issues'), list):
            r['issues'] = []
        if not isinstance(r.get('suggestions'), list):
            r['suggestions'] = []
        r['score'] = _as_score(r.get('score'))
    data['reviews'] = reviews
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 3. TestPoint Designer
# ══════════════════════════════════════════════════════════


async def generate_test_points(client: LLMClient, requirement: dict, stories: list[dict],
                               review_comment: str = '') -> dict:
    """Story 确认后生成测试点树：11 类分类 + parent 层级 + Story 覆盖检查。"""
    dims = ', '.join(TEST_DIMENSIONS)
    prompt = f"""你是资深测试设计专家（TestPoint Designer）。请基于确认的用户故事，生成测试点树，回答「测什么」。

【需求标题】{requirement.get('title', '')}

【Story 清单】
{_stories_to_text(stories)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"test_points": [{{"title": "测试点标题", "description": "测试点说明", "category": "Functional", "story_index": 0, "parent_index": -1}}], "score": 0, "score_reason": "测试点质量评分原因"}}

约束：
1. category 从以下 11 类中选：{dims}
2. 测试点树：顶层 parent_index=-1；子测试点 parent_index 指向其父测试点在数组中的序号
3. story_index 对应 Story 序号（从 0 开始），每条 Story 必须有对应测试点
4. 覆盖正常/异常/边界/状态等维度，数量 8-20 个，避免重复
5. score 为 0-100 的整数"""
    data = await client.chat_json(prompt, schema_hint='测试点生成')
    if not isinstance(data, dict):
        raise ValueError('测试点生成输出应为 JSON 对象')
    tps = data.get('test_points') or []
    if not isinstance(tps, list):
        tps = []
    for t in tps:
        _require_fields(t, ['title', 'description', 'category', 'story_index', 'parent_index'])
    data['test_points'] = tps
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 4. TestPoint Reviewer（11 维）
# ══════════════════════════════════════════════════════════


async def review_test_points(client: LLMClient, requirement: dict, stories: list[dict],
                             test_points: list[dict], review_comment: str = '') -> dict:
    """测试点评审：11 维评分 + 覆盖率 + 缺口建议 + QualityGate。"""
    dims = ', '.join(TEST_POINT_REVIEW_DIMENSIONS)
    prompt = f"""你是资深测试设计评审专家（TestPoint Reviewer）。请评审测试点树对 Story 与业务规则的覆盖情况。

【需求标题】{requirement.get('title', '')}

【Story 清单】
{_stories_to_text(stories)}

【测试点树】
{_test_points_to_text(test_points)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"dimension_scores": {{"Story覆盖": 0}}, "score": 0, "coverage": {{"total": 12, "covered_stories": ["Story0"], "missing_dimensions": ["并发"]}}, "issues": [{{"title": "问题", "detail": "说明"}}], "suggestions": ["建议新增的测试点"], "gate_status": "PASS"}}

约束：
1. 对 11 维逐一评分（0-100）：{dims}
2. coverage 描述覆盖情况；missing_dimensions 列出未覆盖的测试维度
3. suggestions 给出建议新增的具体测试点（供人确认）
4. score 为 0-100 的整数；gate_status 取 PASS/WARNING/BLOCKED"""
    data = await client.chat_json(prompt, schema_hint='测试点评审')
    if not isinstance(data, dict):
        raise ValueError('测试点评审输出应为 JSON 对象')
    if not isinstance(data.get('dimension_scores'), dict):
        data['dimension_scores'] = {}
    if not isinstance(data.get('coverage'), dict):
        data['coverage'] = {}
    if not isinstance(data.get('issues'), list):
        data['issues'] = []
    if not isinstance(data.get('suggestions'), list):
        data['suggestions'] = []
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 5. Scenario Designer
# ══════════════════════════════════════════════════════════


async def generate_scenarios(client: LLMClient, requirement: dict, test_points: list[dict],
                             review_comment: str = '') -> dict:
    """TestPoint → 业务场景（正常/异常/边界/状态分支）。"""
    prompt = f"""你是资深测试设计专家（Scenario Designer）。请基于测试点生成业务场景，回答「在什么业务情况下测」。

【需求标题】{requirement.get('title', '')}

【测试点】
{_test_points_to_text(test_points)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"scenarios": [{{"test_point_index": 0, "title": "场景标题", "description": "业务情况描述", "coverage_dim": "正常"}}], "score": 0, "score_reason": "场景质量评分原因"}}

约束：
1. coverage_dim 取 正常/异常/边界/状态 之一
2. test_point_index 对应上方测试点序号（从 0 开始）
3. 每个测试点至少 1 个场景；整体数量 8-30 个
4. 场景描述需给出具体业务前置与操作路径
5. score 为 0-100 的整数"""
    data = await client.chat_json(prompt, schema_hint='场景生成')
    if not isinstance(data, dict):
        raise ValueError('场景生成输出应为 JSON 对象')
    scenarios = data.get('scenarios') or []
    if not isinstance(scenarios, list):
        scenarios = []
    for s in scenarios:
        _require_fields(s, ['test_point_index', 'title', 'description', 'coverage_dim'])
    data['scenarios'] = scenarios
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 6. Scenario Reviewer
# ══════════════════════════════════════════════════════════


async def review_scenarios(client: LLMClient, requirement: dict, test_points: list[dict],
                           scenarios: list[dict], review_comment: str = '') -> dict:
    """场景评审：覆盖/重复/完整/异常/边界/状态/风险 + QualityGate。"""
    prompt = f"""你是资深测试设计评审专家（Scenario Reviewer）。请评审业务场景的覆盖与完整性。

【需求标题】{requirement.get('title', '')}

【测试点】
{_test_points_to_text(test_points)}

【场景清单】
{_scenarios_to_text(scenarios)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"score": 0, "coverage": {{"total": 15, "normal": 5, "exception": 4, "boundary": 3, "state": 3, "uncovered_tps": [0]}}, "issues": [{{"title": "问题", "detail": "说明"}}], "suggestions": ["建议"], "gate_status": "PASS"}}

约束：
1. coverage 统计各覆盖维度数量与未覆盖的测试点序号
2. issues 检查：场景重复、测试点遗漏、描述不可执行、边界/异常缺失
3. score 为 0-100 的整数；gate_status 取 PASS/WARNING/BLOCKED"""
    data = await client.chat_json(prompt, schema_hint='场景评审')
    if not isinstance(data, dict):
        raise ValueError('场景评审输出应为 JSON 对象')
    if not isinstance(data.get('coverage'), dict):
        data['coverage'] = {}
    if not isinstance(data.get('issues'), list):
        data['issues'] = []
    if not isinstance(data.get('suggestions'), list):
        data['suggestions'] = []
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 7. Case Reviewer（9 维）
# ══════════════════════════════════════════════════════════


async def review_cases(client: LLMClient, requirement: dict, stories: list[dict],
                       test_points: list[dict], scenarios: list[dict],
                       cases: list[dict], review_comment: str = '') -> dict:
    """用例评审：9 维检查 + QualityGate。"""
    checks = ', '.join(CASE_REVIEW_CHECKS)
    prompt = f"""你是资深测试用例评审专家（TestCase Reviewer）。请对用例集做 9 维质量检查。

【需求标题】{requirement.get('title', '')}

【Story 清单】
{_stories_to_text(stories)}

【测试点】
{_test_points_to_text(test_points)}

【场景清单】
{_scenarios_to_text(scenarios)}

【用例清单】
{_cases_to_text(cases)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"checks": {{"步骤": true, "重复": false}}, "score": 0, "issues": [{{"title": "问题", "detail": "说明", "case_index": 0}}], "suggestions": ["建议"], "gate_status": "PASS"}}

约束：
1. checks 对 9 维逐一给布尔/评分结论（true=通过）：{checks}
2. issues 里 case_index 对应用例序号（从 0 开始），指明问题用例
3. 检查重复用例、步骤不可执行、预期不明确、未覆盖测试点/场景
4. score 为 0-100 的整数；gate_status 取 PASS/WARNING/BLOCKED"""
    data = await client.chat_json(prompt, schema_hint='用例评审')
    if not isinstance(data, dict):
        raise ValueError('用例评审输出应为 JSON 对象')
    if not isinstance(data.get('checks'), dict):
        data['checks'] = {}
    if not isinstance(data.get('issues'), list):
        data['issues'] = []
    if not isinstance(data.get('suggestions'), list):
        data['suggestions'] = []
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data


# ══════════════════════════════════════════════════════════
# 8. Strategy Advisor
# ══════════════════════════════════════════════════════════


async def recommend_strategy(client: LLMClient, requirement: dict, cases: list[dict],
                             execution_stats: dict | None = None) -> dict:
    """自动化策略推荐：自动化/半自动化/人工 + 自动化占比。"""
    stats_block = ''
    if execution_stats:
        stats_block = (f'\n【执行历史统计】\n{json.dumps(execution_stats, ensure_ascii=False)}')
    prompt = f"""你是测试策略顾问（Strategy Advisor）。请基于用例清单与执行历史，推荐自动化策略。

【需求标题】{requirement.get('title', '')}
【需求优先级】{requirement.get('priority', 'P2')}
{stats_block}

【用例清单】
{_cases_to_text(cases)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"automation_ratio": 60, "result": {{"level": "半自动化", "rationale": "推荐理由", "per_case": [{{"case_index": 0, "approach": "automation", "reason": "原因"}}]}}}}

约束：
1. approach 取 automation（自动化）/ semi（半自动化）/ manual（人工）
2. 自动化/半自动化用例需给出可自动化理由（UI 稳定、回归高频等）
3. 人工用例标注原因（需人工判断、视觉验证等）
4. automation_ratio 为 0-100 的整数，表示建议自动化占比"""
    data = await client.chat_json(prompt, schema_hint='策略推荐')
    if not isinstance(data, dict):
        raise ValueError('策略推荐输出应为 JSON 对象')
    try:
        ratio = int(data.get('automation_ratio', 0))
    except (TypeError, ValueError):
        ratio = 0
    data['automation_ratio'] = max(0, min(100, ratio))
    if not isinstance(data.get('result'), dict):
        data['result'] = {}
    return data


# ══════════════════════════════════════════════════════════
# 9. Coverage Analyzer（AI 补测）
# ══════════════════════════════════════════════════════════


async def analyze_coverage(client: LLMClient, requirement: dict, layers_stats: dict,
                           review_comment: str = '') -> dict:
    """覆盖率分析：逐层覆盖率 + TestGap（P0/P1）识别 + 补测建议。"""
    stats_text = json.dumps(layers_stats, ensure_ascii=False, indent=1)
    prompt = f"""你是覆盖率分析专家（Coverage Analyzer）。请基于各层资产数量计算覆盖率，识别测试缺口（P0/P1）并给出 AI 补测建议。

【需求标题】{requirement.get('title', '')}

【各层资产统计】
{stats_text}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"coverage": {{"requirement": 100, "story": 80, "test_point": 70, "scenario": 60, "case": 50, "automation": 30, "risk": 40}}, "test_gaps": [{{"layer": "case", "severity": "P1", "description": "缺口描述", "source_ref": "story:0"}}], "suggestions": ["补测建议"]}}

约束：
1. coverage 各层 0-100 的整数，反映需求 → 用例逐层转化完整度
2. test_gaps 识别缺口：layer 取 story/test_point/scenario/case/automation/risk；severity 取 P0（阻断/高风险）/P1（应补充）；source_ref 标注缺口来源
3. suggestions 给出补齐缺口的补测方向（生成补充 TestPoint/Scenario/Case）
4. 每层覆盖率计算：已有层资产数 / 应有层资产数 × 100（应有量按需求复杂度估算）"""
    data = await client.chat_json(prompt, schema_hint='覆盖率分析')
    if not isinstance(data, dict):
        raise ValueError('覆盖率分析输出应为 JSON 对象')
    if not isinstance(data.get('coverage'), dict):
        data['coverage'] = {}
    gaps = data.get('test_gaps') or []
    if not isinstance(gaps, list):
        gaps = []
    for g in gaps:
        _require_fields(g, ['layer', 'severity', 'description'])
        if g['severity'] not in ('P0', 'P1'):
            g['severity'] = 'P1'
        g.setdefault('source_ref', '')
    data['test_gaps'] = gaps
    if not isinstance(data.get('suggestions'), list):
        data['suggestions'] = []
    return data


# ══════════════════════════════════════════════════════════
# 10. AI 补测（TestGap → 补充用例）
# ══════════════════════════════════════════════════════════


async def generate_supplement_cases(client: LLMClient, requirement: dict, gap: dict,
                                    cases: list[dict], review_comment: str = '') -> dict:
    """针对测试缺口生成补充链路：TestPoint → Scenario → Case，形成覆盖率闭环（#23 全链）。"""
    prompt = f"""你是资深测试设计专家。请针对以下测试缺口，生成补充测试链路：先补测试点（TestPoint），再为测试点生成业务场景（Scenario），最后为场景生成测试用例（Case）。

【需求标题】{requirement.get('title', '')}
【需求摘要】{requirement.get('summary', '')}

【测试缺口】
缺口层级: {gap.get('layer', '')}
缺口严重度: {gap.get('severity', 'P1')}
缺口描述: {gap.get('description', '')}
缺口来源: {gap.get('source_ref', '')}

【现有用例（避免重复）】
{_cases_to_text(cases)}
{_extra_comment(review_comment)}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"test_points": [{{"title": "测试点标题", "category": "Functional", "description": "测什么"}}], "scenarios": [{{"title": "场景标题", "test_point_index": 0, "coverage_dim": "正常", "description": "在什么业务情况下测"}}], "cases": [{{"title": "用例标题", "preconditions": "前置条件", "steps": ["步骤1"], "expected": "预期结果", "scenario_index": 0}}], "score": 0, "score_reason": "补充质量评分原因"}}

要求：
1. 全链路针对上述缺口；test_points 至少 1 条；scenarios 的 test_point_index 引用上方测试点序号（从 0 开始）；cases 的 scenario_index 引用上方场景序号
2. 用例与现有用例不重复；步骤可执行、预期明确；数量 1-5 条
3. category 取 Functional/Boundary/Exception/State/Permission/Security/Data/Concurrency/Performance/Compatibility/Dependency
4. score 为 0-100 的整数"""
    data = await client.chat_json(prompt, schema_hint='AI 补测')
    if not isinstance(data, dict):
        raise ValueError('AI 补测输出应为 JSON 对象')
    tps = data.get('test_points') or []
    if not isinstance(tps, list):
        tps = []
    for tp in tps:
        _require_fields(tp, ['title'])
        tp.setdefault('category', 'Functional')
        tp.setdefault('description', '')
    data['test_points'] = tps
    scenarios = data.get('scenarios') or []
    if not isinstance(scenarios, list):
        scenarios = []
    for sc in scenarios:
        _require_fields(sc, ['title'])
        sc.setdefault('test_point_index', 0)
        sc.setdefault('coverage_dim', '')
        sc.setdefault('description', '')
    data['scenarios'] = scenarios
    cases_out = data.get('cases') or []
    if not isinstance(cases_out, list):
        cases_out = []
    for c in cases_out:
        _require_fields(c, ['title', 'preconditions', 'expected'])
        if not isinstance(c.get('steps'), list):
            c['steps'] = []
        c.setdefault('scenario_index', 0)
    data['cases'] = cases_out
    data['score'] = _as_score(data.get('score'))
    return data


# ══════════════════════════════════════════════════════════
# 11. 需求评审闭环（#25）：问题卡片 评论/忽略/确定 + 重新评审 reconcile
# ══════════════════════════════════════════════════════════


async def respond_to_gap(client: LLMClient, gap: dict, comment: str, action: str) -> dict:
    """问题卡片评论/忽略：AI 追加回复。

    action='comment'：用户评论 → AI 回复澄清；
    action='ignore'：告知 LLM 该问题被忽略 → AI 简短确认。
    返回 {'reply': str}
    """
    thread = gap.get('thread') or []
    thread_text = '\n'.join(
        f"{'用户' if t.get('role') == 'user' else 'AI'}: {t.get('text', '')}"
        for t in thread
    ) or '（无历史讨论）'
    if action == 'ignore':
        instruction = '用户决定忽略该问题（不再要求确认）。请简短确认，并说明后续若需求变化可重新打开。'
        extra = ''
    else:
        instruction = '用户针对该问题提出了评论，请澄清/补充分析。'
        extra = f'\n【用户评论】{comment}'
    prompt = f"""你是资深测试需求分析专家。针对以下评审问题，{instruction}

【问题类型】{gap.get('gap_type', '')}（严重度 {gap.get('severity', '')}）
【问题描述】{gap.get('description', '')}
【需确认事项】{gap.get('question', '')}
【历史讨论】
{thread_text}
{extra}

请用 1-3 句中文回复，只输出回复文本，不要 JSON 或多余格式。"""
    reply = await client.chat_text(prompt)
    return {'reply': reply or '已记录。'}


async def confirm_gap_update_doc(client: LLMClient, requirement: dict, gap: dict) -> dict:
    """确定问题：AI 判断是否需要更新需求文档，需要则返回整篇更新后文档。

    返回 {'doc_changed': bool, 'updated_content': str, 'note': str}
    """
    current_content = requirement.get('content') or ''
    if len(current_content) > 12000:
        # 文档过长时整篇重写易截断丢失，改为提示手动修改，避免数据丢失
        return {'doc_changed': False, 'updated_content': '',
                'note': '需求文档过长，为避免覆盖丢失，建议手动在文档中修改'}
    thread_text = '\n'.join(
        f"{t.get('role')}: {t.get('text', '')}" for t in (gap.get('thread') or [])
    ) or '（无）'
    prompt = f"""你是资深测试需求分析师。确定以下评审问题后，判断它是否需要更新需求文档；如需要，输出整篇更新后的需求文档。

【当前需求文档】
{current_content}

【确定的问题】
类型：{gap.get('gap_type', '')}（严重度 {gap.get('severity', '')}）
描述：{gap.get('description', '')}
需确认事项：{gap.get('question', '')}
评论/讨论：{thread_text}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"doc_changed": true, "updated_content": "整篇更新后的需求文档（如需修改则全文输出，未涉及部分保持不变）", "note": "修改说明"}}

约束：
1. doc_changed：该问题确实需要在需求文档补充/修正内容时为 true，否则 false
2. updated_content 始终为整篇文档（不要省略未修改部分）；doc_changed=false 时可为空串
3. 若无文档可改（如纯信息澄清），doc_changed=false"""
    data = await client.chat_json(prompt, schema_hint='确定问题')
    if not isinstance(data, dict):
        raise ValueError('确定问题输出应为 JSON 对象')
    changed = data.get('doc_changed') in (True, 'true', 1, '1')
    updated = (data.get('updated_content') or '').strip()
    return {
        'doc_changed': changed,
        'updated_content': updated if changed and updated else '',
        'note': data.get('note') or '',
    }


async def re_review_requirement(client: LLMClient, requirement: dict, sources: list[dict],
                                old_gaps: list[dict], review_comment: str = '') -> dict:
    """重新评审（reconcile）：核对旧问题状态 + 产出新分析/新问题，不清空旧问题。

    old_gaps: [{gap_type, severity, description, question, status, thread}]
    返回 {elements, score, score_reason, gate_status, information_gaps(新问题), reconciled}
    """
    old_text = '\n'.join(
        f"- [{g.get('status')}] {g.get('gap_type', '')}/{g.get('severity', '')}: {g.get('description', '')}"
        for g in old_gaps
    ) or '（无）'
    prompt = f"""你是资深测试需求分析专家。基于更新后的需求文档，对评审进行【重新核对】：
1. 逐条核对旧问题在新文档中的状态；2. 识别新问题；3. 输出综合评审分析。

【需求标题】{requirement.get('title', '')}
【需求文档】
{_sources_to_text(sources)}
{_extra_comment(review_comment)}

【旧问题清单】
{old_text}

请严格按以下 JSON 返回（不要输出其他内容）：
{{"elements": {{"business_goal": "", "roles": [], "entities": [], "flows": [], "rules": [], "states": [], "inputs_outputs": [], "exceptions": [], "permissions": [], "dependencies": [], "risks": []}}, "reconciled": [{{"index": 0, "new_status": "fixed|not_applicable|keep", "note": "依据（引用文档内容）"}}], "information_gaps": [{{"gap_type": "", "severity": "HIGH", "description": "", "question": ""}}], "score": 0, "score_reason": "综合分析"}}

约束：
1. reconciled 逐条对应旧问题清单（index 从 0 起）：
   - fixed：旧问题已在新文档解决（note 引用解决它的文档内容）
   - not_applicable：旧问题在需求中已不再涉及
   - keep：仍存在需继续确认（note 可为空）
   - 旧问题若已是 confirmed（已确定），标记 keep 即可，不改状态
2. information_gaps 仅列出新识别的问题；旧问题由 reconciled 反映，不重复列出
3. score 为 0-100 整数"""
    data = await client.chat_json(prompt, schema_hint='重新评审')
    if not isinstance(data, dict):
        raise ValueError('重新评审输出应为 JSON 对象')
    if not isinstance(data.get('reconciled'), list):
        data['reconciled'] = []
    for r in data['reconciled']:
        if r.get('new_status') not in ('fixed', 'not_applicable', 'keep'):
            r['new_status'] = 'keep'
        r.setdefault('note', '')
    gaps = data.get('information_gaps') or []
    if not isinstance(gaps, list):
        gaps = []
    for g in gaps:
        _require_fields(g, ['gap_type', 'severity', 'description', 'question'])
    data['information_gaps'] = gaps
    data['score'] = _as_score(data.get('score'))
    data['gate_status'] = _gate(data['score'])
    return data
