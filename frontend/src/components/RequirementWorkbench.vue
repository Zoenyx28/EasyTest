<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useApi } from '../composables/useApi';
import { renderMarkdown } from '../utils/markdown';
import BaseButton from './base/BaseButton.vue';
import BaseTag from './base/BaseTag.vue';
import BaseInput from './base/BaseInput.vue';
import BaseDialog from './base/BaseDialog.vue';

const emit = defineEmits<{ (e: 'showToast', msg: string): void }>();

const { activeProject, getActiveProject } = useProject();
const { activeBranch } = useBranch(activeProject.value?.id);
const { get, post, put, del, postFormData } = useApi();
const route = useRoute();
const router = useRouter();

// ── 状态元数据 ──
const GAP_STATUS: Record<string, { label: string; tone: 'yellow' | 'green' | 'red' | 'gray' | 'blue' }> = {
  pending: { label: '待确定', tone: 'yellow' },
  confirmed: { label: '已确定', tone: 'green' },
  ignored: { label: '已忽略', tone: 'gray' },
  fixed: { label: '已修复', tone: 'blue' },
  not_applicable: { label: '不涉及', tone: 'gray' },
};
const STAGE_META = [
  { key: 'review', label: '需求评审' },
  { key: 'story', label: 'Story' },
  { key: 'test_point', label: '测试点' },
  { key: 'case', label: '测试用例' },
] as const;

const requirements = ref<any[]>([]);
const selectedReqId = ref<number | null>(null);
const loading = ref(false);
const workbenchData = ref<any>(null);
const wbLoading = ref(false);
const searchQuery = ref('');
const projectId = computed(() => activeProject.value?.id || 0);
const branchId = computed(() => activeBranch.value?.id || 0);

// ── 文档（每个需求独立，切换需求时重置）──
const docContent = ref('');
const docLoading = ref(false);
const docError = ref('');
const docSaving = ref(false);
const extractingDoc = ref(false);
const docViewMode = ref<'edit' | 'render'>('render');

function parseMeta(s: string): any {
  try { return JSON.parse(s || '{}'); } catch { return {}; }
}
// 需求有链接来源但 content 为空（未提取）→ 文档面板提示提取
const docNeedsExtract = computed(() => {
  const req = workbenchData.value?.requirement;
  if (!req) return false;
  if ((req.content || '').trim()) return false;
  return !!parseMeta(req.source_meta).link;
});

// 文档面板状态：loading（取文档中）/ render（渲染）/ empty / error
const docState = computed<'loading' | 'render' | 'empty' | 'error'>(() => {
  if (docLoading.value) return 'loading';
  if (docContent.value.trim()) return 'render';
  if (docError.value) return 'error';
  return 'empty';
});

// ── 重新上传 / 添加来源 ──
const showReupload = ref(false);
const reuploadFile = ref<File | null>(null);
const reuploadLink = ref('');
const reuploading = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);
const TEXT_EXTS = ['txt', 'md', 'markdown', 'json', 'csv'];

function onReuploadFile(e: Event) {
  const input = e.target as HTMLInputElement;
  reuploadFile.value = input.files?.[0] || null;
}
async function submitReupload() {
  if (!selectedReqId.value || reuploading.value) return;
  if (!reuploadFile.value && !reuploadLink.value.trim()) {
    emit('showToast', '请选择文件或输入链接');
    return;
  }
  reuploading.value = true;
  try {
    if (reuploadFile.value) {
      const fd = new FormData();
      fd.append('file', reuploadFile.value);
      await postFormData(`/requirements/${selectedReqId.value}/sources/upload`, fd);
      const ext = (reuploadFile.value.name.split('.').pop() || '').toLowerCase();
      if (TEXT_EXTS.includes(ext)) {
        const text = await reuploadFile.value.text();
        await put(`/req/${selectedReqId.value}`, { content: text });
        emit('showToast', '文件已上传并加载为需求文档');
      } else {
        emit('showToast', '文件已上传（二进制/文档格式，正文需在来源中提取）');
      }
      reuploadFile.value = null;
    } else {
      const res = await post<any>(`/requirements/${selectedReqId.value}/sources`, {
        type: 'lark_link', link: reuploadLink.value.trim(),
      });
      reuploadLink.value = '';
      emit('showToast', res.extracted ? '文档已加载' : (res.extract_error || '链接已添加，但正文提取失败'));
    }
    showReupload.value = false;
    await loadWorkbench(selectedReqId.value);
  } catch (e: any) { emit('showToast', e.message || '上传失败'); }
  finally { reuploading.value = false; }
}

async function extractDoc() {
  if (!selectedReqId.value || extractingDoc.value) return;
  const meta = parseMeta(workbenchData.value?.requirement?.source_meta);
  if (!meta.link) return;
  extractingDoc.value = true;
  try {
    const res = await post<any>(`/requirements/${selectedReqId.value}/sources`, {
      type: 'lark_link', link: meta.link,
    });
    if (res.extracted) {
      await loadWorkbench(selectedReqId.value);
      emit('showToast', '文档已加载');
    } else {
      emit('showToast', res.extract_error || '提取失败，请检查飞书授权');
    }
  } catch (e: any) { emit('showToast', e.message || '提取失败'); }
  finally { extractingDoc.value = false; }
}

// ── 需求卡片：hover 操作菜单 ──
const cardMenuFor = ref<number | null>(null);
const menuAlignBottom = ref(false);
const cardMenuRef = ref<HTMLElement | null>(null);

function openCardMenu(r: any) {
  cardMenuFor.value = r.id;
  nextTick(() => {
    const el = cardMenuRef.value;
    if (!el) return;
    // 超出页面底部 → 菜单底部对齐（向上弹出）
    menuAlignBottom.value = el.getBoundingClientRect().bottom > window.innerHeight;
  });
}
function closeCardMenu() { cardMenuFor.value = null; }

// ── 新增需求：行内草稿卡片（可输入需求名称）──
const drafting = ref(false);
const draftTitle = ref('');
const draftSaving = ref(false);
const draftInput = ref<HTMLInputElement | null>(null);

function startDraft() {
  drafting.value = true;
  draftTitle.value = '';
  cardMenuFor.value = null;
  nextTick(() => draftInput.value?.focus());
}
async function saveDraft() {
  const title = draftTitle.value.trim();
  if (!title || draftSaving.value) return;
  draftSaving.value = true;
  try {
    const created = await post<any>('/requirements', {
      project_id: projectId.value, branch_id: branchId.value, title,
      content: '', source_type: 'text', source_meta: '{}',
    });
    drafting.value = false;
    draftTitle.value = '';
    await loadRequirements(created.id);
    emit('showToast', '需求已创建，可在卡片「导入文档」补充正文');
  } catch (e: any) { emit('showToast', e.message || '创建失败'); }
  finally { draftSaving.value = false; }
}

// ── 编辑需求标题（卡片内联）──
const editingId = ref<number | null>(null);
const editingTitle = ref('');
const editingSaving = ref(false);
const editInput = ref<HTMLInputElement | null>(null);

function startEdit(r: any) {
  editingId.value = r.id;
  editingTitle.value = r.title;
  cardMenuFor.value = null;
  nextTick(() => editInput.value?.focus());
}
function cancelEdit() { editingId.value = null; editingTitle.value = ''; }
async function saveEdit() {
  const title = editingTitle.value.trim();
  if (!title || !editingId.value || editingSaving.value) return;
  editingSaving.value = true;
  try {
    await put(`/req/${editingId.value}`, { title });
    editingId.value = null;
    await loadRequirements();
    emit('showToast', '标题已更新');
  } catch (e: any) { emit('showToast', e.message || '保存失败'); }
  finally { editingSaving.value = false; }
}

// ── 删除需求 ──
const deleteTarget = ref<any>(null);
const deleting = ref(false);
async function doDelete() {
  if (!deleteTarget.value || deleting.value) return;
  deleting.value = true;
  try {
    await del(`/requirements/${deleteTarget.value.id}`);
    const deletedId = deleteTarget.value.id;
    deleteTarget.value = null;
    await loadRequirements();
    if (selectedReqId.value === deletedId) {
      selectedReqId.value = null;
      workbenchData.value = null;
      docContent.value = '';
    }
    emit('showToast', '需求已删除');
  } catch (e: any) { emit('showToast', e.message || '删除失败'); }
  finally { deleting.value = false; }
}

// ── 导入文档弹窗（本地 / 飞书 / 网页）──
interface LarkStatus {
  bound: boolean;
  lark_open_id: string;
  token_status: string;
  auth_required: boolean;
  auth_pending: boolean;
  auth_error: string;
}
const showImport = ref(false);
const importReq = ref<any>(null);
const importTab = ref<'local' | 'feishu' | 'web'>('local');
const localFile = ref<File | null>(null);
const localDrag = ref(false);
const localUploading = ref(false);
const localFileInput = ref<HTMLInputElement | null>(null);
const feishuStatus = ref<LarkStatus>({ bound: false, lark_open_id: '', token_status: '', auth_required: true, auth_pending: false, auth_error: '' });
const feishuStatusLoaded = ref(false);
const feishuAuthing = ref(false);
const feishuLink = ref('');
const feishuImporting = ref(false);
let feishuPollTimer: number | undefined;
const webUrl = ref('');
const webImporting = ref(false);

const feishuUnauthorized = computed(() =>
  !feishuStatus.value.bound || ['', 'expired', 'invalid'].includes(feishuStatus.value.token_status),
);
const feishuStatusInfo = computed(() => {
  const s = feishuStatus.value.token_status;
  if (s === 'valid') return { tone: 'green', label: '有效' };
  if (s === 'needs_refresh') return { tone: 'yellow', label: '即将过期' };
  return { tone: 'red', label: '未授权' };
});

function openImport(r: any) {
  cardMenuFor.value = null;
  importReq.value = r;
  importTab.value = 'local';
  localFile.value = null;
  feishuLink.value = '';
  webUrl.value = '';
  showImport.value = true;
}
function switchImportTab(tab: 'local' | 'feishu' | 'web') {
  importTab.value = tab;
  if (tab === 'feishu') loadFeishuStatus();
}

function onLocalDrop(e: Event | DragEvent) {
  const files = (e as DragEvent).dataTransfer ? (e as DragEvent).dataTransfer?.files : (e.target as HTMLInputElement).files;
  const f = files?.[0];
  if (f) localFile.value = f;
  localDrag.value = false;
}
async function importLocal() {
  if (!importReq.value || !localFile.value || localUploading.value) return;
  localUploading.value = true;
  try {
    const fd = new FormData();
    fd.append('file', localFile.value);
    await postFormData(`/requirements/${importReq.value.id}/sources/upload`, fd);
    await loadWorkbench(importReq.value.id);
    showImport.value = false;
    emit('showToast', '文档已导入');
  } catch (e: any) { emit('showToast', e.message || '导入失败'); }
  finally { localUploading.value = false; }
}
async function importFeishu() {
  if (!importReq.value || !feishuLink.value.trim() || feishuImporting.value) return;
  feishuImporting.value = true;
  try {
    const res = await post<any>(`/requirements/${importReq.value.id}/sources`, { type: 'lark_link', link: feishuLink.value.trim() });
    await loadWorkbench(importReq.value.id);
    showImport.value = false;
    emit('showToast', res.extracted ? '飞书文档已导入' : (res.extract_error || '链接已添加，正文提取失败'));
  } catch (e: any) { emit('showToast', e.message || '导入失败'); }
  finally { feishuImporting.value = false; }
}
async function importWeb() {
  if (!importReq.value || !webUrl.value.trim() || webImporting.value) return;
  webImporting.value = true;
  try {
    const res = await post<any>(`/requirements/${importReq.value.id}/sources`, { type: 'web', link: webUrl.value.trim() });
    await loadWorkbench(importReq.value.id);
    showImport.value = false;
    emit('showToast', res.extracted ? '网页内容已获取' : (res.extract_error || '链接已添加'));
  } catch (e: any) { emit('showToast', e.message || '获取失败'); }
  finally { webImporting.value = false; }
}

// 飞书授权状态（复用设置页 OAuth 流程）
async function loadFeishuStatus() {
  feishuStatusLoaded.value = false;
  try {
    feishuStatus.value = await get<any>('/settings/feishu/status');
  } catch (e: any) { emit('showToast', e.message || '查询飞书授权状态失败'); }
  finally { feishuStatusLoaded.value = true; }
}
async function startFeishuAuth() {
  feishuAuthing.value = true;
  try {
    const res = await get<any>('/settings/feishu/auth-url');
    window.open(res.authorize_url, '_blank', 'noopener');
    emit('showToast', '请在浏览器中完成飞书授权');
    stopFeishuPoll();
    feishuPollTimer = window.setInterval(async () => {
      try {
        const s = await get<any>('/settings/feishu/status');
        feishuStatus.value = s;
        if (s.bound) { stopFeishuPoll(); emit('showToast', '飞书授权成功'); }
      } catch { /* 忽略瞬时错误，继续轮询 */ }
    }, 2000);
  } catch (e: any) { emit('showToast', e.message || '发起飞书授权失败'); }
  finally { feishuAuthing.value = false; }
}
function stopFeishuPoll() {
  if (feishuPollTimer) { window.clearInterval(feishuPollTimer); feishuPollTimer = undefined; }
}

function formatTime(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const filteredReqs = computed(() =>
  requirements.value.filter(r => (r.title || '').toLowerCase().includes(searchQuery.value.toLowerCase())),
);

// ── 阶段 ──
const activeStage = ref<'review' | 'story' | 'test_point' | 'case'>('review');
const reviewRunning = ref(false);

// ── 评审 / 问题卡片 ──
const analysisAsset = computed(() =>
  (workbenchData.value?.assets || []).find((a: any) => a.asset_type === 'analysis'),
);
const gapAssets = computed(() =>
  (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'gap'),
);
const analysisElements = computed(() => {
  const c = analysisAsset.value?.content;
  if (!c) return null;
  try { return (typeof c === 'string' ? JSON.parse(c) : c)?.elements || null; } catch { return null; }
});
const analysisReason = computed(() => analysisAsset.value?.description || analysisAsset.value?.review_comment || '');

// 评审进行中（analyze 或 re-review 任务 RUNNING）
const reviewActive = computed(() => {
  if (reviewRunning.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) =>
    ['analyze', 're_review'].includes(t.stage) && ['PENDING', 'RUNNING'].includes(t.status),
  );
});

// ── 资产分组（ADR-0016 统一资产表）──
const assets = computed<any[]>(() => workbenchData.value?.assets || []);
const storyAssets = computed(() => assets.value.filter((a: any) => a.asset_type === 'story'));
const tpAssets = computed(() => assets.value.filter((a: any) => a.asset_type === 'test_point'));
const scenarioAssets = computed(() => assets.value.filter((a: any) => a.asset_type === 'scenario'));
const caseAssets = computed(() => assets.value.filter((a: any) => a.asset_type === 'case'));

function assetContent(a: any): any {
  try { return JSON.parse(a?.content || '{}'); } catch { return {}; }
}
function confirmations(a: any): any {
  return assetContent(a).confirmations || {};
}

const storyMap = computed<Record<number, string>>(() => {
  const m: Record<number, string> = {};
  for (const s of storyAssets.value) m[s.id] = s.title || `Story ${s.sort_order + 1}`;
  return m;
});

const allConfirmed = (list: any[]) => list.length > 0 && list.every((a: any) => a.status === 'confirmed');
const storiesConfirmed = computed(() => allConfirmed(storyAssets.value));
const tpsConfirmed = computed(() => allConfirmed(tpAssets.value));
const scenariosConfirmed = computed(() => allConfirmed(scenarioAssets.value));

// 渐进式选项卡：评审永远显示；Story/测试点/测试用例 在对应资产产出后才显示
const visibleStages = computed(() => STAGE_META.filter((s: any) => {
  if (s.key === 'review') return true;
  if (s.key === 'story') return storyAssets.value.length > 0;
  if (s.key === 'test_point') return tpAssets.value.length > 0;
  if (s.key === 'case') return caseAssets.value.length > 0;
  return false;
}));

function statusLabel(s: string): string {
  return { generated: '已生成', partially_confirmed: '部分确认', confirmed: '已确认' }[s] || s || '--';
}
function scoreTone(score: number): 'green' | 'yellow' | 'red' | 'gray' {
  if (score >= 80) return 'green';
  if (score >= 60) return 'yellow';
  if (score > 0) return 'red';
  return 'gray';
}
function gateTone(g: string): 'green' | 'yellow' | 'red' | 'gray' {
  if (g === 'PASS') return 'green';
  if (g === 'WARNING') return 'yellow';
  if (g === 'BLOCKED') return 'red';
  return 'gray';
}
function typeTone(t: string): 'blue' | 'purple' | 'green' | 'red' | 'yellow' | 'gray' {
  const map: Record<string, 'blue' | 'purple' | 'green' | 'red' | 'yellow' | 'gray'> = {
    功能: 'blue', 接口: 'purple', UI: 'green', 安全: 'red', 性能: 'red', 兼容: 'yellow', Manual: 'gray',
  };
  return map[t] || 'gray';
}

// 编号
function padNo(n: number): string {
  return String(n).padStart(2, '0');
}
function caseNumber(c: any): string {
  return `TC-${padNo((c.sort_order || 0) + 1)}`;
}
function storyNumber(s: any): string {
  return `ST-${padNo((s.sort_order || 0) + 1)}`;
}
function tpNumber(t: any): string {
  return `TP-${padNo((t.sort_order || 0) + 1)}`;
}

// ── 阶段任务执行（生成 / 评审，异步轮询）──
const STAGE_ENDPOINTS: Record<string, { gen: string; review: string; genStage: string; reviewStage: string }> = {
  stories: { gen: 'stories/generate', review: 'stories/review', genStage: 'stories', reviewStage: 'story_review' },
  test_points: { gen: 'test-points/generate', review: 'test-points/review', genStage: 'test_points', reviewStage: 'test_point_review' },
  scenarios: { gen: 'test-scenarios/generate', review: 'test-scenarios/review', genStage: 'scenarios', reviewStage: 'scenario_review' },
  cases: { gen: 'cases/generate', review: 'cases/review', genStage: 'cases', reviewStage: 'case_review' },
};
const runningMap: Record<string, { value: boolean }> = {
  stories: ref(false), story_review: ref(false),
  test_points: ref(false), test_point_review: ref(false),
  scenarios: ref(false), scenario_review: ref(false),
  cases: ref(false), case_review: ref(false),
};
function isStageBusy(stage: string): boolean {
  if (runningMap[stage]?.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) => t.stage === stage && ['PENDING', 'RUNNING'].includes(t.status));
}

// 轮询 workbench 直到指定 stage 任务结束（静默刷新，不打断文档/阶段 UI）
async function refreshForPoll() {
  if (!selectedReqId.value) return;
  try {
    const data = await get<any>(`/req/${selectedReqId.value}/workbench`);
    workbenchData.value = data;
    if (selectedCase.value && !caseAssets.value.some((c: any) => c.id === selectedCase.value.id)) {
      selectedCase.value = null;
    }
  } catch { /* 轮询失败忽略，等下一次 */ }
}

function pollUntilIdle(stage: string, doneMsg: string, runningRef?: any) {
  const timer = setInterval(async () => {
    if (!selectedReqId.value) { clearInterval(timer); return; }
    await refreshForPoll();
    const tasks = workbenchData.value?.ai_tasks || [];
    const failed = tasks.find((t: any) => t.stage === stage && t.status === 'FAILED');
    if (failed) {
      clearInterval(timer);
      if (runningRef) runningRef.value = false;
      emit('showToast', failed.error || `${stage} 任务失败`);
      return;
    }
    const busy = tasks.some((t: any) => t.stage === stage && ['PENDING', 'RUNNING'].includes(t.status));
    if (!busy) {
      clearInterval(timer);
      if (runningRef) runningRef.value = false;
      emit('showToast', doneMsg);
    }
  }, 2000);
}

async function triggerStage(stageKey: 'stories' | 'test_points' | 'scenarios' | 'cases', action: 'gen' | 'review') {
  if (!selectedReqId.value) return;
  const ep = STAGE_ENDPOINTS[stageKey];
  const stage = action === 'gen' ? ep.genStage : ep.reviewStage;
  runningMap[stage].value = true;
  try {
    await post(`/req/${selectedReqId.value}/${action === 'gen' ? ep.gen : ep.review}`, {});
    emit('showToast', `${action === 'gen' ? '生成' : '评审'}已启动`);
    pollUntilIdle(stage, `${action === 'gen' ? '生成' : '评审'}完成`, runningMap[stage]);
  } catch (e: any) { runningMap[stage].value = false; emit('showToast', e.message || '启动失败'); }
}

// ── 双视角确认 ──
async function confirmAsset(asset: any, perspective: 'product' | 'testing') {
  if (!selectedReqId.value) return;
  try {
    await put(`/req/${selectedReqId.value}/assets/${asset.id}`, { perspective });
    await loadWorkbench(selectedReqId.value);
    emit('showToast', `${perspective === 'product' ? '产品' : '测试'}已确认`);
  } catch (e: any) { emit('showToast', e.message || '确认失败'); }
}

// ── 用例：筛选 / 详情 / 绑定 / 执行 ──
const caseTypeFilter = ref('全部');
const caseTypeFilters = computed(() => {
  const set = new Set<string>();
  for (const c of caseAssets.value) set.add(assetContent(c).test_type || '功能');
  if (!set.has('功能')) set.add('功能');
  if (!set.has('接口')) set.add('接口');
  return ['全部', ...Array.from(set)];
});
const filteredCases = computed(() => {
  if (caseTypeFilter.value === '全部') return caseAssets.value;
  return caseAssets.value.filter((c: any) => (assetContent(c).test_type || '功能') === caseTypeFilter.value);
});

const selectedCase = ref<any>(null);
function toggleCase(c: any) {
  selectedCase.value = selectedCase.value?.id === c.id ? null : c;
}

const bindings = computed<any[]>(() => workbenchData.value?.bindings || []);
function caseBindings(c: any): any[] {
  return bindings.value.filter((b: any) => b.generated_case_id === c.id);
}

// 绑定弹窗
const bindingOpen = ref(false);
const bindingCase = ref<any>(null);
const bindSearch = ref('');
const autoCases = ref<any[]>([]);
const bindingLoading = ref(false);
const bindingSaving = ref(false);

async function openBinding(c: any) {
  bindingCase.value = c;
  bindSearch.value = '';
  bindingOpen.value = true;
  bindingLoading.value = true;
  try {
    const res = await get<any>(`/tests?project_id=${projectId.value}&version=${branchId.value || 0}`);
    const flat: any[] = [];
    for (const m of res.modules || []) {
      for (const cl of m.classes || []) {
        for (const it of cl.items || []) {
          flat.push({ ...it, module: m.module || '', className: cl.name || '' });
        }
      }
    }
    autoCases.value = flat;
  } catch (e: any) { emit('showToast', e.message || '加载自动化用例失败'); }
  finally { bindingLoading.value = false; }
}

const filteredAutoCases = computed(() => {
  const q = bindSearch.value.trim().toLowerCase();
  if (!q) return autoCases.value;
  return autoCases.value.filter((c: any) =>
    (c.name || '').toLowerCase().includes(q) || (c.uid || '').toLowerCase().includes(q),
  );
});

async function doBind(c: any) {
  if (!selectedReqId.value || !bindingCase.value || bindingSaving.value) return;
  bindingSaving.value = true;
  try {
    await post(`/req/${selectedReqId.value}/bindings`, {
      generated_case_id: bindingCase.value.id, uid: c.uid,
    });
    bindingOpen.value = false;
    await loadWorkbench(selectedReqId.value);
    emit('showToast', '绑定成功');
  } catch (e: any) { emit('showToast', e.message || '绑定失败'); }
  finally { bindingSaving.value = false; }
}

async function unBind(b: any) {
  if (!selectedReqId.value) return;
  try {
    await del(`/req/${selectedReqId.value}/bindings/${b.id}`);
    await loadWorkbench(selectedReqId.value);
    emit('showToast', '已取消绑定');
  } catch (e: any) { emit('showToast', e.message || '解绑失败'); }
}

async function executeCase(c: any) {
  if (!selectedReqId.value) return;
  const uids = caseBindings(c).map((b: any) => b.uid);
  if (!uids.length) { emit('showToast', '该用例尚未绑定自动化用例'); return; }
  try {
    const res = await post<any>(`/req/${selectedReqId.value}/execute`, { uids, concurrency: 2, sequential: true });
    emit('showToast', `执行已启动（${res.execution_id}）`);
  } catch (e: any) { emit('showToast', e.message || '执行失败'); }
}

// ── 问题卡片内容解析 ──
function gapContent(g: any): any {
  try { return typeof g.content === 'string' ? JSON.parse(g.content) : g.content; } catch { return {}; }
}
function gapThread(g: any): any[] { return gapContent(g).thread || []; }

// 评论输入状态：gapId -> 是否展开输入框
const commentOpen = ref<Record<number, boolean>>({});
const commentText = ref<Record<number, string>>({});

// ── 加载 ──
async function loadRequirements(preferredId?: number) {
  if (!projectId.value || !branchId.value) { requirements.value = []; return; }
  loading.value = true;
  try {
    const data = await get<any>(`/requirements?project_id=${projectId.value}&branch_id=${branchId.value}`);
    requirements.value = Array.isArray(data) ? data : (data.items || []);
    // 加载成功后默认选中第一个需求展示详情；URL 指定 / 当前选中项优先
    if (requirements.value.length > 0) {
      const targetId = preferredId ?? selectedReqId.value ?? undefined;
      const target = requirements.value.find(r => r.id === targetId);
      selectReq(target ? target.id : requirements.value[0].id);
    } else {
      selectedReqId.value = null;
      workbenchData.value = null;
      docContent.value = '';
    }
  } catch (e: any) { emit('showToast', e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function loadWorkbench(reqId: number) {
  wbLoading.value = true;
  docLoading.value = true;
  docError.value = '';
  try {
    const data = await get<any>(`/req/${reqId}/workbench`);
    // 竞态防护：期间已切换到其他需求则丢弃本次结果
    if (selectedReqId.value !== reqId) return;
    workbenchData.value = data;
    const req = data?.requirement;
    docContent.value = req?.content || '';
    docViewMode.value = 'render';
    if (!docContent.value) {
      // 无正文 → 若为链接来源则自动提取渲染（无需手动点渲染）
      const link = parseMeta(req?.source_meta).link;
      if (link) {
        try {
          const res = await get<any>(`/feishu/preview?url=${encodeURIComponent(link)}`);
          if (selectedReqId.value !== reqId) return;
          if (res.markdown) docContent.value = res.markdown;
          else docError.value = res.error || '未能提取文档正文';
        } catch (e: any) {
          if (selectedReqId.value !== reqId) return;
          docError.value = e.message || '文档提取失败';
        }
      } else {
        docError.value = '该需求未关联文档或未填写正文';
      }
    }
    if (selectedCase.value && !caseAssets.value.some((c: any) => c.id === selectedCase.value.id)) {
      selectedCase.value = null;
    }
  } catch (e: any) {
    if (selectedReqId.value !== reqId) return;
    docError.value = e.message || '加载工作台失败';
    emit('showToast', e.message || '加载工作台失败');
  } finally {
    if (selectedReqId.value === reqId) {
      wbLoading.value = false;
      docLoading.value = false;
    }
  }
}

function selectReq(reqId: number) {
  // 已是当前需求且已加载 → 仅同步 URL，避免重复拉取
  if (selectedReqId.value === reqId && workbenchData.value?.requirement?.id === reqId) {
    router.replace({ query: { req_id: reqId } });
    return;
  }
  selectedReqId.value = reqId;
  activeStage.value = 'review';
  selectedCase.value = null;
  caseTypeFilter.value = '全部';
  // 立即清空文档，避免上一个需求的内容残留闪现
  docContent.value = '';
  docError.value = '';
  docViewMode.value = 'render';
  docLoading.value = true;
  loadWorkbench(reqId);
  router.replace({ query: { req_id: reqId } });
}

// ── 文档编辑 ──
async function saveDoc() {
  if (!selectedReqId.value) return;
  docSaving.value = true;
  try {
    await put(`/req/${selectedReqId.value}`, { content: docContent.value });
    await loadWorkbench(selectedReqId.value);
    emit('showToast', '文档已保存（不自动触发评审）');
  } catch (e: any) { emit('showToast', e.message || '保存失败'); }
  finally { docSaving.value = false; }
}

// ── 评审 ──
async function startReview() {
  if (!selectedReqId.value || reviewActive.value) return;
  reviewRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/analyze`, {});
    emit('showToast', 'AI 评审已启动');
    pollUntilIdle('analyze', '评审完成', reviewRunning);
  } catch (e: any) { reviewRunning.value = false; emit('showToast', e.message || '启动评审失败'); }
}

async function reReview() {
  if (!selectedReqId.value || reviewActive.value) return;
  reviewRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/analysis/re-review`, {});
    emit('showToast', '重新评审已启动');
    pollUntilIdle('re_review', '重新评审完成', reviewRunning);
  } catch (e: any) { reviewRunning.value = false; emit('showToast', e.message || '重新评审失败'); }
}

// ── 问题卡片操作 ──
async function gapComment(g: any) {
  const text = (commentText.value[g.id] || '').trim();
  if (!text) return;
  try {
    await post(`/req/${selectedReqId.value}/gaps/${g.id}/comment`, { comment: text });
    commentText.value[g.id] = '';
    commentOpen.value[g.id] = false;
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', 'AI 已回复');
  } catch (e: any) { emit('showToast', e.message || '评论失败'); }
}

async function gapIgnore(g: any) {
  try {
    await post(`/req/${selectedReqId.value}/gaps/${g.id}/ignore`);
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '已忽略');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

async function gapConfirm(g: any) {
  try {
    await post(`/req/${selectedReqId.value}/gaps/${g.id}/confirm`);
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '已确定');
  } catch (e: any) { emit('showToast', e.message || '确定失败'); }
}

// ── 初始化 ──
watch(activeBranch, () => { loadRequirements(); selectedReqId.value = null; workbenchData.value = null; });

// 点击外部关闭卡片操作菜单
function onDocClick() { closeCardMenu(); }

onMounted(async () => {
  document.addEventListener('click', onDocClick);
  if (!activeProject.value?.id) await getActiveProject();
  // URL 指定需求优先；否则加载成功后默认选中第一个需求展示详情
  const qReqId = Number(route.query.req_id) || undefined;
  await loadRequirements(qReqId);
});
onUnmounted(() => {
  document.removeEventListener('click', onDocClick);
  stopFeishuPoll();
});
</script>

<template>
  <div class="workbench flex h-full min-h-0">
    <!-- 左侧需求列表 -->
    <aside class="req-sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">需求列表</h2>
        <BaseButton size="sm" variant="ghost" @click="startDraft">+ 新增</BaseButton>
      </div>
      <div class="px-4 pb-2">
        <BaseInput v-model="searchQuery" placeholder="搜索需求" class="w-full text-sm" />
      </div>
      <div class="req-list" v-if="!loading">
        <!-- 新增需求：行内草稿卡片（可输入需求名称） -->
        <div v-if="drafting" class="req-card req-card--draft" @click.stop>
          <input ref="draftInput" v-model="draftTitle" class="draft-input"
            placeholder="输入需求名称，回车创建" @keydown.enter="saveDraft" @keydown.esc="drafting = false" />
          <div class="draft-actions">
            <BaseButton size="sm" variant="ghost" @click="drafting = false">取消</BaseButton>
            <BaseButton size="sm" variant="primary" :loading="draftSaving" @click="saveDraft">创建</BaseButton>
          </div>
        </div>

        <!-- 需求卡片：名称 + 状态(第二排右对齐) + 创建时间 + hover 操作菜单 -->
        <div v-for="r in filteredReqs" :key="r.id" class="req-card"
          :class="{ active: r.id === selectedReqId }"
          @click="selectReq(r.id)" @mouseleave="closeCardMenu">
          <!-- 编辑态：内联改标题 -->
          <template v-if="editingId === r.id">
            <input ref="editInput" v-model="editingTitle" class="draft-input"
              placeholder="需求名称" @keydown.enter="saveEdit" @keydown.esc="cancelEdit" @click.stop />
            <div class="draft-actions">
              <BaseButton size="sm" variant="ghost" @click="cancelEdit">取消</BaseButton>
              <BaseButton size="sm" variant="primary" :loading="editingSaving" @click="saveEdit">保存</BaseButton>
            </div>
          </template>
          <template v-else>
            <div class="req-card-title-row">
              <span class="req-card-title">{{ r.title }}</span>
              <button class="req-more" title="更多操作"
                @mouseenter="openCardMenu(r)" @click.stop="openCardMenu(r)">⋮</button>
              <!-- 操作菜单（顶部对齐需求卡片；超出页面底部则底部对齐；z-index 高于右侧详情页） -->
              <div v-if="cardMenuFor === r.id" ref="cardMenuRef" class="req-menu"
                :class="{ 'req-menu--bottom': menuAlignBottom }" @click.stop>
                <button class="menu-item" @click="startEdit(r)">编辑</button>
                <button class="menu-item" @click="openImport(r)">导入文档</button>
                <button class="menu-item menu-item--danger" @click="deleteTarget = r">删除</button>
              </div>
            </div>
            <div class="req-card-meta">
              <span class="req-card-time">{{ formatTime(r.created_at) }}</span>
              <span class="req-status">{{ r.status }}</span>
            </div>
          </template>
        </div>
        <div v-if="requirements.length === 0" class="empty-state">暂无需求</div>
      </div>
    </aside>

    <!-- 右侧：需求列表接口加载中 → 动态 loading -->
    <div v-if="loading" class="wb-main flex-1 min-w-0 flex flex-col">
      <div class="wb-loading">
        <div class="skeleton-tabs">
          <div class="sk sk-tab" style="width:64px"></div>
          <div class="sk sk-tab" style="width:48px"></div>
          <div class="sk sk-tab" style="width:64px"></div>
          <div class="sk sk-tab" style="width:64px"></div>
        </div>
        <div class="wb-split">
          <div class="skeleton-panel sk-doc">
            <div class="sk sk-head"></div>
            <div class="sk sk-line" style="width:92%"></div>
            <div class="sk sk-line" style="width:78%"></div>
            <div class="sk sk-line" style="width:86%"></div>
            <div class="sk sk-line" style="width:60%"></div>
          </div>
          <div class="skeleton-panel sk-stage">
            <div class="sk sk-head"></div>
            <div class="sk sk-line" style="width:90%"></div>
            <div class="sk sk-line" style="width:70%"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：需求列表为空 -->
    <div v-else-if="requirements.length === 0" class="wb-main flex-1 flex items-center justify-center">
      <div class="empty-tip">
        <span class="empty-icon">📄</span>
        <p>暂无需求，请先创建需求</p>
      </div>
    </div>

    <!-- 右侧：顶部选项卡 → 60% 文档 + 40% 阶段（严格按原型图），选中需求后展示 -->
    <div class="wb-main flex-1 min-w-0 flex flex-col" v-else-if="selectedReqId">
      <!-- 顶部选项卡（下划线式，渐进式展示） -->
      <nav class="stage-tabs">
        <button v-for="s in visibleStages" :key="s.key" class="stage-tab"
          :class="{ active: activeStage === s.key }" @click="activeStage = s.key">
          {{ s.label }}
        </button>
      </nav>

      <div class="wb-split">
        <!-- ── 需求文档 60%（左）── -->
        <div class="doc-panel">
          <div class="panel-head">
            <h3 class="panel-title">需求文档</h3>
            <div class="doc-tools">
              <template v-if="docState === 'render' && !wbLoading">
                <BaseButton v-if="docViewMode === 'render'" size="sm" variant="ghost" @click="docViewMode = 'edit'">编辑</BaseButton>
                <template v-else>
                  <BaseButton size="sm" variant="ghost" @click="docViewMode = 'render'">取消</BaseButton>
                  <BaseButton size="sm" class="btn-save" @click="saveDoc" :loading="docSaving">保存</BaseButton>
                </template>
              </template>
            </div>
          </div>

          <!-- 取文档中 → loading -->
          <div v-if="docState === 'loading'" class="doc-empty">
            <div class="spinner"></div>
            <span>正在加载需求文档…</span>
          </div>

          <!-- 获取失败 → 重新上传入口 -->
          <div v-else-if="docState === 'error'" class="doc-empty">
            <p>文档获取失败：{{ docError }}</p>
            <div class="doc-empty-actions">
              <BaseButton v-if="docNeedsExtract" variant="secondary" size="sm" @click="extractDoc" :loading="extractingDoc">重新提取</BaseButton>
              <BaseButton variant="primary" size="sm" @click="showReupload = true">重新上传文件</BaseButton>
            </div>
          </div>

          <!-- 无文档 → 上传 / 粘贴链接入口 -->
          <div v-else-if="docState === 'empty'" class="doc-empty">
            <p>该需求暂无文档内容。</p>
            <p v-if="docNeedsExtract" class="doc-link">{{ parseMeta(workbenchData.requirement.source_meta).link }}</p>
            <div class="doc-empty-actions">
              <BaseButton v-if="docNeedsExtract" variant="secondary" size="sm" @click="extractDoc" :loading="extractingDoc">提取文档</BaseButton>
              <BaseButton variant="primary" size="sm" @click="showReupload = true">上传 / 粘贴链接</BaseButton>
            </div>
          </div>

          <!-- 自动渲染（含图片 / 表格） -->
          <div v-else-if="docViewMode === 'render'" class="doc-render" v-html="renderMarkdown(docContent)"></div>
          <textarea v-else v-model="docContent" class="doc-editor" placeholder="需求文档内容（编辑后保存，不自动触发评审）"></textarea>
        </div>

        <!-- ── 阶段面板 40%（右）── -->
        <div class="stage-panel">
          <div v-if="wbLoading" class="pane-body empty-state">加载中…</div>

          <!-- ═══ 需求评审 ═══ -->
          <div v-else-if="activeStage === 'review'" class="tab-pane">
            <div class="pane-head">
              <span class="pane-title">需求评审</span>
            </div>

            <div class="pane-body" v-if="!analysisAsset">
              <div class="empty-state">
                <p>尚未发起需求评审。</p>
                <BaseButton variant="primary" @click="startReview" :loading="reviewActive">
                  {{ reviewActive ? '评审中...' : '开始评审' }}
                </BaseButton>
              </div>
            </div>

            <div class="pane-body empty-state" v-else-if="reviewActive">AI 评审进行中…</div>

            <!-- 评审完成：此时才出现 重新评审 / 生成Story -->
            <div v-else class="pane-body">
              <!-- AI 质量分析摘要 -->
              <div class="analysis-card">
                <div class="analysis-head">
                  <span class="ai-icon">◉</span>
                  <h4>AI 质量分析摘要</h4>
                </div>
                <p class="analysis-text">{{ analysisReason || '评审完成' }}</p>
                <div v-if="analysisElements" class="analysis-elems">
                  <span v-for="(v, k) in analysisElements" :key="k" class="elem-chip">
                    {{ k }}: {{ Array.isArray(v) ? v.length : v }}
                  </span>
                </div>
              </div>

              <!-- 待处理问题 -->
              <h4 class="pane-section">待处理问题（{{ gapAssets.length }}）</h4>
              <div v-for="g in gapAssets" :key="g.id" class="gap-card">
                <div class="gap-head">
                  <span class="gap-status" :class="`gap-status--${g.status}`">
                    {{ GAP_STATUS[g.status]?.label || g.status }}
                  </span>
                  <div class="gap-head-actions">
                    <BaseButton size="sm" variant="ghost" @click="gapIgnore(g)" v-if="g.status !== 'ignored'">忽略</BaseButton>
                    <BaseButton size="sm" variant="ghost" @click="gapConfirm(g)" v-if="g.status !== 'confirmed'">确认解决</BaseButton>
                  </div>
                </div>
                <div class="gap-body">
                  <p class="gap-type">{{ g.title }}</p>
                  <p class="gap-desc">{{ g.description }}</p>
                  <p class="gap-question" v-if="gapContent(g).question">{{ gapContent(g).question }}</p>
                  <!-- AI 评论气泡 -->
                  <div v-for="(t, i) in gapThread(g)" :key="i" class="ai-bubble" :class="`ai-bubble--${t.role}`">
                    <span class="ai-avatar">{{ t.role === 'user' ? '我' : 'AI' }}</span>
                    <span class="ai-text">{{ t.text }}</span>
                  </div>
                  <!-- 评论输入 -->
                  <div v-if="commentOpen[g.id]" class="comment-box">
                    <BaseInput v-model="commentText[g.id]" placeholder="添加评论..." @enter="gapComment(g)" class="w-full" />
                    <div class="comment-actions">
                      <BaseButton size="sm" variant="ghost" @click="commentOpen[g.id] = false">取消</BaseButton>
                      <BaseButton size="sm" variant="primary" @click="gapComment(g)">提交</BaseButton>
                    </div>
                  </div>
                  <BaseButton v-else size="sm" variant="ghost" @click="commentOpen[g.id] = true">评论</BaseButton>
                </div>
              </div>

              <!-- 底部操作栏：评审结果出现后才展示 -->
              <div class="pane-actions">
                <BaseButton class="flex-1" variant="secondary" @click="reReview" :loading="reviewActive">重新评审</BaseButton>
                <BaseButton class="flex-1" variant="primary" @click="triggerStage('stories', 'gen')" :loading="isStageBusy('stories')">
                  {{ isStageBusy('stories') ? '生成中...' : '生成 Story' }}
                </BaseButton>
              </div>
            </div>
          </div>

          <!-- ═══ Story ═══ -->
          <div v-else-if="activeStage === 'story'" class="tab-pane">
            <div class="pane-head">
              <h3 class="pane-title">Story 列表</h3>
              <BaseButton size="sm" variant="primary" @click="triggerStage('test_points', 'gen')"
                :loading="isStageBusy('test_points')" :disabled="!storiesConfirmed">生成测试点</BaseButton>
            </div>
            <div class="pane-body">
              <div v-if="isStageBusy('stories') && !storyAssets.length" class="empty-state">Story 生成中…</div>
              <div v-for="s in storyAssets" :key="s.id" class="story-card">
                <div class="story-head">
                  <div class="story-id-row">
                    <span class="story-id">{{ storyNumber(s) }} {{ s.title }}</span>
                    <span class="score-circle" :class="`score-${scoreTone(s.score)}`" :title="assetContent(s).score_reason">{{ s.score }}</span>
                  </div>
                  <div class="story-head-right">
                    <BaseTag v-if="s.gate_status" :tone="gateTone(s.gate_status)" size="sm">{{ s.gate_status }}</BaseTag>
                    <span class="story-status">{{ statusLabel(s.status) }}</span>
                  </div>
                </div>
                <div class="story-body">
                  <div class="story-block" v-if="s.description">
                    <h4>描述</h4>
                    <p>{{ s.description }}</p>
                  </div>
                  <div class="story-block" v-if="assetContent(s).acceptance_criteria?.length">
                    <h4>验收标准</h4>
                    <ul class="criteria-list">
                      <li v-for="(c, i) in assetContent(s).acceptance_criteria" :key="i">✓ {{ c }}</li>
                    </ul>
                  </div>
                </div>
                <div class="story-actions">
                  <BaseButton size="sm" variant="ghost" :disabled="!!confirmations(s).product"
                    @click="confirmAsset(s, 'product')">
                    {{ confirmations(s).product ? '产品已确认 ✓' : '产品确认' }}
                  </BaseButton>
                  <BaseButton size="sm" variant="ghost" :disabled="!!confirmations(s).testing"
                    @click="confirmAsset(s, 'testing')">
                    {{ confirmations(s).testing ? '测试已确认 ✓' : '测试确认' }}
                  </BaseButton>
                </div>
              </div>
              <p v-if="storyAssets.length && !storiesConfirmed" class="stage-hint">提示：需全部 Story 完成「产品 + 测试」双视角确认后，才可生成测试点。</p>
            </div>
          </div>

          <!-- ═══ 测试点 ═══ -->
          <div v-else-if="activeStage === 'test_point'" class="tab-pane">
            <div class="pane-head">
              <h3 class="pane-title">测试点列表</h3>
            </div>
            <div class="pane-body">
              <div v-if="isStageBusy('test_points') && !tpAssets.length" class="empty-state">测试点生成中…</div>

              <div v-for="t in tpAssets" :key="t.id" class="tp-card">
                <div class="tp-head">
                  <div class="tp-title-col">
                    <span class="tp-name">{{ tpNumber(t) }} {{ t.title }}</span>
                    <span class="tp-meta">关联 Story: {{ storyMap[t.story_id] || '--' }}</span>
                  </div>
                  <div class="tp-head-right">
                    <span class="tp-category">{{ assetContent(t).category || 'Functional' }}</span>
                    <span class="tp-status">{{ statusLabel(t.status) }}</span>
                  </div>
                </div>
                <p class="tp-desc">{{ t.description }}</p>
                <div class="tp-confirm">
                  <BaseButton size="sm" variant="ghost" :disabled="!!confirmations(t).product"
                    @click="confirmAsset(t, 'product')">
                    {{ confirmations(t).product ? '产品已确认 ✓' : '产品确认' }}
                  </BaseButton>
                  <BaseButton size="sm" variant="ghost" :disabled="!!confirmations(t).testing"
                    @click="confirmAsset(t, 'testing')">
                    {{ confirmations(t).testing ? '测试已确认 ✓' : '测试确认' }}
                  </BaseButton>
                </div>
              </div>
              <p v-if="tpAssets.length && !tpsConfirmed" class="stage-hint">提示：需全部测试点完成双视角确认后，才可生成测试场景。</p>

              <!-- 场景子块 -->
              <div class="sub-block" v-if="tpsConfirmed || scenarioAssets.length">
                <div class="sub-block-head">
                  <span class="sub-block-title">测试场景（{{ scenarioAssets.length }}）</span>
                  <div class="sub-block-actions">
                    <BaseButton size="sm" variant="secondary" @click="triggerStage('scenarios', 'review')"
                      :loading="isStageBusy('scenario_review')" :disabled="!scenarioAssets.length">场景评审</BaseButton>
                    <BaseButton size="sm" variant="ghost" @click="triggerStage('scenarios', 'gen')"
                      :loading="isStageBusy('scenarios')">重新生成</BaseButton>
                  </div>
                </div>

                <div v-if="!scenarioAssets.length && !isStageBusy('scenarios')" class="empty-state sub-empty">
                  <p>测试点确认后生成测试场景，回答「在什么业务情况下测」。</p>
                  <BaseButton variant="primary" size="sm" @click="triggerStage('scenarios', 'gen')">生成场景</BaseButton>
                </div>
                <div v-else-if="isStageBusy('scenarios') && !scenarioAssets.length" class="empty-state sub-empty">场景生成中…</div>

                <div v-else class="scenario-list">
                  <div v-for="sc in scenarioAssets" :key="sc.id" class="scenario-card">
                    <div class="scenario-head">
                      <span class="scenario-title">{{ sc.title }}</span>
                      <span class="scenario-status">{{ statusLabel(sc.status) }}</span>
                    </div>
                    <p class="scenario-desc">{{ sc.description }}</p>
                    <div class="scenario-confirm">
                      <BaseButton size="sm" variant="ghost" :disabled="!!confirmations(sc).product"
                        @click="confirmAsset(sc, 'product')">
                        {{ confirmations(sc).product ? '产品已确认 ✓' : '产品确认' }}
                      </BaseButton>
                      <BaseButton size="sm" variant="ghost" :disabled="!!confirmations(sc).testing"
                        @click="confirmAsset(sc, 'testing')">
                        {{ confirmations(sc).testing ? '测试已确认 ✓' : '测试确认' }}
                      </BaseButton>
                    </div>
                  </div>
                </div>
                <p v-if="!scenariosConfirmed && scenarioAssets.length" class="stage-hint">提示：需全部场景完成双视角确认后，才可生成测试用例。</p>

                <!-- 场景确认后 → 生成用例（用例 tab 产出后才出现） -->
                <div v-if="scenariosConfirmed" class="next-step">
                  <BaseButton variant="primary" size="sm" @click="triggerStage('cases', 'gen')"
                    :loading="isStageBusy('cases')">生成用例</BaseButton>
                </div>
              </div>
            </div>
          </div>

          <!-- ═══ 测试用例 ═══ -->
          <div v-else class="tab-pane">
            <div class="pane-head">
              <h3 class="pane-title">测试用例清单</h3>
              <div class="pane-head-actions">
                <select class="type-select" v-model="caseTypeFilter">
                  <option v-for="t in caseTypeFilters" :key="t" :value="t">{{ t }}</option>
                </select>
                <BaseButton size="sm" variant="primary" @click="triggerStage('cases', 'gen')"
                  :loading="isStageBusy('cases')" :disabled="!scenariosConfirmed">生成用例</BaseButton>
              </div>
            </div>
            <div class="pane-body case-pane">
              <div v-if="isStageBusy('cases') && !caseAssets.length" class="empty-state">测试用例生成中…</div>
              <template v-else>
                <div class="case-table-wrap">
                  <table class="case-table">
                    <thead>
                      <tr>
                        <th class="w-16">编号</th>
                        <th>用例名称</th>
                        <th class="w-20">Story</th>
                        <th class="w-20">类型</th>
                        <th class="w-24 text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <template v-for="c in filteredCases" :key="c.id">
                        <tr class="case-row" :class="{ open: selectedCase?.id === c.id }" @click="toggleCase(c)">
                          <td><span class="case-no">{{ caseNumber(c) }}</span></td>
                          <td>
                            <div class="case-name">{{ c.title }}</div>
                            <div class="case-sub" v-if="c.story_id">关联 Story: {{ storyMap[c.story_id] || '--' }}</div>
                          </td>
                          <td class="cell-muted">{{ storyMap[c.story_id] || '--' }}</td>
                          <td><BaseTag :tone="typeTone(assetContent(c).test_type || '功能')" size="sm">{{ assetContent(c).test_type || '功能' }}</BaseTag></td>
                          <td class="ops text-right" @click.stop>
                            <BaseButton size="sm" variant="ghost" title="执行" @click="executeCase(c)" :disabled="!caseBindings(c).length">▶</BaseButton>
                            <span class="expand-icon">{{ selectedCase?.id === c.id ? '▲' : '▼' }}</span>
                          </td>
                        </tr>
                        <!-- 展开的用例详情行 -->
                        <tr v-if="selectedCase?.id === c.id" class="case-detail-row">
                          <td colspan="5">
                            <div class="case-detail">
                              <div class="detail-grid">
                                <div class="detail-field" v-if="assetContent(c).preconditions">
                                  <p class="field-label">前置条件</p>
                                  <p class="field-value">{{ assetContent(c).preconditions }}</p>
                                </div>
                                <div class="detail-field" v-if="assetContent(c).test_data">
                                  <p class="field-label">测试数据</p>
                                  <p class="field-value">{{ assetContent(c).test_data }}</p>
                                </div>
                              </div>
                              <div class="detail-field" v-if="assetContent(c).steps?.length">
                                <p class="field-label">操作步骤</p>
                                <ol class="steps-list">
                                  <li v-for="(st, i) in assetContent(c).steps" :key="i">{{ st }}</li>
                                </ol>
                              </div>
                              <div class="detail-field" v-if="assetContent(c).expected">
                                <p class="field-label">预期结果</p>
                                <p class="field-value expected">{{ assetContent(c).expected }}</p>
                              </div>
                              <div class="detail-field" v-if="assetContent(c).score_reason">
                                <p class="field-label">评分依据</p>
                                <p class="field-value">{{ assetContent(c).score_reason }}</p>
                              </div>
                              <div class="binding-block">
                                <div class="binding-head">
                                  <span class="field-label">自动化绑定</span>
                                  <BaseButton size="sm" variant="secondary" @click="openBinding(c)">重新绑定</BaseButton>
                                </div>
                                <div v-if="!caseBindings(c).length" class="binding-empty">尚未绑定自动化用例</div>
                                <div v-else class="binding-list">
                                  <div v-for="b in caseBindings(c)" :key="b.id" class="binding-item">
                                    <span class="mono">{{ b.uid }}</span>
                                    <BaseButton size="sm" variant="ghost" @click="unBind(b)">取消绑定</BaseButton>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      </template>
                    </tbody>
                  </table>
                </div>
                <div v-if="!filteredCases.length" class="empty-state">暂无测试用例</div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="wb-main flex-1 flex items-center justify-center" style="color: var(--text-tertiary);">
      请选择左侧需求
    </div>

    <!-- 导入文档弹窗（本地 / 飞书 / 网页） -->
    <BaseDialog :open="showImport" :title="`导入文档${importReq ? ' - ' + importReq.title : ''}`" :width="560" @close="showImport = false">
      <div class="import-body">
        <!-- 来源选择 -->
        <div class="src-tabs">
          <button :class="{ active: importTab === 'local' }" @click="switchImportTab('local')">本地导入</button>
          <button :class="{ active: importTab === 'feishu' }" @click="switchImportTab('feishu')">飞书文档</button>
          <button :class="{ active: importTab === 'web' }" @click="switchImportTab('web')">网页获取</button>
        </div>

        <!-- 本地导入：拖入 pdf/doc/docx -->
        <div v-if="importTab === 'local'" class="import-pane">
          <div class="drop-zone" :class="{ 'drop-zone--over': localDrag }"
            @dragover.prevent="localDrag = true" @dragleave.prevent="localDrag = false"
            @drop.prevent="onLocalDrop">
            <p class="drop-title">拖入文档到此处</p>
            <p class="drop-hint">支持 pdf / doc / docx</p>
            <BaseButton size="sm" variant="secondary" @click="localFileInput?.click()">选择文件</BaseButton>
            <input ref="localFileInput" type="file" hidden accept=".pdf,.doc,.docx,.txt,.md,.json" @change="onLocalDrop" />
          </div>
          <div v-if="localFile" class="local-file">已选择：{{ localFile.name }}</div>
        </div>

        <!-- 飞书文档：显示授权状态 -->
        <div v-if="importTab === 'feishu'" class="import-pane">
          <div class="feishu-status-row">
            <span v-if="feishuStatusLoaded" class="feishu-status-tag" :class="`status-${feishuStatusInfo.tone}`">
              {{ feishuStatusInfo.label }}
            </span>
            <span v-if="feishuStatus.bound" class="feishu-open-id">{{ feishuStatus.lark_open_id }}</span>
            <span v-else-if="!feishuStatusLoaded" class="feishu-open-id">查询中…</span>
          </div>
          <div v-if="feishuUnauthorized" class="feishu-auth-box">
            <p>尚未授权飞书，无法读取飞书文档。</p>
            <BaseButton size="sm" variant="primary" @click="startFeishuAuth" :loading="feishuAuthing">去授权</BaseButton>
          </div>
          <template v-else>
            <label class="modal-label">飞书文档链接</label>
            <BaseInput v-model="feishuLink" placeholder="https://xxx.feishu.cn/wiki/...（导入后自动提取正文）" @enter="importFeishu" />
          </template>
        </div>

        <!-- 网页获取 -->
        <div v-if="importTab === 'web'" class="import-pane">
          <label class="modal-label">网页地址</label>
          <BaseInput v-model="webUrl" placeholder="https://example.com/doc" @enter="importWeb" />
          <p class="drop-hint">抓取网页正文并作为需求文档。</p>
        </div>

        <div class="import-actions">
          <BaseButton variant="ghost" @click="showImport = false">取消</BaseButton>
          <BaseButton v-if="importTab === 'local'" variant="primary" :loading="localUploading" :disabled="!localFile"
            @click="importLocal">导入</BaseButton>
          <BaseButton v-else-if="importTab === 'feishu' && !feishuUnauthorized" variant="primary"
            :loading="feishuImporting" :disabled="!feishuLink.trim()" @click="importFeishu">导入</BaseButton>
          <BaseButton v-else-if="importTab === 'web'" variant="primary"
            :loading="webImporting" :disabled="!webUrl.trim()" @click="importWeb">获取内容</BaseButton>
        </div>
      </div>
    </BaseDialog>

    <!-- 删除需求确认 -->
    <BaseDialog :open="!!deleteTarget" title="删除需求" :width="420" @close="deleteTarget = null">
      <p class="delete-hint">确定删除需求「{{ deleteTarget?.title }}」吗？该操作不可撤销，相关 Story / 测试点 / 测试用例将一并删除。</p>
      <template #footer>
        <BaseButton variant="ghost" @click="deleteTarget = null">取消</BaseButton>
        <BaseButton variant="danger" :loading="deleting" @click="doDelete">删除</BaseButton>
      </template>
    </BaseDialog>

    <!-- 重新上传 / 添加来源弹窗 -->
    <BaseDialog :open="showReupload" title="重新上传 / 添加来源" :width="520" @close="showReupload = false">
      <div class="bind-body">
        <label class="modal-label">上传文件</label>
        <div class="file-row">
          <input ref="fileInputRef" type="file" hidden @change="onReuploadFile" />
          <BaseButton variant="secondary" size="sm" @click="fileInputRef?.click()">选择文件</BaseButton>
          <span class="file-hint">{{ reuploadFile?.name || '支持 txt / md / json / csv（上传后自动加载为文档）' }}</span>
        </div>
        <label class="modal-label">或粘贴飞书文档链接</label>
        <BaseInput v-model="reuploadLink" placeholder="https://xxx.feishu.cn/wiki/..." @enter="submitReupload" />
      </div>
      <template #footer>
        <BaseButton variant="ghost" @click="showReupload = false">取消</BaseButton>
        <BaseButton variant="primary" :loading="reuploading" @click="submitReupload">上传并加载</BaseButton>
      </template>
    </BaseDialog>

    <!-- 绑定自动化用例弹窗 -->
    <BaseDialog :open="bindingOpen" title="绑定自动化用例" :width="620" @close="bindingOpen = false">
      <div class="bind-body">
        <p class="bind-for" v-if="bindingCase">为「{{ bindingCase.title }}」绑定自动化用例：</p>
        <BaseInput v-model="bindSearch" placeholder="搜索用例名称 / uid" class="w-full text-sm" />
        <div class="bind-list">
          <div v-if="bindingLoading" class="empty-state">加载中…</div>
          <div v-else-if="!filteredAutoCases.length" class="empty-state">暂无自动化用例（请先在「自动化」页导入项目测试用例）</div>
          <div v-else v-for="c in filteredAutoCases" :key="c.uid" class="bind-item" @click="doBind(c)">
            <div class="bind-item-main">
              <span class="bind-item-name">{{ c.name }}</span>
              <span class="bind-item-uid mono">{{ c.uid }}</span>
            </div>
            <div class="bind-item-meta">
              <BaseTag size="sm" :tone="typeTone(c.testType || 'api')" >{{ c.testType || 'api' }}</BaseTag>
              <span class="bind-item-module">{{ c.module }}</span>
            </div>
          </div>
        </div>
      </div>
    </BaseDialog>
  </div>
</template>

<style scoped>
.workbench { overflow: hidden; }

/* ── 左侧需求列表 ── */
.req-sidebar { width: 264px; min-width: 220px; border-right: 1px solid var(--border); display: flex; flex-direction: column; background: var(--bg-card); }
.sidebar-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border); }
.sidebar-title { margin: 0; font-size: 15px; font-weight: 600; }
.req-list { flex: 1; overflow-y: auto; padding: 10px 8px; }
.req-sidebar { position: relative; z-index: 30; } /* 需求卡片的操作菜单需要高于右侧详情页 */

/* 需求卡片：名称 / 状态(第二排右对齐) / 创建时间 / hover 右上角 ⋮ 操作菜单 */
.req-card { position: relative; padding: 10px 12px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; transition: background-color .12s ease, border-color .12s ease; margin-bottom: 4px; }
.req-card:hover { background: var(--bg-soft); border-color: var(--border); }
.req-card.active { background: var(--color-primary-soft); border-color: var(--color-primary); }
.req-card--draft { border-color: var(--color-primary); background: var(--color-primary-soft); }
.req-card-title-row { display: flex; align-items: center; gap: 6px; min-width: 0; }
.req-card-title { font-size: 13px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.req-more { flex-shrink: 0; width: 22px; height: 22px; border-radius: 6px; background: none; border: none; color: var(--text-secondary); font-size: 16px; line-height: 1; display: flex; align-items: center; justify-content: center; opacity: 0; cursor: pointer; transition: opacity .12s ease, background-color .12s ease; }
.req-card:hover .req-more { opacity: 1; }
.req-more:hover { background: var(--bg-muted); color: var(--text-primary); }
.req-card-meta { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-top: 6px; }
.req-card-time { font-size: 11px; color: var(--text-tertiary); }
.req-status { flex-shrink: 0; padding: 1px 8px; font-size: 10px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-secondary); background: var(--bg-card); }

/* 操作菜单：顶部对齐需求卡片；超出页面底部则底部对齐（向上弹出）；z-index 高于右侧详情 */
.req-menu { position: absolute; top: calc(100% + 2px); right: 8px; min-width: 132px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.14); padding: 4px; z-index: 100; }
.req-menu--bottom { top: auto; bottom: calc(100% + 2px); }
.menu-item { display: block; width: 100%; text-align: left; padding: 7px 10px; font-size: 12.5px; border: none; border-radius: 6px; color: var(--text-primary); background: none; cursor: pointer; }
.menu-item:hover { background: var(--bg-soft); }
.menu-item--danger { color: var(--color-danger); }
.menu-item--danger:hover { background: rgba(220,38,38,.08); }

/* 草稿 / 编辑标题 */
.draft-input { width: 100%; padding: 6px 8px; font-size: 13px; border: 1px solid var(--color-primary); border-radius: 6px; background: var(--bg-card); color: var(--text-primary); outline: none; }
.draft-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 8px; }

/* ── 导入文档弹窗 ── */
.import-body { padding: 16px 20px 8px; display: flex; flex-direction: column; gap: 12px; }
.import-pane { display: flex; flex-direction: column; gap: 10px; }
.drop-zone { border: 2px dashed var(--border); border-radius: 8px; padding: 28px 16px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px; background: var(--bg-soft); transition: border-color .12s ease, background-color .12s ease; }
.drop-zone--over { border-color: var(--color-primary); background: var(--color-primary-soft); }
.drop-title { font-size: 13px; color: var(--text-primary); margin: 0; }
.drop-hint { font-size: 11px; color: var(--text-tertiary); margin: 0; }
.local-file { font-size: 12px; color: var(--color-success); }
.feishu-status-row { display: flex; align-items: center; gap: 8px; }
.feishu-status-tag { font-size: 11px; padding: 2px 10px; border-radius: 999px; font-weight: 600; }
.status-green { background: rgba(16,185,129,.12); color: var(--color-success); }
.status-yellow { background: rgba(245,158,11,.12); color: var(--color-warning); }
.status-red { background: rgba(220,38,38,.12); color: var(--color-danger); }
.feishu-open-id { font-size: 11px; color: var(--text-tertiary); }
.feishu-auth-box { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
.feishu-auth-box p { margin: 0 0 10px; font-size: 12.5px; color: var(--text-secondary); }
.import-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.delete-hint { font-size: 13px; color: var(--text-primary); margin: 0; }

.empty-state { display: flex; flex-direction: column; gap: 12px; align-items: center; justify-content: center; padding: 40px; color: var(--text-tertiary); }

/* ── 右侧区域 ── */
.wb-main { min-width: 0; }

/* 右侧：列表接口加载中 → 动态骨架屏 */
.wb-loading { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.skeleton-tabs { display: flex; gap: 24px; padding: 14px 16px; border-bottom: 1px solid var(--border); }
.sk { position: relative; overflow: hidden; background: var(--bg-soft); border-radius: 6px; }
.sk::after { content: ''; position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255,255,255,.55), transparent); animation: sk-shimmer 1.4s infinite; }
@keyframes sk-shimmer { 100% { transform: translateX(100%); } }
.sk-tab { height: 18px; }
.sk-head { height: 32px; }
.sk-line { height: 12px; }
.skeleton-panel { border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.sk-doc { width: 60%; }
.sk-stage { flex: 1; }

/* 右侧：空列表提示 */
.empty-tip { display: flex; flex-direction: column; align-items: center; gap: 10px; color: var(--text-tertiary); }
.empty-tip p { margin: 0; font-size: 14px; }
.empty-icon { font-size: 34px; }

.stage-tabs { display: flex; gap: 24px; padding: 0 16px; border-bottom: 1px solid var(--border); flex-shrink: 0; background: var(--bg-card); }
.stage-tab { padding: 13px 2px; font-size: 14px; font-weight: 500; color: var(--text-secondary); border-bottom: 2px solid transparent; transition: color .15s ease, border-color .15s ease; background: none; }
.stage-tab:hover { color: var(--color-primary); }
.stage-tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }

/* ── 60% 文档 + 40% 阶段 分栏 ── */
.wb-split { flex: 1; display: flex; gap: 16px; padding: 16px; min-height: 0; }

/* 需求文档（左 60%） */
.doc-panel { width: 60%; min-width: 0; display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); overflow: hidden; }
.panel-head { display: flex; justify-content: space-between; align-items: center; padding: 3px 16px; border-bottom: 1px solid var(--border); background: var(--bg-soft); flex-shrink: 0; }
.panel-title { margin: 0; font-size: 14px; font-weight: 600; }
.doc-tools { display: flex; gap: 6px; align-items: center; }
.btn-save { background: var(--color-success); border-color: var(--color-success); color: #fff; }
.btn-save:hover { background: var(--color-success); opacity: .9; }
.doc-render { flex: 1; overflow-y: auto; padding: 16px; font-size: 13px; line-height: 1.7; color: var(--text-primary); }
.doc-render img { max-width: 100%; border-radius: 8px; margin: 6px 0; }
.doc-render h1, .doc-render h2, .doc-render h3 { margin: 10px 0 6px; }
.doc-render table { border-collapse: collapse; width: 100%; font-size: 12px; margin: 8px 0; }
.doc-render th, .doc-render td { border: 1px solid var(--border); padding: 4px 8px; }
.doc-render th { background: var(--bg-soft); }
.doc-render pre { background: var(--bg-soft); padding: 10px; border-radius: 8px; overflow-x: auto; }
.doc-editor { flex: 1; resize: none; padding: 16px; border: none; background: var(--bg-card); color: var(--text-primary); font-size: 13px; line-height: 1.7; outline: none; }
.doc-empty { flex: 1; display: flex; flex-direction: column; gap: 10px; align-items: center; justify-content: center; color: var(--text-tertiary); text-align: center; padding: 20px; }
.doc-empty-actions { display: flex; gap: 8px; align-items: center; }
.doc-link { font-size: 12px; word-break: break-all; max-width: 90%; color: var(--text-secondary); }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 阶段面板（右 40%） */
.stage-panel { width: 40%; min-width: 0; display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); overflow: hidden; }
.tab-pane { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.pane-head { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--border); background: var(--bg-soft); flex-shrink: 0; gap: 8px; flex-wrap: wrap; }
.pane-title { margin: 0; font-size: 14px; font-weight: 600; }
.pane-head-actions { display: flex; align-items: center; gap: 8px; }
.type-select { border: 1px solid var(--border); background: var(--bg-card); border-radius: 6px; padding: 3px 8px; font-size: 12px; color: var(--text-primary); }
.pane-body { flex: 1; overflow-y: auto; padding: 14px 16px; min-height: 0; }
.pane-actions { display: flex; gap: 10px; padding: 12px 16px; border-top: 1px solid var(--border); flex-shrink: 0; }

/* ── 评审 ── */
.analysis-card { padding: 12px; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 14px; }
.analysis-head { display: flex; align-items: center; gap: 6px; color: var(--color-primary); font-weight: 600; margin-bottom: 6px; }
.analysis-head h4 { margin: 0; font-size: 13px; }
.ai-icon { font-size: 12px; }
.analysis-text { font-size: 12.5px; color: var(--text-secondary); line-height: 1.6; margin: 0; }
.analysis-elems { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.elem-chip { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--bg-card); color: var(--text-secondary); border: 1px solid var(--border); }
.pane-section { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: var(--text-tertiary); margin: 12px 0 8px; }
.gap-card { border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); margin-bottom: 10px; overflow: hidden; }
.gap-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--bg-soft); gap: 8px; }
.gap-status { font-size: 11px; padding: 1px 8px; border-radius: 999px; background: var(--bg-card); color: var(--text-secondary); border: 1px solid var(--border); }
.gap-status--confirmed { background: var(--color-success-soft, rgba(16,185,129,.12)); color: var(--color-success); }
.gap-status--pending { background: var(--color-warning-soft, rgba(245,158,11,.12)); color: var(--color-warning); }
.gap-head-actions { display: flex; gap: 4px; }
.gap-body { padding: 12px; }
.gap-type { font-size: 13px; font-weight: 600; margin: 0 0 4px; }
.gap-desc { font-size: 12.5px; color: var(--text-secondary); margin: 0 0 6px; }
.gap-question { font-size: 12px; color: var(--color-warning); margin: 0 0 6px; }
.ai-bubble { display: flex; gap: 8px; margin: 6px 0; align-items: flex-start; }
.ai-avatar { width: 22px; height: 22px; border-radius: 50%; background: var(--color-primary-soft); color: var(--color-primary); font-size: 10px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ai-bubble--user .ai-avatar { background: var(--bg-soft); color: var(--text-secondary); }
.ai-text { font-size: 12px; color: var(--text-secondary); background: var(--bg-soft); padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border); line-height: 1.5; }
.comment-box { margin-top: 8px; }
.comment-actions { display: flex; gap: 6px; justify-content: flex-end; margin-top: 6px; }

/* ── Story ── */
.story-card { border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 10px; background: var(--bg-card); }
.story-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 10px; }
.story-id-row { display: flex; align-items: center; gap: 10px; min-width: 0; }
.story-id { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.score-circle { width: 32px; height: 32px; border-radius: 50%; border: 2px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.score-green { border-color: var(--color-success); color: var(--color-success); }
.score-yellow { border-color: var(--color-warning); color: var(--color-warning); }
.score-red { border-color: var(--color-danger); color: var(--color-danger); }
.story-head-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.story-status { font-size: 11px; color: var(--text-secondary); }
.story-body { display: flex; flex-direction: column; gap: 10px; }
.story-block h4 { font-size: 11px; font-weight: 600; color: var(--text-tertiary); margin: 0 0 4px; }
.story-block p { font-size: 13px; color: var(--text-primary); margin: 0; white-space: pre-wrap; }
.criteria-list { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 3px; }
.criteria-list li { font-size: 13px; color: var(--text-primary); }
.story-actions { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }

/* ── 测试点 ── */
.tp-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; background: var(--bg-card); }
.tp-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.tp-title-col { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.tp-name { font-size: 13px; font-weight: 600; }
.tp-meta { font-size: 11px; color: var(--text-secondary); }
.tp-head-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.tp-category { font-size: 10px; padding: 1px 8px; border-radius: 999px; background: var(--bg-soft); color: var(--text-secondary); }
.tp-status { font-size: 11px; color: var(--text-secondary); }
.tp-desc { font-size: 12.5px; color: var(--text-secondary); margin: 6px 0 0; }
.tp-confirm { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }

/* ── 场景子块 ── */
.sub-block { margin-top: 16px; border-top: 1px dashed var(--border); padding-top: 12px; }
.sub-block-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-bottom: 8px; }
.sub-block-title { font-size: 13px; font-weight: 600; }
.sub-block-actions { display: flex; gap: 6px; }
.sub-empty { padding: 24px; }
.scenario-list { display: flex; flex-direction: column; gap: 8px; }
.scenario-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; background: var(--bg-card); }
.scenario-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.scenario-title { font-size: 13px; font-weight: 600; }
.scenario-status { font-size: 11px; color: var(--text-secondary); }
.scenario-desc { font-size: 12.5px; color: var(--text-secondary); margin: 6px 0 0; }
.scenario-confirm { display: flex; gap: 6px; margin-top: 8px; }
.next-step { display: flex; justify-content: flex-end; padding: 12px 2px 2px; }
.stage-hint { font-size: 12px; color: var(--text-tertiary); margin: 8px 0 0; }

/* ── 用例表格 ── */
.case-pane { padding: 0; }
.case-table-wrap { overflow-x: auto; }
.case-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.case-table thead th { text-align: left; font-size: 11px; color: var(--text-tertiary); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--bg-soft); position: sticky; top: 0; }
.case-row td { padding: 10px 12px; border-bottom: 1px solid var(--border); cursor: pointer; vertical-align: middle; }
.case-row:hover td { background: var(--bg-soft); }
.case-row.open td { background: var(--color-primary-soft); }
.case-no { font-size: 10px; padding: 2px 6px; border-radius: 6px; background: var(--bg-soft); color: var(--text-secondary); font-weight: 600; }
.case-name { font-weight: 500; color: var(--text-primary); }
.case-sub { font-size: 10px; color: var(--text-secondary); }
.cell-muted { color: var(--text-secondary); }
.ops { white-space: nowrap; }
.expand-icon { font-size: 10px; color: var(--text-tertiary); }
.case-detail-row td { padding: 0; border-bottom: 1px solid var(--border); background: var(--bg-soft); }
.case-detail { display: flex; flex-direction: column; gap: 12px; padding: 14px 16px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.detail-field { display: flex; flex-direction: column; gap: 4px; }
.field-label { font-size: 11px; font-weight: 600; color: var(--text-tertiary); margin: 0; }
.field-value { font-size: 12.5px; color: var(--text-primary); background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; margin: 0; white-space: pre-wrap; }
.steps-list { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 4px; }
.steps-list li { font-size: 12.5px; color: var(--text-primary); }
.expected { color: var(--color-success) !important; }
.binding-block { border-top: 1px dashed var(--border); padding-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.binding-head { display: flex; align-items: center; justify-content: space-between; }
.binding-empty { font-size: 12px; color: var(--text-tertiary); }
.binding-list { display: flex; flex-direction: column; gap: 6px; }
.binding-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; }
.mono { font-family: var(--font-mono); font-size: 12px; }

/* ── 弹窗 ── */
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-box { width: 480px; max-width: 90%; background: var(--bg-card); border-radius: var(--radius-md); padding: 18px; display: flex; flex-direction: column; gap: 8px; box-shadow: var(--shadow-hard); }
.modal-label { font-size: 12px; color: var(--text-secondary); margin-top: 6px; }
.modal-content { min-height: 120px; border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
.src-tabs { display: flex; gap: 6px; }
.src-tabs button { padding: 4px 12px; border-radius: 999px; font-size: 12px; background: var(--bg-soft); color: var(--text-secondary); }
.src-tabs button.active { background: var(--color-primary); color: #fff; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.bind-body { padding: 16px 20px 8px; display: flex; flex-direction: column; gap: 12px; }
.bind-for { font-size: 12px; color: var(--text-secondary); margin: 0; }
.bind-list { max-height: 360px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.bind-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); cursor: pointer; }
.bind-item:hover { background: var(--bg-soft); }
.bind-item-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.bind-item-name { font-size: 12.5px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bind-item-uid { font-size: 11px; color: var(--text-tertiary); }
.bind-item-meta { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.bind-item-module { font-size: 11px; color: var(--text-tertiary); max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-row { display: flex; align-items: center; gap: 10px; }
.file-hint { font-size: 12px; color: var(--text-tertiary); }

/* ── 16:9 响应式：窄屏时纵向堆叠 ── */
@media (max-width: 1100px) {
  .workbench { flex-direction: column; }
  .req-sidebar { width: 100%; min-width: 0; height: auto; max-height: 200px; border-right: none; border-bottom: 1px solid var(--border); }
  .wb-main { min-width: 0; }
  .wb-split { flex-direction: column; }
  .doc-panel { width: 100%; height: 300px; }
  .stage-panel { width: 100%; flex: 1; min-height: 0; }
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
