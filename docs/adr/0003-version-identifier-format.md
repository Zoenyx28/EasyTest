# ADR-0003: Version Identifier Format

## Status

Accepted

## Context

API endpoints that accept a version scope need an identifier for the target branch. Two options exist:

- **Human-readable name** (`?version=v2.0`) — simple but fragile; names change, collide, and may contain URL-unsafe characters.
- **Stable internal ID** (`?version=42` or `?version=a1b2c3d4`) — decouples the URL from the display name; names can be freely edited without breaking links.

Since the `branches` table uses an auto-increment integer PK (`id`), this is the natural choice for the stable identifier.

## Decision

1. Use the primary key of the `branches` table as the version identifier in the URL.
2. Format: `?version=<integer>` — e.g. `/cases?version=1`, `/execution?version=2`.
3. The human-readable branch name is used for display in the UI only.
4. When no `version` parameter is provided, the API defaults to the project's default branch (typically the one with the lowest `id` or a `is_default` flag on the `branches` table).

## Consequences

- **Positive**: URLs survive branch renames.
- **Positive**: Simple integer — no UUID parsing overhead, no URL encoding issues.
- **Positive**: Easy to validate (must be a positive integer).
- **Negative**: Slightly less human-readable when inspecting URLs manually (one can look up the name via an API call).
