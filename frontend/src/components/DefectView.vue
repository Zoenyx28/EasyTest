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

// Module tree state
const selectedModuleId = ref<number | null>(null);
const expandedModules = ref<Set<number>>(new Set());
const moduleSearchQuery = ref('');

function flattenModuleTree(mods: DefectModuleInfo[]): DefectModuleInfo[] {
  const result: DefectModuleInfo[] = [];
  for (const m of mods) {
    result.push(m);
    if (m.children && m.children.length > 0) {
      result.push(...flattenModuleTree(m.children));
    }
  }
  return result;
}

const filteredModules = computed(() => {
  if (!moduleSearchQuery.value) return modules.value;
  const q = moduleSearchQuery.value.toLowerCase();
  return flattenModuleTree(modules.value).filter(m => m.name.toLowerCase().includes(q));
});

function toggleModuleExpand(id: number) {
  if (expandedModules.value.has(id)) {
    expandedModules.value.delete(id);
  } else {
    expandedModules.value.add(id);
  }
  expandedModules.value = new Set(expandedModules.value);
}

function selectModule(id: number | null) {
  selectedModuleId.value = id;
  filterModuleId.value = id;
  currentPage.value = 1;
  loadDefects();
}

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

// Reload when module dialog closes (modules may have changed)
watch(showModuleDialog, async (open) => {
  if (!open) await loadDefects();
});

onMounted(() => {
  initPage();
});
</script>

<template>
  <div class="flex-1 flex min-h-0 w-full overflow-hidden">
    <!-- No active project -->
    <div v-if="!activeProject" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <svg class="opacity-30 mb-3" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-tertiary);">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <p class="text-[13px] font-medium" style="color: var(--text-secondary); margin: 0 0 6px;">请先选择活跃项目</p>
        <p class="text-[11px]" style="color: var(--text-tertiary); margin: 0;">在项目管理页面选择并激活一个项目</p>
      </div>
    </div>

    <template v-else>
      <!-- Left Sidebar: Module Tree -->
      <aside
        class="w-[240px] min-w-[240px] flex flex-col shrink-0 min-h-0 glass"
        style="background-color: var(--sidebar-bg); border-right: 0.5px solid var(--sidebar-border);"
      >
        <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0">
          <h3 class="text-[15px] font-semibold tracking-[-0.01em]" style="color: var(--text-primary);">缺陷模块</h3>
        </div>

        <!-- Search -->
        <div class="px-[12px] pb-[8px] shrink-0">
          <div class="flex items-center gap-[6px] px-[10px] py-[6px] rounded-[8px]" style="background-color: var(--input-bg); border: 1px solid var(--border);">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-tertiary);">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              v-model="moduleSearchQuery"
              type="text"
              placeholder="搜索模块..."
              class="flex-1 bg-transparent text-[12px] outline-none"
              style="color: var(--text-primary);"
            />
          </div>
        </div>

        <!-- Module tree -->
        <div class="flex-1 overflow-y-auto px-[8px] pb-[8px]">
          <!-- All defects -->
          <div
            @click="selectModule(null)"
            class="flex items-center gap-[8px] px-[10px] py-[7px] rounded-[8px] cursor-pointer text-[13px] transition-colors"
            :style="!selectedModuleId ? { backgroundColor: 'var(--selected-bg)', color: 'var(--accent)', fontWeight: 600 } : { color: 'var(--text-secondary)' }"
            @mouseenter="(e: MouseEvent) => { if (selectedModuleId) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)' }"
            @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = '' }"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="flex-1 truncate">全部</span>
            <span class="text-[11px] opacity-60">{{ total }}</span>
          </div>

          <div v-if="modules.length === 0" class="text-center py-8 text-[var(--text-tertiary)] text-[12px]">
            暂无模块<br/>
            <button @click="showModuleDialog = true" class="mt-2 underline cursor-pointer" style="color: var(--accent);">创建模块</button>
          </div>

          <template v-for="mod in modules" :key="mod.id">
            <!-- Module row -->
            <div
              @click="selectModule(mod.id)"
              class="flex items-center gap-[6px] px-[10px] py-[7px] rounded-[8px] cursor-pointer text-[13px] transition-colors"
              :style="selectedModuleId === mod.id ? { backgroundColor: 'var(--selected-bg)', color: 'var(--accent)', fontWeight: 600 } : { color: 'var(--text-secondary)' }"
              @mouseenter="(e: MouseEvent) => { if (selectedModuleId !== mod.id) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)' }"
              @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = '' }"
            >
              <svg
                v-if="mod.children && mod.children.length > 0"
                @click.stop="toggleModuleExpand(mod.id)"
                width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
                class="transition-transform duration-150 shrink-0"
                :style="{ transform: expandedModules.has(mod.id) ? 'rotate(90deg)' : 'rotate(0deg)', color: 'var(--text-tertiary)' }"
              >
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span v-else class="w-[10px] shrink-0"></span>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="shrink-0">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span class="flex-1 truncate">{{ mod.name }}</span>
            </div>

            <!-- Children -->
            <div v-if="mod.children && mod.children.length > 0 && expandedModules.has(mod.id)" class="ml-[14px]">
              <div
                v-for="child in mod.children" :key="child.id"
                @click="selectModule(child.id)"
                class="flex items-center gap-[8px] px-[10px] py-[6px] rounded-[8px] cursor-pointer text-[12.5px] transition-colors"
                :style="selectedModuleId === child.id ? { backgroundColor: 'var(--selected-bg)', color: 'var(--accent)', fontWeight: 600 } : { color: 'var(--text-secondary)' }"
                @mouseenter="(e: MouseEvent) => { if (selectedModuleId !== child.id) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)' }"
                @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = '' }"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="shrink-0">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="flex-1 truncate">{{ child.name }}</span>
              </div>
            </div>
          </template>
        </div>
      </aside>

      <!-- Right Content: Defect List -->
      <main class="flex-1 flex flex-col min-h-0 min-w-0" style="background-color: var(--content-bg);">
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
        <div class="flex-1 min-h-0 overflow-hidden flex flex-col">
          <DefectList
            :defects="defects"
            :total="total"
            :loading="loading"
            :currentPage="currentPage"
            :pageSize="pageSize"
            :modules="modules"
            :currentUserId="currentUserId"
            :externalModuleId="selectedModuleId"
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
      </main>
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