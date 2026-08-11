# ADR-0015: 需求域领域模型对齐 PRD V2.0（全量分层 + 覆盖式版本管理）

## Status

Accepted

## Context

用户重新梳理需求，产出《AI QA Agent 测试设计与测试管理平台 PRD》V2.0（`docs/specs/AI QA Agent 测试设计与测试管理平台 PRD.md`）。PRD V2.0 将产品从"AI 生成测试用例"升级为"AI 持续进行测试设计与质量优化"，定义了完整分层链路：

```text
Requirement → RequirementAnalysis → Story → StoryReview → 人工确认 → TestPoint
→ TestPointReview → 人工确认 → TestScenario → GeneratedCase → CaseReview
→ TestStrategy → Automation → Execution → Coverage / Risk → TestGap → AI补测
```

现有实现（ADR-0011 智能体架构 / ADR-0012 域隔离 / ADR-0014 用例绑定）仅覆盖「评审 → Story → 用例」三步流程：无需求分析层、无 InformationGap、无 QualityGate、无测试点/场景层、无覆盖率闭环。PRD V2.0 与现有领域模型存在结构性差距。

## Decision

### 1. 领域模型全量对齐 PRD V2.0

CONTEXT.md「需求管理（Phase 3）」升级为 PRD V2.0 全量领域模型，新增概念纳入领域术语表：

- **RequirementAnalysis（需求分析）**：AI 先理解需求（业务目标/角色/实体/流程/规则/状态/输入输出/异常/权限/依赖/风险），是 Story 拆解的前置
- **InformationGap（信息缺口）**：7 种类型 + CRITICAL/HIGH/MEDIUM/LOW 四级；存在 Critical 缺口时 QualityGate 必须 BLOCKED
- **StoryReview（Story 评审）**：7 维多维评分 + Issues/Suggestions/InformationGap/QualityGate
- **TestPoint / TestPointReview**：Story 确认后生成测试点树（11 类），11 维评审，循环迭代机制
- **TestScenario / ScenarioReview**：TestPoint 确认后生成业务场景，评审检查覆盖/重复/完整性
- **CaseReview / TestStrategy**：用例评审 9 维检查；Automation Advisor 推荐自动化/半自动化/人工
- **Coverage / Risk / TestGap / AI 补测**：逐层覆盖率计算、P0/P1 缺口分级、AI 补测形成闭环
- **QA Orchestrator**：QA Orchestrator + 12 个专业 Agent，不采用单一超级 Agent
- **AI 任务状态机**：PENDING → RUNNING → REVIEW → WAITING_HUMAN → CONFIRMED → NEXT_STAGE；异常 FAILED → RETRY
- **AI Review 审计记录**：review_id / dimension_scores / gate_status / model / prompt_version 等，过程可审计

### 2. 版本管理：保持覆盖式（与 PRD 第 50 节冲突，显式裁决）

PRD V2.0 第 50 节建议"每次重新生成保留历史版本（Story v1/v2/v3 + Confirmed Version 切换）"。**不采纳，保持现有覆盖式**：

- 每次重新生成直接覆盖当前环节输出并重新评分，保持单一当前版本
- 无历史版本保留、无 Confirmed Version 切换 UI

理由：覆盖式与现有实现一致、数据模型与前端交互显著更简单；历史版本需求优先级低，可由后续需求驱动升级（届时本 ADR 需重新评估）。

### 3. 状态机双层语义

- **需求级状态机**（宏观进度）：沿用现有 待评审 → 评审通过 → Story确认 → 用例生成 → 完成
- **AI 任务状态机**（环节微观状态）：管理每个智能体环节（分析/评审/Story/测试点/场景/用例）的内部推进

### 4. 其余约束延续

- 数据隔离延续 ADR-0012：所有需求域实体带 `(project_id, branch_id)`
- 智能体架构延续 ADR-0011：后端代理 + LLMSettings + 生成时附带评分
- 绑定关系延续 ADR-0014：GeneratedCase 0..N ↔ TestCaseDefinition
- 飞书提取延续 ADR-0013：每用户 Device Flow 授权 + 失败降级

## Considered Options

- **历史版本管理（对齐 PRD 第 50 节）**：可审计、可回溯，但数据模型（版本表）、API、前端版本切换 UI 复杂度显著上升，未选
- **领域模型保持三步流程**：与用户"全量对齐 V2.0"的明确要求冲突，未选
- **AI 单一超级 Agent**：PRD 明确不采用，未选

## Consequences

- **Positive**：领域语言与 PRD V2.0 对齐，后续 tickets 可无障碍引用全量分层概念
- **Positive**：QualityGate 三态 + 双角色确认提升测试设计质量的可控性
- **Positive**：AI Review 审计记录支持过程可审计
- **Negative**：现有三步实现与目标模型存在差距，后续需按新 tickets 增量补齐测试点/场景/覆盖率层
- **Negative**：覆盖式版本管理与 PRD 建议不同，评审过程的历史可回溯性受限（已显式裁决，接受）
- **Negative**：文档先行于实现——实现阶段需分批对齐，避免一次性大重构
