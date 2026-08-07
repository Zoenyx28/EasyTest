# 问题跟踪器：GitLab

本仓库的 issue 和 PRD 存放在 GitLab 的 issue 中。所有操作使用 [`glab`](https://gitlab.com/gitlab-org/cli) CLI。

> **自托管说明：** 本仓库的远程地址是自托管的 GitLab（`git@10.19.13.46:zouyang7/EasyTest.git`）。请先通过 `glab auth login --hostname`（或设置 `GITLAB_HOST`）让 `glab` 指向该实例，之后命令才能正确解析本仓库。

## 约定

- **创建 issue**：`glab issue create --title "..." --description "..."`。多行描述请使用 heredoc；传 `--description -` 会打开编辑器。
- **查看 issue**：`glab issue view <number> --comments`。需要机器可读输出时加 `-F json`。
- **列出 issue**：`glab issue list -F json`，配合 `--label` 过滤器使用。
- **评论 issue**：`glab issue note <number> --message "..."`。GitLab 把评论称为 "notes"。
- **应用 / 移除标签**：`glab issue update <number> --label "..."` / `--unlabel "..."`。多个标签可用逗号分隔或重复该标志。
- **关闭**：`glab issue close <number>`。`glab issue close` 不接受关闭评论，因此先用 `glab issue note <number> --message "..."` 发布说明，再关闭。
- **合并请求**：GitLab 将 PR 称为"合并请求"。使用 `glab mr create`、`glab mr view`、`glab mr note` 等 — 与 `gh pr ...` 形状相同，只是把 `pr` 换成 `mr`、把 `comment`/`--body` 换成 `note`/`--message`。

仓库的推断来自 `git remote -v` — 在克隆内运行时 `glab` 会自动完成。

## 合并请求作为分诊入口

**MR 作为请求入口：否。**（如果本仓库把外部合并请求当作功能请求，请设为 `yes`；`/triage` 会读取此标志。）

设为 `yes` 时，MR 与 issue 走相同的标签和状态，使用 `glab mr` 对应命令：

- **查看 MR**：`glab mr view <number> --comments`；`glab mr diff <number>` 查看差异。
- **列出待分诊的外部 MR**：`glab mr list -F json`，只保留作者不是项目成员/拥有者的 MR（贡献者的 MR，而非维护者在做的进行中工作）。
- **评论 / 打标签 / 关闭**：`glab mr note`、`glab mr update --label`/`--unlabel`、`glab mr close`。

与 GitHub 不同，GitLab 分别对 issue 和 MR 编号，因此一旦确认维护者指的是哪个入口，`#42` 就不会有歧义。

## 当技能说"发布到问题跟踪器"

创建一个 GitLab issue。

## 当技能说"获取相关 ticket"

运行 `glab issue view <number> --comments`。

## Wayfinding 操作

由 `/wayfinder` 使用。**map** 是一个 issue，**子** issue 作为 ticket。

- **Map**：一个带 `wayfinder:map` 标签的 issue，承载 Notes / Decisions-so-far / Fog 正文。`glab issue create --label wayfinder:map`。（在支持原生 epics 的 GitLab 版本上，map 也可由 epic 承载；带标签的 issue 在任何地方都可用。）
- **子 ticket**：描述顶部带有 `Part of #<map>` 且带有 `wayfinder:<type>` 标签（`research`/`prototype`/`grilling`/`task`）的 issue。一旦被认领，ticket 会指派给负责的开发者。
- **阻塞**：GitLab 的**原生阻塞链接** — 规范的、UI 可见的表示方式。通过快速操作 `/blocked_by #<n>` 添加，以 note 形式发布（`glab issue note <child> --message "/blocked_by #<blocker>"`）。原生阻塞链接是 Premium/Ultimate 功能；在免费版（或不可用的情况下）回退到描述顶部的 `Blocked by: #<n>, #<n>` 一行。当所有阻塞项都已关闭时，ticket 解除阻塞。
- **Frontier 查询**：`glab issue list -F json` 限定到 map 的子项，剔除任何有未关闭阻塞项的 — 指向未关闭 issue 的原生 `blocked_by` 链接（`glab api projects/:id/issues/:iid/links`），或 `Blocked by` 一行中未关闭的 issue — 或已有指派人的，按 map 顺序取第一个。
- **认领**：`glab issue update <n> --assignee @me` — 会话的第一次写入。
- **解决**：`glab issue note <n> --message "<answer>"`，然后 `glab issue close <n>`，再把上下文指针（gist + 链接）追加到 map 的 Decisions-so-far。
