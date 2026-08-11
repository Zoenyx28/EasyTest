# EasyTest — 领域术语表

## 核心实体

### Project（项目）

被测软件项目。每个项目都有一个源代码目录和一组 **Branch**（分支/版本）。

### Branch（分支，也称版本）

**Project** 内的一个命名隔离工作线，概念上类似于 Git 分支。

- 一个 **Branch** 拥有自己独立的 **TestCaseDefinition**（从源码发现）
- 一个 **Branch** 拥有自己独立的 **Task**、**Execution**、**Report**
- 跨分支数据通过 `version_id` 外键完全隔离
- 每个 **Branch** 有人类可读的名称（如 `main`、`v2.0`）和稳定的内部标识符（自增 ID）

### TestCaseDefinition（测试用例定义）

通过 `pytest --collect-only` 从项目源码发现的单个测试用例。每个定义存储测试名称、文件路径、标记、文档字符串和类型（api/ui）。

- 当通过复制创建 **Branch** 时，**TestCaseDefinition** 会被深拷贝并分配新 ID
- 当创建空白 **Branch** 时，没有 **TestCaseDefinition**，直到用户触发重新导入

### Task（任务）

用户定义的 **TestCaseDefinition** 集合，用于批量执行。作用域限定在单个 **Branch**。

### TaskCase（任务用例）

连接 **Task** 和 **TestCaseDefinition** 的关联记录。

### Execution（执行）

**Task** 的一次运行记录，包含整体状态、时间和摘要。作用域限定在单个 **Branch**。

### ExecutionCase（执行用例）

**Execution** 中每个测试用例的执行记录，包含状态、日志、耗时和失败详情。

### Report（报告）

汇总 **Execution** 结果的报告文档。以 JSON 格式存储在数据库中，作用域限定在单个 **Branch**。

## 操作

### 创建分支（复制）

通过深拷贝源 **Branch** 的 **TestCaseDefinition** 创建新 **Branch**。每个拷贝的定义获得新 ID。新分支不包含 **Task**、**Execution** 或 **Report**。

### 创建分支（空白）

创建不包含 **TestCaseDefinition** 的新 **Branch**。用户只需指定项目路径和分支名称。后续需要通过发现过程导入定义。

### 切换版本（切换版本上下文）

在 UI 中切换当前活跃的 **Branch**。所有后续视图（测试用例、任务、执行、报告）都限定在所选分支内。分支通过 URL 中的稳定 ID 标识。

### 导入项目文件（发现测试用例）

对项目源码目录运行 `pytest --collect-only` 发现 **TestCaseDefinition**。将发现的定义填充到当前活跃的 **Branch**。

## 数据模型约定

- 所有版本作用域实体都带有 `branch_id`（或 `version_id`）外键列
- 包括：**TestCaseDefinition**、**Task**、**TaskCase**、**Execution**、**ExecutionCase**、**Report**
- **Project** 本身不受版本作用域限制（它跨越所有分支）
- 旧版 `RunRecord` / `TestResultRecord` 模型已移除

## URL 约定

- 版本上下文通过 `?version=<branch-id>`（整数）传递，不通过人类可读名称
- 示例：`/cases?version=1` 而非 `/cases?version=v2.0`
- 省略 `version` 时，API 默认使用项目的默认分支

<br />

## 新实体（Phase 2）

### User（用户）

平台的注册用户。用户可以自行注册、登录和管理个人信息。

- **username**：唯一登录标识
- **nickname**：显示名称
- **Password**：使用 bcrypt 哈希存储
- 用户**没有角色区分**——所有用户平等
- 所有 API 请求**必须通过认证**（register/login/health 除外）
- 未认证请求返回 `401 {code: 401, msg: '未登录或登录已过期', data: null}`

### ProjectMember（项目成员）

**User** 和 **Project** 之间的多对多关联。每个成员可以添加/移除其他成员，但不能移除**创建者**。

- **创建者**记录在 `projects` 表的 `creator_id` 字段
- 成员通过 `(project_id, user_id)` 唯一标识

### Defect（缺陷）

针对特定 **Project**（可选关联 **Branch** 版本）报告的 Bug/问题。遵循禅道缺陷生命周期。

- 字段：标题、简单描述、详细信息（含具体描述、操作步骤、截图）、项目、分支（版本）、模块、严重程度（P0-P3）、优先级（P0-P3）、状态、指派给、创建者、附件
- **状态生命周期**：未确认 → 已确认 → 处理中 → 已解决 → 已关闭（支持激活回退）
- **解决方案**：已修复、重复、不是问题、无法重现、设计如此、外部原因、暂不处理
- 严重程度/优先级：P0（致命/紧急）、P1（严重/高）、P2（一般/中）、P3（建议/低）

### DefectModule（缺陷模块）

**Project** 内用户自定义的模块树，用于对 **Defect** 进行分类。

- 通过 `parent_id` 支持父子树形结构
- 每个模块在 `(project_id, parent_id)` 范围内唯一

### DefectAttachment（缺陷附件）

附加到 **Defect** 的文件。存储在服务器文件系统 `PROJECTS_DATA_DIR/defects/attachments/{defect_id}/` 下。

### DefectLog（缺陷操作日志）

记录 **Defect** 每次状态转换和操作的审计日志条目。

- **action**（操作类型）：created（创建）、assigned（指派）、confirmed（确认）、resolved（解决）、closed（关闭）、activated（激活）、commented（评论）
- 记录旧值、新值和可选备注

### ProjectNote（项目备注）

附加到 **Project** 的 Markdown 备注。与项目一对一关联。

- 内容以原始 Markdown 文本存储
- 支持内联编辑和渲染预览

## 操作（Phase 2）

### 注册 / 登录

用户使用用户名、昵称和密码注册。登录返回有效期 7 天的 JWT token。

### 创建缺陷

在项目下创建新缺陷，可选指定分支、模块、严重程度、优先级、指派给。

### 变更缺陷状态

沿禅道生命周期变更缺陷状态：确认 → 指派 → 解决 → 关闭 → 激活。

### 管理项目成员

向项目添加或移除成员。任何成员都可以添加/移除其他成员，但不能移除创建者。

### 管理缺陷模块

CRUD 操作用于项目级别对缺陷进行分类的模块树。

### 编辑项目备注

编辑与项目关联的 Markdown 备注。备注在项目详情面板中渲染展示。

### 查看最近测试任务

在项目详情面板中查看项目最新的 2 条执行记录。点击任务可跳转到测试执行页面。

## URL 约定（更新）

### 认证

- `POST /api/auth/register` — 注册
- `POST /api/auth/login` — 登录
- `POST /api/auth/change-password` — 修改密码（需要认证）
- `GET /api/auth/me` — 获取当前用户信息（需要认证）

### 缺陷

- `GET /api/projects/{project_id}/defects` — 缺陷列表（限定项目，可选分支筛选）
- `POST /api/projects/{project_id}/defects` — 创建缺陷
- `GET /api/defects/{id}` — 缺陷详情
- `POST /api/defects/{id}/confirm|assign|resolve|close|activate` — 状态转换

### 项目详情

- `GET /api/projects/{project_id}/members` — 成员列表
- `POST /api/projects/{project_id}/members` — 添加成员
- `DELETE /api/projects/{project_id}/members/{user_id}` — 移除成员
- `GET /api/projects/{project_id}/notes` — 获取项目备注
- `PUT /api/projects/{project_id}/notes` — 更新项目备注
- `GET /api/projects/{project_id}/overview` — 项目概览（创建者、成员、最近缺陷打包返回）

## 需求管理（Phase 3，对齐 PRD V2.0）

需求域遵循 PRD V2.0 的完整分层测试设计链路：

```text
Requirement → RequirementAnalysis → Story → StoryReview → 人工确认 → TestPoint
→ TestPointReview → 人工确认 → TestScenario → GeneratedCase → CaseReview
→ TestStrategy → Automation → Execution → Coverage / Risk → TestGap → AI补测
```

核心理念：AI 负责理解、拆解、评估、建议和生成；产品负责业务事实确认；测试工程师负责测试质量确认。AI 生成不是终点，每一层都经过 Review → QualityGate → 人工确认后才进入下一层。

### Requirement（需求）

**Project** 内按 **Branch**（版本）隔离的一条待处理需求单元。来源可以是手工输入、文件、飞书文档链接或项目代码；经过分析 → Story → 测试点 → 场景 → 用例的智能体流程产出测试资产。

- 标题 / 摘要 / 优先级由智能体从来源文档生成，用户可编辑
- 需求级状态生命周期：待评审 → 评审通过 → Story确认 → 用例生成 → 完成；任一步可重新评审
- 需求级状态是宏观推进进度；每个智能体环节的内部推进由「AI 任务状态机」管理

### RequirementSource（需求来源）

**Requirement** 的输入：飞书文档链接（lark-cli 提取正文，失败降级为仅存链接）或上传文件（txt/json/md 直读；doc/docx/pdf 解析提取；截图/图片供视觉模型分析）。一次需求可有多个来源。

### RequirementAnalysis（需求分析）

智能体对 **Requirement** 的**理解**输出（先理解，再测试）。AI 不直接生成测试点，先识别：业务目标、业务角色、业务实体、业务流程、业务规则、状态变化、输入输出、异常条件、权限、外部依赖、数据约束与风险。分析产出作为 Story 拆解的上下文。

### InformationGap（信息缺口）

当智能体判断需求信息不足时创建的信息缺口，需要产品确认。类型：BUSINESS\_RULE\_MISSING / ACCEPTANCE\_CRITERIA\_MISSING / DATA\_RULE\_MISSING / STATE\_TRANSITION\_MISSING / PERMISSION\_RULE\_MISSING / ERROR\_RULE\_MISSING / DEPENDENCY\_MISSING。严重等级：CRITICAL / HIGH / MEDIUM / LOW。存在 Critical InformationGap 时，QualityGate 必须为 BLOCKED。

### Story（用户故事）

**RequirementAnalysis** 拆解出的、从业务角度描述的一个独立、可验证、可测试的业务能力。Story 不是测试用例，也不是简单复制需求标题。

- 字段：标题、业务目标、业务角色、业务行为、业务规则、前置条件、业务结果、异常条件、依赖 Story、来源 Requirement
- 拆解原则：独立性、完整性、可测试性、合理粒度（避免过粗/过细）
- Story 之间需去重（防止两个 Story 表达同一业务能力）

### StoryReview（Story 评审）

Story 生成后不直接进入测试点，先过 **Story Quality Gate**。多维评分（7 维）：

| 评分维度    |  权重 |
| ------- | --: |
| 需求覆盖度   | 25% |
| 业务完整性   | 20% |
| 独立性     | 15% |
| 可测试性    | 15% |
| 粒度合理性   | 10% |
| 业务规则完整性 | 10% |
| 依赖完整性   |  5% |

同时输出 Issues（问题清单）、Suggestions（建议）、InformationGap、QualityGate（PASS / WARNING / BLOCKED）。QualityGate 判定示例：需求覆盖度 ≥90%、可测试性 ≥80%、业务规则完整性 ≥80% 且无 Critical InformationGap 为 PASS；存在关键业务信息缺失为 BLOCKED。

### 人工确认（双角色 Review）

Story 阶段采用产品 + 测试双角色确认：

- **产品经理**确认业务事实、业务规则、业务流程、验收条件
- **测试工程师**确认测试可行性、业务边界、异常流程、风险、Story 粒度

页面提供操作：确认 / 修改 / 补充信息 / 要求 AI 重新生成 / 忽略问题。对于业务事实由人确认，对于结构化拆解由 AI 重新生成（避免测试人员自行猜测业务规则）。

### TestPoint（测试点）

Story 确认后生成，表示"需要验证的测试关注点"（回答"测什么"）。分类：Functional / Boundary / Exception / State / Permission / Data / Concurrency / Security / Performance / Compatibility / Dependency。以测试点树形式组织（如退款申请 → 退款资格 → 可退款订单/不可退款订单/已退款订单）。

### TestPointReview（测试点评审）

测试点生成后进入 **TestPoint Quality Gate**。检查维度：Story 覆盖度、业务规则覆盖度、正常场景、异常场景、边界场景、状态覆盖、权限覆盖、数据覆盖、并发覆盖、风险覆盖、重复度。AI Review 不是一次性过程而是循环过程：生成 → Review → 测试工程师修改 → AI 重新 Review → PASS。

### TestScenario（测试场景）

TestPoint 确认后生成。TestPoint 回答"测什么"，TestScenario 回答"在什么业务情况下测"。例如 TestPoint「退款资格」→ 场景：已支付订单正常申请退款 / 未支付订单申请退款 / 已退款订单再次申请退款 等。

### ScenarioReview（场景评审）

智能体检查：场景覆盖、场景重复、场景完整性、异常覆盖、边界覆盖、状态覆盖、风险覆盖。输出 Coverage / Issues / Suggestions。

### GeneratedCase（生成用例）

TestScenario 确认后生成。字段：Case ID、标题、追溯链（Requirement / Story / TestPoint / TestScenario）、前置条件、测试数据、操作步骤、预期结果、测试类型、优先级、风险等级、来源、状态。生成时必须使用 Requirement + Story + TestPoint + TestScenario + Testing Standard，而非只根据 Story 生成。测试类型（UI / API / Manual）由智能体推荐，测试工程师可修改。

### CaseReview（用例评审）

智能体检查：步骤完整性、预期结果完整性、测试数据完整性、业务规则覆盖、测试点覆盖、场景覆盖、重复用例、优先级合理性、自动化可行性。

### TestStrategy（测试策略）

Automation Advisor 根据 TestCase、TestStrategy、Risk、ExecutionHistory 推荐自动化 / 半自动化 / 人工测试。

### CaseBinding（用例绑定）

**GeneratedCase** 与 **TestCaseDefinition**（自动化用例）0..N 关联记录，指向 `(uid, project_id, branch_id)` 复合主键。绑定在生成用例详情内管理，可取消；删除生成用例时级联删除绑定。GeneratedCase 与 TestCaseDefinition 保持解耦——一个生成用例可对应多套自动化实现。

### TestCaseDefinition（自动化用例定义）

见前述核心实体。通过 `pytest --collect-only` 从源码发现，按 `(project_id, branch_id)` 隔离，是 **CaseBinding** 的绑定目标。

### Coverage（覆盖率）

系统按层计算：Requirement / Story / TestPoint / Scenario / GeneratedCase / Automation / Risk 覆盖率。

### Risk（风险）

执行与设计过程中的风险记录，供 TestStrategy 与 TestGap 分析使用。

### TestGap（测试缺口）

系统发现的缺口：未覆盖 Story、未覆盖 TestPoint、未覆盖 Scenario、未自动化 Case、高风险未覆盖。按 P0 / P1 分级（如 P0：并发退款未覆盖；P1：第三方退款异常未覆盖）。

### AI 补测

TestGap 进入 Coverage Analyzer，AI 根据缺口重新生成 TestPoint → Scenario → GeneratedCase，形成持续质量闭环。

### LLMSettings（模型配置）

全局唯一的智能体配置：provider / api\_base / 文本模型 / 视觉模型 / API key。存于后端数据库，登录用户可改；所有智能体调用由后端代理，API key 不进入前端。

### QA Orchestrator（测试设计编排器）

不采用单一超级 Agent，采用 **QA Orchestrator + 12 个专业 Agent**：Requirement Analyzer / Story Designer / Story Reviewer / TestPoint Designer / TestPoint Reviewer / Scenario Designer / TestCase Generator / TestCase Reviewer / Strategy Advisor / Automation Advisor / Execution Analyzer / Coverage Analyzer。Orchestrator 负责：接收任务 → 判断当前阶段 → 调度 Agent → 管理上下文 → 保存中间产物 → 触发 Review → 判断 Quality Gate → 决定是否进入下一阶段 → 处理人工反馈 → 重新触发 AI。

### AI 任务状态机

所有智能体环节统一采用：

```text
PENDING → RUNNING → REVIEW → WAITING_HUMAN → CONFIRMED → NEXT_STAGE
```

异常分支：RUNNING → FAILED → RETRY。

### AI Review 记录（审计）

每一次 AI Review 必须保存：review\_id、artifact\_type、artifact\_id、score、dimension\_scores、issues、suggestions、information\_gaps、gate\_status、model、prompt\_version、created\_at，实现测试设计过程可审计。

### 版本管理（决策：覆盖式）

每次重新生成**直接覆盖**当前环节输出并重新评分，保持单一当前版本（不保留 v1/v2/v3 历史，无 Confirmed Version 切换）。此决策与 PRD V2.0 第 50 节"保留历史版本"的建议冲突，见 ADR-0015。

## 操作（Phase 3）

### 新建需求

在需求管理页右上角「新建需求」，选择来源（飞书链接 / 上传文件）创建 **Requirement**，绑定当前活跃分支。

### 需求分析

手动触发智能体对需求的理解（RequirementAnalysis），识别业务要素与信息缺口，不直接产出测试点。

### 评审 / 重新评审

手动触发智能体评审。重新评审携带用户评论重新生成该环节输出，直接覆盖，并重新附带 AI 评分；评分 < 60 标记「建议重新评审」。

### 拆解 Story / 生成测试点 / 生成场景 / 生成用例

评审通过后手动触发拆解 Story；Story 确认（含双角色确认）后生成 TestPoint；TestPoint 确认后生成 TestScenario；TestScenario 确认后批量生成用例，单个用例可单独重生成。每一层生成后都经过 AI Review + QualityGate，未 PASS 可携带评论重新生成。

### 绑定自动化用例

在生成用例详情内选择当前项目 + 分支的 **TestCaseDefinition** 建立 **CaseBinding**，可取消。

### AI 评分与质量门

每个环节（分析 / 评审 / Story / 测试点 / 场景 / 用例）在生成时自动附带环节整体分（100 分制）、评分原因与 QualityGate（PASS / WARNING / BLOCKED），前端可查看。

### 覆盖率与补测

系统按层计算覆盖率、识别 TestGap 并驱动 AI 补测，形成需求 → 测试设计 → 自动化 → 执行 → 覆盖率 → 缺口 → 补测的闭环。

## 环境

- sshpass -p 'xdjr0lxGu' ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -p 22022 root\@10.19.195.109 '
- cd /aifs01/zouyang/easytest

## 部署

### 镜像标签

当前版本`<version>:v1`
手动部署阶段使用的镜像标签，格式 `easy-test-<component>:<version>`（如 `easy-test-backend:v2`、`easy-test-frontend:v2`）。Jenkins 接入后切换为 Registry 路径 `10.19.195.109:5000/easytest-<component>:<tag>`。详见 ADR-0004。

### 部署单元

可独立构建发布的部署单元。当前有三个：**Frontend**（nginx + Vue SPA）、**Backend**（FastAPI API + Celery Worker，同一镜像两种启动方式）、**Infra**（Redis、MySQL，官方镜像，无需构建）。
