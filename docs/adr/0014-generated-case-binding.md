# ADR-0014: 生成用例与自动化用例 0..N 绑定（详情内管理）

## Status

Accepted

## Context

需求管理流程最终产出「生成用例」（GeneratedCase，来自 Story）。用户希望生成用例可绑定「自动化用例」（TestCaseDefinition），建立需求→用例的追溯链。自动化用例按 `(project_id, branch_id)` 隔离，与需求域作用域一致。

## Decision

- 绑定关系：**GeneratedCase 0..N ↔ TestCaseDefinition**（一个生成用例可关联多个自动化用例）
- 关联表 `case_bindings`：`generated_case_id` + `(uid, project_id, branch_id)` 指向 TestCaseDefinition（复合主键，复用现有 TCD 主键结构）
- 绑定操作入口在**生成用例详情内管理**（不做列表行内快捷入口）：选择当前项目+分支下的自动化用例（搜索 + 多选），保存后展示已绑定用例标签，可取消绑定
- 绑定不反向修改 TestCaseDefinition；删除生成用例时级联删除绑定

## Considered Options

- **生成用例 0..1 单选**：用户明确需要多关联，未选
- **不建绑定表（弱关联展示）**：无法结构化追溯与去绑定，未选
- **列表行内快捷绑定**：用户选择详情内管理，保持列表简洁

## Consequences

- **Positive**：一条需求用例可覆盖多套自动化实现（如 api + ui 双实现）
- **Positive**：绑定表轻量，仅存外键，无冗余
- **Negative**：自动化用例按分支隔离，切换分支后绑定列表随之变化
