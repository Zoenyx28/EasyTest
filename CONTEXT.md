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

## 环境

- sshpass -p 'xdjr0lxGu' ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -p 22022 root\@10.19.195.109 '
- cd /aifs01/zouyang/easytest

## 部署

### 镜像标签

当前版本`<version>:v1`
手动部署阶段使用的镜像标签，格式 `easy-test-<component>:<version>`（如 `easy-test-backend:v2`、`easy-test-frontend:v2`）。Jenkins 接入后切换为 Registry 路径 `10.19.195.109:5000/easytest-<component>:<tag>`。详见 ADR-0004。

### 部署单元

可独立构建发布的部署单元。当前有三个：**Frontend**（nginx + Vue SPA）、**Backend**（FastAPI API + Celery Worker，同一镜像两种启动方式）、**Infra**（Redis、MySQL，官方镜像，无需构建）。