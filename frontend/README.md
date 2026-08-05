# EasyTest Frontend

基于 **Vue 3** + **TypeScript** + **Vite** 的测试管理平台前端。

## 技术栈

- **Vue 3** — Composition API + `<script setup>`
- **TypeScript** — 全量类型定义
- **Vite 6** — 开发构建工具
- **Tailwind CSS 4** — 原子化样式
- **Vue Router** — 前端路由
- **Lucide Vue** — 图标库

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器（默认 http://localhost:5173）
npm run dev
```

开发模式下 Vite 自动代理 `/api` → `http://localhost:8000`，`/ws` → `ws://localhost:8000`，无需额外配置。

## 构建

```bash
npm run build
```

构建产物输出到 `dist/` 目录。

## Docker 部署

### 构建镜像

```bash
docker build -t easy-test-frontend:v1 .
```

### 镜像说明

采用多阶段构建：

1. **build 阶段** — 基于 `node:20-alpine` 安装依赖并构建
2. **serve 阶段** — 基于 `nginx:stable-alpine` 托管静态文件

Nginx 配置了反向代理，将 `/api/` 和 `/ws/` 请求转发到后端服务。

### 环境变量

| 变量 | 说明 |
| --- | --- |
| `VITE_API_BASE` | 可选，API 基础路径（构建时） |

> 注意：生产环境 API 代理地址通过 Nginx 配置（`nginx.conf`）管理，而非前端构建变量。

## Nginx 配置说明

`nginx.conf` 配置了：

- **Gzip 压缩** — 对 JS/CSS/JSON 等资源启用
- **API 代理** — `/api/` 路由到后端 `backend:8000`
- **WebSocket 代理** — `/ws/` 路由到后端 `backend:8000`，支持 Upgrade 协议
- **SPA 回退** — 所有静态资源请求回退到 `index.html`

## 项目结构

```
src/
├── components/          # 页面组件
│   ├── TestOverviewView.vue      # 测试概览
│   ├── TestExecutionView.vue     # 执行监控
│   ├── TestReportsView.vue       # 报告查看
│   ├── TestProjectsView.vue      # 项目管理
│   ├── Header.vue                # 顶部导航
│   ├── Footer.vue                # 底部
│   ├── HelpModal.vue             # 帮助弹窗
│   ├── SettingsModal.vue         # 设置弹窗
│   └── ToastNotification.vue     # 消息通知
├── composables/        # 组合式逻辑
│   ├── useApi.ts                 # API 请求封装
│   ├── useProject.ts             # 项目状态管理
│   └── useWebSocket.ts           # WebSocket 连接
├── router/
│   └── index.ts                  # 路由配置
├── types.ts                      # 全局类型定义
├── App.vue                       # 根组件
├── main.ts                       # 入口
└── index.css                     # 全局样式
```