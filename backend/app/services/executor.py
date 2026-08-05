"""Pytest executor - runs tests via subprocess with real-time output parsing."""
from __future__ import annotations
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import PROJECTS_SOURCE_DIR, PROJECTS_REPORT_DIR, PROJECTS_VENV_DIR, PROJECT_ROOT

# Debug log path (platform-agnostic)
_EXECUTOR_LOG = PROJECT_ROOT / 'logs' / 'executor_debug.log'

# Ensure log directory exists
_EXECUTOR_LOG.parent.mkdir(parents=True, exist_ok=True)

from app.db import crud


@dataclass
class RunState:
    run_id: str
    state: str = 'pending'
    total: int = 0
    completed: int = 0
    passed: int = 0
    failed: int = 0
    broken: int = 0
    skipped: int = 0
    elapsed: str = ''
    uids: list[str] = field(default_factory=list)
    started_at: float = 0.0
    proc: subprocess.Popen | None = None
    subscribers: list = field(default_factory=list)


class ExecutionManager:
    """Singleton manager for test runs."""

    def __init__(self):
        self._runs: dict[str, RunState] = {}

    async def create_run(self, uids: list[str], concurrency: int = 2,
                         env: str = 'test', smoke_only: bool = False,
                         sequential: bool = False, run_id: str | None = None,
                         name: str = '') -> RunState:
        if not run_id:
            run_id = uuid.uuid4().hex[:8]
        state = RunState(
            run_id=run_id,
            uids=uids,
            started_at=time.time(),
        )
        self._runs[run_id] = state
        # Run execute in background using ensure_future
        loop = asyncio.get_running_loop()
        loop.create_task(self._execute(state, concurrency, env, smoke_only, sequential))
        return state

    async def run_in_worker(self, execution_id: str, uids: list[str], concurrency: int,
                            env: str = 'test', smoke_only: bool = False,
                            sequential: bool = False) -> dict:
        """Celery entry point: run in this worker process, not in FastAPI."""
        state = RunState(run_id=execution_id, uids=uids, started_at=time.time())
        self._runs[execution_id] = state
        await self._execute(state, concurrency, env, smoke_only, sequential)
        return {'execution_id': execution_id, 'status': state.state}

    def get_run(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[RunState]:
        return list(self._runs.values())

    async def stop_run(self, run_id: str) -> bool:
        state = self._runs.get(run_id)
        if state and state.proc and state.state == 'running':
            state.proc.terminate()
            state.proc.wait(timeout=10)
            state.state = 'stopped'
            await self._broadcast(state, {'type': 'run_complete', 'summary': {'state': 'stopped'}})
            return True
        return False

    async def _resolve_python(self, project_id: int) -> str:
        """Resolve the Python executable for a project's virtualenv.

        Each project gets its own virtualenv stored at PROJECTS_VENV_DIR/project_{id}/.
        The venv is created lazily on first access, but only if the project has
        a requirements.txt.  If no requirements.txt exists, the system Python is
        used directly (no venv created).

        - project_id <= 0: returns sys.executable (system Python, no venv)
        - project_id > 0 with requirements.txt: returns the venv's python path
        - project_id > 0 without requirements.txt: returns sys.executable
        """
        if project_id <= 0:
            return sys.executable

        # Check if the project has any requirements.txt
        proj_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
        has_req = (proj_dir / 'requirements.txt').exists()
        if not has_req:
            for f in proj_dir.rglob('requirements.txt'):
                has_req = True
                break

        if not has_req:
            return sys.executable

        venv_dir = PROJECTS_VENV_DIR / f'project_{project_id}'
        venv_python = venv_dir / 'bin' / 'python'

        if not venv_dir.exists():
            await _create_venv(venv_dir, project_id)

        return str(venv_python)

    async def _broadcast(self, state: RunState, msg: dict):
        # Redis makes progress events visible to every API instance and WebSocket.
        try:
            from app.websocket.events import publish
            await publish(state.run_id, msg)
        except Exception:
            # A failed notification must not fail a test execution; DB remains source of truth.
            pass
        dead: list = []
        for q in state.subscribers:
            try:
                await q.put(json.dumps(msg, ensure_ascii=False))
            except Exception:
                dead.append(q)
        for q in dead:
            state.subscribers.remove(q)

    async def _execute(self, state: RunState, concurrency: int, env: str, smoke_only: bool, sequential: bool):
        state.state = 'running'
        os.environ['TEST_ENV'] = env

        # Mark execution running in new model
        await crud.update_execution_status(state.run_id, 'running')

        # Determine project_id from execution record
        project_id = 0
        test_path_rel = ""
        try:
            exec_rec = await crud.get_execution(state.run_id)
            if exec_rec:
                project_id = exec_rec.get('project_id', 0)
                # Look up the project's test_path so we can run pytest from the right directory
                proj = await crud.get_project(project_id)
                if proj:
                    test_path_rel = proj.get('test_path', '') or ''
        except Exception:
            pass

        # Build project-specific paths
        project_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
        # Use the discovery directory as cwd for pytest, but pytest may use
        # a parent directory as rootdir if it finds pytest.ini/setup.cfg there.
        # The test_paths (fullName) are relative to the rootdir, which is the
        # directory containing the pytest config file.
        discovery_dir = project_dir / test_path_rel if test_path_rel else project_dir
        # Walk up to find the pytest rootdir (where pytest.ini/setup.cfg lives)
        cwd = str(discovery_dir)
        for parent in [discovery_dir, *discovery_dir.parents]:
            if any((parent / f).exists() for f in ('pytest.ini', 'setup.cfg', 'pyproject.toml')):
                cwd = str(parent)
                break
        report_base = PROJECTS_REPORT_DIR / f'project_{project_id}' / f'execution_{state.run_id}'
        allure_dir = report_base / 'allure-results'
        json_report_path = report_base / 'pytest-report.json'

        # Mark first N cases as running (N depends on execution mode)
        use_parallel = (not sequential) and concurrency > 1
        running_slots = concurrency if use_parallel else 1
        initial = concurrency if use_parallel else 1
        promoted = await crud.mark_cases_as_running(state.run_id, initial)
        for case in promoted:
            await self._broadcast(state, {
                'type': 'test_result',
                'uid': case['uid'],
                'status': 'running',
                'className': case['class_name'],
                'name': case['method_name'] or case['case_name'],
                'methodName': case['method_name'],
            })

        # Resolve project-specific Python path (virtualenv)
        python_path = await self._resolve_python(project_id)

        cmd = [
            python_path, '-m', 'pytest',
            '-v', '--tb=short',
            f'--alluredir={allure_dir}',
            '--clean-alluredir',
            '--json-report',
            f'--json-report-file={json_report_path}',
        ]
        if use_parallel:
            cmd.extend(['-n', str(concurrency)])

        if smoke_only:
            cmd.extend(['-m', 'smoke'])

        # Build uid<->fullName map from DB
        fullname_to_uid: dict[str, str] = {}
        uid_map: dict[str, str] = {}
        uid_to_type: dict[str, str] = {}
        uid_to_path: dict[str, str] = {}
        if state.uids:
            try:
                raw = await crud.load_discovery_raw()
                for r in raw:
                    uid_map[r['uid']] = r['fullName']
                    fullname_to_uid[r['fullName']] = r['uid']
                    uid_to_type[r['uid']] = r.get('testType', 'api')
                    uid_to_path[r['uid']] = r.get('filePath', '')
            except Exception as e:
                import traceback
                print(f'[EXECUTOR ERROR] load_discovery_raw failed: {e}')
                traceback.print_exc()
            test_paths: list[str] = []
            for uid in state.uids:
                path = uid_map.get(uid)
                if path:
                    test_paths.append(path)
            if test_paths:
                base_len = sum(len(a) + 1 for a in cmd)
                paths_len = sum(len(p) + 1 for p in test_paths)
                if (base_len + paths_len) < 30000:
                    cmd.extend(sorted(test_paths))
                else:
                    # Windows command-line limit: group by module file instead
                    module_paths = sorted(set(p.split('::')[0] for p in test_paths))
                    cmd.extend(module_paths)

        state.started_at = time.time()

        # DEBUG: log the command
        with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
            f.write(f'[{state.run_id}] cmd: {" ".join(cmd)}\n')
            f.write(f'[{state.run_id}] cwd: {cwd}\n')
            f.write(f'[{state.run_id}] uids: {state.uids[:5]}...\n')
            f.write(f'[{state.run_id}] test_paths: {test_paths[:5] if test_paths else "EMPTY"}\n')

        def _run_sync():
            """Run pytest via Popen so the process can be terminated on stop."""
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=cwd,
                )
                state.proc = proc
                try:
                    stdout, _ = proc.communicate(timeout=7200)
                    return stdout, proc.returncode
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, _ = proc.communicate()
                    return stdout, -1
            except Exception as e:
                return f'__ERROR__:{e}', -1

        loop = asyncio.get_event_loop()
        try:
            output, exit_code = await loop.run_in_executor(None, _run_sync)
        except Exception as e:
            import traceback
            traceback.print_exc()
            state.state = 'failed'
            await crud.update_execution_status(state.run_id, 'failed')
            await crud.bulk_fail_pending_cases(state.run_id)
            await self._broadcast(state, {'type': 'run_error', 'message': str(e)})
            return

        # DEBUG: log result
        with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
            f.write(f'[{state.run_id}] exit_code={exit_code}\n')
            f.write(f'[{state.run_id}] output_start={output[:200] if output else "N/A"}\n')
            f.write(f'[{state.run_id}] output_end={output[-200:] if output else "N/A"}\n')

        # Parse collected output 鈥?handles 4 pytest output formats:
        #  1. Clean:      api/.../test_X.py::Class::method STATUS [XX%]
        #  2. Xdist:      [gwN] [XX%] STATUS api/.../test_X.py::Class::method
        #  3. Interleaved: api/.../test_X.py::Class::method <logs>  +  STATUS [XX%]  (track current test)
        #  4. Summary:    STATUS api/.../test_X.py::Class::method  (short test summary section)
        line_pattern_std = re.compile(
            r'^(?:api/test_cases/)?test_(\w+)\.py::(\w+)::([\w\[\]-]+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAILED|XPASS).*?(?:\s+\[\d+%\])?$'
        )
        line_pattern_xdist = re.compile(
            r'^\[gw\d+\]\s+\[\d+%\]\s+(PASSED|FAILED|ERROR|SKIPPED|XFAILED|XPASS)\s+(?:api/test_cases/)?test_(\w+)\.py::(\w+)::([\w\[\]-]+)'
        )
        # Match test-start line (path + anything after) to track current test name
        test_start_pat = re.compile(
            r'^(?:api/test_cases/)?test_(\w+)\.py::(\w+)::([\w\[\]-]+)'
        )
        # Match unlabelled STATUS [XX%] (status line without path)
        status_only_pat = re.compile(r'^(PASSED|FAILED|ERROR|SKIPPED|XFAILED|XPASS)\s+\[(\d+)%\]')
        # Match short-summary format: STATUS path
        summary_pat = re.compile(
            r'^(PASSED|FAILED|ERROR|SKIPPED|XFAILED|XPASS)\s+(?:api/test_cases/)?test_(\w+)\.py::(\w+)::([\w\[\]-]+)'
        )

        STATUS_MAP = {
            'PASSED': 'pass', 'FAILED': 'fail', 'ERROR': 'broken',
            'SKIPPED': 'skip', 'XFAILED': 'xfailed', 'XPASS': 'xpassed',
        }

        # In-memory counters for batch refresh
        _success = _fail = _skip = 0
        _last_flush = time.time()

        result_pattern = re.compile(r'=+\s+(.+)\s+in\s+([\d.]+)s\s+=+')

        # Track already-processed uids to avoid double-counting
        processed_uids: set[str] = set()
        # Track current test path for interleaved output (path on one line, STATUS [XX%] on next)
        current_test: dict | None = None

        def _resolve_uid(module: str, cls: str, method: str) -> str:
            # Use the full method name (including parametrization suffix like [case1])
            # so that each parametrized variant maps to its own UID.
            if cls:
                candidates = [
                    f'test_{module}.py::{cls}::{method}',
                    f'test_{module}.py::{method}',
                ]
            else:
                candidates = [f'test_{module}.py::{method}']
            for suffix in candidates:
                matches = [uid for fn, uid in fullname_to_uid.items() if fn.endswith(suffix)]
                if not matches:
                    continue
                if len(matches) == 1:
                    return matches[0]
                # Multiple hits: prefer the one whose path mentions the module.
                for uid in matches:
                    fn = uid_map.get(uid, '')
                    if f'test_{module}' in fn or module in fn:
                        return uid
                return matches[0]
            # Fallback: try without parametrization suffix (for backward compatibility)
            clean_method = method.split('[')[0] if '[' in method else method
            if clean_method != method:
                if cls:
                    candidates = [
                        f'test_{module}.py::{cls}::{clean_method}',
                        f'test_{module}.py::{clean_method}',
                    ]
                else:
                    candidates = [f'test_{module}.py::{clean_method}']
                for suffix in candidates:
                    matches = [uid for fn, uid in fullname_to_uid.items() if fn.endswith(suffix)]
                    if not matches:
                        continue
                    if len(matches) == 1:
                        return matches[0]
                    for uid in matches:
                        fn = uid_map.get(uid, '')
                        if f'test_{module}' in fn or module in fn:
                            return uid
                    return matches[0]
            return method

        def _map_status(raw: str) -> str:
            st = STATUS_MAP.get(raw, 'unknown')
            if st in ('xfailed', 'xpassed'):
                st = 'pass'
            return st

        async def _on_test_result(uid: str, raw_status: str, class_name: str, method_name: str):
            nonlocal _success, _fail, _skip
            if uid in processed_uids:
                return
            processed_uids.add(uid)

            st = _map_status(raw_status)

            state.completed += 1
            if st == 'pass':
                state.passed += 1
                _success += 1
            elif st == 'fail':
                state.failed += 1
                _fail += 1
            elif st == 'broken':
                state.broken += 1
                _fail += 1
            elif st == 'skip':
                state.skipped += 1
                _skip += 1

            # Write final status to execution_cases table
            await crud.update_execution_case(
                execution_id=state.run_id, uid=uid, status=st,
            )

            await self._broadcast(state, {
                'type': 'test_result',
                'uid': uid,
                'status': st,
                'className': class_name,
                'name': method_name,
                'methodName': method_name,
            })

            # Promote next waiting case to running
            next_cases = await crud.mark_cases_as_running(state.run_id, 1)
            for case in next_cases:
                await self._broadcast(state, {
                    'type': 'test_result',
                    'uid': case['uid'],
                    'status': 'running',
                    'className': case['class_name'],
                    'name': case['method_name'] or case['case_name'],
                    'methodName': case['method_name'],
                })

        async def _maybe_flush_counts():
            nonlocal _last_flush
            now = time.time()
            remaining = len(state.uids) - state.completed
            if now - _last_flush >= 1.0:
                c = min(running_slots, max(0, remaining))
                asyncio.create_task(crud.update_execution_counts(
                    execution_id=state.run_id,
                    success=_success, fail=_fail, skip=_skip,
                    running=c,
                    waiting=max(0, remaining - c),
                ))
                _last_flush = now

        async def _broadcast_progress():
            remaining = len(state.uids) - state.completed
            c = min(running_slots, max(0, remaining))
            await self._broadcast(state, {
                'type': 'suite_progress',
                'total': len(state.uids),
                'completed': state.completed,
                'passed': state.passed,
                'failed': state.failed,
                'broken': state.broken,
                'skipped': state.skipped,
                'waiting': max(0, remaining - c),
                'running': c,
                'success': _success,
                'fail': _fail,
                'skip': _skip,
                'elapsed': f'{time.time() - state.started_at:.1f}s',
            })

        if output and not output.startswith('__ERROR__:'):
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue

                m = result_pattern.search(line)
                if m:
                    state.elapsed = f'{float(m.group(2)):.1f}s'

        if json_report_path.exists():
            try:
                with open(json_report_path, 'r', encoding='utf-8') as f:
                    json_report = json.load(f)
                
                for test in json_report.get('tests', []):
                    nodeid = test.get('nodeid', '')
                    outcome = test.get('outcome', '')
                    
                    if not nodeid or not outcome:
                        continue
                    
                    parts = nodeid.split('::')
                    if len(parts) >= 3:
                        file_path = parts[0]
                        class_name = parts[1]
                        method_name = parts[2]
                        
                        module_match = re.search(r'test_(\w+)\.py', file_path)
                        if module_match:
                            module = module_match.group(1)
                            
                            uid = _resolve_uid(module, class_name, method_name)
                            if uid:
                                raw_status = outcome.upper()
                                await _on_test_result(
                                    uid=uid,
                                    raw_status=raw_status,
                                    class_name=class_name,
                                    method_name=method_name,
                                )
                                await _maybe_flush_counts()
                                await _broadcast_progress()
            except Exception as e:
                print(f'[DEBUG] Failed to parse JSON report: {e}')
                import traceback
                traceback.print_exc()
        else:
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue

                m = line_pattern_std.match(line)
                if m:
                    current_test = None
                    await _on_test_result(
                        uid=_resolve_uid(m.group(1), m.group(2), m.group(3)),
                        raw_status=m.group(4),
                        class_name=m.group(2),
                        method_name=m.group(3),
                    )
                    await _maybe_flush_counts()
                    await _broadcast_progress()
                    continue

                m = line_pattern_xdist.match(line)
                if m:
                    current_test = None
                    await _on_test_result(
                        uid=_resolve_uid(m.group(2), m.group(3), m.group(4)),
                        raw_status=m.group(1),
                        class_name=m.group(3),
                        method_name=m.group(4),
                    )
                    await _maybe_flush_counts()
                    await _broadcast_progress()
                    continue

                m = test_start_pat.match(line)
                if m and not line_pattern_std.match(line) and not summary_pat.match(line):
                    current_test = {
                        'module': m.group(1), 'class': m.group(2), 'method': m.group(3),
                        'uid': _resolve_uid(m.group(1), m.group(2), m.group(3)),
                    }
                    continue

                if current_test is not None:
                    m = status_only_pat.match(line)
                    if m:
                        await _on_test_result(
                            uid=current_test['uid'],
                            raw_status=m.group(1),
                            class_name=current_test['class'],
                            method_name=current_test['method'],
                        )
                        await _maybe_flush_counts()
                        await _broadcast_progress()
                        current_test = None
                        continue

                m = summary_pat.match(line)
                if m:
                    await _on_test_result(
                        uid=_resolve_uid(m.group(2), m.group(3), m.group(4)),
                        raw_status=m.group(1),
                        class_name=m.group(3),
                        method_name=m.group(4),
                    )
                    continue

        state.elapsed = f'{time.time() - state.started_at:.1f}s'

        # A stop request is persisted by the API.  A worker can receive it
        # while pytest is running, so never overwrite that terminal state.
        persisted = await crud.get_execution(state.run_id)
        if state.state == 'stopped' or (persisted and persisted.get('status') == 'stopped'):
            state.state = 'stopped'
            await crud.update_execution_status(state.run_id, 'stopped')
            await self._broadcast(state, {'type': 'run_complete', 'summary': {'state': 'stopped'}})
            return

        print(f'[DEBUG] exit_code={exit_code}, state.state will be set to {"finished" if exit_code in (0, 1) else "failed"}')
        print(f'[DEBUG] parsed: completed={state.completed}, passed={state.passed}, failed={state.failed}, broken={state.broken}, skipped={state.skipped}')
        print(f'[DEBUG] processed_uids count={len(processed_uids)}')
        print(f'[DEBUG] pytest output snippet: {output[-500:] if output else "N/A"}')
        state.state = 'finished' if exit_code in (0, 1) else 'failed'

        # Mark any remaining running/waiting cases as broken (parser didn't capture them)
        if state.state == 'failed':
            await crud.bulk_fail_pending_cases(state.run_id)
        else:
            # For finished executions, mark remaining running cases as broken
            # (e.g., if output parser missed some results)
            remaining = await crud.bulk_fail_pending_cases(state.run_id)
            if remaining > 0:
                print(f'[DEBUG] Marked {remaining} remaining cases as broken after execution finished')

        # Final flush to execution table
        try:
            await crud.update_execution_status(state.run_id, state.state)
            await crud.update_execution_counts(
                execution_id=state.run_id,
                success=state.passed,
                fail=state.failed + state.broken,
                skip=state.skipped,
                running=0,
                waiting=0,
            )
        except Exception:
            pass


        # Post-process: read Allure result JSONs to capture detailed error logs
        try:
            if allure_dir.exists():
                # Build full_name -> uid map from discovery data
                allure_to_uid = {}
                try:
                    raw = await crud.load_discovery_cache()
                    items = raw[0] if isinstance(raw, tuple) else raw
                    if items:
                        for r in items:
                            fn = r.get('fullName', '')
                            uid = r.get('uid', '')
                            if fn and uid:
                                allure_to_uid[fn] = uid
                    with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
                        f.write(f'[{state.run_id}] allure_to_uid built: {len(allure_to_uid)} entries\n')
                        if allure_to_uid:
                            sample_key = list(allure_to_uid.keys())[0]
                            f.write(f'  sample key: {sample_key}\n')
                            f.write(f'  sample val: {allure_to_uid[sample_key][:20]}...\n')
                except Exception as e:
                    with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
                        f.write(f'[{state.run_id}] allure_to_uid ERROR: {e}\n')

                def _collect_steps(steps_list):
                    """Flatten Allure steps into [{'name','status'}, ...]."""
                    out = []
                    for st in steps_list or []:
                        out.append({
                            'name': st.get('name', ''),
                            'status': st.get('status', ''),
                        })
                        nested = st.get('steps')
                        if nested:
                            out.extend(_collect_steps(nested))
                    return out

                def _collect_shots(attachments, steps_list):
                    """Collect image attachment source filenames from result + steps."""
                    out = []
                    for att in attachments or []:
                        if str(att.get('type', '')).startswith('image/'):
                            src = att.get('source')
                            if src:
                                out.append(src)
                    for st in steps_list or []:
                        out.extend(_collect_shots(st.get('attachments'), st.get('steps')))
                    return out

                for result_file in allure_dir.glob('*-result.json'):
                    try:
                        data = json.loads(result_file.read_text(encoding='utf-8'))
                        allure_fn = data.get('fullName', '')
                        sd = data.get('statusDetails', {})
                        msg = sd.get('message', '')
                        tr = sd.get('trace', '')

                        # Read text attachments (pytest captured stdout)
                        attachment_texts: list[str] = []
                        for att in data.get('attachments', []):
                            att_source = att.get('source', '')
                            att_type = att.get('type', '')
                            if att_source and att_type == 'text/plain':
                                att_path = allure_dir / att_source
                                if att_path.exists():
                                    try:
                                        attachment_texts.append(att_path.read_text(encoding='utf-8'))
                                    except Exception:
                                        pass
                        full_log = '\n'.join(attachment_texts) if attachment_texts else ''
                        combined_log = (full_log + '\n' + msg if full_log and msg else full_log or msg or '')

                        steps_list = data.get('steps', [])
                        step_items = _collect_steps(steps_list)
                        shot_items = _collect_shots(data.get('attachments'), steps_list)
                        steps_json = json.dumps(step_items, ensure_ascii=False) if step_items else None
                        shots_json = json.dumps(shot_items, ensure_ascii=False) if shot_items else None

                        if not combined_log and not tr and not steps_json and not shots_json:
                            with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
                                f.write(f'[{state.run_id}] Allure SKIP: no data for {allure_fn}\n')
                            continue
                        # Convert Allure format to discovery format
                        # Allure: data_annotation.tests.api.test_cases.test_batch.TestBatchCreate#test_method
                        # Discovery: data_annotation/tests/api/test_cases/test_batch.py::TestBatchCreate::test_method
                        def _allure_to_disc(full_name: str) -> str:
                            """Convert Allure fullName to discovery fullName format."""
                            if '#' in full_name:
                                prefix, method = full_name.split('#', 1)
                                parts = prefix.split('.')
                            else:
                                parts = full_name.split('.')
                                method = ''
                            try:
                                idx = parts.index('test_cases')
                                if idx + 2 < len(parts):
                                    dir_prefix = '/'.join(parts[:idx])
                                    module = parts[idx + 1]
                                    cls = parts[idx + 2]
                                    if not method:
                                        method = '.'.join(parts[idx + 3:]) if idx + 3 < len(parts) else ''
                                    return '{dir_prefix}/test_cases/{module}.py::{cls}::{method}'.format(
                                        dir_prefix=dir_prefix, module=module, cls=cls, method=method
                                    )
                            except ValueError:
                                pass
                            return full_name
                        disc_fn = _allure_to_disc(allure_fn)
                        uid = allure_to_uid.get(disc_fn, '')
                        if not uid:
                            allure_name = data.get('name', '')
                            param_suffix = ''
                            if '[' in allure_name and allure_name.endswith(']'):
                                param_suffix = allure_name[allure_name.index('['):]
                                disc_fn_param = disc_fn + param_suffix
                                uid = allure_to_uid.get(disc_fn_param, '')
                        if not uid:
                            for fn, uid_val in allure_to_uid.items():
                                if fn.startswith(disc_fn + '['):
                                    uid = uid_val
                                    break
                        with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
                            f.write(f'[{state.run_id}] Allure: {allure_fn} -> disc={disc_fn} -> uid={"FOUND" if uid else "NOT FOUND"}\n')
                            if not uid:
                                f.write(f'  allure_to_uid keys (first 3): {list(allure_to_uid.keys())[:3]}\n')
                        if uid:
                            await crud.update_execution_case(
                                execution_id=state.run_id, uid=uid,
                                status=None, message=msg[:5000] if msg else '',
                                trace=tr[:10000] if tr else '',
                                logs=combined_log[:10000] if combined_log else '',
                                test_type=uid_to_type.get(uid, 'api'),
                                steps=steps_json,
                                screenshots=shots_json,
                            )
                            with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
                                f.write(f'[{state.run_id}] Allure UPDATED case for uid={uid[:20]}\n')
                    except Exception as e:
                        with open(_EXECUTOR_LOG, 'a', encoding='utf-8') as f:
                            f.write(f'[{state.run_id}] Allure ERROR: {e}\n')
        except Exception:
            pass

        # Generate and save report to database
        try:
            cases_full = await crud.get_execution_cases_full(state.run_id)
            if cases_full:
                total = len(cases_full)
                passed = sum(1 for c in cases_full if c.get('status') in ('pass', 'passed'))
                failed = sum(1 for c in cases_full if c.get('status') in ('fail', 'failed'))
                broken = sum(1 for c in cases_full if c.get('status') == 'broken')
                skipped = sum(1 for c in cases_full if c.get('status') in ('skip', 'skipped'))
                pass_rate = round((passed / total * 100), 2) if total > 0 else 0

                # Get execution to find project_id
                execution = await crud.get_execution(state.run_id)
                project_id = execution.get('project_id', 0) if execution else 0

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
                for c in cases_full:
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

                total_duration_ms = sum((c.get('duration_ms', 0) or 0) for c in cases_full)
                summary = {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                    'broken': broken,
                    'skipped': skipped,
                    'xfailed': 0,
                    'passRate': pass_rate,
                    'totalDuration': format_duration(total_duration_ms),
                    'totalDurationMs': total_duration_ms,
                    'generatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'host': '',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state.started_at)),
                }

                await crud.create_report(
                    execution_id=state.run_id,
                    project_id=project_id,
                    summary=summary,
                    module_groups={'moduleGroups': module_groups},
                    results=items,
                )
        except Exception:
            import logging
            logging.getLogger('executor').exception('report generation failed')

        await self._broadcast(state, {
            'type': 'run_complete',
            'summary': {
                'state': state.state,
                'total': len(state.uids),
                'success': state.passed,
                'fail': state.failed + state.broken,
                'skip': state.skipped,
                'elapsed': state.elapsed,
            }
        })


# Global instance
execution_manager = ExecutionManager()


async def _create_venv(venv_dir: Path, project_id: int) -> None:
    """Create a virtualenv at *venv_dir* and install project dependencies.

    Shared helper used by both the executor (lazy creation) and the sync
    endpoint (rebuild).  Fails silently so neither caller is disrupted.
    """
    import logging
    _log = logging.getLogger('executor')

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'venv', str(venv_dir),
        )
        returncode = await proc.wait()
        if returncode != 0:
            # ensurepip may have failed (e.g. slim image, transient error).
            # Retry with --without-pip and install pip manually.
            _log.warning('venv creation returned %s, retrying with --without-pip', returncode)
            if venv_dir.exists():
                import shutil
                shutil.rmtree(venv_dir)
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'venv', '--without-pip', str(venv_dir),
            )
            await proc.wait()

        # The server cannot reach pypi.org at runtime, so always install via
        # the Aliyun mirror.  pytest is required for discovery even when the
        # project has no requirements.txt.
        venv_python = venv_dir / 'bin' / 'python'

        # Ensure pip is available in the venv
        pip_check = await asyncio.create_subprocess_exec(
            str(venv_python), '-m', 'pip', '--version',
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await pip_check.wait() != 0:
            _log.warning('pip not found in venv, running ensurepip')
            proc = await asyncio.create_subprocess_exec(
                str(venv_python), '-m', 'ensurepip', '--upgrade', '--default-pip',
            )
            await proc.wait()

        pip_cmd = [
            str(venv_python), '-m', 'pip', 'install',
            '--index-url', 'https://mirrors.aliyun.com/pypi/simple/',
            '--timeout', '60', '--quiet',
            'pytest',
        ]

        req_file = PROJECTS_SOURCE_DIR / f'project_{project_id}' / 'requirements.txt'
        if not req_file.exists():
            # Fallback: search for requirements.txt in subdirectories
            proj_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
            for f in proj_dir.rglob('requirements.txt'):
                req_file = f
                break
        if req_file.exists():
            pip_cmd.extend(['-r', str(req_file)])

        proc = await asyncio.create_subprocess_exec(*pip_cmd)
        await proc.wait()
    except Exception:
        _log.exception(
            'Failed to create venv for project %s', project_id,
        )


# Cached discovery result (shared via setter to avoid Python import binding issues)
_discovery_cache: DiscoverResponse | None = None


def set_discovery_cache(data):
    global _discovery_cache
    _discovery_cache = data
