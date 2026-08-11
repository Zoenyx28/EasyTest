# SPEC: 需求工作台全流程闭环与架构精简

## 问题陈述

测试人员目前完成一个需求从导入到缺陷提交，需要在 4 个页面之间反复跳转：需求管理页 → 测试设计工作台 → 自动化用例页 → 测试执行页 → 缺陷管理页。每步切换都丢失上下文、重新定位。同时后端需求域有 17 张数据库表，对 3 名测试 + 3 名开发的团队规模而言过度设计，维护成本高于收益。

## 解决方案

1. **架构精简**：需求域从 17 张表合并为 5 张核心表，后端按限界上下文拆分为 4 个独立模块
2. **工作台单页闭环**：将需求设计、执行、缺陷集成到一个工作台页面内，测试人员从需求导入到缺陷提交零次跳转
3. **全链路追溯**：缺陷关联需求，需求概览可追溯执行结果和缺陷状态

## 用户故事

### 需求导入与分析

1. 作为测试人员，我希望能通过飞书链接、上传文件或粘贴文本三种方式导入需求，系统自动提取正文为统一格式供我预览，这样我不需要关心来源格式差异
2. 作为测试人员，我希望能一键触发 AI 需求分析，系统自动识别业务目标、角色、实体、流程、规则、风险等要素，这样我不需要手动梳理需求结构
3. 作为测试人员，我希望 AI 分析时能识别信息缺口并提示我补充，这样我可以及时找产品确认不确定的业务规则

### 分层测试设计

4. 作为测试人员，我希望 AI 能将需求拆解为多个独立的 Story，每个 Story 附带 7 维评分和 QualityGate（PASS/WARNING/BLOCKED），这样我一眼能判断哪些 Story 需要调整
5. 作为测试人员，我希望能对 Story 逐条确认、修改或要求 AI 重新生成，确认后的 Story 才进入下一层测试点设计，这样每个阶段的输出质量有保证
6. 作为测试人员，我希望 AI 能为确认后的 Story 生成测试点树（按 Functional/Boundary/Exception/State 等 11 类组织），每个测试点有明确的"测什么"描述
7. 作为测试人员，我希望 AI 能为确认后的测试点生成测试场景（回答"在什么业务情况下测"），覆盖正常/异常/边界/状态四个维度
8. 作为测试人员，我希望 AI 能为确认后的场景生成测试用例，包含前置条件、测试数据、操作步骤、预期结果，并附带质量评分
9. 作为测试人员，我希望能重新生成任一层的资产，覆盖式替换旧结果，这样我可以根据需要反复优化

### 用例绑定与执行

10. 作为测试人员，我希望能在工作台内看到生成的测试用例，并将其绑定到已有的自动化用例（pytest 发现的 TestCaseDefinition），绑定非必填
11. 作为测试人员，我希望能在工作台内勾选已绑定的自动化用例并一键执行，不需要跳转到测试执行页
12. 作为测试人员，我希望执行期间能实时看到进度（WebSocket 推送），每个用例的状态变化即时展示
13. 作为测试人员，我希望执行完成后能直接在工作台内查看结果：pass/fail 明细、日志、耗时

### 缺陷提交流程

14. 作为测试人员，我希望执行失败的用例旁有一个"提缺陷"按钮，点击后弹出缺陷创建弹窗，自动填入：标题（含用例名和失败摘要）、关联需求、关联用例 UID、失败日志和用例步骤作为复现描述，我只需确认和补充
15. 作为测试人员，我希望能手动新建缺陷并关联到当前需求，不需要跳转到缺陷管理页

### 需求追溯

16. 作为测试人员，我希望在需求概览中能看到关联缺陷的数量和状态（"2 个关联缺陷，1 个未关闭"），这样我一眼知道这个需求的质量状态
17. 作为测试人员，我希望在需求概览中能看到最近一次执行的结果摘要（"3 pass / 1 fail"），这样我知道测试覆盖的执行情况
18. 作为测试人员，我希望在工作台的"缺陷"Tab 中看到所有关联当前需求的缺陷列表，点击可展开详情和活动记录，这样可以追溯到每个缺陷的完整生命周期

### 页面导航

19. 作为测试人员，我希望在需求工作台内左侧看到需求列表（支持按状态筛选和搜索），点击任意需求即可在右侧切换上下文，不需要跳回列表页
20. 作为项目成员，我希望所有页面（需求、自动化、执行、缺陷、报告）对项目内所有成员可见，不区分角色权限

### 架构可维护性

21. 作为开发者，我希望需求域的数据库表从 17 张缩减到 5 张，用一张统一的 `requirement_assets` 表存储所有分层资产，这样新增资产类型只需加数据行而非建表
22. 作为开发者，我希望后端代码按限界上下文（测试执行、缺陷跟踪、需求设计、项目管理）拆分为独立模块，改一个上下文不影响其他上下文
23. 作为开发者，我希望数据库迁移使用 Alembic 管理，不再在 `init_db()` 中手动写 ALTER TABLE 语句

## 实施决策

### 数据库变更

- **合并分层资产表**：将 `requirement_analyses`、`stories`、`requirement_reviews`、`test_points`、`test_point_reviews`、`test_scenarios`、`scenario_reviews`、`generated_cases`、`case_reviews`、`test_strategies`、`information_gaps` 合并为一张 `requirement_assets` 表，用 `asset_type` 枚举区分类型，用 `parent_id` 支持树形结构
- **移除独立来源表**：`requirement_sources` 降级为 `requirements` 表的 `source_type` + `source_meta`（JSON）两个字段，保留溯源信息和提取状态
- **缺陷关联需求**：`defects` 表新增可选字段 `requirement_id`，建立缺陷到需求的追溯链
- **使用 MySQL JSON 列**：`requirement_assets.content` 和 `requirement.source_meta` 使用 MySQL 原生 JSON 列类型替代 TEXT
- **数据库迁移工具**：用 Alembic 替代 `init_db()` 中的手动 SQL

### 后端模块拆分

- `domains/test_execution/` — Task、Execution、ExecutionCase、Report
- `domains/defect_tracking/` — Defect、DefectModule、DefectLog、DefectComment、DefectAttachment
- `domains/requirement_design/` — Requirement、RequirementAsset、CaseBinding、AITask、ReviewAudit、CoverageSnapshot
- `domains/project_mgmt/` — Project、Branch、ProjectMember、ProjectNote
- `shared/` — User、Auth、LLMSettings、Database、Common

### API 变更

- **新增聚合端点**：`GET /api/requirements/{req_id}/workbench` — 一次返回需求详情 + 概览统计 + 全部分层资产 + 最近执行记录 + 关联缺陷列表，替代当前 3-4 个独立 API 调用
- **新增执行端点**：`POST /api/requirements/{req_id}/execute` — 接收 `uids[]`，内部创建 Task 和 Execution，返回 `execution_id` 供 WebSocket 监听
- **修改缺陷创建**：`POST /api/defects` — 请求体新增可选字段 `requirement_id`，创建时自动关联需求
- **修改需求查询**：需求列表和详情接口返回新增字段 `defect_count`、`open_defect_count`、`latest_execution_summary`

### 前端重构

- **合并页面**：`/requirements` 和 `/requirements/:reqId` 合并为一个路由 `/requirements`，左右分栏布局（左侧需求列表 320px + 右侧工作台），用路由 query `?req_id=X` 标识当前选中需求
- **工作台 Tab**：右侧面板 4 个 Tab —— 概览、资产（原分层视图）、执行、缺陷
- **执行 Tab**：复用现有 `useWebSocket` composable 监听执行进度，UI 内嵌展示结果。`[🐛 提缺陷]` 按钮仅出现在失败结果旁
- **缺陷 Tab**：列表展示关联需求的所有缺陷，点击可展开详情和活动记录
- **提缺陷弹窗**：从执行结果触发时自动预填标题、关联需求 ID、关联用例 UID、失败日志和步骤；从缺陷 Tab 触发时只预填关联需求 ID
- **组件拆分**：单个 `.vue` 文件不超过 300 行。工作台拆为容器组件 + 4 个展示 Tab 组件。弹窗保持独立组件。

### 状态管理与数据流

- 工作台数据通过一个 `useWorkbench(reqId)` composable 管理（新建），内部复用 `useApi` 调用新聚合端点
- 执行状态通过 `useWebSocket` 监听，执行进度和结果通过 composable 内部 ref 驱动 UI 更新
- AI 任务进度统一通过轮询 `GET /api/ai-tasks?requirement_id=X` 获取，不依赖全局轮询

## 测试决策

### 测试原则

- 只测试外部行为（API 响应格式、返回字段、状态码），不测内部实现
- 每个 API 端点至少覆盖：正常返回、边界条件（空数据）、权限错误
- 前端测试覆盖核心交互流：需求列表加载 → 切换需求 → Tab 切换 → 执行 → 提缺陷

### 测试模块

- **后端 API 测试**：`tests/test_workbench.py`（新增）— 测试聚合端点 `GET /workbench`、`POST /execute`。参照已有 `tests/test_requirements_api.py` 的 pytest + httpx 模式
- **后端 CRUD 测试**：`tests/test_requirement_assets.py`（新增）— 测试统一资产表的 CRUD 操作和树形查询。参照已有 `tests/test_requirements_layers_api.py` 的模式
- **前端交互测试**：`tests/e2e/workbench.spec.ts`（新增）— Playwright 端到端测试工作台闭环。参照已有 Playwright 配置（`frontend/package.json` 中已引入 playwright）

### 测试数据

- 使用 conftest.py 的 fixture 模式初始化测试数据，参照 `backend/tests/conftest.py`
- 使用工厂函数创建 Requirement、RequirementAsset、Defect 等测试实体，避免在测试中直接写 SQL

## 不在本规范范围内

- 角色权限区分（项目内成员平等可见，不做角色隔离）
- PostgreSQL 数据库迁移（当前保持 MySQL）
- RAG 向量检索（当前文档规模不需要）
- 全局搜索重构（使用页面内搜索即可）
- 历史版本管理（保持覆盖式，不保留 v1/v2/v3）
- 执行引擎从进程内存迁移到 Redis（性能优化后置）
- CI/CD 集成和 Jenkins 构建

## 补充说明

### 本规范依赖以下已有架构决策

- ADR-0011：LLM 智能体后端代理架构
- ADR-0012：需求域按 (project_id, branch_id) 隔离
- ADR-0013：飞书文档提取流程
- ADR-0014：GeneratedCase 与 TestCaseDefinition 的 0..N 绑定
- ADR-0015：PRD V2.0 分层链路对齐 + 覆盖式版本管理
- **ADR-0016（新增）**：领域模型精简与模块边界划分

### 交互流程图（从用户视角）

```text
打开系统 → /requirements（工作台）
  │
  ├─ 左侧列表 → 选需求 → 右侧 [概览] Tab
  │   └─ 点击 [需求分析] → AI 跑 → 结果显示
  │
  ├─ [资产] Tab → [Story] → [AI 生成] → PASS → [确认]
  │             → [测试点] → [AI 生成] → 人工确认
  │             → [场景] → [AI 生成]
  │             → [用例] → [AI 生成]
  │
  ├─ [执行] Tab → 看到绑定用例 → 勾选 → [▶ 执行]
  │   └─ 实时进度 → 结果: PASS/FAIL
  │       └─ FAIL 旁 [🐛 提缺陷] → 弹窗自动填好 → 提交
  │
  ├─ [缺陷] Tab → 看到关联缺陷 → 展开详情
  │
  └─ [概览] Tab → "关联 1 缺陷(未关)" → "上次执行 2P/1F"
```

### 执行优先级

| 优先级 | 事项 | 依赖 |
|--------|------|------|
| **P0** | 需求域表合并（17→5）+ Alembic 迁移 | 无 |
| **P0** | 后端模块拆分 | P0 表合并完成后 |
| **P1** | `GET /workbench` 聚合端点 | P0 表合并完成后 |
| **P1** | 前端工作台左右分栏 + 4 Tab | P1 聚合端点就绪后 |
| **P1** | `POST /execute` 执行端点 + 工作台执行 Tab | P1 工作台 UI 就绪后 |
| **P2** | 失败 → 一键提缺陷（预填） | P1 执行 Tab 就绪后 |
| **P2** | 需求概览统计卡片（缺陷/执行/覆盖率） | P1 聚合端点就绪后 |
| **P3** | 使用 MySQL JSON 列（可与 P0 并行） | 无 |
