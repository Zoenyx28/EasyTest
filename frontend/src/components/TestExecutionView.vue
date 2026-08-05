<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
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
  selectedTaskId.value = task.id;
  
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
        executed_at: logData.end_time || logData.start_time || '',
      };
    } catch { /* ignore */ }
    detailLoading.value = false;
  }
  if (!isClickable(item.status) || item.id <= 0) {
    detailLog.value = null;
  }
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

function formatDateTime(iso: string) {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleString('zh-CN', { 
      month: '2-digit', 
      day: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  } catch { return iso; }
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
            caseStates.push({
              uid: c.uid,
              id: c.id,
              status: c.status as TestCaseState['status'],
              name: c.case_name || c.method_name || c.uid,
              description: '',
              methodName: c.method_name || '',
              className: c.class_name || '',
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
      <!-- macOS Traffic Light Dots -->
      <div class="traffic-lights flex items-center gap-[8px] px-[14px] pt-[14px] pb-[10px] shrink-0">
        <span class="flex items-center justify-between px-[16px] py-[12px] shrink-0">测试任务</span>
      </div>

      <!-- Task List -->
      <div class="flex-1 overflow-y-auto px-[12px] pb-[10px] space-y-[8px] select-none">
        <div v-if="tasks.length === 0" class="text-center py-8 text-[var(--text-tertiary)] text-xs">
          暂无测试任务<br/>请从用例总览页选择用例并点击"执行选中"或"执行全部"创建任务
        </div>
        <div
          v-for="task in filteredTasks"
          :key="task.id"
          @click="selectedTaskId = String(task.id); closeMenu()"
          class="task-card p-[12px] rounded-[12px] cursor-pointer transition-all border relative group"
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
            v-if="openMenuTaskId === String(task.id)"
            class="task-menu fixed w-[130px] rounded-[10px] border shadow-lg z-[100] py-[4px]"
            :style="{ top: menuPosition.top + 'px', left: menuPosition.left + 'px', backgroundColor: 'var(--card-bg)', borderColor: 'var(--border)' }"
          >
            <button
              @click.stop="startRename(String(task.id)); closeMenu()"
              class="w-full px-[14px] py-[8px] text-left text-[12.5px] cursor-pointer hover:bg-[var(--row-hover)]"
              style="color: var(--text-primary);"
            >
              重命名
            </button>
            <button
              @click.stop="deleteTask(String(task.id)); closeMenu()"
              class="w-full px-[14px] py-[8px] text-left text-[12.5px] cursor-pointer hover:bg-[var(--row-hover)]"
              style="color: var(--red);"
            >
              删除任务
            </button>
          </div>
          <div class="text-[13px] font-medium truncate mb-[8px] task-card-title" style="color: var(--text-primary);">
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
          <div class="metric-card p-[20px_24px] rounded-[14px] border grid grid-cols-[auto_1fr] gap-[28px]">
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
            全部<span class="ml-[4px] opacity-70">{{ filterCounts.all }}</span>
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
                  <div class="text-[11px] mt-[3px] truncate" style="color: var(--text-tertiary);" :title="item.methodName">{{ item.methodName }}</div>
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
                <div class="section-label text-[11.5px] font-semibold uppercase tracking-[0.04em] mb-[6px]" style="color: var(--text-tertiary);">描述</div>
                <div 
                  class="detail-description p-[10px_12px] rounded-[10px] text-[13px] mb-[8px]"
                  style="background-color: var(--card-bg); border: 1px solid var(--border); color: var(--text-secondary);"
                >
                  {{ activeCase.description || '暂无描述' }}
                </div>
                <div v-if="detailLog && detailLog.executed_at" class="mb-[14px] text-[11px]" style="color: var(--text-tertiary);">
                  执行时间: {{ formatDateTime(detailLog.executed_at) }}
                </div>
                <div v-if="detailLoading" class="text-center py-4" style="color: var(--text-tertiary);">
                  加载中...
                </div>
                <template v-else-if="detailLog">
                  <div class="flex-1 min-h-0 flex flex-col">
                    <div class="section-label text-[11.5px] font-semibold uppercase tracking-[0.04em] mb-[6px]" style="color: var(--text-tertiary);">执行日志</div>
                    <div 
                      class="log-viewer flex-1 p-[10px_12px] rounded-[10px] text-[12px] font-code overflow-auto whitespace-pre-wrap"
                      style="background-color: var(--card-bg); border: 1px solid var(--border); color: var(--text-secondary);"
                    >
                      {{ detailLog.logs || detailLog.message || '暂无日志' }}
                    </div>
                  </div>
                  <div v-if="detailLog.trace" class="mt-[12px] flex-1 min-h-0 flex flex-col">
                    <div class="section-label text-[11.5px] font-semibold uppercase tracking-[0.04em] mb-[6px]" style="color: var(--red);">错误堆栈</div>
                    <div 
                      class="trace-viewer flex-1 p-[10px_12px] rounded-[10px] text-[12px] font-code overflow-auto whitespace-pre-wrap"
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
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
}

.sidebar-title {
  color: var(--text-tertiary);
}

/* macOS Sidebar */
.execution-sidebar {
  background-color: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* Task Cards */
.task-card {
  transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.task-card-default {
  background-color: var(--card-bg-2);
  border-color: var(--border);
  box-shadow: 0 0.5px 1px rgba(0,0,0,0.04);
}
.task-card-default:hover {
  background-color: var(--row-hover);
  border-color: var(--border-strong);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  transform: translateY(-0.5px);
}
.task-card-selected {
  background-color: var(--selected-bg);
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent), 0 1px 3px var(--color-primary-soft);
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
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  border-radius: 10px;
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
  border-bottom: 0.5px solid var(--border);
}
.icon-btn {
  background-color: var(--input-bg);
  border: 0.5px solid var(--border);
  color: var(--text-tertiary);
}
.icon-btn:hover {
  background-color: var(--border);
  color: var(--text-secondary);
  border-color: var(--border-strong);
}
.rename-input {
  font-family: inherit;
  font-size: 12.5px;
  border-radius: 8px;
}

/* macOS Action Buttons */
.action-btn {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
  border: none;
  color: #fff;
  position: relative;
}
.action-btn:active {
  transform: scale(0.92);
}
.action-btn-play {
  background-color: var(--green);
  box-shadow: 0 4px 14px rgba(48, 209, 88, 0.35);
}
.action-btn-play:hover {
  box-shadow: 0 6px 20px rgba(48, 209, 88, 0.45);
  transform: translateY(-1px);
}
.action-btn-stop {
  background-color: var(--red);
  box-shadow: 0 4px 14px rgba(255, 69, 58, 0.35);
}
.action-btn-stop:hover {
  box-shadow: 0 6px 20px rgba(255, 69, 58, 0.45);
  transform: translateY(-1px);
}
.action-btn-replay {
  background-color: var(--accent);
  box-shadow: 0 4px 14px var(--color-primary-soft);
}
.action-btn-replay:hover {
  box-shadow: 0 6px 20px var(--color-primary-soft);
  transform: translateY(-1px);
}

/* macOS Metric Card */
.metric-card {
  background-color: var(--card-bg);
  border-color: var(--border);
  box-shadow: 0 0.5px 1px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.03);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
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
  border: 0.5px solid transparent;
}
.filter-pill-active {
  color: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}
.filter-pill-inactive {
  color: var(--text-secondary);
  background-color: var(--input-bg);
  border-color: var(--border);
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
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
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
</style>