# ADR-0001: Remove Legacy Models and Unify Data Model

## Status

Accepted

## Context

The codebase currently has two parallel sets of models for execution tracking:

- **Legacy**: `RunRecord` (table: `runs`) and `TestResultRecord` (table: `test_results`)
- **Current**: `Execution` (table: `executions`) and `ExecutionCase` (table: `execution_cases`)

The legacy models were used in an earlier version of the application and are no longer in active use. They complicate maintenance, increase cognitive load, and add unnecessary migration surface area. Since this is a test environment with no production data that must be preserved, a clean break is feasible.

## Decision

1. Drop the `runs` and `test_results` tables entirely.
2. Remove the `RunRecord` and `TestResultRecord` SQLAlchemy model classes.
3. Remove any service or API code that references these models.
4. Create a single Alembic migration (or equivalent) that executes `DROP TABLE IF EXISTS runs, test_results`.

## Consequences

- **Positive**: Cleaner codebase — one path for execution tracking instead of two.
- **Positive**: Reduced confusion for new developers.
- **Negative**: Irreversible — any old data is permanently lost. Acceptable for a test environment.

## Compliance

This repo documents no coding standards beyond what is listed in this ADR. Code review should flag any residual imports or references to the removed models.
