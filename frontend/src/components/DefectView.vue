<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useDefect } from '../composables/useDefect';
import { useAuth } from '../composables/useAuth';
import DefectList from './DefectList.vue';
import DefectCreateDialog from './DefectCreateDialog.vue';
import DefectDetailDialog from './DefectDetailDialog.vue';
import DefectModuleDialog from './DefectModuleDialog.vue';
import DefectConfirmDialog from './DefectConfirmDialog.vue';
import DefectResolveDialog from './DefectResolveDialog.vue';
import DefectCloseDialog from './DefectCloseDialog.vue';
import type { DefectInfo, DefectModuleInfo } from '../types';

const props = defineProps<{
  globalSearch: string;
}>();

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
}>();

const { activeProject, getActiveProject } = useProject();
const { branches, activeBranch, loadBranches } = useBranch(activeProject.value?.id);
const { currentUser } = useAuth();

const projectId = computed(() => activeProject.value?.id || 0);
const branchId = computed(() => activeBranch.value?.id || 0);
const currentUserId = computed(() => currentUser.value?.id || 0);

const defectApi = useDefect(projectId.value);

const defects = ref<DefectInfo[]>([]);
const total = ref(0);
const loading = ref(false);
const modules = ref<DefectModuleInfo[]>([]);
const currentPage = ref(1);
const pageSize = ref(20);

const filterStatus = ref('');
const filterSeverity = ref('');
const filterPriority = ref('');
const filterModuleId = ref<number | null>(null);
const filterAssigneeId = ref<number | null>(null);
const filterCreatorId = ref<number | null>(null);
const filterSearch = ref('');

const showCreateDialog = ref(false);
const showModuleDialog = ref(false);
const showDetailDialog = ref(false);
const showConfirmDialog = ref(false);
const showResolveDialog = ref(false);
const showCloseDialog = ref(false);
const selectedDefectId = ref<number | null>(null);
const selectedDefect = ref<DefectInfo | null>(null);

async function loadDefects() {
  if (!projectId.value || !branchId.value) return;
  loading.value = true;
  try {
    const [defectResult, moduleResult] = await Promise.all([
      defectApi.getDefects({
        project_id: projectId.value,
        branch_id: branchId.value,
        status: filterStatus.value || undefined,
        severity: filterSeverity.value || undefined,
        priority: filterPriority.value || undefined,
        module_id: filterModuleId.value || undefined,
        assignee_id: filterAssigneeId.value || undefined,
        creator_id: filterCreatorId.value || undefined,
        search: filterSearch.value || undefined,
        page: currentPage.value,
        page_size: pageSize.value,
      }),
      defectApi.getModules(projectId.value),
    ]);
    defects.value = defectResult.items;
    total.value = defectResult.total;
    modules.value = moduleResult;
  } catch (e: any) {
    emit('showToast', e.message || '加载缺陷列表失败');
    defects.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function handleFilterChange(filters: { 
  status: string; 
  severity: string; 
  priority: string; 
  moduleId: number | null; 
  assigneeId: number | null; 
  creatorId: number | null; 
  search: string;
}) {
  filterStatus.value = filters.status;
  filterSeverity.value = filters.severity;
  filterPriority.value = filters.priority;
  filterModuleId.value = filters.moduleId;
  filterAssigneeId.value = filters.assigneeId;
  filterCreatorId.value = filters.creatorId;
  filterSearch.value = filters.search;
  currentPage.value = 1;
  loadDefects();
}

function handlePageChange(page: number) {
  currentPage.value = page;
  loadDefects();
}

function handleSelectDefect(defect: DefectInfo) {
  selectedDefectId.value = defect.id;
  showDetailDialog.value = true;
}

function handleCreated() {
  loadDefects();
}

function handleUpdated() {
  loadDefects();
}

function handleListAction(action: string, defect: DefectInfo) {
  selectedDefect.value = defect;
  selectedDefectId.value = defect.id;

  if (action === 'confirm') {
    showConfirmDialog.value = true;
  } else if (action === 'resolve') {
    showResolveDialog.value = true;
  } else if (action === 'close') {
    showCloseDialog.value = true;
  } else if (action === 'edit') {
    showDetailDialog.value = true;
  } else if (action === 'copy') {
    handleCopyDefect(defect);
  }
}

async function handleCopyDefect(defect: DefectInfo) {
  try {
    const result = await defectApi.copyDefect(defect.id);
    emit('showToast', '缺陷复制成功');
    await loadDefects();
  } catch (e: any) {
    emit('showToast', e.message || '复制缺陷失败');
  }
}

async function initPage() {
  try {
    await getActiveProject();
    if (projectId.value) {
      await loadBranches(projectId.value);
    }
    await loadDefects();
  } catch {
    // ignore
  }
}

watch(projectId, async () => {
  if (projectId.value) {
    await loadBranches(projectId.value);
    currentPage.value = 1;
    await loadDefects();
  }
});

watch(branchId, async () => {
  if (branchId.value) {
    currentPage.value = 1;
    await loadDefects();
  }
});

onMounted(() => {
  initPage();
});
</script>

<template>
  <div class="defect-view" style="background-color: var(--content-bg);">
    <!-- No active project -->
    <div v-if="!activeProject" class="no-project">
      <div class="no-project-inner">
        <svg class="no-project-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <p class="no-project-text">请先选择活跃项目</p>
        <p class="no-project-hint">在项目管理页面选择并激活一个项目</p>
      </div>
    </div>

    <template v-else>
      <!-- Panel header -->
      <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0" style="border-bottom: 1px solid var(--border);">
        <h2 class="text-[15px] font-semibold tracking-[-0.01em]" style="color: var(--text-primary);">缺陷管理</h2>
        <div class="flex gap-[8px]">
          <button
            @click="showModuleDialog = true"
            class="flex items-center gap-[4px] px-[12px] py-[6px] text-[12px] font-semibold rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.97]"
            style="background-color: var(--card-bg); color: var(--text-secondary); border: 1px solid var(--border);"
            @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = 'var(--accent)'; ($event.currentTarget as HTMLElement).style.color = 'var(--accent)'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; ($event.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            模块管理
          </button>
          <button
            @click="showCreateDialog = true"
            class="flex items-center gap-[4px] px-[12px] py-[6px] text-[12px] font-semibold rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.97]"
            style="background-color: var(--accent); color: #fff;"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            创建缺陷
          </button>
        </div>
      </div>

      <!-- Defect list -->
      <div class="list-area">
        <DefectList
          :defects="defects"
          :total="total"
          :loading="loading"
          :currentPage="currentPage"
          :pageSize="pageSize"
          :modules="modules"
          :currentUserId="currentUserId"
          @select="handleSelectDefect"
          @pageChange="handlePageChange"
          @filterChange="handleFilterChange"
          @confirm="(d: DefectInfo) => handleListAction('confirm', d)"
          @resolve="(d: DefectInfo) => handleListAction('resolve', d)"
          @close="(d: DefectInfo) => handleListAction('close', d)"
          @edit="(d: DefectInfo) => handleListAction('edit', d)"
          @copy="(d: DefectInfo) => handleListAction('copy', d)"
        />
      </div>
    </template>

    <!-- Create dialog -->
    <DefectCreateDialog
      :isOpen="showCreateDialog"
      :projectId="projectId"
      :branchId="branchId"
      @close="showCreateDialog = false"
      @created="handleCreated"
      @showToast="(msg: string) => emit('showToast', msg)"
    />

    <!-- Detail dialog -->
    <DefectDetailDialog
      :isOpen="showDetailDialog"
      :defectId="selectedDefectId"
      :projectId="projectId"
      @close="showDetailDialog = false"
      @updated="handleUpdated"
      @showToast="(msg: string) => emit('showToast', msg)"
    />

    <!-- Module dialog -->
    <DefectModuleDialog
      :isOpen="showModuleDialog"
      :projectId="projectId"
      @close="showModuleDialog = false"
      @showToast="(msg: string) => emit('showToast', msg)"
    />

    <!-- Confirm dialog -->
    <DefectConfirmDialog
      :isOpen="showConfirmDialog"
      :defect="selectedDefect"
      :projectId="projectId"
      @close="showConfirmDialog = false"
      @done="handleUpdated"
      @showToast="(msg: string) => emit('showToast', msg)"
    />

    <!-- Resolve dialog -->
    <DefectResolveDialog
      :isOpen="showResolveDialog"
      :defect="selectedDefect"
      :projectId="projectId"
      @close="showResolveDialog = false"
      @done="handleUpdated"
      @showToast="(msg: string) => emit('showToast', msg)"
    />

    <!-- Close dialog -->
    <DefectCloseDialog
      :isOpen="showCloseDialog"
      :defect="selectedDefect"
      :projectId="projectId"
      @close="showCloseDialog = false"
      @done="handleUpdated"
      @showToast="(msg: string) => emit('showToast', msg)"
    />
  </div>
</template>

<style scoped>
.defect-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* No project */
.no-project {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.no-project-inner {
  text-align: center;
}

.no-project-icon {
  opacity: 0.3;
  margin-bottom: 12px;
  color: var(--text-tertiary);
}

.no-project-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin: 0 0 6px;
}

.no-project-hint {
  font-size: 11px;
  margin: 0;
  color: var(--text-tertiary);
}

/* List area */
.list-area {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>