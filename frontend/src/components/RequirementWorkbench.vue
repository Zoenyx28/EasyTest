<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useApi } from '../composables/useApi';
import BaseButton from './base/BaseButton.vue';
import BaseTag from './base/BaseTag.vue';
import BaseInput from './base/BaseInput.vue';
import type { RequirementInfo } from '../types';

const emit = defineEmits<{ (e: 'showToast', msg: string): void }>();

const { activeProject, getActiveProject } = useProject();
const { activeBranch } = useBranch(activeProject.value?.id);
const { get, post, put, del } = useApi();
const route = useRoute();
const router = useRouter();

// ── Status metadata ──
const STATUS_META: Record<string, { label: string; tone: 'blue' | 'gray' | 'green' | 'orange' | 'purple' | 'red' | 'yellow' }> = {
  pending_review: { label: '待评审', tone: 'yellow' },
  review_passed: { label: '评审通过', tone: 'blue' },
  story_confirmed: { label: 'Story 已确认', tone: 'purple' },
  cases_generated: { label: '用例已生成', tone: 'green' },
  done: { label: '已完成', tone: 'green' },
};

// AI 任务状态徽标（#21/#22 状态机：PENDING→RUNNING→REVIEW→WAITING_HUMAN→CONFIRMED→NEXT_STAGE，FAILED→RETRY）
const TASK_META: Record<string, { label: string; tone: 'blue' | 'gray' | 'green' | 'orange' | 'purple' | 'red' | 'yellow' }> = {
  PENDING: { label: '排队中', tone: 'gray' },
  RUNNING: { label: '执行中', tone: 'blue' },
  REVIEW: { label: '待确认', tone: 'yellow' },
  WAITING_HUMAN: { label: '等待人工', tone: 'orange' },
  CONFIRMED: { label: '已确认', tone: 'green' },
  NEXT_STAGE: { label: '下一阶段', tone: 'purple' },
  FAILED: { label: '失败', tone: 'red' },
  RETRY: { label: '重试中', tone: 'orange' },
};

const ACTIVE_TABS = ['overview', 'assets', 'execution', 'defects'] as const;
type TabType = (typeof ACTIVE_TABS)[number];

const tonemap = (t: string): 'blue' | 'gray' | 'green' | 'orange' | 'purple' | 'red' | 'yellow' => {
  const allowed = ['blue', 'gray', 'green', 'orange', 'purple', 'red', 'yellow'];
  return allowed.includes(t) ? (t as any) : 'gray';
};
const requirements = ref<RequirementInfo[]>([]);
const selectedReqId = ref<number | null>(null);
const loading = ref(false);
const workbenchData = ref<any>(null);
const wbLoading = ref(false);
const searchQuery = ref('');
const statusFilter = ref('');
const activeTab = ref<TabType>('overview');
const showNewReqModal = ref(false);

// New requirement form
const newReqTitle = ref('');
const newReqContent = ref('');
const newReqSourceType = ref<'text' | 'lark_link' | 'file'>('text');
const newReqLarkLink = ref('');

const projectId = computed(() => activeProject.value?.id || 0);
const branchId = computed(() => activeBranch.value?.id || 0);

const statusFilterTabs = [
  { key: '', label: '全部' },
  { key: 'pending_review', label: '待评审' },
  { key: 'review_passed', label: '评审通过' },
  { key: 'story_confirmed', label: 'Story 确认' },
  { key: 'cases_generated', label: '用例生成' },
  { key: 'done', label: '已完成' },
];

// Derive asset counts from assets array (workbench requirement doesn't include asset_counts)
const assetCounts = computed(() => {
  const counts: Record<string, number> = {};
  for (const a of (workbenchData.value?.assets || [])) {
    counts[a.asset_type] = (counts[a.asset_type] || 0) + 1;
  }
  return counts;
});

// ── Analysis state ──
const analyzing = ref(false);
let pollingTimer: ReturnType<typeof setInterval> | null = null;

// Analysis asset (first analysis-type asset from workbench)
const analysisAsset = computed(() => {
  return (workbenchData.value?.assets || []).find((a: any) => a.asset_type === 'analysis');
});

// Gap assets
const gapAssets = computed(() => {
  return (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'gap');
});

// Parse analysis elements (11 business elements) from content JSON
const analysisElements = computed(() => {
  if (!analysisAsset.value?.content) return null;
  try {
    const c = typeof analysisAsset.value.content === 'string'
      ? JSON.parse(analysisAsset.value.content)
      : analysisAsset.value.content;
    return c.elements || null;
  } catch { return null; }
});

// Analysis score & reason
const analysisScore = computed(() => analysisAsset.value?.score || 0);
const analysisReason = computed(() => analysisAsset.value?.review_comment || analysisAsset.value?.description || '');

// Check for CRITICAL gaps
const hasCriticalGaps = computed(() => {
  return gapAssets.value.some((g: any) => {
    const gs = (g.gate_status || '').toUpperCase();
    if (gs === 'CRITICAL') return true;
    try {
      const c = typeof g.content === 'string' ? JSON.parse(g.content) : g.content;
      return (c?.severity || '').toUpperCase() === 'CRITICAL';
    } catch { return false; }
  });
});

// Is analysis currently running?
const analysisRunning = computed(() => {
  if (analyzing.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) =>
    t.stage === 'analyze' && ['PENDING', 'RUNNING'].includes(t.status),
  );
});

// ── Assets / Story state ──
const assetLayer = ref<'story' | 'test_point' | 'scenario' | 'case' | 'coverage'>('story');
const selectedStoryId = ref<number | null>(null);
const storyGenRunning = ref(false);
const storyReviewRunning = ref(false);

// Story assets from workbench
const storyAssets = computed(() => {
  return (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'story');
});

// Selected story detail
const selectedStory = computed(() => {
  if (!selectedStoryId.value) return null;
  return storyAssets.value.find((s: any) => s.id === selectedStoryId.value) || null;
});

// 双视角确认进度（产品/测试）
const storyConfirmations = computed(() =>
  selectedStory.value ? confirmationsOf(selectedStory.value) : { product: false, testing: false },
);

// Parse story content JSON
function parseStoryContent(story: any): Record<string, any> {
  if (!story?.content) return {};
  try {
    return typeof story.content === 'string' ? JSON.parse(story.content) : story.content;
  } catch { return {}; }
}

// Computed: story gen running
const storyGenActive = computed(() => {
  if (storyGenRunning.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) =>
    t.stage === 'stories' && ['PENDING', 'RUNNING'].includes(t.status),
  );
});

// Computed: story review running
const storyReviewActive = computed(() => {
  if (storyReviewRunning.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) =>
    t.stage === 'story_review' && ['PENDING', 'RUNNING'].includes(t.status),
  );
});

// ── 双视角确认（#22）：product / testing 均确认后 status=confirmed ──
function confirmationsOf(asset: any): { product: boolean; testing: boolean } {
  const c = parseStoryContent(asset);
  const conf = c?.confirmations || {};
  return { product: !!conf.product, testing: !!conf.testing };
}
const allConfirmed = (assets: any[]) => assets.length > 0 && assets.every((a: any) => a.status === 'confirmed');

async function confirmAssetPerspective(assetId: number, perspective: 'product' | 'testing') {
  if (!selectedReqId.value) return;
  try {
    await put(`/requirements/${selectedReqId.value}/assets/${assetId}`, { perspective });
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', `${perspective === 'product' ? '产品' : '测试'}视角已确认`);
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

// ── 评论重新评审（#22）：携带 review_comment 触发后端 ──
const storyReviewComment = ref('');
const tpReviewComment = ref('');
const scReviewComment = ref('');
const caseReviewComment = ref('');
const analysisReviewComment = ref('');
const COMMENT_BY_ENDPOINT: Record<string, { ref: typeof storyReviewComment; label: string }> = {
  'test-points/review': { ref: tpReviewComment, label: '测试点' },
  'test-scenarios/review': { ref: scReviewComment, label: '场景' },
  'cases/review': { ref: caseReviewComment, label: '用例' },
};

// ── 段锁定（#22）：上一段资产全部双视角确认后才解锁下一段 ──
const storiesConfirmed = computed(() => allConfirmed(storyAssets.value));
const testPointsConfirmed = computed(() => allConfirmed(testPointAssets.value));
const scenariosConfirmed = computed(() => allConfirmed(scenarioAssets.value));

// ── AI 任务徽标列表（#21/#22）──
const aiTasks = computed(() => (workbenchData.value?.ai_tasks || []).slice(0, 10));

// ── 覆盖率 / 缺口（⑥，#23）──
const COV_LABELS: Record<string, string> = {
  requirement_coverage: '需求', story_coverage: 'Story', test_point_coverage: '测试点',
  scenario_coverage: '场景', case_coverage: '用例', automation_coverage: '自动化', risk_coverage: '风险',
};
const coverageRunning = ref(false);
const supplementRunning = ref(false);
const coverageData = computed(() => workbenchData.value?.coverage || null);
const testGaps = computed(() => workbenchData.value?.test_gaps || []);

async function runCoverage() {
  if (!selectedReqId.value || coverageRunning.value) return;
  coverageRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/coverage/analyze`, {});
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '覆盖率分析完成');
  } catch (e: any) { emit('showToast', e.message || '覆盖率分析失败'); }
  finally { coverageRunning.value = false; }
}

async function runSupplement(gapId: number) {
  if (!selectedReqId.value || supplementRunning.value) return;
  supplementRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/test-gaps/${gapId}/generate`, {});
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', 'AI 补测已生成');
  } catch (e: any) { emit('showToast', e.message || '补测失败'); }
  finally { supplementRunning.value = false; }
}

// ── Test Point / Scenario / Case state ──
const selectedTpId = ref<number | null>(null);
const selectedScId = ref<number | null>(null);
const selectedCaseId = ref<number | null>(null);
const tpGenRunning = ref(false);
const tpReviewRunning = ref(false);
const scGenRunning = ref(false);
const scReviewRunning = ref(false);
const caseGenRunning = ref(false);
const caseReviewRunning = ref(false);

const testPointAssets = computed(() =>
  (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'test_point'),
);
const scenarioAssets = computed(() =>
  (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'scenario'),
);
const caseAssets = computed(() =>
  (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'case'),
);

// Build test point tree (parent_id → children)
const testPointTree = computed(() => {
  const items = testPointAssets.value.map((tp: any) => ({
    ...tp, children: [] as any[],
  }));
  const byId = new Map<number, any>();
  const roots: any[] = [];
  for (const tp of items) { byId.set(tp.id, tp); }
  for (const tp of items) {
    if (tp.parent_id && byId.has(tp.parent_id)) {
      byId.get(tp.parent_id)!.children.push(tp);
    } else { roots.push(tp); }
  }
  return roots;
});

// Scenario groups by test point
const scenarioGroups = computed(() => {
  const map = new Map<number, any[]>();
  for (const sc of scenarioAssets.value) {
    const tpId = sc.parent_id || 0;
    if (!map.has(tpId)) map.set(tpId, []);
    map.get(tpId)!.push(sc);
  }
  return map;
});

// Running state helpers
function makeLayerActive(stage: string, refVal: boolean): boolean {
  if (refVal) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) => t.stage === stage && ['PENDING', 'RUNNING'].includes(t.status));
}
const tpGenActive = computed(() => makeLayerActive('test_points', tpGenRunning.value));
const tpReviewActive = computed(() => makeLayerActive('test_point_review', tpReviewRunning.value));
const scGenActive = computed(() => makeLayerActive('scenarios', scGenRunning.value));
const scReviewActive = computed(() => makeLayerActive('scenario_review', scReviewRunning.value));
const caseGenActive = computed(() => makeLayerActive('cases', caseGenRunning.value));
const caseReviewActive = computed(() => makeLayerActive('case_review', caseReviewRunning.value));

// Element display labels
const ELEMENT_LABELS: Record<string, string> = {
  business_goal: '业务目标',
  roles: '角色',
  entities: '业务实体',
  flows: '关键流程',
  rules: '业务规则',
  states: '状态',
  inputs_outputs: '输入输出',
  exceptions: '异常场景',
  permissions: '权限',
  dependencies: '外部依赖',
  risks: '风险',
};

const SEVERITY_TONES: Record<string, 'red' | 'orange' | 'yellow' | 'blue'> = {
  CRITICAL: 'red', HIGH: 'orange', MEDIUM: 'yellow', LOW: 'blue',
};

const filteredReqs = computed(() => {
  let list = requirements.value;
  if (statusFilter.value) list = list.filter(r => r.status === statusFilter.value);
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter(r => r.title.toLowerCase().includes(q));
  }
  return list;
});

// ── Loaders ──
async function loadRequirements() {
  if (!projectId.value || !branchId.value) { requirements.value = []; return; }
  loading.value = true;
  try {
    const data = await get<any>(`/requirements?project_id=${projectId.value}&branch_id=${branchId.value}`);
    // 兼容两种返回：旧接口裸数组 / 新接口 {items, total}
    requirements.value = Array.isArray(data) ? data : (data.items || []);
  } catch (e: any) { emit('showToast', e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function loadWorkbench(reqId: number) {
  wbLoading.value = true;
  try {
    workbenchData.value = await get<any>(`/requirements/${reqId}/workbench`);
  } catch (e: any) { emit('showToast', e.message || '加载工作台失败'); }
  finally { wbLoading.value = false; }
}

function selectReq(reqId: number) {
  stopPolling();
  selectedReqId.value = reqId;
  activeTab.value = 'overview';
  loadWorkbench(reqId);
  router.replace({ query: { req_id: reqId } });
}

async function createRequirement() {
  if (!newReqTitle.value.trim()) return;
  try {
    let sourceMeta = '{}';
    if (newReqSourceType.value === 'lark_link') {
      sourceMeta = JSON.stringify({ link: newReqLarkLink.value, extracted: false });
    }
    await post('/requirements', {
      project_id: projectId.value, branch_id: branchId.value,
      title: newReqTitle.value, content: newReqContent.value,
      source_type: newReqSourceType.value, source_meta: sourceMeta,
    });
    showNewReqModal.value = false;
    newReqTitle.value = ''; newReqContent.value = ''; newReqLarkLink.value = '';
    await loadRequirements();
    emit('showToast', '需求创建成功');
  } catch (e: any) { emit('showToast', e.message || '创建失败'); }
}

// ── AI Analysis ──
async function triggerAnalysis() {
  if (!selectedReqId.value || analysisRunning.value) return;
  analyzing.value = true;
  try {
    const res = await post<{ task_id: number; status: string }>(`/req/${selectedReqId.value}/analyze`, {
      review_comment: analysisReviewComment.value,
    });
    analysisReviewComment.value = '';
    analysisTaskId.value = res.task_id;
    emit('showToast', 'AI 分析已启动');
    startPolling();
  } catch (e: any) {
    analyzing.value = false;
    emit('showToast', e.message || '启动分析失败');
  }
}

function startPolling() {
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(async () => {
    if (!selectedReqId.value) { stopPolling(); return; }
    await loadWorkbench(selectedReqId.value);
    if (!analysisRunning.value) {
      stopPolling();
      emit('showToast', 'AI 分析完成');
    }
  }, 2000);
}

function stopPolling() {
  analyzing.value = false;
  if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
}

const analysisTaskId = ref<number | null>(null);

// Gap actions
async function confirmGap(gapId: number) {
  try {
    await put(`/requirements/${selectedReqId.value}/assets/${gapId}`, {
      status: 'confirmed',
    });
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '缺口已确认');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

async function ignoreGap(gapId: number) {
  try {
    await put(`/requirements/${selectedReqId.value}/assets/${gapId}`, {
      status: 'ignored',
    });
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '缺口已忽略');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

// ── Story Generation & Review ──
async function triggerStoryGen() {
  if (!selectedReqId.value || storyGenActive.value) return;
  storyGenRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/stories/generate`, {});
    emit('showToast', 'Story 生成已启动');
    startStoryPolling('generate');
  } catch (e: any) {
    storyGenRunning.value = false;
    emit('showToast', e.message || '启动失败');
  }
}

async function triggerStoryReview() {
  if (!selectedReqId.value || storyReviewActive.value) return;
  storyReviewRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/stories/review`, {
      review_comment: storyReviewComment.value,
    });
    storyReviewComment.value = '';
    emit('showToast', 'Story 评审已启动');
    startStoryPolling('review');
  } catch (e: any) {
    storyReviewRunning.value = false;
    emit('showToast', e.message || '评审启动失败');
  }
}

function startStoryPolling(mode: 'generate' | 'review') {
  const timer = setInterval(async () => {
    if (!selectedReqId.value) { clearInterval(timer); return; }
    await loadWorkbench(selectedReqId.value);
    if (mode === 'generate' && !storyGenActive.value) {
      clearInterval(timer);
      storyGenRunning.value = false;
      emit('showToast', 'Story 生成完成');
    }
    if (mode === 'review' && !storyReviewActive.value) {
      clearInterval(timer);
      storyReviewRunning.value = false;
      emit('showToast', 'Story 评审完成');
    }
  }, 2000);
}

function selectStory(story: any) {
  selectedStoryId.value = story.id;
}

// Story actions
async function confirmStory(storyId: number) {
  try {
    await put(`/requirements/${selectedReqId.value}/assets/${storyId}`, { status: 'confirmed' });
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', 'Story 已确认');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

async function ignoreStory(storyId: number) {
  try {
    await put(`/requirements/${selectedReqId.value}/assets/${storyId}`, { status: 'ignored' });
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', 'Story 已忽略');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

// ── Asset helpers ──
const currentLayerAssets = computed(() => {
  return (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === assetLayer.value);
});

// Generic layer trigger
async function triggerLayerGen(endpoint: string, refVal: any, label: string) {
  if (!selectedReqId.value) return;
  refVal.value = true;
  try {
    const comment = COMMENT_BY_ENDPOINT[endpoint]?.ref.value || '';
    await post(`/req/${selectedReqId.value}/${endpoint}`, { review_comment: comment });
    if (COMMENT_BY_ENDPOINT[endpoint]) COMMENT_BY_ENDPOINT[endpoint].ref.value = '';
    emit('showToast', `${label}已启动`);
    pollLayer(endpoint, refVal, label);
  } catch (e: any) { refVal.value = false; emit('showToast', e.message || '启动失败'); }
}

function pollLayer(endpoint: string, refVal: any, _label: string) {
  const timer = setInterval(async () => {
    if (!selectedReqId.value) { clearInterval(timer); return; }
    await loadWorkbench(selectedReqId.value);
    // Check if any running task still exists for this stage
    const stageMap: Record<string, string> = {
      'test-points/generate': 'test_points',
      'test-points/review': 'test_point_review',
      'test-scenarios/generate': 'scenarios',
      'test-scenarios/review': 'scenario_review',
      'cases/generate': 'cases',
      'cases/review': 'case_review',
    };
    const stage = stageMap[endpoint] || '';
    const tasks = workbenchData.value?.ai_tasks || [];
    const running = tasks.some((t: any) => t.stage === stage && ['PENDING', 'RUNNING'].includes(t.status));
    if (!running) { clearInterval(timer); refVal.value = false; emit('showToast', '任务完成'); }
  }, 2000);
}

// Test point helpers
function parseTpContent(tp: any): Record<string, any> {
  if (!tp?.content) return {};
  try { return typeof tp.content === 'string' ? JSON.parse(tp.content) : tp.content; } catch { return {}; }
}

function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    Functional: '功能', Boundary: '边界', Exception: '异常', State: '状态',
    Permission: '权限', Security: '安全', Data: '数据', Concurrency: '并发',
    Performance: '性能', Compatibility: '兼容', Dependency: '依赖',
  };
  return map[cat] || cat;
}

function statusLabel(s: string): string {
  const map: Record<string, string> = { generated: '已生成', confirmed: '已确认', ignored: '已忽略', pending: '待处理' };
  return map[s] || s;
}
function statusClass(s: string): string {
  return s === 'confirmed' ? 'text-green' : s === 'ignored' ? 'text-muted' : '';
}
function assetTypeTone(t: string): 'blue' | 'gray' | 'green' | 'orange' | 'purple' | 'red' | 'yellow' {
  const map: Record<string, 'blue' | 'gray' | 'green' | 'orange' | 'purple' | 'red' | 'yellow'> = { story: 'blue', test_point: 'purple', scenario: 'orange', case: 'green' };
  return map[t] || 'yellow';
}
function dimBarClass(score: number): string {
  if (score >= 80) return 'dim-pass';
  if (score >= 60) return 'dim-warn';
  return 'dim-fail';
}

// ── Execution / Defect state ──
const showBindingInput = ref(false);
const bindUid = ref('');
const executing = ref(false);
const executionResults = ref<any[]>([]);
const selectedExecCases = ref<Set<string>>(new Set());
const showDefectModal = ref(false);
const showNewDefectModal = ref(false);
const expandedDefectId = ref<number | null>(null);
const defectForm = ref({
  title: '', description: '', steps: '', severity: 'P3', priority: 'P3',
  case_uid: '', module_id: 0,
});

// Bound cases from workbench
const boundCases = computed(() => workbenchData.value?.bindings || []);

async function addBinding() {
  if (!bindUid.value.trim() || !selectedReqId.value) return;
  try {
    await post(`/req/${selectedReqId.value}/bindings`, {
      generated_case_id: 0,
      uid: bindUid.value.trim(),
      project_id: projectId.value,
      branch_id: branchId.value,
    });
    bindUid.value = '';
    showBindingInput.value = false;
    await loadWorkbench(selectedReqId.value);
    emit('showToast', '绑定成功');
  } catch (e: any) { emit('showToast', e.message || '绑定失败'); }
}

async function removeBinding(bindingId: number) {
  try {
    await del(`/req/${selectedReqId.value}/bindings/${bindingId}`);
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '绑定已取消');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

async function executeCases() {
  if (!selectedReqId.value || executing.value) return;
  const uids = boundCases.value.map((b: any) => b.uid);
  if (uids.length === 0) { emit('showToast', '请先绑定用例'); return; }
  executing.value = true;
  try {
    const res = await post<any>(`/req/${selectedReqId.value}/execute`, { uids, concurrency: 2 });
    emit('showToast', `执行已启动 (${res.execution_id})`);
    // Poll for results
    pollExecution(res.execution_id);
  } catch (e: any) { executing.value = false; emit('showToast', e.message || '执行失败'); }
}

function pollExecution(execId: string) {
  const timer = setInterval(async () => {
    try {
      const data = await get<any>(`/executions/${execId}/cases?size=200`);
      executionResults.value = data.items || [];
      const allDone = executionResults.value.every((c: any) => !['waiting', 'running'].includes(c.status));
      if (allDone) { clearInterval(timer); executing.value = false; emit('showToast', '执行完成'); }
    } catch { clearInterval(timer); executing.value = false; }
  }, 2000);
}

function openDefectFromExec(caseUid: string, caseName: string) {
  defectForm.value = {
    title: `[自动] ${caseName} 执行失败`,
    description: `用例 ${caseUid} 执行失败，需进一步排查`,
    steps: '', severity: 'P2', priority: 'P2',
    case_uid: caseUid, module_id: 0,
  };
  showDefectModal.value = true;
}

async function submitDefect() {
  if (!defectForm.value.title.trim()) return;
  try {
    await post('/defects', {
      ...defectForm.value,
      project_id: projectId.value,
      branch_id: branchId.value,
      requirement_id: selectedReqId.value,
    });
    showDefectModal.value = false;
    showNewDefectModal.value = false;
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '缺陷创建成功');
  } catch (e: any) { emit('showToast', e.message || '创建失败'); }
}

function openNewDefect() {
  defectForm.value = {
    title: '', description: '', steps: '', severity: 'P3', priority: 'P3',
    case_uid: '', module_id: 0,
  };
  showNewDefectModal.value = true;
}

async function loadDefectDetail(defectId: number) {
  try {
    const detail = await get<any>(`/defects/${defectId}/detail`);
    // Store in local map
    defectDetails.value.set(defectId, detail);
    expandedDefectId.value = defectId;
  } catch { }
}

const defectDetails = ref<Map<number, any>>(new Map());

// ── Branch / URL handling ──
watch(activeBranch, () => {
  loadRequirements();
  selectedReqId.value = null;
  workbenchData.value = null;
});

onMounted(async () => {
  if (!activeProject.value?.id) await getActiveProject();
  await loadRequirements();
  const qReqId = Number(route.query.req_id);
  if (qReqId) selectReq(qReqId);
});

onUnmounted(() => {
  if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
});
</script>

<template>
  <div class="workbench flex h-full min-h-0">
    <!-- Left: Requirement List -->
    <aside class="req-sidebar">
      <div class="sidebar-header">
        <h3 class="sidebar-title">需求列表</h3>
        <BaseButton size="sm" @click="showNewReqModal = true">新增需求</BaseButton>
      </div>

      <!-- Search -->
      <div class="px-3 pb-2">
        <BaseInput v-model="searchQuery" placeholder="搜索需求" class="w-full text-sm" />
      </div>



      <!-- List -->
      <div class="req-list" v-if="!loading">
        <!-- Status filter -->
        <div class="filter-bar">
          <button v-for="t in statusFilterTabs" :key="t.key"
            class="filter-chip" :class="{ active: statusFilter === t.key }"
            @click="statusFilter = t.key">
            {{ t.label }}
          </button>
        </div>
        <div v-if="filteredReqs.length === 0" class="p-4 text-center text-sm" style="color:var(--text-tertiary);">
          暂无需求
        </div>
        <div v-for="r in filteredReqs" :key="r.id"
          class="req-item" :class="{ selected: r.id === selectedReqId }"
          @click="selectReq(r.id)">
          <div class="flex items-center justify-between mb-1">
            <span class="req-item-title">{{ r.title }}</span>
            <BaseTag :tone="STATUS_META[r.status]?.tone || 'gray'" size="sm">
              {{ STATUS_META[r.status]?.label || r.status }}
            </BaseTag>
          </div>
          <div class="req-item-meta">
            <span>{{ r.priority }}</span>
            <span v-if="r.updated_at">· {{ r.updated_at.substring(0, 10) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="p-4 text-center text-sm" style="color:var(--text-tertiary);">加载中...</div>
    </aside>

    <!-- Right: Workbench Tabs -->
    <main class="workbench-main">
      <template v-if="selectedReqId && workbenchData">
        <!-- Tabs -->
        <nav class="wb-tabs">
          <button v-for="t in ACTIVE_TABS" :key="t"
            class="wb-tab" :class="{ active: activeTab === t }"
            @click="activeTab = t">
            <span v-if="t === 'overview'">概览</span>
            <span v-else-if="t === 'assets'">资产<span v-if="assetCounts.story" class="count-badge">{{ assetCounts.story + (assetCounts.test_point||0) + (assetCounts.case||0) }}</span></span>
            <span v-else-if="t === 'execution'">执行</span>
            <span v-else-if="t === 'defects'">缺陷<span v-if="workbenchData.defect_count" class="count-badge">{{ workbenchData.defect_count }}</span></span>
          </button>
        </nav>

        <!-- Overview Tab -->
        <div v-if="activeTab === 'overview'" class="tab-content">
          <!-- BLOCKED banner -->
          <div v-if="hasCriticalGaps" class="blocked-banner">
            ⛔ 存在严重信息缺口，需求分析未通过
          </div>

          <div class="overview-grid">
            <div class="ov-card">
              <div class="ov-card-header">
                <h4>{{ workbenchData.requirement.title }}</h4>
                <div class="ov-actions">
                  <BaseInput v-model="analysisReviewComment" placeholder="评审反馈（可选，携带重新分析）" size="sm" class="review-comment-input" />
                  <BaseButton
                    size="sm"
                    @click="triggerAnalysis"
                    :disabled="analysisRunning"
                    :loading="analysisRunning"
                  >
                    {{ analysisRunning ? '分析中...' : (analysisAsset ? '重新分析' : 'AI 分析') }}
                  </BaseButton>
                </div>
              </div>
              <div class="ov-meta">
                <span>优先级: {{ workbenchData.requirement.priority }}</span>
                <span>来源: {{ workbenchData.requirement.source_type === 'lark_link' ? '飞书' : workbenchData.requirement.source_type === 'file' ? '文件' : '文本' }}</span>
                <span>状态: <BaseTag :tone="STATUS_META[workbenchData.requirement.status]?.tone || 'gray'" size="sm">{{ STATUS_META[workbenchData.requirement.status]?.label || workbenchData.requirement.status }}</BaseTag></span>
                <span v-if="hasCriticalGaps"><BaseTag tone="red" size="sm">BLOCKED</BaseTag></span>
              </div>
              <div v-if="workbenchData.requirement.content" class="ov-content">
                {{ (workbenchData.requirement.content || '').substring(0, 500) }}{{ (workbenchData.requirement.content || '').length > 500 ? '...' : '' }}
              </div>
            </div>

            <div class="ov-card">
              <h4>测试设计进度</h4>
              <div class="progress-list">
                <div class="progress-row"><span>需求分析</span><span>{{ assetCounts.analysis ? '✅' : '⬜' }}</span></div>
                <div class="progress-row"><span>Story</span><span>{{ assetCounts.story || 0 }}个</span></div>
                <div class="progress-row"><span>测试点</span><span>{{ assetCounts.test_point || 0 }}个</span></div>
                <div class="progress-row"><span>测试用况</span><span>{{ assetCounts.case || 0 }}个</span></div>
              </div>
            </div>

            <div class="ov-card" v-if="workbenchData.execution_summary">
              <h4>最近执行</h4>
              <div class="exec-stats">
                <span class="pass">✓ {{ workbenchData.execution_summary.success_count }}</span>
                <span class="fail">✗ {{ workbenchData.execution_summary.fail_count }}</span>
              </div>
              <div class="text-xs" style="color:var(--text-tertiary);">{{ workbenchData.execution_summary.start_time?.substring(0,16) }}</div>
            </div>

            <div class="ov-card">
              <h4>关联缺陷</h4>
              <div class="text-lg font-bold">{{ workbenchData.defect_count }} 个</div>
              <div class="text-sm" style="color:var(--text-tertiary);">{{ workbenchData.open_defect_count }} 个未关闭</div>
            </div>

            <!-- Analysis Result Card (full width, 11 business elements) -->
            <div v-if="analysisAsset" class="ov-card ov-card-full">
              <h4>AI 分析结果 <span class="text-sm font-normal" style="color:var(--text-tertiary);">评分 {{ analysisScore }}/100</span></h4>
              <div v-if="analysisReason" class="analysis-reason">{{ analysisReason }}</div>
              <div v-if="analysisElements" class="elements-grid">
                <div v-for="(val, key) in analysisElements" :key="key" class="element-chip"
                  :class="{ 'element-empty': !val || (Array.isArray(val) && val.length === 0) }">
                  <span class="element-key">{{ ELEMENT_LABELS[key] || key }}</span>
                  <span class="element-val" v-if="val && !(Array.isArray(val) && val.length === 0)">
                    {{ Array.isArray(val) ? val.join(', ') : val }}
                  </span>
                  <span class="element-val element-na" v-else>—</span>
                </div>
              </div>
            </div>

            <!-- Information Gaps Card (full width) -->
            <div v-if="gapAssets.length > 0" class="ov-card ov-card-full">
              <h4>信息缺口 ({{ gapAssets.length }})</h4>
              <div class="gaps-list">
                <div v-for="gap in gapAssets" :key="gap.id" class="gap-item"
                  :class="{ 'gap-confirmed': gap.status === 'confirmed', 'gap-ignored': gap.status === 'ignored' }">
                  <div class="gap-header">
                    <BaseTag :tone="SEVERITY_TONES[(gap.gate_status || '').toUpperCase()] || 'yellow'" size="sm">{{ gap.gate_status || gap.title }}</BaseTag>
                    <span class="gap-question">{{ gap.description }}</span>
                  </div>
                  <div class="gap-actions" v-if="gap.status === 'pending'">
                    <button class="gap-btn confirm" @click="confirmGap(gap.id)">确认</button>
                    <button class="gap-btn ignore" @click="ignoreGap(gap.id)">忽略</button>
                  </div>
                  <div v-else class="gap-status-label">
                    {{ gap.status === 'confirmed' ? '已确认' : '已忽略' }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Assets Tab -->
        <div v-if="activeTab === 'assets'" class="tab-content assets-tab">
          <!-- Layer selector + actions -->
          <div class="layer-bar">
            <div class="layer-tabs">
              <button class="layer-tab" :class="{ active: assetLayer === 'story' }" @click="selectedStoryId = null; assetLayer = 'story'">
                Story <span class="layer-count">{{ assetCounts.story || 0 }}</span>
              </button>
              <button class="layer-tab" :class="{ active: assetLayer === 'test_point' }" @click="assetLayer = 'test_point'">
                测试点 <span class="layer-count">{{ assetCounts.test_point || 0 }}</span>
              </button>
              <button class="layer-tab" :class="{ active: assetLayer === 'scenario' }" @click="assetLayer = 'scenario'">
                场景 <span class="layer-count">{{ assetCounts.scenario || 0 }}</span>
              </button>
              <button class="layer-tab" :class="{ active: assetLayer === 'case' }" @click="assetLayer = 'case'">
                用例 <span class="layer-count">{{ assetCounts.case || 0 }}</span>
              </button>
              <button class="layer-tab" :class="{ active: assetLayer === 'coverage' }" @click="assetLayer = 'coverage'">
                ⑥ 覆盖率
              </button>
            </div>
            <!-- AI 任务状态徽标（#21/#22，随轮询更新）-->
            <div class="ai-task-badges">
              <span v-for="t in aiTasks" :key="t.id" class="ai-task-badge" :class="'task-' + t.status.toLowerCase()">
                <span class="task-stage">{{ t.stage }}</span>
                <span class="task-status">{{ TASK_META[t.status]?.label || t.status }}</span>
                <span v-if="t.status === 'RUNNING'" class="task-dot">●</span>
              </span>
              <span v-if="aiTasks.length === 0" class="ai-task-empty">暂无 AI 任务</span>
            </div>
            <div class="layer-actions">
              <template v-if="assetLayer === 'story'">
                <BaseButton size="sm" @click="triggerStoryGen" :loading="storyGenActive" :disabled="storyGenActive || storyReviewActive">
                  {{ storyGenActive ? '生成中...' : 'AI 生成 Story' }}
                </BaseButton>
                <BaseButton v-if="storyAssets.length > 0" size="sm" variant="secondary" @click="triggerStoryReview" :loading="storyReviewActive" :disabled="storyGenActive || storyReviewActive">
                  {{ storyReviewActive ? '评审中...' : 'AI 评审 Story' }}
                </BaseButton>
                <BaseInput v-if="storyAssets.length > 0 && !storyGenActive" v-model="storyReviewComment"
                  placeholder="评审反馈（可选，携带重新评审）" size="sm" class="review-comment-input" />
              </template>
              <template v-else-if="assetLayer === 'test_point'">
                <BaseButton size="sm" @click="triggerLayerGen('test-points/generate', tpGenRunning, '测试点生成')" :loading="tpGenActive" :disabled="tpGenActive || tpReviewActive || !storiesConfirmed" :title="storiesConfirmed ? '' : '需全部 Story 双视角确认'">
                  {{ tpGenActive ? '生成中...' : 'AI 生成测试点' }}
                </BaseButton>
                <BaseButton v-if="testPointAssets.length > 0" size="sm" variant="secondary" @click="triggerLayerGen('test-points/review', tpReviewRunning, '测试点评审')" :loading="tpReviewActive" :disabled="tpGenActive || tpReviewActive">
                  {{ tpReviewActive ? '评审中...' : 'AI 评审测试点' }}
                </BaseButton>
                <BaseInput v-if="testPointAssets.length > 0 && !tpGenActive" v-model="tpReviewComment"
                  placeholder="评审反馈（可选）" size="sm" class="review-comment-input" />
              </template>
              <template v-else-if="assetLayer === 'scenario'">
                <BaseButton size="sm" @click="triggerLayerGen('test-scenarios/generate', scGenRunning, '场景生成')" :loading="scGenActive" :disabled="scGenActive || scReviewActive || !testPointsConfirmed" :title="testPointsConfirmed ? '' : '需全部测试点确认'">
                  {{ scGenActive ? '生成中...' : 'AI 生成场景' }}
                </BaseButton>
                <BaseButton v-if="scenarioAssets.length > 0" size="sm" variant="secondary" @click="triggerLayerGen('test-scenarios/review', scReviewRunning, '场景评审')" :loading="scReviewActive" :disabled="scGenActive || scReviewActive">
                  {{ scReviewActive ? '评审中...' : 'AI 评审场景' }}
                </BaseButton>
                <BaseInput v-if="scenarioAssets.length > 0 && !scGenActive" v-model="scReviewComment"
                  placeholder="评审反馈（可选）" size="sm" class="review-comment-input" />
              </template>
              <template v-else-if="assetLayer === 'case'">
                <BaseButton size="sm" @click="triggerLayerGen('cases/generate', caseGenRunning, '用例生成')" :loading="caseGenActive" :disabled="caseGenActive || caseReviewActive || !scenariosConfirmed" :title="scenariosConfirmed ? '' : '需全部场景确认'">
                  {{ caseGenActive ? '生成中...' : 'AI 生成用例' }}
                </BaseButton>
                <BaseButton v-if="caseAssets.length > 0" size="sm" variant="secondary" @click="triggerLayerGen('cases/review', caseReviewRunning, '用例评审')" :loading="caseReviewActive" :disabled="caseGenActive || caseReviewActive">
                  {{ caseReviewActive ? '评审中...' : 'AI 评审用例' }}
                </BaseButton>
                <BaseInput v-if="caseAssets.length > 0 && !caseGenActive" v-model="caseReviewComment"
                  placeholder="评审反馈（可选）" size="sm" class="review-comment-input" />
              </template>
              <BaseButton v-if="assetLayer === 'case' && caseAssets.length > 0" size="sm" variant="secondary" @click="assetLayer = 'coverage'">⑥ 覆盖率</BaseButton>
            </div>
          </div>

          <!-- Story View: Left-Right Split -->
          <div v-if="assetLayer === 'story'" class="assets-split">
            <!-- Left: Story List -->
            <div class="assets-list-panel">
              <div v-if="storyAssets.length === 0" class="empty-state">暂无 Story，请点击「AI 生成 Story」开始</div>
              <div v-for="s in storyAssets" :key="s.id"
                class="asset-list-item" :class="{ selected: selectedStoryId === s.id }"
                @click="selectStory(s)">
                <div class="asset-item-header">
                  <span class="asset-item-title">{{ s.title }}</span>
                  <BaseTag v-if="s.gate_status" :tone="s.gate_status === 'PASS' ? 'green' : s.gate_status === 'WARNING' ? 'yellow' : 'red'" size="sm">{{ s.gate_status }}</BaseTag>
                </div>
                <div class="asset-item-meta">
                  <span v-if="s.score">评分 {{ s.score }}</span>
                  <span :class="statusClass(s.status)">{{ statusLabel(s.status) }}</span>
                </div>
              </div>
            </div>

            <!-- Right: Story Detail -->
            <div class="assets-detail-panel">
              <template v-if="selectedStory">
                <h4 class="detail-title">{{ selectedStory.title }}</h4>
                <div class="detail-meta">
                  <span>评分: <strong>{{ selectedStory.score || '—' }}</strong></span>
                  <BaseTag v-if="selectedStory.gate_status" :tone="selectedStory.gate_status === 'PASS' ? 'green' : selectedStory.gate_status === 'WARNING' ? 'yellow' : 'red'" size="sm">
                    {{ selectedStory.gate_status }}
                  </BaseTag>
                  <span>{{ statusLabel(selectedStory.status) }}</span>
                </div>
                <div v-if="selectedStory.description" class="detail-section">
                  <h5>描述</h5>
                  <p>{{ selectedStory.description }}</p>
                </div>
                <div v-if="parseStoryContent(selectedStory).acceptance_criteria?.length" class="detail-section">
                  <h5>验收标准</h5>
                  <ul class="ac-list">
                    <li v-for="(ac, i) in parseStoryContent(selectedStory).acceptance_criteria" :key="i">{{ ac }}</li>
                  </ul>
                </div>
                <!-- 7-dim scores -->
                <div v-if="Object.keys(parseStoryContent(selectedStory).dimension_scores || {}).length" class="detail-section">
                  <h5>7 维评审明细</h5>
                  <div class="dim-scores">
                    <div v-for="(score, dim) in parseStoryContent(selectedStory).dimension_scores" :key="dim" class="dim-row">
                      <span class="dim-name">{{ dim }}</span>
                      <div class="dim-bar"><div class="dim-fill" :style="{ width: score + '%' }" :class="dimBarClass(score)"></div></div>
                      <span class="dim-val">{{ score }}</span>
                    </div>
                  </div>
                </div>
                <!-- Issues -->
                <div v-if="parseStoryContent(selectedStory).issues?.length" class="detail-section">
                  <h5>问题</h5>
                  <div v-for="(iss, i) in parseStoryContent(selectedStory).issues" :key="i" class="issue-item">
                    <strong>{{ iss.title }}</strong>: {{ iss.detail }}
                  </div>
                </div>
                <!-- 双视角确认（#22）-->
                <div class="detail-section">
                  <h5>双视角确认</h5>
                  <div class="perspective-row">
                    <BaseTag :tone="storyConfirmations.product ? 'green' : 'gray'" size="sm">产品 {{ storyConfirmations.product ? '✓' : '未确认' }}</BaseTag>
                    <BaseTag :tone="storyConfirmations.testing ? 'green' : 'gray'" size="sm">测试 {{ storyConfirmations.testing ? '✓' : '未确认' }}</BaseTag>
                    <BaseTag v-if="selectedStory.status === 'confirmed'" tone="green" size="sm">已解锁下一段</BaseTag>
                  </div>
                  <div class="detail-actions">
                    <BaseButton v-if="!storyConfirmations.product" size="sm" @click="confirmAssetPerspective(selectedStory.id, 'product')">产品确认</BaseButton>
                    <BaseButton v-if="!storyConfirmations.testing" size="sm" @click="confirmAssetPerspective(selectedStory.id, 'testing')">测试确认</BaseButton>
                    <BaseButton v-if="selectedStory.status !== 'ignored'" size="sm" variant="warning" @click="ignoreStory(selectedStory.id)">忽略</BaseButton>
                  </div>
                </div>
              </template>
              <div v-else class="empty-state">← 选择一条 Story 查看详情</div>
            </div>
          </div>

          <!-- Test Point View: Tree -->
          <div v-else-if="assetLayer === 'test_point'" class="assets-split">
            <div class="assets-list-panel">
              <div v-if="testPointTree.length === 0" class="empty-state">暂无测试点，请点击「AI 生成测试点」</div>
              <div v-for="tp in testPointTree" :key="tp.id">
                <div class="asset-list-item" :class="{ selected: selectedTpId === tp.id }" @click="selectedTpId = tp.id">
                  <div class="asset-item-header">
                    <BaseTag :tone="tonemap('purple')" size="sm">{{ categoryLabel(parseTpContent(tp).category) }}</BaseTag>
                    <span class="asset-item-title">{{ tp.title }}</span>
                    <BaseTag v-if="tp.gate_status" :tone="tp.gate_status === 'PASS' ? 'green' : tp.gate_status === 'WARNING' ? 'yellow' : 'red'" size="sm">{{ tp.gate_status }}</BaseTag>
                  </div>
                  <div class="asset-item-meta">
                    <span v-if="tp.score">评分 {{ tp.score }}</span>
                  </div>
                </div>
                <!-- Children -->
                <div v-for="child in tp.children" :key="child.id" class="asset-list-item tree-child" :class="{ selected: selectedTpId === child.id }" @click="selectedTpId = child.id">
                  <div class="asset-item-header">
                    <BaseTag :tone="tonemap('purple')" size="sm">{{ categoryLabel(parseTpContent(child).category) }}</BaseTag>
                    <span class="asset-item-title">{{ child.title }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="assets-detail-panel">
              <div v-if="!selectedTpId" class="empty-state">← 选择测试点查看详情</div>
              <div v-else v-for="tp in testPointAssets.filter(a => a.id === selectedTpId)" :key="tp.id">
                <h4 class="detail-title">{{ tp.title }}</h4>
                <div class="detail-meta">
                  <BaseTag :tone="tonemap('purple')" size="sm">{{ categoryLabel(parseTpContent(tp).category) }}</BaseTag>
                  <span>评分: <strong>{{ tp.score || '—' }}</strong></span>
                  <BaseTag v-if="tp.gate_status" :tone="tp.gate_status === 'PASS' ? 'green' : 'red'" size="sm">{{ tp.gate_status }}</BaseTag>
                </div>
                <div v-if="tp.description" class="detail-section"><h5>描述</h5><p>{{ tp.description }}</p></div>
                <div v-if="Object.keys(parseTpContent(tp).dimension_scores || {}).length" class="detail-section">
                  <h5>11 维评审明细</h5>
                  <div class="dim-scores">
                    <div v-for="(score, dim) in parseTpContent(tp).dimension_scores" :key="dim" class="dim-row">
                      <span class="dim-name">{{ dim }}</span><div class="dim-bar"><div class="dim-fill" :style="{ width: score + '%' }" :class="dimBarClass(score)"></div></div><span class="dim-val">{{ score }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Scenario View -->
          <div v-else-if="assetLayer === 'scenario'" class="assets-split">
            <div class="assets-list-panel">
              <div v-if="scenarioAssets.length === 0" class="empty-state">暂无场景，请点击「AI 生成场景」</div>
              <div v-for="sc in scenarioAssets" :key="sc.id" class="asset-list-item" :class="{ selected: selectedScId === sc.id }" @click="selectedScId = sc.id">
                <div class="asset-item-header">
                  <BaseTag :tone="tonemap('orange')" size="sm">{{ parseTpContent(sc).coverage_dim || 'Normal' }}</BaseTag>
                  <span class="asset-item-title">{{ sc.title }}</span>
                </div>
              </div>
            </div>
            <div class="assets-detail-panel">
              <div v-if="!selectedScId" class="empty-state">← 选择场景查看详情</div>
              <div v-else v-for="sc in scenarioAssets.filter(a => a.id === selectedScId)" :key="sc.id">
                <h4 class="detail-title">{{ sc.title }}</h4>
                <div class="detail-meta">
                  <BaseTag :tone="tonemap('orange')" size="sm">{{ parseTpContent(sc).coverage_dim || 'Normal' }}</BaseTag>
                  <span v-if="sc.score">评分: <strong>{{ sc.score }}</strong></span>
                  <BaseTag v-if="sc.gate_status" :tone="sc.gate_status === 'PASS' ? 'green' : 'red'" size="sm">{{ sc.gate_status }}</BaseTag>
                </div>
                <div v-if="sc.description" class="detail-section"><h5>描述</h5><p>{{ sc.description }}</p></div>
              </div>
            </div>
          </div>

          <!-- Case View -->
          <div v-else-if="assetLayer === 'case'" class="assets-split">
            <div class="assets-list-panel">
              <div v-if="caseAssets.length === 0" class="empty-state">暂无用例，请点击「AI 生成用例」</div>
              <div v-for="c in caseAssets" :key="c.id" class="asset-list-item" :class="{ selected: selectedCaseId === c.id }" @click="selectedCaseId = c.id">
                <div class="asset-item-header">
                  <span class="asset-item-title">{{ c.title }}</span>
                  <BaseTag v-if="c.gate_status" :tone="c.gate_status === 'PASS' ? 'green' : c.gate_status === 'WARNING' ? 'yellow' : 'red'" size="sm">{{ c.gate_status }}</BaseTag>
                </div>
                <div class="asset-item-meta"><span v-if="c.score">评分 {{ c.score }}</span></div>
              </div>
            </div>
            <div class="assets-detail-panel">
              <div v-if="!selectedCaseId" class="empty-state">← 选择用例查看详情</div>
              <div v-else v-for="c in caseAssets.filter(a => a.id === selectedCaseId)" :key="c.id">
                <h4 class="detail-title">{{ c.title }}</h4>
                <div class="detail-meta">
                  <span>评分: <strong>{{ c.score || '—' }}</strong></span>
                  <BaseTag v-if="c.gate_status" :tone="c.gate_status === 'PASS' ? 'green' : c.gate_status === 'WARNING' ? 'yellow' : 'red'" size="sm">{{ c.gate_status }}</BaseTag>
                </div>
                <div v-if="c.description" class="detail-section"><h5>描述</h5><p>{{ c.description }}</p></div>
                <div v-if="parseTpContent(c).preconditions" class="detail-section"><h5>前置条件</h5><p>{{ parseTpContent(c).preconditions }}</p></div>
                <div v-if="parseTpContent(c).steps" class="detail-section"><h5>步骤</h5><pre class="case-pre">{{ parseTpContent(c).steps }}</pre></div>
                <div v-if="parseTpContent(c).expected" class="detail-section"><h5>预期结果</h5><pre class="case-pre">{{ parseTpContent(c).expected }}</pre></div>
                <div v-if="Object.keys(parseTpContent(c).checks || {}).length" class="detail-section">
                  <h5>9 维检查</h5>
                  <div class="dim-scores">
                    <div v-for="(score, dim) in parseTpContent(c).checks" :key="dim" class="dim-row">
                      <span class="dim-name">{{ dim }}</span><div class="dim-bar"><div class="dim-fill" :style="{ width: score + '%' }" :class="dimBarClass(score)"></div></div><span class="dim-val">{{ score }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 覆盖率 / 缺口（⑥，#23）-->
          <div v-else-if="assetLayer === 'coverage'" class="assets-split">
            <div class="assets-detail-panel coverage-panel">
              <div class="coverage-header">
                <h4>覆盖率</h4>
                <BaseButton size="sm" @click="runCoverage" :loading="coverageRunning">
                  {{ coverageRunning ? '分析中...' : '覆盖率分析' }}
                </BaseButton>
              </div>
              <div v-if="coverageData" class="coverage-bars">
                <div v-for="(v, key) in coverageData" :key="key" class="cov-row">
                  <span class="cov-name">{{ COV_LABELS[key] || key }}</span>
                  <div class="dim-bar"><div class="dim-fill" :style="{ width: v + '%' }" :class="dimBarClass(v)"></div></div>
                  <span class="cov-val">{{ v }}%</span>
                </div>
              </div>
              <div v-else class="empty-state">尚未分析覆盖率，点击「覆盖率分析」计算</div>

              <h4 class="mt-3">测试缺口（TestGap）</h4>
              <div v-if="testGaps.length === 0" class="empty-state">暂无缺口</div>
              <div v-for="g in testGaps" :key="g.id" class="gap-row">
                <BaseTag :tone="g.severity === 'P0' ? 'red' : 'orange'" size="sm">{{ g.severity }}</BaseTag>
                <BaseTag tone="gray" size="sm">{{ g.layer }}</BaseTag>
                <span class="flex-1 mx-2">{{ g.description }}</span>
                <BaseTag :tone="g.status === 'closed' ? 'green' : 'yellow'" size="sm">{{ g.status === 'closed' ? '已关闭' : g.status }}</BaseTag>
                <BaseButton v-if="g.status !== 'closed'" size="sm" variant="secondary" @click="runSupplement(g.id)" :loading="supplementRunning">AI 补测</BaseButton>
              </div>
            </div>
          </div>

          <!-- Flat list for unknown layers -->
          <div v-else class="assets-flat">
            <div v-for="a in currentLayerAssets" :key="a.id" class="asset-row">
              <BaseTag :tone="assetTypeTone(a.asset_type)" size="sm">{{ a.asset_type }}</BaseTag>
              <span class="flex-1 mx-2">{{ a.title }}</span>
              <span v-if="a.score" class="text-xs">{{ a.score }}分</span>
            </div>
          </div>
        </div>

        <!-- Execution Tab -->
        <div v-if="activeTab === 'execution'" class="tab-content">
          <div class="execution-view">
            <p class="text-sm" style="color:var(--text-secondary);">绑定的自动化用例可在工作台内执行</p>
            <div v-if="!workbenchData.bindings?.length && !workbenchData.execution_summary" class="empty-state">
              暂无绑定用例。在资产 Tab 中将生成用例绑定到自动化用例
            </div>
            <div v-if="workbenchData.execution_summary" class="exec-summary mt-2">
              <div class="text-sm">最近执行: {{ workbenchData.execution_summary.status }}</div>
              <div>总计 {{ workbenchData.execution_summary.total_count }} · 通过 {{ workbenchData.execution_summary.success_count }} · 失败 {{ workbenchData.execution_summary.fail_count }}</div>
            </div>
          </div>
        </div>

        <!-- Defects Tab -->
        <div v-if="activeTab === 'defects'" class="tab-content">
          <div class="defects-view">
            <p class="text-sm" style="color:var(--text-secondary);">关联需求的所有缺陷</p>
            <div v-if="!workbenchData.defects?.length" class="empty-state">暂无关联缺陷</div>
            <div v-for="d in workbenchData.defects" :key="d.id" class="defect-row">
              <BaseTag :tone="d.severity === 'P0' ? 'red' : d.severity === 'P1' ? 'orange' : 'yellow'" size="sm">{{ d.severity }}</BaseTag>
              <span class="flex-1 mx-2">{{ d.title }}</span>
              <BaseTag :tone="d.status === 'closed' ? 'gray' : d.status === 'resolved' ? 'green' : 'blue'" size="sm">{{ d.status }}</BaseTag>
            </div>
          </div>
        </div>
      </template>

      <!-- No selection placeholder -->
      <div v-else class="placeholder">
        <p>暂无需求</p>
      </div>
    </main>

    <!-- New Requirement Modal -->
    <teleport to="body">
      <div v-if="showNewReqModal" class="modal-overlay" @click.self="showNewReqModal = false">
        <div class="modal-panel">
          <h3>新建需求</h3>
          <div class="mb-3">
            <label class="block text-sm mb-1">来源类型</label>
            <div class="flex gap-2">
              <label class="radio-label"><input type="radio" v-model="newReqSourceType" value="text" /> 文本</label>
              <label class="radio-label"><input type="radio" v-model="newReqSourceType" value="lark_link" /> 飞书链接</label>
              <label class="radio-label"><input type="radio" v-model="newReqSourceType" value="file" /> 文件</label>
            </div>
          </div>
          <div class="mb-3">
            <label class="block text-sm mb-1">标题</label>
            <BaseInput v-model="newReqTitle" placeholder="需求标题" class="w-full" @enter="createRequirement" />
          </div>
          <div v-if="newReqSourceType === 'lark_link'" class="mb-3">
            <label class="block text-sm mb-1">飞书文档链接</label>
            <BaseInput v-model="newReqLarkLink" placeholder="https://asiainfo.feishu.cn/wiki/..." class="w-full" />
          </div>
          <div class="mb-3">
            <label class="block text-sm mb-1">正文（可选）</label>
            <textarea v-model="newReqContent" class="w-full h-24 p-2 rounded" style="background:var(--input-bg);color:var(--text-primary);border:2px solid var(--outline);" placeholder="粘贴需求正文内容..."></textarea>
          </div>
          <div class="flex justify-end gap-2">
            <button @click="showNewReqModal = false" class="btn-cancel">取消</button>
            <BaseButton @click="createRequirement" :disabled="!newReqTitle.trim()">创建</BaseButton>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<style scoped>
.workbench { display: flex; gap: 0; }
.req-sidebar {
  width: 320px; min-width: 320px; flex-shrink: 0;
  border-right: 2px solid var(--outline);
  display: flex; flex-direction: column; overflow: hidden;
  background-color: var(--card-bg);
}
.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 12px 8px;
}
.sidebar-title { font-family: var(--font-heading); font-size: 14px; font-weight: 600; }

.filter-bar { display: flex; flex-wrap: wrap; gap: 4px; padding: 4px 12px 8px; }
.filter-chip {
  padding: 2px 8px; border-radius: 99px; font-size: 11px;
  border: 1px solid var(--outline); cursor: pointer;
  background: var(--input-bg); color: var(--text-secondary);
}
.filter-chip.active { background: var(--color-primary); color: white; border-color: var(--color-primary); }

.req-list { flex: 1; overflow-y: auto; }
.req-item {
  padding: 10px 12px; cursor: pointer; border-bottom: 1px solid var(--border);
  transition: background-color 0.15s;
}
.req-item:hover { background-color: var(--hover-bg); }
.req-item.selected { background-color: var(--accent-bg); border-left: 3px solid var(--color-primary); }
.req-item-title { font-size: 13px; font-weight: 500; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.req-item-meta { font-size: 11px; color: var(--text-tertiary); }

.workbench-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.placeholder { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); }

.wb-tabs { display: flex; gap: 0; border-bottom: 2px solid var(--outline); padding: 0 16px; background: var(--toolbar-bg); }
.wb-tab {
  padding: 10px 16px; font-size: 13px; font-weight: 500; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -2px;
  color: var(--text-secondary); position: relative;
}
.wb-tab:hover { color: var(--text-primary); }
.wb-tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.count-badge {
  position: absolute; top: 2px; right: -4px; font-size: 10px;
  background: var(--color-primary); color: white; border-radius: 99px;
  padding: 0 5px; min-width: 16px; text-align: center;
}

.tab-content { flex: 1; overflow-y: auto; padding: 16px; }

.overview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ov-card {
  padding: 16px; border-radius: var(--radius-md); background: var(--card-bg-2);
  border: 2px solid var(--outline);
}
.ov-card h4 { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.ov-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.ov-card-header h4 { margin-bottom: 0; flex: 1; }
.ov-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.ov-card-full { grid-column: 1 / -1; }
.ov-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; flex-wrap: wrap; align-items: center; }
.ov-content { font-size: 12px; color: var(--text-secondary); line-height: 1.5; white-space: pre-wrap; }
.progress-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; }
.exec-stats { display: flex; gap: 12px; font-size: 18px; font-weight: 700; }
.exec-stats .pass { color: #22c55e; }
.exec-stats .fail { color: #ef4444; }

.blocked-banner {
  padding: 8px 16px; margin-bottom: 12px;
  border-radius: var(--radius-md); background: #fef2f2;
  border: 2px solid #ef4444; color: #b91c1c;
  font-size: 13px; font-weight: 600;
}

.spinner-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: currentColor; animation: spin 1s ease-in-out infinite;
  vertical-align: middle;
}
@keyframes spin {
  0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; }
}
.mr-1 { margin-right: 4px; }

.analysis-reason {
  font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;
  padding: 6px 10px; border-radius: var(--radius-sm); background: var(--bg-soft);
}

.elements-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px;
}

.element-chip {
  display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px; border-radius: var(--radius-sm);
  background: var(--bg-soft); border: 1px solid var(--border);
  font-size: 12px;
}
.element-chip.element-empty { opacity: 0.55; }
.element-key { font-weight: 600; color: var(--text-primary); }
.element-val { color: var(--text-secondary); line-height: 1.4; }
.element-na { font-style: italic; color: var(--text-tertiary); }

.gaps-list { display: flex; flex-direction: column; gap: 8px; }
.gap-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--bg-soft); border: 1px solid var(--border);
  font-size: 12px;
}
.gap-item.gap-confirmed { border-left: 3px solid #22c55e; opacity: 0.7; }
.gap-item.gap-ignored { border-left: 3px solid #9ca3af; opacity: 0.55; text-decoration: line-through; }
.gap-header { display: flex; align-items: center; gap: 8px; flex: 1; }
.gap-question { color: var(--text-secondary); }
.gap-actions { display: flex; gap: 6px; flex-shrink: 0; }
.gap-btn {
  padding: 3px 10px; border-radius: 99px; font-size: 11px; cursor: pointer;
  border: 1px solid var(--border); background: var(--card-bg);
}
.gap-btn.confirm { color: #16a34a; border-color: #16a34a; }
.gap-btn.confirm:hover { background: #f0fdf4; }
.gap-btn.ignore { color: #9ca3af; border-color: #9ca3af; }
.gap-btn.ignore:hover { background: #f9fafb; }
.gap-status-label { font-size: 11px; color: var(--text-tertiary); flex-shrink: 0; }

.assets-view, .execution-view, .defects-view { display: flex; flex-direction: column; gap: 8px; }
.asset-row, .defect-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: var(--radius-sm);
  background: var(--card-bg-2); border: 1px solid var(--border);
  font-size: 13px;
}
.empty-state { padding: 32px; text-align: center; color: var(--text-tertiary); font-size: 13px; }

.modal-overlay { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; background: var(--overlay-bg); }
.modal-panel { background: var(--card-bg); border: 3px solid var(--outline); border-radius: var(--radius-lg); padding: 20px; min-width: 400px; max-width: 500px; box-shadow: var(--shadow-hard-lg); }
.modal-panel h3 { font-family: var(--font-heading); font-size: 15px; font-weight: 600; margin-bottom: 12px; }
.radio-label { display: flex; align-items: center; gap: 4px; font-size: 12px; cursor: pointer; }
.btn-cancel { padding: 7px 16px; border-radius: var(--radius-sm); font-size: 12px; background: var(--bg-soft); border: 2px solid var(--outline); color: var(--text-secondary); cursor: pointer; }

/* ── Assets Tab ── */
.assets-tab { display: flex; flex-direction: column; }

.layer-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 8px; flex-wrap: wrap; }
.layer-tabs { display: flex; gap: 4px; }
.layer-tab {
  padding: 4px 12px; border-radius: 99px; font-size: 12px; font-weight: 500; cursor: pointer;
  border: 1px solid var(--outline); background: var(--input-bg); color: var(--text-secondary);
}
.layer-tab.active { background: var(--color-primary); color: white; border-color: var(--color-primary); }
.layer-count { font-size: 10px; opacity: 0.8; }
.layer-actions { display: flex; gap: 6px; }
.layer-placeholder-text { font-size: 12px; color: var(--text-tertiary); }
.review-comment-input { width: 180px; min-width: 140px; }

.perspective-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }

.ai-task-badges { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.ai-task-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: var(--bg-soft); border: 1px solid var(--outline);
}
.ai-task-badge .task-stage { color: var(--text-secondary); }
.ai-task-badge .task-dot { color: var(--accent); animation: pulse 1s infinite; }
.ai-task-badge.task-running { border-color: var(--accent); color: var(--accent); }
.ai-task-badge.task-failed { border-color: var(--danger); color: var(--danger); }
.ai-task-badge.task-review, .ai-task-badge.task-waiting_human, .ai-task-badge.task-retry { border-color: var(--warning); color: var(--warning); }
.ai-task-badge.task-confirmed, .ai-task-badge.task-next_stage { border-color: var(--success); color: var(--success); }
.ai-task-empty { font-size: 12px; color: var(--text-tertiary); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }

.coverage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.coverage-bars { margin-bottom: 16px; }
.cov-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.cov-name { width: 56px; font-size: 12px; color: var(--text-secondary); flex-shrink: 0; }
.cov-val { width: 40px; font-size: 12px; text-align: right; flex-shrink: 0; }
.gap-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border); }
.mt-3 { margin-top: 12px; }

.assets-split { flex: 1; display: flex; gap: 12px; min-height: 0; overflow: hidden; }

.assets-list-panel {
  width: 280px; min-width: 220px; flex-shrink: 0;
  overflow-y: auto; border-right: 1px solid var(--border);
  padding-right: 8px;
}
.assets-detail-panel {
  flex: 1; overflow-y: auto; background: var(--card-bg-2);
  border-radius: var(--radius-md); border: 1px solid var(--outline);
  padding: 16px;
}
.assets-flat { overflow-y: auto; flex: 1; }

.asset-list-item {
  padding: 10px 12px; cursor: pointer; border-radius: var(--radius-sm);
  border: 1px solid var(--border); margin-bottom: 6px;
  transition: background-color 0.15s;
}
.asset-list-item:hover { background-color: var(--hover-bg); }
.asset-list-item.selected { background-color: var(--accent-bg); border-left: 3px solid var(--color-primary); }
.asset-item-header { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.asset-item-title { font-size: 13px; font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-item-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-tertiary); margin-top: 4px; }

.detail-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.detail-meta { display: flex; gap: 12px; align-items: center; font-size: 12px; color: var(--text-secondary); margin-bottom: 16px; }
.detail-section { margin-bottom: 16px; }
.detail-section h5 { font-size: 12px; font-weight: 600; margin-bottom: 6px; color: var(--text-primary); }
.detail-section p { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
.ac-list { margin: 0; padding-left: 18px; font-size: 12px; color: var(--text-secondary); }
.ac-list li { margin-bottom: 4px; }

.dim-scores { display: flex; flex-direction: column; gap: 6px; }
.dim-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.dim-name { width: 100px; flex-shrink: 0; color: var(--text-secondary); text-align: right; }
.dim-bar { flex: 1; height: 6px; background: var(--bg-soft); border-radius: 3px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.dim-pass { background: #22c55e; }
.dim-warn { background: #f59e0b; }
.dim-fail { background: #ef4444; }
.dim-val { width: 28px; font-weight: 600; color: var(--text-primary); text-align: right; }

.issue-item { font-size: 11px; padding: 4px 8px; margin-bottom: 4px; background: #fef2f2; border-radius: 4px; color: #b91c1c; }

.detail-actions { display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid var(--border); }

.tree-child { margin-left: 16px; border-left: 2px solid var(--outline); padding-left: 12px; }
.case-pre { font-size: 11px; color: var(--text-secondary); white-space: pre-wrap; background: var(--bg-soft); padding: 8px; border-radius: var(--radius-sm); margin: 0; }

.text-green { color: #16a34a; }
.text-muted { color: var(--text-tertiary); }
</style>
