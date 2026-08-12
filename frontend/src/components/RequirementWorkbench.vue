<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
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
const { get, post, del } = useApi();
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

const assetCounts = computed(() => workbenchData.value?.requirement?.asset_counts || {});

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
    const data = await get<{ items: RequirementInfo[] }>(`/requirements?project_id=${projectId.value}&branch_id=${branchId.value}`);
    requirements.value = data.items || [];
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
</script>

<template>
  <div class="workbench flex h-full min-h-0">
    <!-- Left: Requirement List -->
    <aside class="req-sidebar">
      <div class="sidebar-header">
        <h3 class="sidebar-title">需求列表</h3>
        <BaseButton size="sm" @click="showNewReqModal = true">+ 新建</BaseButton>
      </div>

      <!-- Search -->
      <div class="px-3 pb-2">
        <BaseInput v-model="searchQuery" placeholder="搜索需求..." class="w-full text-sm" />
      </div>

      <!-- Status filter -->
      <div class="filter-bar">
        <button v-for="t in statusFilterTabs" :key="t.key"
          class="filter-chip" :class="{ active: statusFilter === t.key }"
          @click="statusFilter = t.key">
          {{ t.label }}
        </button>
      </div>

      <!-- List -->
      <div class="req-list" v-if="!loading">
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
          <div class="overview-grid">
            <div class="ov-card">
              <h4>{{ workbenchData.requirement.title }}</h4>
              <div class="ov-meta">
                <span>优先级: {{ workbenchData.requirement.priority }}</span>
                <span>来源: {{ workbenchData.requirement.source_type === 'lark_link' ? '飞书' : workbenchData.requirement.source_type === 'file' ? '文件' : '文本' }}</span>
                <span>状态: <BaseTag :tone="STATUS_META[workbenchData.requirement.status]?.tone || 'gray'" size="sm">{{ STATUS_META[workbenchData.requirement.status]?.label || workbenchData.requirement.status }}</BaseTag></span>
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
          </div>
        </div>

        <!-- Assets Tab -->
        <div v-if="activeTab === 'assets'" class="tab-content">
          <div class="assets-view">
            <p class="text-sm" style="color:var(--text-secondary);">分层测试资产 · {{ workbenchData.assets?.length || 0 }} 条</p>
            <div v-if="!workbenchData.assets?.length" class="empty-state">暂无资产，请先触发 AI 分析</div>
            <div v-for="a in workbenchData.assets" :key="a.id" class="asset-row">
              <BaseTag :tone="a.asset_type === 'story' ? 'blue' : a.asset_type === 'test_point' ? 'purple' : a.asset_type === 'case' ? 'green' : 'yellow'" size="sm">{{ a.asset_type }}</BaseTag>
              <span class="flex-1 mx-2">{{ a.title }}</span>
              <span v-if="a.score" class="text-xs">{{ a.score }}分</span>
              <BaseTag v-if="a.gate_status" :tone="a.gate_status === 'PASS' ? 'green' : a.gate_status === 'WARNING' ? 'yellow' : 'red'" size="sm">{{ a.gate_status }}</BaseTag>
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
        <p>← 从左侧列表选择一个需求</p>
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
.ov-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; flex-wrap: wrap; }
.ov-content { font-size: 12px; color: var(--text-secondary); line-height: 1.5; white-space: pre-wrap; }
.progress-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; }
.exec-stats { display: flex; gap: 12px; font-size: 18px; font-weight: 700; }
.exec-stats .pass { color: #22c55e; }
.exec-stats .fail { color: #ef4444; }

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
</style>
