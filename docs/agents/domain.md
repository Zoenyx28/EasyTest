# 领域文档

各工程技能在探索代码库时应如何消费本仓库的领域文档。

## 探索前请阅读

- 仓库根目录的 **`CONTEXT.md`**，或
- 如果存在，仓库根目录的 **`CONTEXT-MAP.md`** — 它指向每个上下文一个 `CONTEXT.md`。阅读与主题相关的每个文件。
- **`docs/adr/`** — 阅读与你即将工作的领域相关的 ADR。在多上下文仓库中，还要检查 `src/<context>/docs/adr/` 中上下文专属的决策。

如果这些文件都不存在，请**静默继续**。不要标记它们的缺失，也不要主动建议创建它们。`/domain-modeling` 技能（通过 `/grill-with-docs` 和 `/improve-codebase-architecture` 触达）会在术语或决策真正确定时惰性创建它们。

## 文件结构

单上下文仓库（大多数仓库）：

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

多上下文仓库（根目录存在 `CONTEXT-MAP.md`）：

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 全局决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 上下文专属决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用术语表的词汇

当你的输出命名一个领域概念（在 issue 标题、重构提案、假设、测试名中）时，使用 `CONTEXT.md` 中定义的术语。不要漂移到术语表明确避免的同义词。

如果你需要的概念不在术语表中，这是一个信号 — 要么你在发明项目未使用的语言（请重新考虑），要么存在真正的空缺（为 `/domain-modeling` 记录它）。

## 标记 ADR 冲突

如果你的输出与现有 ADR 矛盾，请明确提出来，而不是静默覆盖：

> _与 ADR-0007（event-sourced orders）矛盾 — 但值得重新讨论，因为…_
