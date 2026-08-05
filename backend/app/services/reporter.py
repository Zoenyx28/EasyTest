"""Report service - wraps generate_report.py for API consumption and provides execution-based reports."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

HISTORY_FILE = str(PROJECT_ROOT / 'reports' / 'history.json')


def get_latest_report():
    """Build report data from the most recent allure results."""
    from app.generate_report import build_report_data  # noqa: E402
    data = build_report_data()
    if data is None:
        return None
    return data


def get_history() -> list[dict]:
    """Return historical run records."""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_history(record: dict, execution_id: str | None = None):
    """Save a report record to history file, optionally with execution_id."""
    history = get_history()
    if execution_id:
        record['execution_id'] = execution_id
    history.append(record)
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_report_list() -> list[dict]:
    """Return lightweight list of report summaries for the selector."""
    history = get_history()
    summaries = []
    for idx, entry in enumerate(reversed(history)):
        summaries.append({
            'index': len(history) - 1 - idx,
            'timestamp': entry.get('timestamp', ''),
            'total': entry.get('summary', {}).get('total', 0),
            'passed': entry.get('summary', {}).get('passed', 0),
            'failed': entry.get('summary', {}).get('failed', 0),
            'passRate': entry.get('summary', {}).get('passRate', 0),
            'totalDuration': entry.get('summary', {}).get('totalDuration', ''),
        })
    return summaries


def get_report_by_index(index: int) -> dict | None:
    """Return the full report data for a specific history index."""
    history = get_history()
    if not history or index < 0 or index >= len(history):
        return None
    return history[index]


def delete_history_entry(index: int) -> bool:
    """Delete a report from history by index."""
    history = get_history()
    if not history or index < 0 or index >= len(history):
        return False
    del history[index]
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return True


async def get_report_by_execution(execution_id: str) -> dict | None:
    """Build report data from ExecutionCase records in database."""
    from app.db import crud

    execution = await crud.get_execution(execution_id)
    if execution is None:
        return None

    cases = await crud.get_execution_cases_full(execution_id)
    if not cases:
        return None

    total = len(cases)
    passed = sum(1 for c in cases if c.get('status') in ('pass', 'passed'))
    failed = sum(1 for c in cases if c.get('status') in ('fail', 'failed'))
    broken = sum(1 for c in cases if c.get('status') == 'broken')
    skipped = sum(1 for c in cases if c.get('status') in ('skip', 'skipped'))
    xfailed = 0
    pass_rate = round((passed / total * 100), 2) if total > 0 else 0
    total_duration_ms = sum(c.get('duration_ms', 0) or 0 for c in cases)

    def format_duration(ms):
        if ms < 1000:
            return f"{ms}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            m = ms // 60000
            s = (ms % 60000) / 1000
            return f"{m}m{s:.0f}s"

    items = []
    for c in cases:
        items.append({
            'name': c.get('case_name', ''),
            'uid': c.get('uid', ''),
            'methodName': c.get('method_name', ''),
            'className': c.get('class_name', ''),
            'module': c.get('module', ''),
            'fullName': c.get('case_name', '') or c.get('uid', ''),
            'status': c.get('status', 'unknown'),
            'description': '',
            'duration': format_duration(c.get('duration_ms', 0) or 0),
            'duration_ms': c.get('duration_ms', 0) or 0,
            'message': c.get('message', ''),
            'trace': c.get('trace', ''),
            'logs': c.get('logs', ''),
            'tags': [],
            'params': '',
            'history': [],
            'testType': c.get('test_type', 'api'),
            'steps': c.get('steps'),
            'screenshots': c.get('screenshots'),
            'start': c.get('start_time') or '',
        })

    groups = {}
    for item in items:
        mod = item['module'] or 'unknown'
        cls = item['className'] or 'Unknown'
        if mod not in groups:
            groups[mod] = {}
        if cls not in groups[mod]:
            groups[mod][cls] = []
        groups[mod][cls].append(item)

    module_groups = []
    for mod_name in sorted(groups.keys()):
        classes = []
        for cls_name in sorted(groups[mod_name].keys()):
            cls_items = groups[mod_name][cls_name]
            cls_passed = sum(1 for i in cls_items if i['status'] in ('pass', 'passed'))
            cls_failed = sum(1 for i in cls_items if i['status'] in ('fail', 'failed'))
            cls_broken = sum(1 for i in cls_items if i['status'] == 'broken')
            classes.append({
                'name': cls_name,
                'items': cls_items,
                'total': len(cls_items),
                'passed': cls_passed,
                'failed': cls_failed,
                'broken': cls_broken,
            })
        mod_total = sum(c['total'] for c in classes)
        mod_passed = sum(c['passed'] for c in classes)
        module_groups.append({
            'module': mod_name,
            'classes': classes,
            'total': mod_total,
            'passed': mod_passed,
        })

    return {
        'execution_id': execution_id,
        'task_name': execution.get('task_name', ''),
        'timestamp': execution.get('start_time', '') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'total': total,
            'passed': passed,
            'failed': failed,
            'broken': broken,
            'skipped': skipped,
            'xfailed': xfailed,
            'passRate': pass_rate,
            'totalDuration': format_duration(total_duration_ms),
            'totalDurationMs': total_duration_ms,
            'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'host': '',
        },
        'moduleGroups': module_groups,
        'items': items,
        'allTags': [],
    }
