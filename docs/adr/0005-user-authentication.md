# ADR-0005: 用户认证与注册系统

## Status

Accepted

## Context

平台当前完全开放，所有 API 均可匿名访问。为了实现以下功能，需要引入用户系统：

- **项目详情板块**：项目需要记录创建者、项目成员清单
- **缺陷管理**：缺陷需要记录创建者、指派给特定用户
- **项目成员管理**：项目成员添加/移除操作需要用户身份

需求要点：

- 用户可以自行注册，注册后直接可用，无需管理员审核
- 用户信息仅需：用户名、昵称、密码
- 不区分用户角色（所有用户平等）
- 注册/登录后通过 JWT token 维持会话
- 密码通过 bcrypt 加密存储
- 所有 API 默认需要认证（JWT），仅白名单路径可匿名访问
- 未认证请求返回 401，无权限请求返回 403

## Decision

### 数据模型

新增 `users` 表：

```sql
users
├── id            (PK, auto-increment)
├── username      (VARCHAR 64, UNIQUE, NOT NULL)  — 用户名，登录用
├── nickname      (VARCHAR 128, NOT NULL)          — 昵称，显示用
├── password_hash (VARCHAR 256, NOT NULL)          — bcrypt 哈希密码
├── avatar_url    (VARCHAR 512, DEFAULT '')        — 头像 URL，可选：自定义上传路径 或 预设头像编号（如 `default:1`）
├── is_active     (BOOLEAN, DEFAULT TRUE)          — 账号状态
├── created_at    (DATETIME)
└── updated_at    (DATETIME)
```

### 认证方式

- 使用 **JWT (JSON Web Token)** 进行无状态认证
- Token 过期时间：**7 天**
- Token 通过 `Authorization: Bearer <token>` 请求头传递
- 密码使用 `bcrypt` 哈希（`passlib[bcrypt]`）

### 后端 API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册（username, nickname, password, avatar?） |
| POST | `/api/auth/login` | 登录（username, password）→ 返回 token + user |
| POST | `/api/auth/change-password` | 修改密码（需认证） |
| GET  | `/api/auth/me` | 获取当前用户信息（需认证，含头像 URL） |
| POST | `/api/auth/avatar` | 上传自定义头像（需认证，multipart/form-data） |
| GET  | `/api/auth/default-avatars` | 获取预设头像列表（5 张） |
| GET  | `/api/users/search?q=` | 搜索用户（供添加成员时搜索） |
| GET  | `/api/users/batch?ids=1,2,3` | 批量获取用户信息 |

### 认证策略

- **认证中间件**：解析 `Authorization` 头，验证 JWT 有效性，将用户信息注入 `request.state.user`
- **全量鉴权**：所有 API 默认需要认证，未登录请求返回 401
- **白名单例外**（无需认证即可访问）：

  | 路径 | 说明 |
  |------|------|
  | `POST /api/auth/register` | 注册 |
  | `POST /api/auth/login` | 登录 |
  | `GET /api/health` | 健康检查 |

- 认证失败统一返回 `{code: 401, msg: '未登录或登录已过期', data: null}`
- 权限不足统一返回 `{code: 403, msg: '无权限访问', data: null}`

### 前端实现

- 新增 **登录/注册页面**（路由 `/login` 和 `/register`）
- 注册页提供头像选择：
  - 5 个预设默认头像（圆形彩色图标，标号 1-5）供点击选择
  - 支持自定义上传头像（支持 png、svg、jpeg、gif 格式）
- 登录成功后 token 存储在 `localStorage` 中
- 前端 `useApi` 自动在请求头附加 `Authorization: Bearer <token>`
- 顶部导航栏右侧显示用户头像（圆形），点击弹出下拉菜单：
  - 显示用户昵称
  - "修改密码"入口
  - "退出登录"按钮
- 未登录用户访问任何受保护页面 → 自动跳转到 `/login`
- `useApi` 中统一捕获 401 响应 → 清除 token 并跳转登录页
- 路由守卫：`router.beforeEach` 检查登录状态，未登录只能访问 `/login`、`/register`

### 预设头像

5 个预设默认头像以 SVG 内联方式存储在前后端，颜色各异，形如圆形用户图标加数字标号。前端直接渲染，无需额外请求（注册页即时显示）。后端存储时记录 `default:1` ~ `default:5` 作为头像标识。

### 自定义头像上传

- 支持格式：png、svg、jpeg、gif
- 文件大小限制：2MB
- 存储路径：`PROJECTS_DATA_DIR / avatars / {user_id} / {timestamp}.{ext}`
- 上传后更新 `users.avatar_url` 为存储路径
- 前端通过 `GET /uploads/avatars/{path}` 访问

### 项目模型变更

`projects` 表增加 `creator_id` 字段（FK → users.id），记录项目创建者。

### 项目成员模型

新增 `project_members` 表：

```sql
project_members
├── id          (PK, auto-increment)
├── project_id  (FK → projects.id)
├── user_id     (FK → users.id)
├── created_at  (DATETIME)
└── UNIQUE(project_id, user_id)
```

## Consequences

- **Positive**: 用户系统简单轻量，无复杂角色权限，符合需求
- **Positive**: JWT 无状态认证，无需服务端 session 存储
- **Positive**: 全量鉴权确保数据安全，非成员无法访问项目数据
- **Negative**: 需要增加 `creator_id` 字段迁移和 `project_members` 表
- **Negative**: 现有项目需要设置默认创建者（或允许空值）
- **Negative**: 现有未认证 API 客户端需要改造，增加 token 获取逻辑

## 迁移方案

1. 创建 `users` 表
2. 创建 `project_members` 表
3. 为 `projects` 表添加 `creator_id` 列（允许 NULL）
4. 首次部署时在 `init_db` 中创建默认用户 `admin/admin123`（用户名/密码）
5. 现有项目设置 `creator_id = 1`（指向默认管理员）
6. 部署完成后，所有 API 请求都需要携带 `Authorization: Bearer <token>` 头
7. 5 个预设头像的 SVG 资源在前后端打包时即内置