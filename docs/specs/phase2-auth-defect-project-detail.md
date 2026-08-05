# Phase 2 实现计划：用户系统 + 缺陷管理 + 项目详情

## 概述

本阶段新增三大功能模块，分为 5 个迭代实现：

1. **迭代 1**：用户认证系统（后端 + 前端）
2. **迭代 2**：项目创建者 + 项目成员管理
3. **迭代 3**：缺陷管理（后端）
4. **迭代 4**：缺陷管理（前端）
5. **迭代 5**：项目详情面板（重构项目管理页面）

---

## 迭代 1：用户认证系统

### 后端

| # | 文件 | 变更 |
|---|------|------|
| 1.1 | `backend/app/db/models.py` | 新增 `User` ORM 模型 |
| 1.2 | `backend/app/db/crud.py` | 新增 `create_user`、`get_user_by_username`、`get_user_by_id`、`search_users`、`update_password` |
| 1.3 | `backend/app/models/schemas.py` | 新增 `UserRegister`（含 avatar 字段）、`UserLogin`、`UserInfo`（含 avatar_url）、`ChangePassword`、`UserSearchResult` |
| 1.4 | `backend/app/api/auth.py` | 新增 `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/change-password`、`GET /api/auth/me`、`POST /api/auth/avatar`（上传头像）、`GET /api/auth/default-avatars`（预设头像列表） |
| 1.5 | `backend/app/api/users.py` | 新增 `GET /api/users/search?q=`、`GET /api/users/batch?ids=1,2,3` |
| 1.6 | `backend/app/main.py` | 注册 `auth` 和 `users` 路由；添加 JWT 认证中间件（全量鉴权，白名单：register/login/health） |
| 1.7 | `backend/requirements.txt` | 添加 `pyjwt`、`passlib[bcrypt]` 依赖 |
| 1.8 | `backend/app/config.py` | 添加 `JWT_SECRET` 配置项 |

### 前端

| # | 文件 | 变更 |
|---|------|------|
| 1.9 | `frontend/src/composables/useAuth.ts` | 新增：登录/注册/修改密码/logout/获取当前用户 |
| 1.10 | `frontend/src/composables/useApi.ts` | 修改：自动附加 `Authorization: Bearer <token>` 头；捕获 401 自动跳转登录页 |
| 1.11 | `frontend/src/components/LoginView.vue` | 新增：登录页面 |
| 1.12 | `frontend/src/components/RegisterView.vue` | 新增：注册页面（含 5 个预设默认头像选择 + 自定义上传头像，支持 png/svg/jpeg/gif） |
| 1.13 | `frontend/src/components/Header.vue` | 修改：右侧显示用户圆形头像，点击弹出下拉菜单（昵称、修改密码、退出登录） |
| 1.14 | `frontend/src/router/index.ts` | 新增 `/login`、`/register` 路由；添加路由守卫，未登录只能访问 login/register |
| 1.15 | `frontend/src/types.ts` | 新增用户相关类型 |
| 1.16 | `frontend/src/components/ChangePasswordModal.vue` | 新增：修改密码弹窗 |
| 1.17 | `frontend/src/components/UserMenu.vue` | 新增：头像下拉菜单组件（含用户信息、修改密码入口、退出按钮） |
| 1.18 | `frontend/src/assets/default-avatars.ts` | 新增：5 个预设默认头像的 SVG 数据 |

---

## 迭代 2：项目创建者 + 项目成员管理

### 后端

| # | 文件 | 变更 |
|---|------|------|
| 2.1 | `backend/app/db/models.py` | 新增 `ProjectMember` ORM 模型；`Project` 增加 `creator_id` 字段 |
| 2.2 | `backend/app/db/crud.py` | 新增 `add_project_member`、`remove_project_member`、`list_project_members`、`is_project_member`、`is_project_creator` |
| 2.3 | `backend/app/api/projects.py` | 修改 `create_project` API 自动设置 `creator_id`；新增 `GET/POST /{id}/members`、`DELETE /{id}/members/{user_id}`；新增 `GET /{id}/overview`；修改 `GET /{id}` 返回创建人信息 |
| 2.4 | `backend/app/models/schemas.py` | 新增 `MemberInfo`、`ProjectOverview` |

### 前端

| # | 文件 | 变更 |
|---|------|------|
| 2.5 | `frontend/src/composables/useProject.ts` | 新增成员管理相关方法 |
| 2.6 | `frontend/src/types.ts` | 新增成员相关类型 |

---

## 迭代 3：缺陷管理（后端）

### 后端

| # | 文件 | 变更 |
|---|------|------|
| 3.1 | `backend/app/db/models.py` | 新增 `Defect`、`DefectModule`、`DefectAttachment`、`DefectLog` ORM 模型 |
| 3.2 | `backend/app/db/crud.py` | 新增缺陷 CRUD、状态转换、附件 CRUD、模块 CRUD、最近缺陷查询 |
| 3.3 | `backend/app/models/schemas.py` | 新增 `DefectCreate`、`DefectUpdate`、`DefectInfo`、`DefectModuleCreate`、`DefectModuleInfo`、`DefectAttachmentInfo`、`DefectLogInfo` |
| 3.4 | `backend/app/api/defects.py` | 新增缺陷 CRUD + 状态转换 + 附件 + 模块 API |
| 3.5 | `backend/app/main.py` | 注册 `defects` 路由 |
| 3.6 | `backend/app/config.py` | 添加 `DEFECTS_ATTACHMENT_DIR` 配置 |

### 关键状态转换逻辑

```python
STATUS_TRANSITIONS = {
    '未确认': {'confirm': '已确认'},
    '已确认': {'assign': '处理中', 'close': '已关闭'},
    '处理中': {'resolve': '已解决'},
    '已解决': {'close': '已关闭', 'activate': '处理中'},
    '已关闭': {'activate': '处理中'},
}
```

---

## 迭代 4：缺陷管理（前端）

### 前端

| # | 文件 | 变更 |
|---|------|------|
| 4.1 | `frontend/src/composables/useDefect.ts` | 新增：缺陷 CRUD、状态转换、模块管理、附件管理 |
| 4.2 | `frontend/src/components/DefectListView.vue` | 新增：缺陷列表页面（表格 + 筛选） |
| 4.3 | `frontend/src/components/DefectDetailView.vue` | 新增：缺陷详情页（富文本描述、操作日志、附件） |
| 4.4 | `frontend/src/components/DefectCreateModal.vue` | 新增：创建缺陷弹窗（富文本编辑器） |
| 4.5 | `frontend/src/components/DefectModuleManageModal.vue` | 新增：模块管理弹窗 |
| 4.6 | `frontend/src/router/index.ts` | 新增 `/defects` 路由 |
| 4.7 | `frontend/src/components/Header.vue` | 修改：导航增加"缺陷管理"按钮 |
| 4.8 | `frontend/src/types.ts` | 新增缺陷相关类型 |
| 4.9 | `frontend/package.json` | 添加富文本编辑器依赖（如 `@tiptap/vue-3`） |

---

## 迭代 5：项目详情面板

### 后端

| # | 文件 | 变更 |
|---|------|------|
| 5.1 | `backend/app/db/models.py` | 新增 `ProjectNote` ORM 模型 |
| 5.2 | `backend/app/db/crud.py` | 新增 `get_project_note`、`update_project_note`、`get_project_overview` |
| 5.3 | `backend/app/api/projects.py` | 新增 `GET/PUT /{id}/notes` 路由 |

### 前端

| # | 文件 | 变更 |
|---|------|------|
| 5.4 | `frontend/src/components/TestProjectsView.vue` | 重构为左右分栏布局 |
| 5.5 | `frontend/src/components/ProjectDetailPanel.vue` | 新增：右侧详情面板（无子导航，垂直排列项目信息、最近缺陷、最近测试任务、备注） |
| 5.6 | `frontend/src/components/ProjectInfoSection.vue` | 新增：项目信息区块（名称、创建人、成员管理入口） |
| 5.7 | `frontend/src/components/ProjectRecentDefects.vue` | 新增：最近缺陷区块（最近 2 条） |
| 5.8 | `frontend/src/components/ProjectRecentTasks.vue` | 新增：最近测试任务区块（最近 2 条，可点击跳转） |
| 5.9 | `frontend/src/components/ProjectNotesSection.vue` | 新增：备注区块（Markdown 渲染 + 编辑切换） |
| 5.10 | `frontend/src/components/ProjectMemberManageModal.vue` | 新增：成员管理弹窗（搜索用户、添加、移除） |
| 5.11 | `frontend/src/types.ts` | 新增项目详情相关类型 |

---

## 依赖关系

```
迭代 1 (用户系统) ──────────→ 迭代 2 (项目成员) ──→ 迭代 5 (项目详情面板)
                                        │
                                        └─────────→ 迭代 3 (缺陷后端) ──→ 迭代 4 (缺陷前端)
```

- 迭代 1 是**前置依赖**，所有迭代都需要用户系统
- 迭代 2 依赖迭代 1
- 迭代 3 依赖迭代 1（缺陷需要创建者/指派给）
- 迭代 4 依赖迭代 3
- 迭代 5 依赖迭代 1 + 2 + 3（项目详情需要成员管理 + 最近缺陷）