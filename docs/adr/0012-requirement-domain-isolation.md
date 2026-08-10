# ADR-0012: 需求域实体按项目+分支隔离，删除级联清理

## Status

Accepted

## Context

新增需求管理模块，涉及 Requirement（需求）、RequirementSource（来源：飞书链接/文件）、RequirementReview（评审输出）、Story（用户故事）、GeneratedCase（生成用例）、CaseBinding（与自动化用例的绑定）。

需求本身不随代码版本变化（一份需求文档通常描述多个版本的功能），直觉上应挂在项目级。但用户明确要求与现有实体（TestCaseDefinition / Defect / Task 等）一致，按 `(project_id, branch_id)` 隔离，保证「切版本即切上下文」的统一心智。

## Decision

- 需求域所有实体带 `project_id` + `branch_id`（默认取创建时当前活跃分支）
- 跨分支不共享需求数据；同一需求如需多版本维护，在各分支下分别创建
- 需求可删除，**级联清理**：上传文件（磁盘目录）、Story、GeneratedCase、CaseBinding、以及 LLMSettings 之外的关联记录
- 文件存储沿用缺陷附件模式：`PROJECTS_DATA_DIR/requirements/{requirement_id}/`，访问走签名 URL（`file_signer.py`）

## Considered Options

- **需求按项目级、生成用例按分支级**：两套隔离语义并存，增加心智负担，未选
- **需求软删除（归档）**：用户选择硬删除 + 级联清理，未选

## Consequences

- **Positive**：与现有版本隔离体系一致，前端无需特殊分支处理
- **Positive**：删除即彻底清理，无孤儿文件
- **Negative**：跨分支复用需求需手动复制
- **Negative**：硬删除不可恢复，需在 UI 二次确认
