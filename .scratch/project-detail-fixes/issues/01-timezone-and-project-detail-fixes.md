# 修复项目概览页时间、状态卡片与最近面板问题

Status: needs-triage

## 问题清单

1. **后端所有接口返回的时间格式不对**
   - 现象：接口返回如 `2026-08-05T06:29:15`，为 UTC 无时区标记
   - 期望：加上时区偏移，如 `2026-08-05T14:29:15+08:00`（东八区）
   - 范围：`backend/app/db/crud.py` 中所有 `.isoformat()` 序列化点、`backend/app/api/auth.py` 注册接口返回的 `created_at`

2. **项目状态卡片背景色和文字颜色相同，文字显示不出来**
   - 现象：`空闲` 徽标 `background-color: var(--text-muted)` 与 `color: var(--text-tertiary)`，而 `--text-tertiary: var(--text-muted)`，颜色相同导致文字不可见
   - 位置：`frontend/src/components/TestProjectsView.vue` 项目卡片状态徽标

3. **项目路径应放到右侧项目简介下**
   - 现象：路径显示在左侧项目卡片的信息框中（`truncate max-w-[60%]`）
   - 期望：路径放到右侧项目简介（Project Information）区域，左侧卡片不再显示路径

4. **测试任务执行的时长没显示出来**
   - 现象：最近测试任务卡片显示 `执行: --`
   - 原因：`get_recent_executions` 未返回 `duration` 字段，前端 `task.duration` 为空
   - 期望：后端根据 `start_time`/`end_time` 计算并返回 `duration`（格式同报告 `5ms / 1.5s / 2m5s`）

5. **最近缺陷 / 最近测试任务面板**
   - 移除"查看全部缺陷"、"查看全部任务"按钮
   - 两个面板各展示最近 5 条即可，不限时间
   - 缺陷卡片需要展示缺陷状态和最近的操作日志（`defect_logs`）

## 验收

- [x] 接口时间带 `+08:00` 偏移，前端显示为本地时间
- [x] `空闲` 徽标文字清晰可见
- [x] 左侧项目卡片不再显示路径，路径仅在右侧简介区展示
- [x] 已完成执行的最近任务卡片显示执行时长
- [x] 最近缺陷/任务各 5 条，无"查看全部"按钮；缺陷卡片含状态与最近操作日志

## 修复记录

- 后端 `backend/app/db/crud.py`：新增 `dt_iso()` / `dt_iso_from_str()` / `fmt_duration_ms()` / `duration_between()` helper；全部序列化点改为输出 UTC+8 偏移；`get_recent_executions` 返回 `duration`；新增 `get_recent_defect_logs()`
- 后端 `backend/app/api/projects.py`：`get_project_detail` 最近缺陷/任务改为 5 条，缺陷附 `recent_logs`（含操作人）
- 后端 `backend/app/api/auth.py`：注册返回的 `created_at` 加时区偏移
- 前端 `frontend/src/components/TestProjectsView.vue`：修复"空闲"徽标配色（`--card-bg-2`/`--text-secondary`）；路径移至右侧简介区；缺陷卡片加状态徽标与最近操作日志；移除两个"查看全部"按钮
- 已验证：项目列表/详情、缺陷详情接口均返回 `+08:00`；任务时长如 `17.0s`、`25m7s`
