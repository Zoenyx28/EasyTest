# ADR-0002: Branch-Based Data Isolation

## Status

Accepted

## Context

The application needs to support multiple parallel work streams within a single project — conceptually similar to Git branches. Each branch operates independently: its own test case definitions, tasks, executions, and reports. Users must be able to switch between branches to view or work on version-specific data.

The key requirement is that branches must be **cheap to create** (both from an existing branch and as a blank slate) and **fully isolated** — activity in one branch must never leak into another.

## Decision

### Data Model

Add a `branch_id` (integer, foreign key to a new `branches` table) to every version-scoped entity:

| Entity | Table | Branch-Scoped? |
|---|---|---|
| Branch | `branches` | — (defines the scope) |
| TestCaseDefinition | `test_case_definitions` | Yes |
| Task | `tasks` | Yes |
| TaskCase | `task_cases` | Yes |
| Execution | `executions` | Yes |
| ExecutionCase | `execution_cases` | Yes |
| Report | `reports` | Yes |
| Project | `projects` | No (spans branches) |

### Branch Table

```
branches
├── id            (PK, auto-increment)
├── project_id    (FK → projects.id)
├── name          (human-readable, e.g. "main", "v2.0")
├── source_branch_id (nullable FK → branches.id, for "copy from")
├── is_empty      (boolean, true = blank branch requiring import)
├── created_at
└── updated_at
```

### Copy Behaviour

When creating a branch from an existing one (`source_branch_id` is set):

1. Create a new `Branch` row.
2. Deep-copy all `TestCaseDefinition` rows from the source branch — each copy gets a **new ID** (not shared).
3. `Task`, `Execution`, `Report` are **not** copied — the new branch starts with zero tasks.

### Blank Branch Behaviour

When creating a blank branch:

1. Create a new `Branch` row with `is_empty = true`.
2. No `TestCaseDefinition`s are created.
3. User must trigger discovery (import) to populate definitions.

### Query Pattern

Every version-scoped query includes `WHERE branch_id = <active_branch_id>`. The active branch ID is provided as a query parameter in the API (`?version=<branch_id>`).

## Consequences

- **Positive**: Simple, predictable isolation — add one WHERE clause.
- **Positive**: Cheap branching — only metadata + test case definitions are copied.
- **Positive**: Backward-compatible table structure — adding a column, not replacing tables.
- **Negative**: Every query needs a branch_id filter — easy to forget; recommend a DB-layer helper that enforces it.

## Compliance

- All new queries on version-scoped tables MUST include a `branch_id = ?` filter.
- Code review will flag any query that omits it.
