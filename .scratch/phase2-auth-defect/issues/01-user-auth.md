# 01 — 用户注册与登录认证（含头像）

**What to build:** 完整的用户注册与登录认证功能，包含头像选择，覆盖全栈。

- 注册页提供 5 个预设默认头像（SVG 内联）点击选择 + 自定义上传头像（png/svg/jpeg/gif）
- 登录/注册 API → 前端页面 → token 存入 localStorage
- JWT 全量鉴权中间件，白名单 register/login/health
- 顶部导航栏右侧显示用户圆形头像 → 点击下拉菜单：昵称 / 修改密码 / 退出
- 路由守卫：未登录自动跳转 /login
- 默认管理员用户 admin/admin123

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 用户可自行注册（用户名 + 昵称 + 密码 + 可选头像）
- [ ] 注册时可选 5 个预设默认头像，或上传自定义头像
- [ ] 注册后立即可用，无需审核
- [ ] 已注册用户可登录获取 JWT token
- [ ] 未登录访问受保护页面自动跳转 /login
- [ ] 顶部导航栏右侧显示用户头像，点击弹出下拉菜单（昵称、修改密码、退出）
- [ ] 可修改密码
- [ ] 所有 API 默认需要鉴权（白名单除外）
- [ ] 默认管理员用户 admin/admin123 可用