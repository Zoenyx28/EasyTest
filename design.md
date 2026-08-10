# EasyTest 前端设计规范（Claymorphism）

> 本文档是 EasyTest 项目视觉风格与组件样式的**唯一设计依据**。
> **创建任何新页面 / 新组件之前，必须先阅读本规范，并严格按照其中的 token 与组件规则进行设计。**
> 所有样式一律使用 `frontend/src/index.css` 中的设计 token（CSS 变量），禁止硬编码色值、字体栈、圆角、阴影。
> 设计决策背景见 [docs/adr/0010-claymorphism-design-system.md](docs/adr/0010-claymorphism-design-system.md)。

---

## 0. 风格总览

本项目为 **Claymorphism（黏土拟态）** 风格：圆润饱满的色块、**粗硬描边 + 硬偏移投影**（形如立体黏土按压）、暖白底色、糖果色点缀。核心语言：

- **硬描边 `--outline`**：跟随文字色（亮色深灰 / 暗色浅灰），常规控件 `2~3px` 粗，是全站最有辨识度的元素
- **硬偏移阴影 `--shadow-hard-*`**：`Npx Npx 0` 无模糊投影，按下时阴影收缩、元素"下沉"
- **软阴影 `--shadow-*`**：用于弹层浮起、卡片悬浮的柔和投影
- 支持**明暗双主题**（`data-theme="dark"` 切换），以下色值均已固化为 CSS 变量，写样式时**只用变量名，不写死值**

---

## 1. 配色

### 1.1 主色 Primary（桃粉，装饰性）

> 桃粉**不作为主按钮色**，仅用于：装饰色块 / 图标底 / 选中态背景 / 输入框焦点光环 / 导航激活 Tab。

| 场景 | Light | Dark |
|---|---|---|
| 主色 `--color-primary` | `#FDBCB4` | `#FDBCB4` |
| 主色加深 `--color-primary-dark` | `#F5A69D` | `#F5A69D` |
| 主色柔和底 `--color-primary-soft` | `rgba(253,188,180,0.20)` | `rgba(253,188,180,0.18)` |

### 1.2 CTA 绿（主按钮 / 链接 / 行动号召）

| 场景 | Light | Dark |
|---|---|---|
| CTA `--cta`（别名 `--accent`） | `#22C55E` | `#4ADE80` |
| CTA 加深 `--cta-dark` | `#16A34A` | `#22C55E` |
| CTA 柔和底 `--cta-soft`（别名 `--accent-soft`） | `rgba(34,197,94,0.15)` | `rgba(74,222,128,0.15)` |

### 1.3 Secondary 浅蓝（次级按钮 / 辅助块）

| 场景 | Light | Dark |
|---|---|---|
| 次级 `--color-secondary` | `#ADD8E6` | `#8BC4D6` |
| 次级加深 `--color-secondary-dark` | `#8BC4D6` | `#ADD8E6` |
| 次级柔和底 `--color-secondary-soft` | `rgba(173,216,230,0.25)` | `rgba(139,196,214,0.20)` |

### 1.4 装饰糖果色

| 变量 | Light | Dark | 用途 |
|---|---|---|---|
| `--lavender` | `#E6E6FA` | `#A78BFA` | 装饰色块、图标底 |
| `--mint` | `#98FF98` | `#4ADE80` | 装饰色块、图标底 |

> 糖果色仅作点缀，禁止作为大面积底色或文字色。

### 1.5 强调色 Accent（橙，高风险专用）

> ⚠️ 橙色**仅用于**高风险操作 / 警告 / P0-P1 优先级（ADR-0008 约束沿用），**禁止**用于常规 CTA。

| 场景 | Light | Dark |
|---|---|---|
| 强调色 `--color-accent` | `#EA580C` | `#F97316` |
| 悬停加深 `--color-accent-dark` | `#C2410C` | `#EA580C` |

### 1.6 状态色（Status）

| 语义 | 变量 | Light | Dark |
|---|---|---|---|
| 成功/通过 | `--color-success` | `#16A34A` | `#22C55E` |
| 危险/失败/删除 | `--color-danger` | `#DC2626` | `#EF4444` |
| 警告 | `--color-warning` | `#F59E0B` | `#F59E0B` |
| 异常/Broken（紫） | `--color-broken` | `#7C3AED` | `#A78BFA` |
| 跳过/Skipped | `--skipped` | 同 `--text-muted` | 同 `--text-muted` |

状态标签柔和底色统一为 12%~15% 透明度：`--success-soft` / `--danger-soft` / `--warning-soft`。

优先级（severity）标签有独立色板：`--priority-p0-bg/-text`（红）… `--priority-p3-bg/-text`（绿）；状态标签同理：`--status-confirmed-*` / `--status-in-progress-*` / `--status-resolved-*`（见 index.css，明暗各一套）。

### 1.7 背景色（Background，暖白系）

| 场景 | 变量 | Light | Dark |
|---|---|---|---|
| 窗口底色 | `--bg-window` | `#FFF9F5` | `#0B0B10` |
| 侧栏/工具栏（玻璃拟态） | `--bg-sidebar` | `rgba(255,249,245,0.85)` | `rgba(11,11,16,0.85)` |
| 内容区 | `--bg-content` | `#FFFFFF` | `#0B0B10` |
| 卡片 | `--bg-card` | `#FFFFFF` | `#121218` |
| 卡片悬停 | `--bg-card-hover` | `#FFF0E9` | `#1E1E28` |
| 柔和底色（次级卡片/菜单分隔） | `--bg-soft` | `#FFF0E9` | `#1E1E28` |
| 弱化底 | `--bg-muted` | `#FFF9F5` | `#121218` |
| 输入框底 | `--bg-input` | `#FFF0E9` | `rgba(255,255,255,0.06)` |
| 悬停覆盖色 | `--hover-bg` | `rgba(0,0,0,0.04)` | `rgba(255,255,255,0.04)` |

### 1.8 边框（Border）

| 场景 | 变量 | Light | Dark |
|---|---|---|---|
| 软边框（细分隔线） | `--border` | `#E2E8F0` | `#1E293B` |
| 软边框悬停 | `--border-hover` | `#CBD5E1` | `#334155` |
| **硬描边（Clay）** | `--outline` | `#2D3748` | `#E2E8F0` |

> `--outline` 是 Claymorphism 的核心 token：按钮、输入框、弹窗、卡片、Tab 等控件的粗描边统一用它，随主题自动切换深浅。

### 1.9 文字色（Text）

| 场景 | 变量 | Light | Dark |
|---|---|---|---|
| 主文字 | `--text-primary` | `#2D3748` | `#F8FAFC` |
| 次要文字 | `--text-secondary` | `#475569` | `#94A3B8` |
| 弱化/占位文字 | `--text-muted` | `#64748B` | `#64748B` |

### 1.10 交互态（Interaction）

| 场景 | 变量 | Light | Dark |
|---|---|---|---|
| 悬停覆盖 | `--hover-bg` | `rgba(0,0,0,0.04)` | `rgba(255,255,255,0.04)` |
| 选中态底（桃粉软底） | `--selected-bg` | `rgba(253,188,180,0.25)` | `rgba(253,188,180,0.18)` |

---

## 2. 字体

| 用途 | 字体变量 | 字体栈 |
|---|---|---|
| 标题 | `--font-heading` | `"Fredoka", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif` |
| 正文 | `--font` | `"Nunito", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif` |
| 代码/日志 | `--font-mono` | `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace` |

- 西文用 Fredoka（标题，字重 300~700）+ Nunito（正文，字重 200~1000），中文走系统字体栈，**不引入中文字体文件**。
- 字体文件自托管于 `frontend/public/fonts/`（Fredoka.ttf / Nunito.ttf，OFL 开源协议，许可证文件随仓库保留）。
- `h1~h6` 一律使用 `--font-heading`；代码、执行日志统一使用 `--font-mono`（或 `.font-code` 类）。

### 2.1 字号（Font Size）

| 级别 | 字号 | 字重 | 使用场景 |
|---|---|---|---|
| 页面/区块标题 | `15px` | 600 semibold | 任务详情标题、侧栏标题 |
| 次级标题/弹窗标题 | `13px` | 600 semibold | 弹窗标题、logo 文字 |
| 卡片标题 | `13px` | 500 medium | 任务卡片、列表项标题 |
| 正文/按钮默认 | `12.5px` | 400/600 | 按钮、输入框、菜单项、正文 |
| 辅助文字 | `12px` | 400/500 | 标签文字、说明、弹窗标题栏 |
| 弱注释 | `11px` | 400 | 计数、时间、次级信息 |
| 标签（Tag） | `10.5px`(sm) / `11.5px`(md) | 600 semibold | 状态/优先级标签 |

### 2.2 字重（Weight）

- `400` regular：正文
- `500` medium：卡片标题、菜单项
- `600` semibold：标题、按钮、标签
- `700` bold：强调

### 2.3 行高（Line Height）

- 正文/按钮：`1.4`
- 代码日志：`1.6`（日志面板 `leading-[1.6]`）
- 标题：紧凑（可叠加 `tracking-[-0.01em]` 微调字距）

---

## 3. 间距

间距遵循 4px 基线，统一用 Tailwind 间距类（`gap-*`、`px-*`、`py-*`、`mb-*`、`space-y-*`），不要使用零散的自定义值。

### 3.1 常用间距档位

| 档位 | 值 | 使用场景 |
|---|---|---|
| 微距 | 2px | 导航 tab 间隙 |
| 小距 | 6px / 8px | 图标与文字、表单字段间、列表项间（`gap-2`/`space-y-2`） |
| 中距 | 10px / 12px | 卡片内边距、工具行、模块内部 |
| 大距 | 16px / 20px | 侧栏标题、内容区左右留白、弹窗 footer |
| 超大 | 24px | 主内容区左右留白（`px-[24px]`） |

### 3.2 模块间距（页面结构）

| 模块 | 规则 |
|---|---|
| 顶部导航栏 | 高度 `56px`（`h-14`），左右内边距 `20px`（`px-5`），固定在顶部，3px 底部硬描边 |
| 主内容区 | 相对导航栏 `pt-[56px]`，内容区 `px-[24px]` + 底部 `pb-[20px]` |
| 页面标题行 | 顶部 `pt-[20px]`、底部 `pb-[16px]`，标题与副信息纵向 `gap-[6px]` |
| 卡片列表 | 卡片之间 `space-y-[8px]` |
| 侧栏 | 宽 `260px`，标题行 `px-16px py-12px`，列表区 `px-12px pb-10px` |

### 3.3 组件内边距

| 组件 | 内边距 |
|---|---|
| 按钮 sm | `5px 12px` |
| 按钮 md | `7px 14px` |
| 输入框 | `7px 12px` |
| 卡片 | `12px` |
| 弹窗头部 | `12px 16px` |
| 弹窗底部操作区 | `14px 20px` |
| 下拉菜单项 | `8px 14px`（横向 `px-3 py-2` 亦可） |
| 标签 Tag sm/md | `2px 8px` / `3px 10px` |

---

## 4. 组件样式

### 4.1 圆角（Radius，Clay 大圆角）

| 档位 | 变量 | 值 | 使用场景 |
|---|---|---|---|
| 大 | `--radius-lg` | `24px` | 弹窗面板 |
| 中 | `--radius-md` | `16px` | 卡片、按钮、下拉菜单 |
| 小 | `--radius-sm` | `12px` | 输入框、导航 Tab 容器、分支选择器 |
| 全圆 | — | `999px` | 标签 Tag、头像、主题切换按钮 |

### 4.2 阴影（Shadow）

#### 4.2.1 软阴影（弹层浮起 / 卡片悬浮）

| 档位 | 变量 | Light 值 | 使用场景 |
|---|---|---|---|
| 极小 | `--shadow-xs` | `0 1px 2px rgba(0,0,0,0.04)` | 极小元素 |
| 小 | `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.04)` | 常规悬浮 |
| 卡片 | `--shadow-card` | `0 1px 3px rgba(0,0,0,0.08)` | 卡片悬浮 |
| 弹层 | `--shadow-popover` | `0 8px 24px rgba(0,0,0,0.10)` | 下拉菜单、气泡 |
| 弹窗 | `--shadow-dialog` | `0 20px 50px rgba(0,0,0,0.15)` | 模态弹窗 |
| 遮罩 | `--overlay-bg` | `rgba(0,0,0,0.4)` | 弹窗背景遮罩 |

#### 4.2.2 硬偏移阴影（Clay 核心，无模糊）

| 档位 | 变量 | 值 |
|---|---|---|
| 小 | `--shadow-hard-sm` | `3px 3px 0 var(--outline)` |
| 中 | `--shadow-hard-md` | `4px 4px 0 var(--outline)` |
| 大 | `--shadow-hard-lg` | `6px 6px 0 var(--outline)` |
| 小按下 | `--shadow-hard-sm-pressed` | `1px 1px 0 var(--outline)` |
| 中按下 | `--shadow-hard-md-pressed` | `2px 2px 0 var(--outline)` |
| 大按下 | `--shadow-hard-lg-pressed` | `3px 3px 0 var(--outline)` |

> **交互语言**：可点击元素默认带硬阴影（"浮起"）；hover/按下时阴影收缩为 pressed 态并 `translate(2px, 2px)`（"下沉"）。暗色下硬阴影透明度提升（`rgba(226,232,240,0.55)`），用法不变。

### 4.3 按钮（BaseButton）

- **变体**：`primary`（CTA 绿，常规行动）/ `secondary`（浅蓝，次级）/ `ghost`（文字，无描边无阴影）/ `danger`（红）/ `warning`（橙，仅高风险，ADR-0008）
- **规格**：`sm`（`12px` 字）/ `md`（`12.5px` 字）
- 结构：**3px 硬描边 `var(--outline)` + 圆角 `--radius-md` + 阴影 `--shadow-hard-md`**，字重 600，行高 1.4，图标与文字 `gap-6px`
- 交互：hover → `translate(2px,2px)` + `--shadow-hard-md-pressed`（下沉）；active → 完全压下（`translate(3px,3px)`、阴影归零）；禁用态 `opacity: 0.5`
- primary 悬停 → `--cta-dark`；secondary 悬停 → `--color-secondary-dark`；danger 悬停 → `brightness(0.92)`
- 带 loading 时显示旋转 spinner
- **优先复用 `base/BaseButton.vue`，不要手写按钮样式**

### 4.4 卡片

- 常规卡片：背景 `--bg-card`，`1px solid var(--border)` 软边框，圆角 `--radius-md`，轻阴影；悬停 `translateY(-1px)` + 阴影加深
- 立体卡片（Clay 面）：**2px 硬描边 `var(--outline)` + 圆角 `--radius-sm`/`--radius-md` + `--shadow-hard-sm`**，选中态底 `--selected-bg` 桃粉软底
- 悬停背景 `--bg-card-hover`；悬停动效 `transition-all`

### 4.5 导航栏（Header）

- 整体：高度 `56px`、固定顶部、玻璃拟态 `backdrop-filter: blur(20px)`（`.glass` 类）、背景 `--bg-sidebar`、**3px 底部硬描边 `var(--outline)`**
- 导航 Tab：容器圆角 `--radius-sm` 的 `--bg-input` 底（`gap-2px`）；**激活项** = 桃粉底 `--color-primary` + `2px solid var(--outline)` 描边 + `--shadow-hard-sm` + 主文字色 600；未激活 = 透明底 + 次要文字色，hover 时桃粉软底
- 右侧操作区（分支选择器、主题切换、用户菜单）`gap-2`
- 分支选择器按钮：`2px solid var(--outline)` + 圆角 `--radius-sm` + `--shadow-hard-sm`，hover 下沉
- 主题切换按钮：胶囊形（`rounded-full`），`--bg-input` 底 + 硬描边

### 4.6 弹窗（BaseDialog / modal-panel）

- 面板：宽默认 `520px`，圆角 `--radius-lg`，**3px 硬描边 `var(--outline)`**，阴影 `--shadow-hard-lg, var(--shadow-dialog)` 叠加
- 遮罩：`--overlay-bg` + `backdrop-filter: blur(6px)`
- **标题栏（全站统一）**：左对齐标题（`--font-heading` 13~15px/600）+ 右侧 × 关闭按钮。关闭按钮规格固定：`32×32`、`2px solid var(--outline)` 描边、圆角 `--radius-sm`、底 `--bg-soft`、`--shadow-hard-sm`，hover 时桃粉软底 + 下沉（`translate(2px,2px)` + pressed 阴影）。不再使用 macOS 红黄绿交通灯
- 底部操作区：右对齐、`gap-8px`、顶部 `2px solid var(--outline)` 描边
- 进出场动画：透明度 0.18s + 面板 `scale(0.96)`
- 小弹窗（如确认框）：宽 `340~380px`，圆角 `--radius-md`，内边距 `20px`

### 4.7 输入框（BaseInput）

- **2px 硬描边 `var(--outline)` + 圆角 `--radius-sm` + 内凹阴影 `--shadow-hard-sm-pressed`**，内边距 `7px 12px`，字号 `12.5px`，底 `--bg-input`
- 聚焦态：描边变 `--color-primary` + `0 0 0 3px var(--color-primary-soft)` 光环，底色转 `--bg-card`
- 占位符 `--text-muted`；禁用态 `opacity: 0.6`

### 4.8 标签 Tag（BaseTag）

- 胶囊形（`999px`），字重 600，可带 5px 状态圆点
- **sm**：`1.5px` 硬描边；**md**：`2px` 硬描边 + `--shadow-hard-sm`
- tone：`red / orange / yellow / green / blue / purple / gray`，颜色映射见 1.6 状态色与优先级色

### 4.9 下拉菜单（Menu / Dropdown）

- 面板：`--bg-card` 底 + **2px 硬描边 `var(--outline)`** + 圆角 `--radius-md` + 阴影 `--shadow-hard-lg, var(--shadow-popover)` 叠加
- 菜单项：`12.5px`，悬停 `--hover-bg`；危险项用 `--danger` 色；选中项 `--accent-bg`（桃粉软底）底 + `--accent`（CTA 绿）文字
- 分组分隔线：`1px solid var(--border)`，距左右 `8px` 内缩

### 4.10 表格

- 采用**紧凑行高**（ADR-0008 吸收方案 C），保证数据密度
- 表头/数据文字用 `12~12.5px`，行悬停 `--row-hover`

### 4.11 其他约定

- **滚动条**：宽 `6px`，轨道透明，滑块 `--text-muted`（悬停 `--text-secondary`），圆角 `4px`
- **Toast**：右下角 `20px` 定位，`--bg-card` 底 + 圆角 `12px` + **`var(--outline)` 描边** + 阴影 `--shadow-hard-sm, 0 10px 24px rgba(0,0,0,.16)`，12.5px 文字，前置 7px CTA 绿圆点，0.18s 位移动画
- **空状态**：居中，图标 `opacity-30`，说明文字 `--text-muted`
- **动画节奏**：交互过渡统一 `0.15s ease`，弹窗/Toast `0.18s ease`，Clay 按压位移 `2~3px`
- **玻璃拟态**：侧栏、导航栏使用 `.glass`（`backdrop-filter: blur(20px)`）

---

## 5. 使用约束（铁律）

1. **只用 token**：所有颜色、字体、圆角、阴影必须引用 `index.css` 中的 CSS 变量，禁止硬编码。
2. **硬描边统一用 `--outline`**：Clay 风格的关键是描边与硬阴影，禁止混用深浅不一的写死描边色。
3. **复用基础组件**：按钮/输入框/弹窗/标签优先使用 `base/` 下的规范组件，不重复造轮子。
4. **遵循圆角/阴影档位**：不要引入规范之外的圆角、阴影值。
5. **桃粉不是主按钮色**：主按钮一律 CTA 绿；桃粉仅作装饰/选中/焦点用途。
6. **橙色慎用**：`--color-accent`（橙）仅用于高风险操作与警告。
7. **新增设计元素**：若规范未覆盖，需先在 `index.css` 定义 token 并在本文档登记，再投入使用。
