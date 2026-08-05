"""Test discovery service - scans pytest test cases using --collect-only."""
from __future__ import annotations
import ast
import asyncio
import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path

from app.config import PROJECTS_SOURCE_DIR

_log = logging.getLogger("discoverer")

from app.models.schemas import TestCaseInfo, TestClassInfo, TestModuleInfo, DiscoverResponse


def _nodeid_to_uid(nodeid: str) -> str:
    """Generate a stable uid from pytest nodeid."""
    return hashlib.md5(nodeid.encode()).hexdigest()[:36]


def _extract_docstrings(file_paths: set[str], base_path: Path) -> dict[str, str]:
    """Parse Python test files with AST to extract function/class docstrings.

    Returns a dict mapping 'ClassName::method_name' -> docstring first line.
    """
    doc_map: dict[str, str] = {}
    for fpath in file_paths:
        full_path = base_path / fpath
        if not full_path.exists():
            continue
        try:
            source = full_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
        except Exception:
            continue

        current_class: str | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                current_class = node.name
                # Also extract class docstring
                cls_doc = ast.get_docstring(node)
                if cls_doc:
                    doc_map[node.name] = cls_doc.strip().split('\n')[0]
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_doc = ast.get_docstring(node)
                if func_doc:
                    key = f'{current_class}::{node.name}' if current_class else node.name
                    doc_map[key] = func_doc.strip().split('\n')[0]
        # Handle module-level test functions (not in a class)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_doc = ast.get_docstring(node)
                if func_doc and node.name not in doc_map:
                    doc_map[node.name] = func_doc.strip().split('\n')[0]
    return doc_map


def _marker_name_from_decorator(dec: ast.expr) -> str | None:
    """Extract the pytest marker name from a decorator node.

    Handles `@pytest.mark.ui` (ast.Attribute) and
    `@pytest.mark.parametrize(...)` (ast.Call wrapping an Attribute).
    Returns the mark name (e.g. 'ui') or None if not a pytest.mark.* decorator.
    """
    node = dec.func if isinstance(dec, ast.Call) else dec
    # node should be an Attribute like pytest.mark.<name>
    if not isinstance(node, ast.Attribute):
        return None
    mark_name = node.attr
    value = node.value
    # value should be `pytest.mark` -> ast.Attribute(attr='mark')
    if isinstance(value, ast.Attribute) and value.attr == 'mark':
        return mark_name
    return None


def _extract_markers(file_paths: set[str], base_path: Path) -> dict[str, set[str]]:
    """Parse Python test files with AST to extract pytest markers.

    Returns a dict mapping 'ClassName::method_name' (or 'method_name' for
    module-level functions) -> set of marker names. Class-level markers are
    inherited by all methods within that class.
    """
    marker_map: dict[str, set[str]] = {}
    for fpath in file_paths:
        full_path = base_path / fpath
        if not full_path.exists():
            continue
        try:
            source = full_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
        except Exception:
            continue

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_markers: set[str] = set()
                for dec in node.decorator_list:
                    name = _marker_name_from_decorator(dec)
                    if name:
                        class_markers.add(name)
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_markers = set(class_markers)
                        for dec in sub.decorator_list:
                            name = _marker_name_from_decorator(dec)
                            if name:
                                method_markers.add(name)
                        marker_map[f'{node.name}::{sub.name}'] = method_markers
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_markers: set[str] = set()
                for dec in node.decorator_list:
                    name = _marker_name_from_decorator(dec)
                    if name:
                        func_markers.add(name)
                marker_map[node.name] = func_markers
    return marker_map


def _determine_test_type(file_path: str, class_name: str, method_name: str,
                         marker_map: dict[str, set[str]]) -> str:
    """Determine test_type ('api' or 'ui') via markers then path fallback."""
    key = f'{class_name}::{method_name}' if class_name else method_name
    markers = marker_map.get(key, set())
    if 'ui' in markers:
        return 'ui'
    if 'api' in markers:
        return 'api'
    # Path-based fallback
    if file_path.startswith('src/testcase/ui') or '/ui/' in file_path:
        return 'ui'
    return 'api'


def _run_discovery(discovery_path: str | None = None, project_id: int = 0) -> DiscoverResponse:
    """Synchronous discovery using subprocess.run with docstring extraction.
    
    Args:
        discovery_path: Optional path to the test directory. If None, uses
            the default PROJECTS_SOURCE_DIR.
        project_id: If > 0, use the project's virtualenv Python for discovery
            so that project-specific dependencies are available.
    """
    # Resolve Python executable: use project virtualenv if available
    python_exe = sys.executable
    if project_id > 0:
        from app.config import PROJECTS_VENV_DIR
        venv_python = PROJECTS_VENV_DIR / f'project_{project_id}' / 'bin' / 'python'
        if venv_python.exists():
            # Only use the venv if pytest is installed there. A bare venv
            # (created before deps could be installed) would otherwise fail
            # collection with "No module named pytest" and yield zero cases.
            probe = subprocess.run(
                [str(venv_python), '-c', 'import pytest'],
                capture_output=True, text=True, timeout=15,
            )
            if probe.returncode == 0:
                python_exe = str(venv_python)
            else:
                _log.warning(
                    "Discoverer: venv python lacks pytest (%s), falling back to system python",
                    venv_python,
                )
    _log.info("Discoverer: python_exe = %s", python_exe)
    
    cwd = Path(discovery_path) if discovery_path else PROJECTS_SOURCE_DIR
    _log.info("Discoverer: cwd = %s", str(cwd))
    
    sys.path.insert(0, str(cwd))
    
    result = subprocess.run(
        [python_exe, '-m', 'pytest', '--collect-only', '-q', '--co',
         '--override-ini=addopts='],
        capture_output=True, text=True, timeout=60,
        cwd=str(cwd),
    )
    _log.info("Discoverer: returncode = %d", result.returncode)
    _log.info("Discoverer: stdout lines = %d, stderr lines = %d",
              len(result.stdout.splitlines()), len(result.stderr.splitlines()))
    if result.stderr.strip():
        _log.warning("Discoverer: stderr (first 5 lines):\n%s",
                     '\n'.join(result.stderr.splitlines()[:5]))
    lines = result.stdout.split('\n')

    # First pass: collect all file paths for AST parsing
    file_paths: set[str] = set()
    for line in lines:
        line = line.strip()
        if not line or '::' not in line:
            continue
        parts = line.split('::')
        if len(parts) >= 1:
            file_paths.add(parts[0].replace('\\', '/'))

    # Extract docstrings from source files
    doc_map = _extract_docstrings(file_paths, cwd)
    # Extract markers for test_type determination
    marker_map = _extract_markers(file_paths, cwd)

    modules: dict[str, dict[str, list[TestCaseInfo]]] = {}

    for line in lines:
        line = line.strip()
        if not line or '::' not in line:
            continue
        # Format: api/test_cases/test_xxx.py::TestClass::test_method
        #     or: src/testcase/ui/test_xxx.py::test_func (module-level)
        # Keep original nodeid for UID (includes parametrize brackets)
        raw_nodeid = line.split('[')[0]
        parts = raw_nodeid.split('::')
        if len(parts) >= 3:
            file_path = parts[0].replace('\\', '/')
            class_name = parts[1]
            method_name_with_brackets = parts[2]
        elif len(parts) == 2:
            # Module-level test function (no class)
            file_path = parts[0].replace('\\', '/')
            class_name = ''
            method_name_with_brackets = parts[1]
        else:
            continue

        # Use full line (include parametrize brackets) for unique UID
        uid = _nodeid_to_uid(line)

        # Strip brackets for display
        method_name = method_name_with_brackets.split('[')[0]

        module = Path(file_path).stem
        if module.startswith('test_'):
            module = module[5:]

        param = ''
        if '[' in line:
            param = line.split('[')[1].rstrip(']')
            method_name_with_brackets = f"{method_name}[{param}]"
        full_name = f"{file_path}::{class_name}::{method_name_with_brackets}" if class_name else f"{file_path}::{method_name_with_brackets}"

        # Try to get docstring: first ClassName::method, then method only
        doc_key = f'{class_name}::{method_name}' if class_name else method_name
        description = doc_map.get(doc_key, doc_map.get(method_name, ''))

        test_type = _determine_test_type(file_path, class_name, method_name, marker_map)

        item = TestCaseInfo(
            uid=uid,
            name=method_name,
            methodName=method_name,
            className=class_name,
            module=module,
            fullName=full_name,
            description=description,
            tags=[],
            filePath=file_path,
            testType=test_type,
        )

        if module not in modules:
            modules[module] = {}
        if class_name not in modules[module]:
            modules[module][class_name] = []
        modules[module][class_name].append(item)

    module_list: list[TestModuleInfo] = []
    total = 0

    for mod_name in sorted(modules.keys()):
        classes: list[TestClassInfo] = []
        mod_total = 0
        for cls_name in sorted(modules[mod_name].keys()):
            items = modules[mod_name][cls_name]
            cls_total = len(items)
            mod_total += cls_total
            total += cls_total
            classes.append(TestClassInfo(
                name=cls_name,
                items=items,
                total=cls_total,
            ))
        module_list.append(TestModuleInfo(
            module=mod_name,
            classes=classes,
            total=mod_total,
        ))

    return DiscoverResponse(modules=module_list, total=total)


async def discover_tests() -> DiscoverResponse:
    """Run pytest --collect-only in a thread to avoid async subprocess issues."""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run_discovery, None, 0)
    # Update the global uid-to-info cache
    _uid_cache.clear()
    for mod in result.modules:
        for cls in mod.classes:
            for item in cls.items:
                _uid_cache[item.uid] = item
    return result


async def discover_tests_at_path(discovery_path: str, project_id: int = 0) -> DiscoverResponse:
    """Run pytest --collect-only at a specific path."""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run_discovery, discovery_path, project_id)
    # Update the global uid-to-info cache
    _uid_cache.clear()
    for mod in result.modules:
        for cls in mod.classes:
            for item in cls.items:
                _uid_cache[item.uid] = item
    return result


# Global cache for quick uid lookups
_uid_cache: dict[str, TestCaseInfo] = {}


async def get_test_by_uid(uid: str, project_id: int = 0, branch_id: int = 0) -> TestCaseInfo | None:
    """Look up a single test case by uid from cache, fall back to database."""
    if uid in _uid_cache:
        return _uid_cache[uid]
    # Fallback to database
    from app.db import crud
    row = await crud.get_test_case_by_uid(uid, project_id=project_id, branch_id=branch_id)
    if row is None:
        return None
    info = TestCaseInfo(
        uid=row['uid'],
        name=row['name'],
        methodName=row.get('methodName', ''),
        className=row.get('className', ''),
        module=row.get('module', ''),
        fullName=row.get('fullName', ''),
        description=row.get('description', ''),
        tags=row.get('tags', []),
    )
    _uid_cache[uid] = info
    return info
