#!/usr/bin/env python3
"""Cleanup old data/git_repo_* directories after migration to unified project data directory.

Usage:
    python scripts/cleanup_old_project_dirs.py          # dry-run (no deletions)
    python scripts/cleanup_old_project_dirs.py --apply   # actually delete

This script checks for directories matching backend/data/git_repo_* and only
deletes them if the corresponding PROJECTS_SOURCE_DIR/project_{id} exists.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# Backend project root (parent of scripts/)
BACKEND_ROOT = Path(__file__).resolve().parent.parent

# Old directory pattern: backend/data/git_repo_{id}
OLD_DATA_DIR = BACKEND_ROOT / "data"

# New directory: use the same logic as config.py
# (config.py may not be importable here if dependencies are missing)
PROJECT_ROOT = BACKEND_ROOT.parent
_DEFAULT_DATA_DIR = (
    str(PROJECT_ROOT / "data" / "projects") if sys.platform == "win32"
    else "/data/local/project"
)
NEW_DATA_DIR = Path(_DEFAULT_DATA_DIR)  # will be overridden by PROJECTS_DATA_DIR if set
NEW_DATA_DIR = Path(os.getenv("PROJECTS_DATA_DIR", str(NEW_DATA_DIR)))
NEW_SOURCE_DIR = NEW_DATA_DIR / "source"


def find_old_dirs() -> list[tuple[int, Path]]:
    """Find all data/git_repo_{id} directories and return (id, path) pairs."""
    results: list[tuple[int, Path]] = []
    if not OLD_DATA_DIR.exists():
        return results
    for p in sorted(OLD_DATA_DIR.iterdir()):
        if p.is_dir() and p.name.startswith("git_repo_"):
            m = re.match(r"git_repo_(\d+)$", p.name)
            if m:
                results.append((int(m.group(1)), p))
    return results


def check_new_dir(project_id: int) -> Path | None:
    """Return the new source directory path if it exists, else None."""
    new_dir = NEW_SOURCE_DIR / f"project_{project_id}"
    return new_dir if new_dir.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup old data/git_repo_* directories")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    args = parser.parse_args()

    old_dirs = find_old_dirs()
    if not old_dirs:
        print("✅ No old data/git_repo_* directories found. Nothing to clean up.")
        return

    print(f"📁 Found {len(old_dirs)} old git_repo_* director{'y' if len(old_dirs) == 1 else 'ies'}:")
    print(f"   New source dir: {NEW_SOURCE_DIR}")
    print()

    deletable: list[Path] = []
    skip_reason: list[tuple[Path, str]] = []

    for pid, old_path in old_dirs:
        new_path = check_new_dir(pid)
        if new_path:
            deletable.append(old_path)
            print(f"   [project_{pid}] {old_path.name} → {new_path}  ✅ safe to delete")
        else:
            skip_reason.append((old_path, f"New directory {NEW_SOURCE_DIR / f'project_{pid}'} does not exist"))
            print(f"   [project_{pid}] {old_path.name} → SKIP (new directory missing)")

    if not deletable:
        print("\n⚠️  No directories are safe to delete. Re-sync the projects first.")
        return

    total_size = sum(
        sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        for p in deletable
    )
    print(f"\n📊 Total deletable: {len(deletable)} director{'y' if len(deletable) == 1 else 'ies'}, ~{total_size / 1024 / 1024:.1f} MB")

    if not args.apply:
        print("\n🔍 Dry-run mode. Run with --apply to actually delete.")
        for p in deletable:
            print(f"   Would delete: {p}")
        return

    for p in deletable:
        try:
            shutil.rmtree(p)
            print(f"   ✅ Deleted: {p}")
        except Exception as e:
            print(f"   ❌ Failed to delete {p}: {e}")

    print("\n✅ Cleanup complete.")


if __name__ == "__main__":
    main()