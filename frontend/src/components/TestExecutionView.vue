<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue';
import { useApi } from '../composables/useApi';
import { useProject } from '../composables/useProject';
import { useWebSocket } from '../composables/useWebSocket';
import type { TestTask, TestCaseInfo, RunLogDetail, ExecutionRecord, ExecutionCaseItem } from '../types';

const { connected, connect: wsConnect, onMessage: wsOnMessage, close: wsClose } = useWebSocket();

const props = defineProps<{
  globalSearch: string;
  selectedUids: string[];
}>();

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
}>();

const { activeProject, getActiveProject } = useProject();

const getApi = () => useApi(activeProject.value?.id);

interface TestCaseState {
  uid: string;
  status: 'waiting' | 'running' | 'pass' | 'fail' | 'skip' | 'broken';
  name: string;
  description: string;
  methodName: string;
  className: string;
  id: number;
  duration_ms?: number;
  /** Case-defined steps JSON (from the case detail: 调用xxx接口 / 断言xxx). */
  steps?: string;
}

const tasks = ref<TestTask[]>([]);
const selectedTaskId = ref<string>('');
const taskCaseStates = ref<Record<string, TestCaseState[]>>({});

const queueFilter = ref<string>('All');
const selectedStatusFilters = ref<Set<string>>(new Set());
const selectedCaseId = ref<string>('');
const detailLog = ref<RunLogDetail | null>(null);
const detailLoading = ref(false);
const elapsingSeconds = ref<Record<string, number>>({});
const elapsedTimers = ref<Record<string, ReturnType<typeof setInterval>>>({});
const renamingTaskId = ref<string>('');
const renameInput = ref('');
const concurrency = ref(1);
const sequential = ref(true);
const openMenuTaskId = ref<string>('');
const menuPosition = ref({ top: 0, left: 0 });

const selectedTask = computed(() => {
  return tasks.value.find(t => String(t.id) === String(selectedTaskId.value)) || null;
});

const filteredTasks = computed(() => {
  if (!props.globalSearch) return tasks.value;
  const search = props.globalSearch.toLowerCase();
  return tasks.value.filter(t => 
    t.name.toLowerCase().includes(search) || 
    String(t.id).toLowerCase().includes(search)
  );
});

const selectedCaseStates = computed(() => {
  if (!selectedTaskId.value) return [];
  return taskCaseStates.value[selectedTaskId.value] || [];
});

const filteredQueue = computed(() => {
  const states = selectedCaseStates.value;
  return states.filter(c => {
    const matchesSearch = !props.globalSearch ||
      c.name.toLowerCase().includes(props.globalSearch.toLowerCase()) ||
      c.uid.toLowerCase().includes(props.globalSearch.toLowerCase());
    if (!matchesSearch) return false;
    if (selectedStatusFilters.value.size === 0) return true;
    return selectedStatusFilters.value.has(c.status);
  });
});

function toggleStatusFilter(status: string) {
  if (selectedStatusFilters.value.has(status)) {
    selectedStatusFilters.value.delete(status);
  } else {
    selectedStatusFilters.value.add(status);
  }
  selectedStatusFilters.value = new Set(selectedStatusFilters.value);
}

const barChartSegments = computed(() => {
  const colors: Record<string, string> = {
    pass: '#2AA84A', fail: 'var(--red)', skip: '#8E8E93',
    running: 'var(--accent)', broken: 'var(--purple)', waiting: 'var(--text-tertiary)',
  };
  return [
    { status: 'pass', label: '成功', bgClass: 'bg-[var(--color-success)]', color: 'var(--color-success)', count: filterCounts.value.pass },
    { status: 'fail', label: '失败', bgClass: 'bg-[var(--red)]', color: 'var(--red)', count: filterCounts.value.fail },
    { status: 'skip', label: '跳过', bgClass: 'bg-[var(--text-muted)]', color: 'var(--text-muted)', count: filterCounts.value.skip },
    { status: 'running', label: '执行中', bgClass: 'bg-[var(--accent)]', color: 'var(--accent)', count: filterCounts.value.running },
    { status: 'broken', label: '异常', bgClass: 'bg-[var(--purple)]', color: 'var(--purple)', count: filterCounts.value.broken },
    { status: 'waiting', label: '等待', bgClass: 'bg-[var(--input-bg)]', color: 'var(--text-tertiary)', count: filterCounts.value.waiting },
  ].filter(s => s.count > 0);
});

const filterCounts = computed(() => {
  const states = selectedCaseStates.value;
  return {
    all: states.length,
    running: states.filter(c => c.status === 'running').length,
    fail: states.filter(c => c.status === 'fail').length,
    broken: states.filter(c => c.status === 'broken').length,
    pass: states.filter(c => c.status === 'pass').length,
    skip: states.filter(c => c.status === 'skip').length,
    waiting: states.filter(c => c.status === 'waiting').length,
  };
});

const activeCase = computed(() => {
  if (selectedCaseId.value) {
    const found = selectedCaseStates.value.find(c => c.uid === selectedCaseId.value);
    if (found) return found;
  }
  return selectedCaseStates.value[0] || null;
});

const DOT_COLORS: Record<string, string> = {
  pass: '#2AA84A', fail: 'var(--red)', broken: 'var(--purple)',
  running: 'var(--accent)', skip: '#8E8E93', waiting: 'var(--input-bg)',
};

interface ResultDot {
  color: string;
  label: string;
  hint: string;
}

const resultDots = computed(() => {
  const items = selectedCaseStates.value.slice(0, 5);
  const dots: ResultDot[] = [];
  let groupStart = 0;
  for (let i = 0; i < items.length; i++) {
    const isLast = i === items.length - 1;
    const curStatus = items[i].status;
    const nextStatus = isLast ? null : items[i + 1].status;
    if (curStatus !== nextStatus) {
      const count = i - groupStart + 1;
      for (let j = groupStart; j <= i; j++) {
        dots.push({
          color: DOT_COLORS[curStatus] || 'var(--input-bg)',
          label: STATUS_LABELS[curStatus] || curStatus,
          hint: (STATUS_LABELS[curStatus] || curStatus) + ': ' + count,
        });
      }
      groupStart = i + 1;
    }
  }
  return dots;
});

const taskCounts = computed(() => {
  if (!selectedTask.value) return { total: 0, waiting: 0, running: 0, success: 0, fail: 0, skip: 0, progress: 0, passRate: 0, elapsed: 0 };
  const task = selectedTask.value;
  const states = selectedCaseStates.value;
  const success = states.filter(t => t.status === 'pass').length;
  const fail = states.filter(t => t.status === 'fail').length + states.filter(t => t.status === 'broken').length;
  const skip = states.filter(t => t.status === 'skip').length;
  const waiting = states.filter(t => t.status === 'waiting').length;
  const running = states.filter(t => t.status === 'running').length;
  const finished = success + fail + skip;
  // Calculate elapsed time: use running timer if available, otherwise compute from timestamps
  const timerSecs = elapsingSeconds.value[String(task.id)];
  let elapsed = 0;
  if (timerSecs !== undefined && timerSecs > 0) {
    elapsed = timerSecs;
  } else if (task.completed_at && task.started_at) {
    elapsed = Math.floor((new Date(task.completed_at).getTime() - new Date(task.started_at).getTime()) / 1000);
  } else if (task.completed_at && task.created_at) {
    elapsed = Math.floor((new Date(task.completed_at).getTime() - new Date(task.created_at).getTime()) / 1000);
  }
  return {
    total: task.total,
    waiting,
    running,
    success,
    fail,
    skip,
    progress: task.total > 0 ? Math.round((finished / task.total) * 100) : 0,
    passRate: finished > 0 ? Math.round((success / finished) * 100) : 0,
    elapsed,
  };
});

async function createTask(uids: string[]) {
  if (uids.length === 0) return;
  const existingUids = new Set<string>();
  for (const task of tasks.value) {
    for (const uid of task.uids) {
      existingUids.add(uid);
    }
  }
  const newUids = uids.filter(u => !existingUids.has(u));
  if (newUids.length === 0) {
    emit('showToast', '选中的用例已存在于其他任务中');
    return;
  }

  const now = new Date();
  const taskName = `测试任务 ${now.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`;
  
  let taskId = 0;
  try {
    const { post } = getApi();
    const res = await post<{ task_id: number }>('/tasks', { uids: newUids, name: taskName, project_id: activeProject.value?.id });
    taskId = res.task_id;
  } catch {
    taskId = Date.now();
  }

  const task: TestTask = {
    id: String(taskId),
    name: taskName,
    status: 'idle',
    uids: newUids,
    total: newUids.length,
    passed: 0,
    failed: 0,
    broken: 0,
    skipped: 0,
    completed: 0,
    run_id: String(taskId),
    created_at: now.toISOString(),
  };
  tasks.value.push(task);
  selectedTaskId.value = String(task.id);
  
  const { get } = getApi();
  const states: TestCaseState[] = [];
  for (const uid of newUids) {
    try {
      const info = await get<TestCaseInfo>(`/tests/${uid}`);
      states.push({
        uid, id: 0,
        status: 'waiting',
        name: info.description || info.name || info.methodName || uid,
        description: info.description || '',
        methodName: info.methodName || '',
        className: info.className || '',
        steps: info.steps || '',
      });
    } catch {
      states.push({ uid, id: 0, status: 'waiting', name: uid, description: '', methodName: '', className: '' });
    }
  }
  taskCaseStates.value[task.id] = states;
  if (!selectedCaseId.value && states.length > 0) {
    selectedCaseId.value = states[0].uid;
  }
  if (selectedCaseId.value && states.length > 0) {
    const firstItem = states.find(s => s.uid === selectedCaseId.value) || states[0];
    if (isClickable(firstItem.status) && firstItem.id > 0) {
      showDetail(firstItem);
    }
  }
  emit('showToast', `已创建测试任务，包含 ${newUids.length} 个用例`);
}

let pollingTimer: ReturnType<typeof setInterval> | null = null;
let currentExecutionId = ref<string>('');
let currentTaskId = ref<string>('');
let wsFailedOnce = ref(false);

async function pollExecutionState(executionId: string, taskId: string) {
  try {
    const { get } = getApi();
    const exec = await get<{
      status: string;
      success: number;
      fail: number;
      skip: number;
      running: number;
      waiting: number;
    }>(`/executions/${executionId}`);
    
    const task = tasks.value.find(t => String(t.id) === String(taskId));
    if (!task) return;
    
    task.passed = exec.success || 0;
    task.failed = exec.fail || 0;
    task.skipped = exec.skip || 0;
    task.completed = (exec.success || 0) + (exec.fail || 0) + (exec.skip || 0);
    
    const casesResp = await get<{ items: ExecutionCaseItem[] }>(`/executions/${executionId}/cases/all`);
    const caseStates = taskCaseStates.value[taskId];
    if (caseStates && casesResp.items) {
      for (const apiCase of casesResp.items) {
        const localCase = caseStates.find(c => c.uid === apiCase.uid);
        if (localCase) {
          localCase.status = apiCase.status as any;
          if (apiCase.id && !localCase.id) {
            localCase.id = apiCase.id;
          }
          if (apiCase.duration_ms != null) {
            localCase.duration_ms = apiCase.duration_ms;
          }
        }
      }
    }
    
    if (exec.status === 'finished' || exec.status === 'failed' || exec.status === 'stopped') {
      stopPolling();
      stopWebSocket();
      task.status = exec.status === 'finished' ? 'done' : exec.status === 'failed' ? 'error' : 'stopped';
      task.completed_at = new Date().toISOString();
      if (elapsedTimers.value[taskId]) { clearInterval(elapsedTimers.value[taskId]); delete elapsedTimers.value[taskId]; }
    }
  } catch {
    // ignore polling errors
  }
}

async function refreshCaseStates(executionId: string, taskId: string) {
  try {
    const { get } = getApi();
    const casesResp = await get<{ items: ExecutionCaseItem[] }>(`/executions/${executionId}/cases/all`);
    const caseStates = taskCaseStates.value[taskId];
    if (caseStates && casesResp.items) {
      for (const apiCase of casesResp.items) {
        const localCase = caseStates.find(c => c.uid === apiCase.uid);
        if (localCase) {
          localCase.status = apiCase.status as any;
          if (apiCase.id && !localCase.id) {
            localCase.id = apiCase.id;
          }
          if (apiCase.duration_ms != null) {
            localCase.duration_ms = apiCase.duration_ms;
          }
        }
      }
    }
  } catch {
    // ignore
  }
}

function handleWebSocketMessage(msg: any) {
  if (!msg || msg.type === 'heartbeat') return;
  
  const taskId = currentTaskId.value;
  const task = tasks.value.find(t => String(t.id) === String(taskId));
  if (!task) return;
  
  if (msg.type === 'test_result') {
    const caseStates = taskCaseStates.value[taskId];
    if (caseStates && msg.data) {
      const localCase = caseStates.find(c => c.uid === msg.data.uid);
      if (localCase) {
        localCase.status = msg.data.status as any;
        if (msg.data.id && !localCase.id) {
          localCase.id = msg.data.id;
        }
      }
    }
    if (msg.stats) {
      task.passed = msg.stats.success || 0;
      task.failed = msg.stats.fail || 0;
      task.skipped = msg.stats.skip || 0;
      task.completed = (msg.stats.success || 0) + (msg.stats.fail || 0) + (msg.stats.skip || 0);
    }
    const execId = task.execution_id || task.run_id;
    if (execId) {
      refreshCaseStates(execId, taskId);
    }
  } else if (msg.type === 'suite_progress') {
    if (msg.stats) {
      task.passed = msg.stats.success || 0;
      task.failed = msg.stats.fail || 0;
      task.skipped = msg.stats.skip || 0;
      task.completed = (msg.stats.success || 0) + (msg.stats.fail || 0) + (msg.stats.skip || 0);
    }
  } else if (msg.type === 'run_complete') {
    stopPolling();
    stopWebSocket();
    const summary = msg.summary || {};
    task.status = summary.state === 'stopped' ? 'stopped' : 'done';
    task.completed_at = new Date().toISOString();
    if (elapsedTimers.value[taskId]) { clearInterval(elapsedTimers.value[taskId]); delete elapsedTimers.value[taskId]; }
    const execId = task.execution_id || task.run_id;
    if (execId) {
      refreshCaseStates(execId, taskId);
    }
  } else if (msg.type === 'run_error') {
    stopPolling();
    stopWebSocket();
    task.status = 'error';
    task.completed_at = new Date().toISOString();
    if (elapsedTimers.value[taskId]) { clearInterval(elapsedTimers.value[taskId]); delete elapsedTimers.value[taskId]; }
  }
}

function startWebSocket(executionId: string, taskId: string) {
  stopWebSocket();
  currentExecutionId.value = executionId;
  currentTaskId.value = taskId;
  wsFailedOnce.value = false;
  wsOnMessage(handleWebSocketMessage);
  
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  wsConnect(executionId);
  
  setTimeout(() => {
    if (!connected.value && !wsFailedOnce.value) {
      wsFailedOnce.value = true;
      stopWebSocket();
      startPolling(executionId, taskId);
    }
  }, 3000);
}

function stopWebSocket() {
  wsClose();
  currentExecutionId.value = '';
  currentTaskId.value = '';
}

function startPolling(executionId: string, taskId: string) {
  stopPolling();
  pollExecutionState(executionId, taskId);
  pollingTimer = setInterval(() => {
    if (connected.value) {
      stopPolling();
      return;
    }
    pollExecutionState(executionId, taskId);
  }, 3000);
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

async function executeTask(taskId: string) {
  const task = tasks.value.find(t => String(t.id) === String(taskId));
  if (!task || task.status === 'running') return;

  task.status = 'running';
  task.started_at = new Date().toISOString();

  try {
    const { post } = getApi();
    const data = await post<{ execution_id: string; ws_url: string }>('/executions', {
      task_id: Number(taskId),
      concurrency: concurrency.value,
      sequential: concurrency.value <= 1,
    });
    task.execution_id = data.execution_id;
    task.run_id = data.execution_id;
    elapsingSeconds.value[taskId] = 0;
    if (elapsedTimers.value[taskId]) clearInterval(elapsedTimers.value[taskId]);
    elapsedTimers.value[taskId] = setInterval(() => { elapsingSeconds.value[taskId] = (elapsingSeconds.value[taskId] || 0) + 1; }, 1000);
    // Poll immediately so UI reflects status changes right away; WebSocket supplements
    startPolling(data.execution_id, taskId);
    startWebSocket(data.execution_id, taskId);
    emit('showToast', '测试已启动!');
  } catch (e: any) {
    task.status = 'error';
    emit('showToast', '启动失败: ' + (e.message || '无法连接后端'));
  }
}

async function reRunTask(taskId: string) {
  const task = tasks.value.find(t => String(t.id) === String(taskId));
  if (!task || task.status === 'running' || task.status === 'idle') return;

  const caseStates = taskCaseStates.value[taskId];
  if (caseStates) {
    for (const c of caseStates) {
      c.status = 'waiting';
      c.id = 0;
    }
  }

  task.status = 'running';
  task.started_at = new Date().toISOString();
  task.passed = 0;
  task.failed = 0;
  task.skipped = 0;
  task.completed = 0;

  try {
    const { post } = getApi();
    const data = await post<{ execution_id: string; ws_url: string }>('/executions', {
      task_id: Number(taskId),
      concurrency: concurrency.value,
      sequential: concurrency.value <= 1,
    });
    task.execution_id = data.execution_id;
    task.run_id = data.execution_id;
    elapsingSeconds.value[taskId] = 0;
    if (elapsedTimers.value[taskId]) clearInterval(elapsedTimers.value[taskId]);
    elapsedTimers.value[taskId] = setInterval(() => { elapsingSeconds.value[taskId] = (elapsingSeconds.value[taskId] || 0) + 1; }, 1000);
    startPolling(data.execution_id, taskId);
    startWebSocket(data.execution_id, taskId);
    emit('showToast', '测试已重新启动!');
  } catch (e: any) {
    task.status = 'error';
    emit('showToast', '重跑失败: ' + (e.message || '无法连接后端'));
  }
}

async function stopTask(taskId: string) {
  const task = tasks.value.find(t => String(t.id) === String(taskId));
  if (!task || task.status !== 'running') return;

  stopPolling();
  if (elapsedTimers.value[taskId]) { clearInterval(elapsedTimers.value[taskId]); delete elapsedTimers.value[taskId]; }
  
  const execId = task.execution_id || task.run_id;
  if (execId) {
    const { post } = getApi();
    try { await post(`/executions/${execId}/stop`); } catch { /* ignore */ }
  }

  task.status = 'stopped';
  task.completed_at = new Date().toISOString();
  emit('showToast', '测试执行已停止');
}

async function executeAllTasks() {
  const idleTasks = tasks.value.filter(t => t.status === 'idle');
  if (idleTasks.length === 0) {
    emit('showToast', '没有待执行的任务');
    return;
  }
  for (const task of idleTasks) {
    await executeTask(String(task.id));
  }
}

async function deleteTask(taskId: string) {
  const task = tasks.value.find(t => String(t.id) === String(taskId));
  if (!task) return;
  if (task.status === 'running') {
    emit('showToast', '请先停止正在运行的任务');
    return;
  }
  try {
    const { del } = getApi();
    await del(`/tasks/${taskId}`);
  } catch { /* ignore */ }
  tasks.value = tasks.value.filter(t => String(t.id) !== taskId);
  delete taskCaseStates.value[taskId];
  if (selectedTaskId.value === taskId) {
    selectedTaskId.value = '';
  }
  emit('showToast', '任务已删除');
}

function startRename(taskId: string) {
  const task = tasks.value.find(t => String(t.id) === String(taskId));
  if (!task) return;
  renamingTaskId.value = taskId;
  renameInput.value = task.name;
}

async function confirmRename() {
  if (!renamingTaskId.value || !renameInput.value.trim()) return;
  const newName = renameInput.value.trim();
  const task = tasks.value.find(t => String(t.id) === renamingTaskId.value);
  if (task) {
    try {
      const { patch } = getApi();
      await patch(`/tasks/${renamingTaskId.value}`, { name: newName });
    } catch { /* ignore */ }
    task.name = newName;
  }
  renamingTaskId.value = '';
  renameInput.value = '';
}

function cancelRename() {
  renamingTaskId.value = '';
  renameInput.value = '';
}

function openMenu(taskId: string, event: MouseEvent) {
  event.stopPropagation();
  if (openMenuTaskId.value === taskId) {
    openMenuTaskId.value = '';
  } else {
    openMenuTaskId.value = taskId;
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    menuPosition.value = { top: rect.top, left: rect.right + 4 };
  }
}

function closeMenu() {
  openMenuTaskId.value = '';
}

function onDocumentClick(e: MouseEvent) {
  if (openMenuTaskId.value) {
    const target = e.target as HTMLElement;
    if (!target.closest('.task-menu')) {
      openMenuTaskId.value = '';
    }
  }
}

function getFilterCount(label: string): number {
  const map: Record<string, keyof typeof filterCounts.value> = {
    'All': 'all', '运行中': 'running', '失败': 'fail',
    '异常': 'broken', '通过': 'pass', '跳过': 'skip', '等待': 'waiting',
  };
  return filterCounts.value[map[label] || 'all'] || 0;
}

function isClickable(status: string) {
  return ['passed', 'failed', 'broken', 'skipped', 'pass', 'fail', 'skip'].includes(status);
}

async function showDetail(item: TestCaseState) {
  selectedCaseId.value = item.uid;
  detailLog.value = null;
  highlightLine.value = -1;
  activeStepIndex.value = -1;
  if (isClickable(item.status) && item.id > 0) {
    detailLoading.value = true;
    try {
      const { get } = getApi();
      const logData = await get<any>(`/execution-cases/${item.id}/log`);
      detailLog.value = {
        uid: logData.uid,
        status: logData.status,
        duration_ms: logData.duration_ms,
        message: logData.message || '',
        trace: logData.trace || '',
        logs: logData.logs || logData.message || '',
        steps: logData.steps || '',
        screenshots: logData.screenshots || '',
        executed_at: logData.end_time || logData.start_time || '',
      };
    } catch { /* ignore */ }
    detailLoading.value = false;
  }
  if (!isClickable(item.status) || item.id <= 0) {
    detailLog.value = null;
  }
}

// ── Step ↔ Log linking ──
const highlightLine = ref(-1);
const activeStepIndex = ref(-1);
const logLineRefs = ref<HTMLElement[]>([]);

interface ParsedStep {
  name: string;
  status: string;
  type?: 'api' | 'assert';
  /** Exact 0-based log line this step maps to (when parsed from the log). */
  line?: number;
}

/** Parse steps directly from the execution log text:
 *  - API calls: 【API调用】POST /api/xxx  → status from following Response line
 *  - Assertions: Assert xxx passed/failed  → status from the line itself
 *  Each step records its exact log line so clicking it can scroll precisely.
 */
function parseLogStepsFromText(logs: string): ParsedStep[] {
  const steps: ParsedStep[] = [];
  const lines = logs.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const apiMatch = line.match(/【API调用】\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\/\S+)/);
    if (apiMatch) {
      steps.push({ name: `${apiMatch[1]} ${apiMatch[2]}`, status: '', type: 'api', line: i });
      continue;
    }
    const assertMatch = line.match(/Assert\s+([^:]+?)\s+(passed|failed)(?::\s*(.*))?$/);
    if (assertMatch) {
      const detail = assertMatch[3] ? ` (${assertMatch[3]})` : '';
      steps.push({ name: `断言: ${assertMatch[1].trim()}${detail}`, status: assertMatch[2], type: 'assert', line: i });
      continue;
    }
    const respMatch = line.match(/Response:\s*(\d{3})/);
    if (respMatch) {
      const code = parseInt(respMatch[1], 10);
      let j = steps.length - 1;
      while (j >= 0 && steps[j].status) j--;
      if (j >= 0) {
        steps[j].status = code >= 200 && code < 300 ? 'passed' : 'failed';
      }
      continue;
    }
  }
  return steps;
}

/** Match case-defined steps (from the case detail: 调用xxx接口 / 断言xxx) against
 *  the steps parsed from the execution log, so each definition step gets a
 *  precise log line + result status. Matching strategy:
 *   1. api steps: try to match the source method name (from `method`/`code`) against
 *      the raw log line of each unassigned api log-step;
 *   2. otherwise align by order within the same type (api/assert);
 *   3. steps with no remaining log counterpart are left unexecuted (status '').
 */
function buildDefinitionSteps(rawSteps: string, logs: string): ParsedStep[] {
  let defs: any[] = [];
  try {
    defs = JSON.parse(rawSteps || '');
  } catch { /* fall through */ }
  if (!Array.isArray(defs) || defs.length === 0) return [];

  const logSteps = parseLogStepsFromText(logs || '');
  const lines = (logs || '').split('\n');
  const used = new Set<number>(); // indices of already-assigned log steps

  function matchByKeyword(def: any, type: 'api' | 'assert', candidates: number[]): number {
    let kw = '';
    if (type === 'api') {
      kw = String(def.method || '');
      if (!kw && def.code) {
        const m = String(def.code).match(/(?:\.|\b)([A-Za-z_]\w*)\s*\(/);
        kw = m ? m[1] : '';
      }
    }
    if (!kw) return -1;
    for (const ci of candidates) {
      if (used.has(ci)) continue;
      if ((lines[logSteps[ci].line!] || '').includes(kw)) return ci;
    }
    return -1;
  }

  const byType: Record<string, number[]> = { api: [], assert: [] };
  logSteps.forEach((s, i) => { if (s.type) byType[s.type].push(i); });

  return defs.map((def: any) => {
    const type: 'api' | 'assert' = def.type === 'assert' ? 'assert' : 'api';
    const candidates = byType[type];
    let assigned = -1;
    // 1) keyword match on the raw log line
    assigned = matchByKeyword(def, type, candidates);
    // 2) order-based alignment within the same type
    if (assigned < 0) {
      for (const ci of candidates) {
        if (!used.has(ci)) { assigned = ci; break; }
      }
    }
    let status = '';
    let line: number | undefined;
    if (assigned >= 0) {
      used.add(assigned);
      status = logSteps[assigned].status || '';
      line = logSteps[assigned].line;
    }
    return {
      name: def.description || def.code || '',
      status,
      type,
      line,
    };
  });
}

const parsedSteps = computed<ParsedStep[]>(() => {
  // 1) Case-defined steps from the case detail (自动化里的步骤), linked to the log
  if (activeCase.value?.steps) {
    const defSteps = buildDefinitionSteps(activeCase.value.steps, detailLog.value?.logs || '');
    if (defSteps.length > 0) return defSteps;
  }
  // 2) Allure-style execution steps (name + status)
  if (detailLog.value?.steps) {
    try {
      const raw = JSON.parse(detailLog.value.steps);
      if (Array.isArray(raw) && raw.length > 0) {
        return raw
          .filter((s: any) => s && typeof s.name === 'string')
          .map((s: any) => ({ name: s.name, status: s.status || '' }));
      }
    } catch {
      /* fall through to log parsing */
    }
  }
  // 3) Steps parsed from the log itself (precise line linking)
  return parseLogStepsFromText(detailLog.value?.logs || '');
});

const logLines = computed<string[]>(() => {
  const logs = detailLog.value?.logs || '';
  if (!logs) return [];
  return logs.split('\n');
});

function statusOfStep(status: string): string {
  if (status === 'passed' || status === 'pass') return 'success';
  if (status === 'failed' || status === 'fail') return 'fail';
  if (status === 'broken') return 'broken';
  if (status === 'skipped' || status === 'skip') return 'skip';
  return '';
}

/** Result glyph for a step: ✓ pass / ✗ fail / – skip / '' not executed */
function stepResultSymbol(status: string): string {
  const s = statusOfStep(status);
  if (s === 'success') return '✓';
  if (s === 'fail' || s === 'broken') return '✗';
  if (s === 'skip') return '–';
  return '';
}

/** Find the log line (0-based) that best matches a step keyword. */
function findLogLineIndex(keyword: string): number {
  if (!keyword) return -1;
  const kw = keyword.trim();
  const lines = logLines.value;
  // 1) exact substring match (first occurrence)
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(kw)) return i;
  }
  // 2) fuzzy: split keyword into words, match line containing all words
  const words = kw.split(/[\s_\-:/，。；：]+/).filter(w => w.length >= 2);
  if (words.length > 0) {
    for (let i = 0; i < lines.length; i++) {
      if (words.every(w => lines[i].includes(w))) return i;
    }
  }
  // 3) fallback to next step's start or last line
  return -1;
}

function jumpToStep(index: number) {
  const step = parsedSteps.value[index];
  if (!step) return;
  activeStepIndex.value = index;
  let lineIdx = step.line ?? -1;
  if (lineIdx < 0) {
    lineIdx = findLogLineIndex(step.name);
  }
  if (lineIdx >= 0) {
    highlightLine.value = lineIdx;
    nextTick(() => {
      const el = logLineRefs.value[lineIdx];
      if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
  } else {
    highlightLine.value = -1;
  }
}

function stepStatusBadgeClass(status: string): string {
  const s = statusOfStep(status);
  return s ? 'step-badge-' + s : '';
}

function copyPath() {
  if (activeCase.value) {
    const text = activeCase.value.className
      ? `${activeCase.value.className}::${activeCase.value.methodName || activeCase.value.name}`
      : activeCase.value.name;
    navigator.clipboard.writeText(text);
    emit('showToast', '已复制: ' + text);
  }
}

function formatElapsed(secs: number) {
  const h = Math.floor(secs / 3600).toString().padStart(2, '0');
  const m = Math.floor((secs % 3600) / 60).toString().padStart(2, '0');
  const s = (secs % 60).toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function formatDurationMs(ms?: number): string {
  if (ms == null || ms <= 0) return '';
  if (ms < 1000) return ms + 'ms';
  const secs = ms / 1000;
  if (secs < 60) return secs.toFixed(1) + 's';
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m}m${s}s`;
}

function formatExecTime(iso: string) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch { return iso; }
}

async function loadHistoryTasks() {
  try {
    const { get } = getApi();
    const taskResp = await get<{ items: { id: number; name: string; status: string; total: number; create_time: string }[]; total: number }>('/tasks');
    const taskList = taskResp.items || [];

    const execResp = await get<{ items: ExecutionRecord[]; total: number }>('/executions');
    const executions = execResp.items || [];
    const taskExecMap: Record<number, ExecutionRecord> = {};
    for (const e of executions) {
      if (!taskExecMap[e.task_id]) {
        taskExecMap[e.task_id] = e;
      }
    }

    for (const t of taskList) {
      const existingTask = tasks.value.find(task => String(task.id) === String(t.id));
      if (existingTask) continue;

      const exec = taskExecMap[t.id];
      const taskStatus = exec
        ? (exec.status === 'running' ? 'running' : exec.status === 'finished' ? 'done' : exec.status === 'stopped' ? 'stopped' : 'error')
        : 'idle';

      const task: TestTask = {
        id: t.id,
        name: t.name || `测试任务 ${new Date(t.create_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`,
        status: taskStatus as TestTask['status'],
        uids: [],
        total: t.total,
        passed: exec?.success || 0,
        failed: exec?.fail || 0,
        broken: 0,
        skipped: exec?.skip || 0,
        completed: (exec?.success || 0) + (exec?.fail || 0) + (exec?.skip || 0),
        execution_id: exec?.execution_id,
        run_id: exec?.execution_id,
        created_at: t.create_time,
        started_at: exec?.start_time,
        completed_at: exec?.end_time,
      };
      tasks.value.push(task);

      const caseStates: TestCaseState[] = [];
      if (exec) {
        try {
          const casesResp = await get<{ items: ExecutionCaseItem[]; total: number }>(`/executions/${exec.execution_id}/cases/all`);
          for (const c of casesResp.items || []) {
            let defSteps = '';
            try {
              const info = await get<TestCaseInfo>(`/tests/${c.uid}`);
              defSteps = info.steps || '';
            } catch { /* definition steps unavailable for this uid */ }
            caseStates.push({
              uid: c.uid,
              id: c.id,
              status: c.status as TestCaseState['status'],
              name: c.description || c.case_name || c.method_name || c.uid,
              description: c.description || '',
              methodName: c.method_name || '',
              className: c.class_name || '',
              duration_ms: c.duration_ms != null ? c.duration_ms : undefined,
              steps: defSteps,
            });
          }
        } catch { /* fallback */ }
      }

      if (caseStates.length === 0) {
        try {
          const taskDetail = await get<{ uids: string[] }>(`/tasks/${t.id}`);
          const uids = taskDetail.uids || [];
          task.uids = uids;
          for (const uid of uids) {
            try {
              const info = await get<TestCaseInfo>(`/tests/${uid}`);
              caseStates.push({
                uid, id: 0,
                status: 'waiting',
                name: info.description || info.name || info.methodName || uid,
                description: info.description || '',
                methodName: info.methodName || '',
                className: info.className || '',
                steps: info.steps || '',
              });
            } catch {
              caseStates.push({ uid, id: 0, status: 'waiting', name: uid, description: '', methodName: '', className: '' });
            }
          }
        } catch { /* ignore */ }
      }
      taskCaseStates.value[String(t.id)] = caseStates;
    }

    if (tasks.value.length > 0 && !selectedTaskId.value) {
      selectedTaskId.value = String(tasks.value[0].id);
    }
  } catch {
    // ignore
  }
}

watch(() => props.selectedUids, (uids) => {
  if (uids.length > 0) createTask(uids);
}, { immediate: true });

watch(selectedTaskId, (newId) => {
  detailLog.value = null;
  selectedStatusFilters.value = new Set();
  if (newId) {
    const states = taskCaseStates.value[newId];
    if (states && states.length > 0) {
      selectedCaseId.value = states[0].uid;
      if (isClickable(states[0].status) && states[0].id > 0) {
        showDetail(states[0]);
      }
    }
  } else {
    selectedCaseId.value = '';
  }
});

watch(activeProject, async () => {
  tasks.value = [];
  taskCaseStates.value = {};
  selectedTaskId.value = '';
  await loadHistoryTasks();
});

onMounted(async () => {
  document.addEventListener('click', onDocumentClick, true);
  await getActiveProject();
  await loadHistoryTasks();
  for (const task of tasks.value) {
    if (task.status === 'running') {
      const execId = task.execution_id || task.run_id;
      if (execId) {
        startPolling(execId, String(task.id));
        const taskId = String(task.id);
        let initialSeconds = 0;
        if (task.started_at) {
          try {
            const startTime = new Date(task.started_at).getTime();
            const now = Date.now();
            initialSeconds = Math.max(0, Math.floor((now - startTime) / 1000));
          } catch { /* ignore */ }
        }
        elapsingSeconds.value[taskId] = initialSeconds;
        if (elapsedTimers.value[taskId]) clearInterval(elapsedTimers.value[taskId]);
        elapsedTimers.value[taskId] = setInterval(() => { elapsingSeconds.value[taskId] = (elapsingSeconds.value[taskId] || 0) + 1; }, 1000);
      }
    }
  }
});

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick, true);
  stopPolling();
  for (const timer of Object.values(elapsedTimers.value)) {
    clearInterval(timer);
  }
});

const STATUS_LABELS: Record<string, string> = {
  waiting: '等待', running: '运行中',
  pass: '通过', fail: '失败',
  broken: '异常', skip: '跳过',
};

const TASK_STATUS_LABELS: Record<string, string> = {
  idle: '待运行', running: '运行中',
  done: '测试成功', stopped: '已停止',
  error: '测试失败',
};
</script>

<template>
  <div class="execution-container flex-1 flex min-h-0 w-full overflow-hidden">
    <!-- macOS Sidebar -->
    <aside 
      class="execution-sidebar w-[260px] flex flex-col shrink-0 min-h-0 glass"
    >
      <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0">
        <h3 class="sidebar-title">测试任务</h3>
      </div>

      <!-- Task List -->
      <div class="flex-1 overflow-y-auto px-[12px] pb-[10px] space-y-[8px] select-none">
        <div v-if="tasks.length === 0" class="text-center py-8 text-[var(--text-tertiary)] text-xs">
          暂无测试任务<br/>
        </div>
        <div
          v-for="task in filteredTasks"
          :key="task.id"
          @click="selectedTaskId = String(task.id); closeMenu()"
          class="task-card p-[12px] rounded-[12px] cursor-pointer transition-all relative group"
          :class="[
            String(selectedTaskId) === String(task.id)
              ? 'task-card-selected'
              : 'task-card-default'
          ]"
        >
          <button
            v-if="task.status !== 'running'"
            @click="openMenu(String(task.id), $event)"
            class="task-menu-btn absolute top-[8px] right-[8px] w-[22px] h-[22px] rounded-[6px] flex items-center justify-center text-[14px] opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer z-10"
            title="更多操作"
          >
            ⋮
          </button>
          <div
            class="text-[13px] font-medium truncate mb-[8px] task-card-title" style="color: var(--text-primary);">
            {{ task.name.substring(0, 20) }}{{ task.name.length > 20 ? '...' : '' }}
          </div>
          <div class="flex justify-between items-center">
            <span class="task-status-badge text-[10.5px] font-semibold px-[8px] py-[3px] rounded-full"
              :class="{
                'badge-idle': task.status === 'idle',
                'badge-running': task.status === 'running',
                'badge-done': task.status === 'done',
                'badge-stopped': task.status === 'stopped',
                'badge-error': task.status === 'error'
              }"
            >
              {{ TASK_STATUS_LABELS[task.status] }}
            </span>
            <span class="text-[11px] task-count" style="color: var(--text-secondary);">{{ task.completed || 0 }}/{{ task.total }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Task menu popup: teleported to body so position:fixed keeps the viewport
         as its containing block (a transform on .task-card would otherwise hijack
         the containing block and offset the menu by the card's own position). -->
    <Teleport to="body">
      <div
        v-if="openMenuTaskId"
        class="task-menu fixed w-[130px] z-[100] py-[4px]"
        :style="{ top: menuPosition.top + 'px', left: menuPosition.left + 'px', backgroundColor: 'var(--card-bg)', borderColor: 'var(--outline)' }"
      >
        <button
          @click.stop="startRename(openMenuTaskId); closeMenu()"
          class="w-full px-[14px] py-[8px] text-left text-[12.5px] cursor-pointer hover:bg-[var(--row-hover)]"
          style="color: var(--text-primary);"
        >
          重命名
        </button>
        <button
          @click.stop="deleteTask(openMenuTaskId); closeMenu()"
          class="w-full px-[14px] py-[8px] text-left text-[12.5px] cursor-pointer hover:bg-[var(--row-hover)]"
          style="color: var(--red);"
        >
          删除任务
        </button>
      </div>
    </Teleport>

    <!-- Main Content -->
    <main class="flex-1 flex flex-col min-h-0 overflow-hidden" style="background-color: var(--content-bg);">
      <!-- Empty State -->
      <div v-if="!selectedTask" class="flex-1 flex items-center justify-center" style="color: var(--text-tertiary);">
        <div class="text-center">
          <span class="text-6xl block mb-4 opacity-30">▢</span>
          <p class="text-[15px]">请从左侧选择一个测试任务查看详情</p>
        </div>
      </div>

      <template v-else>
        <!-- macOS Header -->
        <div class="exec-header px-[24px] pt-[20px] pb-[16px] flex justify-between items-start shrink-0">
          <div class="flex flex-col gap-[6px]">
            <div class="flex items-center gap-3">
              <h2 class="text-[15px] font-semibold tracking-[-0.01em]" style="color: var(--text-primary);">任务详情</h2>
              <div v-if="renamingTaskId === String(selectedTask.id)" class="flex items-center gap-2">
                <input
                  v-model="renameInput"
                  @keyup.enter="confirmRename"
                  @keyup.esc="cancelRename"
                  @blur="confirmRename"
                  @input="renameInput = renameInput.substring(0, 20)"
                  maxlength="20"
                  class="rename-input px-[10px] py-[6px] text-[12.5px] rounded-[8px] border outline-none"
                  style="background-color: var(--card-bg); border-color: var(--accent); color: var(--text-primary);"
                  autofocus
                />
              </div>
              <div v-else class="flex items-center gap-2">
                <span class="text-[13px]" style="color: var(--text-tertiary);">
                  {{ selectedTask.name.substring(0, 20) }}{{ selectedTask.name.length > 20 ? '...' : '' }}
                </span>
                <button
                  @click="startRename(String(selectedTask.id))"
                  class="icon-btn w-[26px] h-[26px] rounded-[8px] flex items-center justify-center text-[12px] cursor-pointer transition-all"
                  title="重命名"
                >
                  ✏
                </button>
              </div>
            </div>
            <span v-if="selectedTask.completed_at || selectedTask.created_at" class="text-[11px]" style="color: var(--text-tertiary);">
              {{ formatExecTime(selectedTask.completed_at || selectedTask.created_at) }}
            </span>
          </div>
          <div class="flex items-center gap-[10px]">
            <button
              v-if="selectedTask.status === 'idle'"
              @click="executeTask(String(selectedTask.id))"
              class="action-btn action-btn-play"
              title="开始执行"
            >
              ▶
            </button>
            <button
              v-if="selectedTask.status === 'running'"
              @click="stopTask(String(selectedTask.id))"
              class="action-btn action-btn-stop"
              title="停止执行"
            >
              ■
            </button>
            <button
              v-if="selectedTask.status === 'done' || selectedTask.status === 'stopped' || selectedTask.status === 'error'"
              @click="reRunTask(String(selectedTask.id))"
              class="action-btn action-btn-replay"
              title="重新执行"
            >
              ↻
            </button>
          </div>
        </div>

        <!-- macOS Metric Card -->
        <div class="px-[24px] mb-[16px] shrink-0">
          <div class="metric-card p-[20px_24px] grid grid-cols-[auto_1fr] gap-[28px]">
            <!-- Progress Ring -->
            <div class="w-[80px] h-[80px] relative">
              <svg width="80" height="80" class="transform -rotate-90">
                <circle cx="40" cy="40" r="34" stroke="var(--input-bg)" stroke-width="6" fill="none"/>
                <circle v-if="taskCounts.success + taskCounts.fail + taskCounts.skip > 0" cx="40" cy="40" r="34" 
                  :stroke="taskCounts.passRate >= 80 ? 'var(--color-success)' : 'var(--red)'" 
                  stroke-width="6" fill="none" stroke-dasharray="213.6" 
                  :stroke-dashoffset="213.6 * (1 - taskCounts.passRate / 100)" stroke-linecap="round"/>
              </svg>
              <div class="absolute inset-0 flex items-center justify-center text-[17px] font-semibold" 
                :style="{ color: (taskCounts.success + taskCounts.fail + taskCounts.skip) > 0 ? (taskCounts.passRate >= 80 ? 'var(--color-success)' : 'var(--red)') : 'var(--text-tertiary)' }">
                {{ (taskCounts.success + taskCounts.fail + taskCounts.skip) > 0 ? taskCounts.passRate + '%' : '--' }}
              </div>
            </div>
            <!-- Stats -->
            <div class="text-[13px]" style="color: var(--text-secondary);">
              <div class="flex justify-between mb-[10px]">
                <span>通过率 · 目标 &gt;80%</span>
                <span class="font-medium">耗时 {{ formatElapsed(taskCounts.elapsed) }}</span>
              </div>
              <!-- macOS Bar Chart -->
              <div class="bar-chart h-[20px] rounded-full mb-[12px] flex overflow-hidden" style="background-color: var(--input-bg);">
                <div
                  v-for="seg in barChartSegments"
                  :key="seg.status"
                  class="bar-segment h-full flex-shrink-0 transition-all relative group cursor-pointer"
                  :class="[seg.bgClass]"
                  :style="{ width: taskCounts.total > 0 ? (seg.count / taskCounts.total * 100) + '%' : '0%' }"
                >
                  <div 
                    class="bar-tooltip absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity rounded-full text-[11px] font-semibold"
                    style="background-color: rgba(0,0,0,0.55); color: #fff;"
                  >
                    {{ seg.label }}: {{ seg.count }}
                  </div>
                </div>
              </div>
              <div class="flex gap-[24px] text-[12px]">
                <span class="stat-item">并发数 <b>{{ concurrency }}</b></span>
                <span class="stat-item">通过率 <b>{{ taskCounts.passRate }}%</b></span>
                <span class="stat-item">状态 <b>{{ TASK_STATUS_LABELS[selectedTask.status] }}</b></span>
              </div>
            </div>
          </div>
        </div>

        <!-- macOS Filter Pills -->
        <div class="px-[24px] pb-[12px] flex gap-[6px] flex-wrap shrink-0">
          <button
            @click="selectedStatusFilters = new Set()"
            class="filter-pill px-[14px] py-[6px] rounded-full text-[11.5px] font-medium transition-all cursor-pointer"
            :class="selectedStatusFilters.size === 0 ? 'filter-pill-active' : 'filter-pill-inactive'"
            :style="{ backgroundColor: selectedStatusFilters.size === 0 ? 'var(--accent)' : 'var(--input-bg)' }"
          >
            全部<span class="ml-[4px] opacity-70"></span>
          </button>
          <button
            v-for="seg in barChartSegments"
            :key="'tag-' + seg.status"
            @click="toggleStatusFilter(seg.status)"
            class="filter-pill px-[14px] py-[6px] rounded-full text-[11.5px] font-medium transition-all cursor-pointer"
            :class="selectedStatusFilters.has(seg.status) ? 'filter-pill-active' : 'filter-pill-inactive'"
            :style="{ backgroundColor: selectedStatusFilters.has(seg.status) ? seg.color : 'var(--input-bg)' }"
          >
            {{ seg.label }}<span class="ml-[4px] opacity-70">{{ seg.count }}</span>
          </button>
        </div>

        <!-- macOS Panels Grid -->
        <div class="flex-1 min-h-0 px-[24px] pb-[20px]">
          <div class="grid grid-cols-[290px_1fr] gap-[16px] h-full">
            <!-- Execution Queue Panel -->
            <div class="exec-panel border rounded-[14px] overflow-hidden flex flex-col" style="border-color: var(--border);">
              <div 
                class="panel-header px-[14px] py-[10px] border-b text-[11.5px] font-semibold uppercase tracking-[0.03em] shrink-0"
                style="color: var(--text-tertiary);"
              >
                执行队列<span class="ml-[6px] opacity-70">{{ filteredQueue.length }}</span>
              </div>
              <div class="flex-1 overflow-y-auto">
                <div v-if="filteredQueue.length === 0" class="text-center py-8 text-[var(--text-tertiary)] text-sm">
                  没有匹配的用例
                </div>
                <div
                  v-for="item in filteredQueue"
                  :key="item.uid"
                  @click="showDetail(item)"
                  class="queue-item px-[14px] py-[10px] border-b cursor-pointer transition-all"
                  :class="{ 'queue-item-selected': selectedCaseId === item.uid }"
                  style="border-color: var(--border);"
                >
                  <div class="flex items-center justify-between gap-2">
                    <div class="text-[13px] font-medium truncate min-w-0" style="color: var(--text-primary);" :title="item.name">{{ item.name }}</div>
                    <span class="queue-status-badge shrink-0 text-[10.5px] font-semibold px-[8px] py-[3px] rounded-full"
                      :class="{
                        'badge-pass': item.status === 'pass',
                        'badge-fail': item.status === 'fail',
                        'badge-broken': item.status === 'broken',
                        'badge-skip': item.status === 'skip' || item.status === 'waiting',
                        'badge-running': item.status === 'running',
                      }"
                    >
                      {{ STATUS_LABELS[item.status] }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between gap-2 mt-[3px]">
                    <div class="text-[11px] truncate min-w-0" style="color: var(--text-tertiary);" :title="item.methodName">{{ item.methodName }}</div>
                    <span v-if="item.duration_ms != null && item.duration_ms > 0" class="queue-duration shrink-0 text-[10.5px] font-mono" style="color: var(--text-tertiary);">
                      {{ formatDurationMs(item.duration_ms) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Detail Panel -->
            <div 
              class="detail-panel border rounded-[14px] p-[18px_20px] flex flex-col min-w-0 overflow-hidden select-text"
              style="background-color: var(--card-bg-2); border-color: var(--border);"
            >
              <template v-if="activeCase">
                <h2 class="text-[15px] font-semibold mb-[4px]" style="color: var(--text-primary);">{{ activeCase.name }}</h2>
                <div class="detail-path font-code text-[12px] mb-[14px]" style="color: var(--text-secondary);">
                  {{ activeCase.className ? activeCase.className + ' :: ' : '' }}{{ activeCase.methodName || activeCase.name }}
                </div>
                <div v-if="detailLoading" class="text-center py-4" style="color: var(--text-tertiary);">
                  加载中...
                </div>
                <template v-else-if="detailLog">
                  <!-- Steps directory + log lines (linked) -->
                  <div v-if="parsedSteps.length > 0" class="flex-1 min-h-0 flex flex-col mt-[4px]">
                    <div class="section-label text-[11.5px] font-semibold uppercase tracking-[0.04em] mb-[6px]" style="color: var(--text-tertiary);">步骤与日志</div>
                    <div class="steps-log-layout flex-1 min-h-0 flex gap-[10px]">
                      <!-- Steps directory -->
                      <div class="steps-panel w-[220px] min-w-[180px] shrink-0 flex flex-col rounded-[10px] overflow-hidden"
                        style="background-color: var(--card-bg); border: 1px solid var(--border);"
                      >
                        <div class="steps-panel-header px-[10px] py-[7px] text-[11px] font-semibold" style="color: var(--text-tertiary); border-bottom: 1px solid var(--border);">步骤目录</div>
                        <div class="steps-list flex-1 overflow-y-auto py-[4px]">
                          <div
                            v-for="(step, idx) in parsedSteps"
                            :key="idx"
                            @click="jumpToStep(idx)"
                            class="step-item px-[10px] py-[6px] cursor-pointer text-[12px] flex items-start gap-[7px]"
                            :class="[ activeStepIndex === idx ? 'step-item-active' : '', 'step-item-' + statusOfStep(step.status) ]"
                          >
                            <span class="step-result shrink-0 mt-[1px] w-[16px] text-center font-semibold"
                              :class="'step-result-' + statusOfStep(step.status)"
                            >{{ stepResultSymbol(step.status) }}</span>
                            <span class="step-name min-w-0 flex-1 break-words">{{ step.name }}</span>
                          </div>
                          <div v-if="parsedSteps.length === 0" class="px-[10px] py-[8px] text-[11.5px]" style="color: var(--text-tertiary);">暂无步骤</div>
                        </div>
                      </div>
                      <!-- Log lines -->
                      <div class="log-panel flex-1 min-w-0 flex flex-col rounded-[10px] overflow-hidden"
                        style="background-color: var(--card-bg); border: 1px solid var(--border);"
                      >
                        <div class="log-panel-header px-[10px] py-[7px] text-[11px] font-semibold" style="color: var(--text-tertiary); border-bottom: 1px solid var(--border);">日志信息</div>
                        <div class="log-lines flex-1 overflow-auto font-mono text-[12px] leading-[1.6]" style="color: var(--text-secondary);">
                          <template v-if="logLines.length > 0">
                            <div
                              v-for="(line, idx) in logLines"
                              :key="idx"
                              :ref="el => { if (el) (logLineRefs as any)[idx] = el }"
                              class="log-line px-[10px] whitespace-pre-wrap break-all"
                              :class="{ 'log-line-highlight': highlightLine === idx, 'log-line-hover': activeStepIndex >= 0 && highlightLine === idx }"
                            >{{ line }}</div>
                          </template>
                          <div v-else class="px-[10px] py-[8px]" style="color: var(--text-tertiary);">暂无日志</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- Plain log fallback (no steps) -->
                  <div v-else class="flex-1 min-h-0 flex flex-col">
                    <div class="section-label text-[11.5px] font-semibold uppercase tracking-[0.04em] mb-[6px]" style="color: var(--text-tertiary);">执行日志</div>
                    <div 
                      class="log-viewer flex-1 p-[10px_12px] rounded-[10px] text-[12px] font-code overflow-auto whitespace-pre-wrap"
                      style="background-color: var(--card-bg); border: 1px solid var(--border); color: var(--text-secondary);"
                    >
                      {{ detailLog.logs || detailLog.message || '暂无日志' }}
                    </div>
                  </div>
                  <div v-if="detailLog.trace" class="mt-[12px] shrink-0 flex flex-col" style="max-height: 35%;">
                    <div class="section-label text-[11.5px] font-semibold uppercase tracking-[0.04em] mb-[6px]" style="color: var(--red);">错误堆栈</div>
                    <div 
                      class="trace-viewer p-[10px_12px] rounded-[10px] text-[12px] font-code overflow-auto whitespace-pre-wrap"
                      style="background-color: rgba(255,59,48,0.05); border: 1px solid var(--red); color: var(--red);"
                    >
                      {{ detailLog.trace }}
                    </div>
                  </div>
                </template>
                <div v-else-if="isClickable(activeCase.status)" class="text-center py-4" style="color: var(--text-tertiary);">
                  点击用例查看日志
                </div>
              </template>
              <div v-else class="flex-1 flex items-center justify-center" style="color: var(--text-tertiary);">
                请从左侧队列选择一个用例查看详情
              </div>
            </div>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
/* macOS Font */
.execution-container {
  font-family: var(--font);
}

.sidebar-title {
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

/* macOS Sidebar */
.execution-sidebar {
  background-color: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  /* Raise the sidebar's stacking context so its popup menus (task-menu)
     are never covered by right-side detail elements (which also create
     stacking contexts via backdrop-filter). */
  z-index: 5;
}

/* Task Cards */
.task-card {
  transition: all 0.15s ease;
}
.task-card-default {
  background-color: var(--card-bg-2);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
}
.task-card-default:hover {
  background-color: var(--bg-card-hover);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.task-card-selected {
  background-color: var(--selected-bg);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
}
.task-card-selected:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.task-card-title {
  letter-spacing: -0.01em;
}
.task-menu-btn {
  background-color: var(--input-bg);
  color: var(--text-secondary);
  border: none;
}
.task-menu-btn:hover {
  background-color: var(--border);
}
.task-menu {
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 2px solid var(--outline);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-hard-lg), var(--shadow-popover);
}

/* Task Status Badges */
.task-status-badge {
  letter-spacing: 0.01em;
}
.badge-idle {
  background-color: var(--warning-soft);
  color: var(--color-warning);
}
.badge-running {
  background-color: var(--success-soft);
  color: var(--color-success);
}
.badge-done {
  background-color: var(--color-primary-soft);
  color: var(--accent);
}
.badge-stopped {
  background-color: var(--warning-soft);
  color: var(--color-warning);
}
.badge-error {
  background-color: var(--danger-soft);
  color: var(--red);
}
.task-count {
  font-variant-numeric: tabular-nums;
}

/* macOS Header */
.exec-header {
  border-bottom: 2px solid var(--outline);
}
.page-title {
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
.icon-btn {
  background-color: var(--input-bg);
  border: 2px solid var(--outline);
  color: var(--text-tertiary);
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}
.icon-btn:hover {
  background-color: var(--border);
  color: var(--text-secondary);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.rename-input {
  font-family: inherit;
  font-size: 12.5px;
  border-radius: 8px;
}

/* macOS Action Buttons */
.action-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 2px solid var(--outline);
  color: #fff;
  position: relative;
}
.action-btn:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
}
.action-btn-play {
  background-color: var(--green);
  box-shadow: var(--shadow-hard-sm);
}
.action-btn-play:hover {
  box-shadow: var(--shadow-hard-sm-pressed);
  transform: translate(2px, 2px);
}
.action-btn-stop {
  background-color: var(--red);
  box-shadow: var(--shadow-hard-sm);
}
.action-btn-stop:hover {
  box-shadow: var(--shadow-hard-sm-pressed);
  transform: translate(2px, 2px);
}
.action-btn-replay {
  background-color: var(--accent);
  box-shadow: var(--shadow-hard-sm);
}
.action-btn-replay:hover {
  box-shadow: var(--shadow-hard-sm-pressed);
  transform: translate(2px, 2px);
}

/* macOS Metric Card */
.metric-card {
  background-color: var(--card-bg);
  border: 2px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg);
}

/* macOS Bar Chart */
.bar-chart {
  box-shadow: inset 0 0.5px 1px rgba(0,0,0,0.06);
}
.bar-segment {
  transition: width 0.4s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.bar-segment:first-child {
  border-radius: 999px 0 0 999px;
}
.bar-segment:last-child {
  border-radius: 0 999px 999px 0;
}
.bar-segment:only-child {
  border-radius: 999px;
}
.bar-tooltip {
  z-index: 2;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

/* Stat Items */
.stat-item b {
  color: var(--text-primary);
  font-weight: 600;
  margin-left: 2px;
}

/* macOS Filter Pills */
.filter-pill {
  letter-spacing: 0.01em;
  border: 2px solid transparent;
}
.filter-pill-active {
  color: #fff;
  border-color: var(--outline);
  box-shadow: var(--shadow-hard-sm);
}
.filter-pill-active:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.filter-pill-inactive {
  color: var(--text-secondary);
  background-color: var(--input-bg);
  border-color: var(--outline);
}
.filter-pill-inactive:hover {
  background-color: var(--border);
  color: var(--text-primary);
}

/* macOS Panels */
.exec-panel {
  background-color: var(--card-bg-2);
  box-shadow: 0 0.5px 1px rgba(0,0,0,0.04);
}
.panel-header {
  background-color: var(--card-bg-2);
}

/* Queue Items */
.queue-item {
  transition: all 0.15s ease;
}
.queue-item:hover {
  background-color: var(--row-hover);
}
.queue-item-selected {
  background-color: var(--selected-bg);
}
.queue-item-selected:hover {
  background-color: var(--selected-bg);
}

/* Queue Status Badges */
.queue-status-badge {
  letter-spacing: 0.01em;
}
.badge-pass {
  background-color: var(--success-soft);
  color: var(--color-success);
}
.badge-fail {
  background-color: rgba(255, 69, 58, 0.15);
  color: var(--red);
}
.badge-broken {
  background-color: rgba(191, 90, 242, 0.15);
  color: var(--purple);
}
.badge-skip {
  background-color: var(--input-bg);
  color: var(--text-secondary);
}
.badge-running {
  background-color: rgba(10, 132, 255, 0.15);
  color: var(--accent);
}

/* Detail Panel */
.detail-panel {
  box-shadow: 0 0.5px 1px rgba(0,0,0,0.04);
}
.detail-path {
  font-family: var(--font-mono);
}
.section-label {
  letter-spacing: 0.04em;
}
.detail-description {
  line-height: 1.5;
}

/* Log Viewer */
.log-viewer {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  line-height: 1.6;
  tab-size: 2;
}
.trace-viewer {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  line-height: 1.6;
  tab-size: 2;
}

/* ── Steps ↔ Log linking ── */
.steps-log-layout {
  min-height: 0;
}

.steps-panel,
.log-panel {
  min-height: 0;
}

.steps-panel-header,
.log-panel-header {
  flex-shrink: 0;
}

.steps-list,
.log-lines {
  min-height: 0;
}

.step-item {
  transition: background 0.12s ease;
}

.step-item:hover {
  background: var(--row-hover);
}

.step-item-active {
  background: var(--selected-bg);
  color: var(--accent);
  font-weight: 500;
}

.step-result {
  flex-shrink: 0;
  font-family: var(--font-mono);
  line-height: 1.5;
}

.step-result-success {
  color: var(--color-success);
}
.step-result-fail {
  color: var(--red);
}
.step-result-broken {
  color: var(--purple);
}
.step-result-skip {
  color: var(--text-tertiary);
}

.step-item-success .step-name {
  color: var(--color-success);
}
.step-item-fail .step-name {
  color: var(--red);
}
.step-item-broken .step-name {
  color: var(--purple);
}
.step-item-skip .step-name {
  color: var(--text-tertiary);
}

.log-lines {
  scrollbar-width: thin;
}

.log-line {
  transition: background 0.15s ease;
}

.log-line-highlight {
  background: rgba(255, 204, 0, 0.22) !important;
  color: var(--text-primary) !important;
  box-shadow: inset 2px 0 0 var(--color-warning);
}
</style>