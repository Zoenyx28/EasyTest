<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick as tick } from 'vue';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useDefect } from '../composables/useDefect';
import { useAuth } from '../composables/useAuth';
import DefectList from './DefectList.vue';
import DefectCreateDialog from './DefectCreateDialog.vue';
import DefectDetailDialog from './DefectDetailDialog.vue';
import DefectConfirmDialog from './DefectConfirmDialog.vue';
import DefectResolveDialog from './DefectResolveDialog.vue';
import DefectCloseDialog from './DefectCloseDialog.vue';
import DefectActivateDialog from './DefectActivateDialog.vue';
import DefectAssignDialog from './DefectAssignDialog.vue';
import ConfirmDialog from './ConfirmDialog.vue';
import DefectModuleTreeNode from './DefectModuleTreeNode.vue';
import BaseButton from './base/BaseButton.vue';
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
const pageSize = ref(10);
const initialized = ref(false);

const filterStatus = ref('');
const filterSeverity = ref('');
const filterPriority = ref('');
const filterModuleId = ref<number | null>(null);
const filterAssigneeId = ref<number | null>(null);
const filterCreatorId = ref<number | null>(null);
const filterSearch = ref('');

const showCreateDialog = ref(false);
const showDetailDialog = ref(false);
const showConfirmDialog = ref(false);
const showResolveDialog = ref(false);
const showCloseDialog = ref(false);
const showActivateDialog = ref(false);
const showAssignDialog = ref(false);
const selectedDefectId = ref<number | null>(null);
const selectedDefect = ref<DefectInfo | null>(null);
const confirmDialog = ref<InstanceType<typeof ConfirmDialog> | null>(null);
const defectListRef = ref<InstanceType<typeof DefectList> | null>(null);

const listSelectedCount = computed(() => defectListRef.value?.selectedCount ?? 0);

// Module tree state
const selectedModuleId = ref<number | null>(null);
const expandedModules = ref<Set<number>>(new Set());
const moduleSearchQuery = ref('');

// Inline edit state
const renamingModuleId = ref<number | null>(null);
const renameValue = ref('');
const addingChildParentId = ref<number | null>(null);
const newChildName = ref('');
const hoveredModuleId = ref<number | null>(null);

function getModuleDepth(mods: DefectModuleInfo[], targetId: number, depth = 1): number {
  for (const m of mods) {
    if (m.id === targetId) return depth;
    if (m.children && m.children.length > 0) {
      const found = getModuleDepth(m.children, targetId, depth + 1);
      if (found > 0) return found;
    }
  }
  return 0;
}

async function startRename(mod: DefectModuleInfo) {
  renamingModuleId.value = mod.id;
  renameValue.value = mod.name;
  await tick();
}

async function saveRename() {
  const id = renamingModuleId.value;
  const name = renameValue.value.trim();
  if (!id || !name) return;
  try {
    await defectApi.updateModule(id, { name });
    renamingModuleId.value = null;
    await loadDefects();
  } catch (e: any) {
    emit('showToast', e.message || '重命名失败');
  }
}

function cancelRename() {
  renamingModuleId.value = null;
}

async function deleteModuleAction(id: number) {
  try {
    await defectApi.deleteModule(id);
    if (selectedModuleId.value === id) selectedModuleId.value = null;
    await loadDefects();
  } catch (e: any) {
    emit('showToast', e.message || '删除失败');
  }
}

async function addChildModule(parentId: number) {
  const name = newChildName.value.trim();
  if (!name) return;
  try {
    await defectApi.createModule({ project_id: projectId.value, name, parent_id: parentId }, branchId.value);
    expandedModules.value.add(parentId);
    expandedModules.value = new Set(expandedModules.value);
    addingChildParentId.value = null;
    newChildName.value = '';
    await loadDefects();
  } catch (e: any) {
    emit('showToast', e.message || '创建子模块失败');
  }
}

function cancelAddChild() {
  addingChildParentId.value = null;
  newChildName.value = '';
}

function startAddRoot() {
  addingChildParentId.value = 0;
  newChildName.value = '';
}

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
      defectApi.getModules(projectId.value, branchId.value),
    ]);
    defects.value = defectResult.items;
    total.value = defectResult.total;
    modules.value = moduleResult;
    // Auto-expand root modules that have children
    const expanded = new Set<number>();
    for (const m of moduleResult) {
      if (m.children && m.children.length > 0) expanded.add(m.id);
    }
    expandedModules.value = expanded;
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
  } else if (action === 'view') {
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

async function handleDeleteDefects(ids: number[]) {
  if (!ids.length) return;
  const confirmed = await confirmDialog.value?.confirm({
    title: '删除缺陷',
    message: `确定删除选中的 ${ids.length} 个缺陷吗？将同时删除其附件、日志和评论，此操作不可撤销。`,
    confirmText: '删除',
    confirmColor: 'var(--color-danger)',
  });
  if (!confirmed) return;

  let okCount = 0;
  for (const id of ids) {
    try {
      await defectApi.deleteDefect(id);
      okCount++;
    } catch (e: any) {
      emit('showToast', e.message || `删除缺陷 #${id} 失败`);
    }
  }
  if (okCount > 0) {
    emit('showToast', `已删除 ${okCount} 个缺陷`);
    // 当前页被删空时回退一页
    if (defects.value.length === okCount && currentPage.value > 1) {
      currentPage.value--;
    }
    await loadDefects();
    // 删除成功后清空选中状态
    defectListRef.value?.clearSelection();
  }
}

async function handleDeleteSelected() {
  const ids = defectListRef.value?.getSelectedIds() ?? [];
  if (!ids.length) return;
  await handleDeleteDefects(ids);
}

function handleAssignDone() {
  loadDefects();
}

async function initPage() {
  try {
    await getActiveProject();
    if (projectId.value) {
      await loadBranches(projectId.value);
    }
    // Default filter: show "assigned to me" if the current user has assigned defects;
    // otherwise show all defects.
    if (currentUserId.value && branchId.value) {
      try {
        const mine = await defectApi.getDefects({
          project_id: projectId.value,
          branch_id: branchId.value,
          assignee_id: currentUserId.value,
          page: 1,
          page_size: 1,
        });
        if (mine.total > 0) {
          filterAssigneeId.value = currentUserId.value;
        }
      } catch {
        // ignore — fall back to showing all defects
      }
    }
    await loadDefects();
  } catch {
    // ignore
  } finally {
    initialized.value = true;
  }
}

watch(projectId, async () => {
  if (projectId.value && initialized.value) {
    await loadBranches(projectId.value);
    currentPage.value = 1;
    await loadDefects();
  }
});

watch(branchId, async () => {
  if (branchId.value && initialized.value) {
    currentPage.value = 1;
    await loadDefects();
  }
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
        <p class="text-[13px] font-medium" style="color: var(--text-secondary); margin: 0 0 6px;">请先创建项目</p>
        <p class="text-[11px]" style="color: var(--text-tertiary); margin: 0;">在项目管理页面创建并激活一个项目后，即可管理缺陷</p>
      </div>
    </div>

    <template v-else>
      <!-- Left Sidebar: Module Tree -->
      <aside
        class="w-[240px] min-w-[240px] flex flex-col shrink-0 min-h-0"
        style="background-color: var(--sidebar-bg); border-right: 1px solid var(--sidebar-border);"
      >
        <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0">
          <h3 class="sidebar-title" style="color: var(--text-primary);">缺陷模块</h3>
        </div>

        <!-- Search -->
        <div class="px-[12px] pb-[8px] shrink-0">
          <div class="module-search flex items-center gap-[6px] px-[10px] py-[6px]">
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
            class="group flex items-center gap-[8px] px-[10px] py-[7px] rounded-[8px] cursor-pointer text-[13px] transition-colors"
            :style="!selectedModuleId ? { backgroundColor: 'var(--selected-bg)', color: 'var(--color-primary)', fontWeight: 600 } : { color: 'var(--text-secondary)' }"
            @mouseenter="(e: MouseEvent) => { if (selectedModuleId) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)' }"
            @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = '' }"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="flex-1 truncate">全部</span>
            <button
              @click.stop="startAddRoot()"
              class="w-[20px] h-[20px] rounded-[4px] flex items-center justify-center cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              style="color: var(--text-tertiary);"
              @mouseenter="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)'; (e.currentTarget as HTMLElement).style.color = 'var(--color-primary)' }"
              @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = ''; (e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)' }"
              title="添加根模块"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
          </div>

          <!-- Root add input -->
          <div v-if="addingChildParentId === 0" class="flex items-center gap-[6px] px-[10px] py-[5px]">
            <input
              v-model="newChildName"
              ref="rootInputRef"
              type="text"
              placeholder="输入模块名称..."
              class="flex-1 bg-transparent text-[12px] outline-none px-[6px] py-[3px] rounded-[4px]"
              style="color: var(--text-primary); border: 2px solid var(--color-primary);"
              @keyup.enter="addChildModule(0)"
              @keyup.escape="cancelAddChild()"
            />
            <button @click="addChildModule(0)" class="w-[20px] h-[20px] flex items-center justify-center cursor-pointer" style="color: var(--color-primary);">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
            <button @click="cancelAddChild()" class="w-[20px] h-[20px] flex items-center justify-center cursor-pointer" style="color: var(--text-tertiary);">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <!-- Empty state -->
          <div v-if="modules.length === 0 && addingChildParentId !== 0" class="text-center py-8 text-[var(--text-tertiary)] text-[12px]">
            暂无模块<br/>
            <button @click="startAddRoot()" class="mt-2 underline cursor-pointer" style="color: var(--accent);">创建根模块</button>
          </div>

          <!-- Module tree nodes -->
          <template v-for="mod in modules" :key="mod.id">
            <DefectModuleTreeNode
              :module="mod"
              :depth="1"
              :selectedModuleId="selectedModuleId"
              :expandedModules="expandedModules"
              :renamingModuleId="renamingModuleId"
              :renameValue="renameValue"
              :addingChildParentId="addingChildParentId"
              :newChildName="newChildName"
              @toggleExpand="toggleModuleExpand"
              @select="selectModule"
              @startRename="startRename"
              @saveRename="saveRename"
              @cancelRename="cancelRename"
              @deleteModule="deleteModuleAction"
              @addChild="(parentId: number) => { addingChildParentId = parentId; newChildName = '' }"
              @addChildSave="addChildModule"
              @cancelAddChild="cancelAddChild"
              @updateNewChildName="(v: string) => newChildName = v"
              @updateRenameValue="(v: string) => renameValue = v"
            />
          </template>
        </div>
      </aside>

      <!-- Right Content: Defect List -->
      <main class="flex-1 flex flex-col min-h-0 min-w-0" style="background-color: var(--content-bg);">
        <!-- Panel header -->
        <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0" style="border-bottom: 2px solid var(--outline);">
          <h2 class="page-title" style="color: var(--text-primary);">缺陷管理</h2>
          <div class="flex gap-[8px]">
            <button
              v-if="listSelectedCount > 0"
              @click="handleDeleteSelected"
              class="danger-btn flex items-center gap-[4px] px-[12px] py-[6px] text-[12px] font-semibold cursor-pointer"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              删除({{ listSelectedCount }})
            </button>
            <BaseButton
              @click="showCreateDialog = true"
              variant="primary"
              size="md"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              创建缺陷
            </BaseButton>
          </div>
        </div>

        <!-- Defect list -->
        <div class="flex-1 min-h-0 overflow-hidden flex flex-col">
          <DefectList
            ref="defectListRef"
            :defects="defects"
            :total="total"
            :loading="loading"
            :currentPage="currentPage"
            :pageSize="pageSize"
            :modules="modules"
            :currentUserId="currentUserId"
            :externalModuleId="selectedModuleId"
            :filterAssigneeId="filterAssigneeId"
            :filterCreatorId="filterCreatorId"
            @pageChange="handlePageChange"
            @filterChange="handleFilterChange"
            @confirm="(d: DefectInfo) => handleListAction('confirm', d)"
            @resolve="(d: DefectInfo) => handleListAction('resolve', d)"
            @close="(d: DefectInfo) => handleListAction('close', d)"
            @edit="(d: DefectInfo) => handleListAction('edit', d)"
            @view="(d: DefectInfo) => handleListAction('view', d)"
            @copy="(d: DefectInfo) => handleListAction('copy', d)"
            @assign="(d: DefectInfo) => { selectedDefect = d; selectedDefectId = d.id; showAssignDialog = true }"
            @delete="handleDeleteDefects"
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
      @activate="(d: DefectInfo) => { selectedDefectId = d.id; selectedDefect = d; showActivateDialog = true }"
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

    <!-- Activate dialog -->
    <DefectActivateDialog
      :isOpen="showActivateDialog"
      :defect="selectedDefect"
      :projectId="projectId"
      @close="showActivateDialog = false"
      @done="handleUpdated"
      @showToast="(msg: string) => emit('showToast', msg)"
    />

    <!-- Global confirm dialog -->
    <ConfirmDialog ref="confirmDialog" />

    <!-- Assign dialog -->
    <DefectAssignDialog
      :isOpen="showAssignDialog"
      :defect="selectedDefect"
      :projectId="projectId"
      @close="showAssignDialog = false"
      @done="handleAssignDone"
      @showToast="(msg: string) => emit('showToast', msg)"
    />
  </div>
</template>

<style scoped>
/* ── Claymorphism ── */

/* 页面主标题 */
.page-title {
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

/* 侧栏标题 */
.sidebar-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

/* 模块搜索框（Clay 输入框） */
.module-search {
  background-color: var(--input-bg);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.module-search:focus-within {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

/* 危险操作按钮（删除，保留红色语义） */
.danger-btn {
  background-color: transparent;
  color: var(--color-danger);
  border: 2px solid var(--color-danger);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.danger-btn:hover {
  background-color: var(--danger-soft);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.danger-btn:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
}
</style>