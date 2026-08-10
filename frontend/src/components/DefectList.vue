<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { buildModulePath } from '../composables/useDefect';
import type { DefectInfo, DefectModuleInfo } from '../types';
import UserAvatar from './UserAvatar.vue';

const props = defineProps<{
  defects: DefectInfo[];
  total: number;
  loading: boolean;
  currentPage: number;
  pageSize: number;
  modules: DefectModuleInfo[];
  currentUserId: number;
  externalModuleId?: number | null;
  filterAssigneeId?: number | null;
  filterCreatorId?: number | null;
}>();

const emit = defineEmits<{
  (e: 'pageChange', page: number): void;
  (e: 'pageSizeChange', size: number): void;
  (e: 'filterChange', filters: { status: string; severity: string; priority: string; moduleId: number | null; assigneeId: number | null; creatorId: number | null; search: string }): void;
  (e: 'confirm', defect: DefectInfo): void;
  (e: 'resolve', defect: DefectInfo): void;
  (e: 'close', defect: DefectInfo): void;
  (e: 'view', defect: DefectInfo): void;
  (e: 'edit', defect: DefectInfo): void;
  (e: 'copy', defect: DefectInfo): void;
  (e: 'assign', defect: DefectInfo): void;
  (e: 'delete', ids: number[]): void;
}>();

const selectedIds = ref<Set<number>>(new Set());

const selectedCount = computed(() => selectedIds.value.size);

const isAllSelected = computed(
  () => props.defects.length > 0 && props.defects.every(d => selectedIds.value.has(d.id)),
);

function toggleSelect(defect: DefectInfo) {
  const next = new Set(selectedIds.value);
  if (next.has(defect.id)) next.delete(defect.id);
  else next.add(defect.id);
  selectedIds.value = next;
}

function toggleSelectAll() {
  const next = new Set(selectedIds.value);
  if (isAllSelected.value) {
    props.defects.forEach(d => next.delete(d.id));
  } else {
    props.defects.forEach(d => next.add(d.id));
  }
  selectedIds.value = next;
}

function clearSelection() {
  selectedIds.value = new Set();
}

// Expose selection state to parent (DefectView) so the delete button can live in the header
defineExpose({
  selectedCount,
  getSelectedIds: () => Array.from(selectedIds.value),
  clearSelection,
});

const filterStatus = ref('');
const filterSeverity = ref('');
const filterPriority = ref('');
const filterModuleId = ref<number | null>(null);
const filterAssigneeId = ref<number | null>(null);
const filterCreatorId = ref<number | null>(null);
const filterSearch = ref('');

const statusOptions = [
  { value: '', label: '全部' },
  { value: 'unconfirmed', label: '未确认' },
  { value: 'confirmed', label: '已确认' },
  { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已解决' },
  { value: 'closed', label: '已关闭' },
];

const severityOptions = [
  { value: '', label: '全部' },
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
];

const priorityOptions = [
  { value: '', label: '全部' },
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
];

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return;
  clearSelection();
  emit('pageChange', page);
}

function getPageNumbers(): (number | string)[] {
  const pages: (number | string)[] = [];
  const total = totalPages.value;
  const current = props.currentPage;
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (current > 3) pages.push('...');
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let i = start; i <= end; i++) pages.push(i);
    if (current < total - 2) pages.push('...');
    pages.push(total);
  }
  return pages;
}

const severityColors: Record<string, string> = {
  P0: 'var(--priority-p0-bg)',
  P1: 'var(--priority-p1-bg)',
  P2: 'var(--priority-p2-bg)',
  P3: 'var(--priority-p3-bg)',
};

const severityTextColors: Record<string, string> = {
  P0: 'var(--priority-p0-text)',
  P1: 'var(--priority-p1-text)',
  P2: 'var(--priority-p2-text)',
  P3: 'var(--priority-p3-text)',
};

const statusLabels: Record<string, string> = {
  unconfirmed: '未确认',
  confirmed: '已确认',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

const statusColors: Record<string, string> = {
  unconfirmed: 'var(--border)',
  confirmed: 'var(--status-confirmed-bg)',
  in_progress: 'var(--status-in-progress-bg)',
  resolved: 'var(--status-resolved-bg)',
  closed: 'var(--border)',
};

const statusTextColors: Record<string, string> = {
  unconfirmed: 'var(--text-secondary)',
  confirmed: 'var(--status-confirmed-text)',
  in_progress: 'var(--status-in-progress-text)',
  resolved: 'var(--status-resolved-text)',
  closed: 'var(--text-secondary)',
};

function formatTime(iso: string): string {
  if (!iso) return '--';
  try {
    return iso.substring(0, 10) + ' ' + iso.substring(11, 19);
  } catch {
    return iso;
  }
}

function applyFilters() {
  if (syncingParent) return;
  emit('filterChange', {
    status: filterStatus.value,
    severity: filterSeverity.value,
    priority: filterPriority.value,
    moduleId: filterModuleId.value,
    assigneeId: filterAssigneeId.value,
    creatorId: filterCreatorId.value,
    search: filterSearch.value,
  });
}

function toggleAssigneeFilter() {
  // Mutually exclusive with "我创建的": selecting one clears the other
  filterCreatorId.value = null;
  filterAssigneeId.value = filterAssigneeId.value === props.currentUserId ? null : props.currentUserId;
}

function toggleCreatorFilter() {
  // Mutually exclusive with "指派给我": selecting one clears the other
  filterAssigneeId.value = null;
  filterCreatorId.value = filterCreatorId.value === props.currentUserId ? null : props.currentUserId;
}

function canConfirm(status: string): boolean {
  return status === 'unconfirmed';
}

function canResolve(status: string): boolean {
  return status === 'confirmed' || status === 'in_progress';
}

function canClose(status: string): boolean {
  return status === 'resolved';
}

function handleActionClick(action: string, defect: DefectInfo) {
  emit(action as any, defect);
}

function flattenModules(mods: DefectModuleInfo[]): DefectModuleInfo[] {
  const result: DefectModuleInfo[] = [];
  for (const m of mods) {
    result.push(m);
    if (m.children && m.children.length > 0) {
      result.push(...flattenModules(m.children));
    }
  }
  return result;
}

function clearFilters() {
  filterStatus.value = '';
  filterSeverity.value = '';
  filterPriority.value = '';
  filterModuleId.value = null;
  filterAssigneeId.value = null;
  filterCreatorId.value = null;
  filterSearch.value = '';
}

watch([filterStatus, filterSeverity, filterPriority, filterModuleId, filterAssigneeId, filterCreatorId, filterSearch], applyFilters);

// Sync assignee/creator filters from parent (used for default "指派给我" on first load)
let syncingParent = false;
watch(() => props.filterAssigneeId, (v) => {
  const next = v ?? null;
  if (next === filterAssigneeId.value) return;
  syncingParent = true;
  filterAssigneeId.value = next;
  syncingParent = false;
});

watch(() => props.filterCreatorId, (v) => {
  const next = v ?? null;
  if (next === filterCreatorId.value) return;
  syncingParent = true;
  filterCreatorId.value = next;
  syncingParent = false;
});

// Sync external module filter from parent sidebar
watch(() => props.externalModuleId, (newVal) => {
  if (newVal !== undefined) {
    filterModuleId.value = newVal;
  }
}, { immediate: true });
</script>

<template>
  <div class="defect-list">
    <!-- Search and quick filter bar -->
    <div class="search-bar">
      <div class="search-input-wrapper">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="search-icon">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          class="search-input"
          placeholder="通过ID或标题搜索缺陷..."
          v-model="filterSearch"
        />
      </div>
      <div class="quick-filters">
        <button
          class="quick-filter-button"
          :class="{ 'quick-filter-active': !filterAssigneeId && !filterCreatorId }"
          @click="clearFilters"
        >
          全部 ({{ total }})
        </button>
        <button
          class="quick-filter-button"
          :class="{ 'quick-filter-active': filterAssigneeId === currentUserId && !filterCreatorId }"
          @click="toggleAssigneeFilter"
        >
          指派给我
        </button>
        <button
          class="quick-filter-button"
          :class="{ 'quick-filter-active': filterCreatorId === currentUserId && !filterAssigneeId }"
          @click="toggleCreatorFilter"
        >
          我创建的
        </button>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="filter-section">
        <div class="filter-label">状态:</div>
        <select
          class="filter-select"
          :value="filterStatus"
          @change="filterStatus = ($event.target as HTMLSelectElement).value"
        >
          <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="filter-section">
        <div class="filter-label">严重程度:</div>
        <select
          class="filter-select"
          :value="filterSeverity"
          @change="filterSeverity = ($event.target as HTMLSelectElement).value"
        >
          <option v-for="opt in severityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="filter-section">
        <div class="filter-label">优先级:</div>
        <select
          class="filter-select"
          :value="filterPriority"
          @change="filterPriority = ($event.target as HTMLSelectElement).value"
        >
          <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div v-if="externalModuleId === undefined" class="filter-section">
        <div class="filter-label">模块:</div>
        <select
          class="filter-select"
          :value="filterModuleId || ''"
          @change="filterModuleId = ($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null"
        >
          <option value="">全部模块</option>
          <option v-for="mod in flattenModules(modules)" :key="mod.id" :value="mod.id">{{ mod.name }}</option>
        </select>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="defects.length === 0" class="empty-state">
      <svg class="empty-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <p class="empty-text">暂无缺陷</p>
    </div>

    <!-- Table -->
    <div v-else class="table-wrapper">
      <table class="defect-table">
        <thead>
          <tr>
            <th class="col-checkbox">
              <input
                type="checkbox"
                class="table-checkbox"
                :checked="isAllSelected"
                @change="toggleSelectAll"
              />
            </th>
            <th class="col-id">ID</th>
            <th class="col-title">标题</th>
            <th class="col-severity">严重程度</th>
            <th class="col-status">状态</th>
            <th class="col-assignee">指派给</th>
            <th class="col-creator">创建者</th>
            <th class="col-time">创建时间</th>
            <th class="col-actions" style="width: 140px; text-align: center;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="defect in defects"
            :key="defect.id"
            class="defect-row"
            :class="{ 'defect-row-selected': selectedIds.has(defect.id) }"
          >
            <td class="col-checkbox">
              <input
                type="checkbox"
                class="table-checkbox"
                :checked="selectedIds.has(defect.id)"
                @change="toggleSelect(defect)"
                @click.stop
              />
            </td>
            <td class="cell-id">#{{ defect.id }}</td>
            <td class="cell-title">
              <div class="cell-title-main cell-title-clickable" title="点击查看详情" @click="emit('view', defect)">{{ defect.title }}</div>
              <div class="cell-title-sub">{{ buildModulePath(props.modules, defect.module_id) }}</div>
            </td>
            <td class="cell-severity">
              <span
                class="severity-badge"
                :style="{
                  backgroundColor: severityColors[defect.severity] || 'var(--border)',
                  color: severityTextColors[defect.severity] || 'var(--text-secondary)',
                }"
              >
                {{ defect.severity }}
              </span>
            </td>
            <td class="cell-status">
              <span
                class="status-badge"
                :style="{
                  backgroundColor: statusColors[defect.status] || 'var(--border)',
                  color: statusTextColors[defect.status] || 'var(--text-secondary)',
                }"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;">
                  <circle cx="12" cy="12" r="8"></circle>
                </svg>
                {{ statusLabels[defect.status] || defect.status }}
              </span>
            </td>
            <td class="cell-assignee">
              <div
                class="assignee-cell assignee-cell-clickable"
                :class="{ 'assignee-cell-unassigned': !defect.assignee_name }"
                title="点击指派/重新指派"
                @click.stop="emit('assign', defect)"
              >
                <UserAvatar :name="defect.assignee_name || '未指派'" :avatar="defect.assignee_avatar || ''" :size="24" />
                <span class="assignee-cell-name">{{ defect.assignee_name || '未指派' }}</span>
              </div>
            </td>
            <td class="cell-creator">
              <span class="text-muted">{{ defect.creator_name }}</span>
            </td>
            <td class="cell-time">
              <span class="text-muted">{{ formatTime(defect.created_at) }}</span>
            </td>
            <td class="cell-actions">
              <div class="action-buttons" @click.stop>
                <button
                  class="action-btn"
                  :class="{ 'action-disabled': !canConfirm(defect.status) }"
                  :disabled="!canConfirm(defect.status)"
                  title="确认"
                  @click="canConfirm(defect.status) && handleActionClick('confirm', defect)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </button>
                <button
                  class="action-btn"
                  :class="{ 'action-disabled': !canResolve(defect.status) }"
                  :disabled="!canResolve(defect.status)"
                  title="解决"
                  @click="canResolve(defect.status) && handleActionClick('resolve', defect)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                </button>
                <button
                  class="action-btn"
                  :class="{ 'action-disabled': !canClose(defect.status) }"
                  :disabled="!canClose(defect.status)"
                  title="关闭"
                  @click="canClose(defect.status) && handleActionClick('close', defect)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
                <button
                  class="action-btn"
                  title="编辑"
                  @click="handleActionClick('edit', defect)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <button
                  class="action-btn"
                  title="复制"
                  @click="handleActionClick('copy', defect)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > 0" class="pagination">
      <div class="pagination-info">
        共 <span class="pagination-num">{{ props.total }}</span> 条，显示
        <span class="pagination-num">{{ Math.min((props.currentPage - 1) * props.pageSize + 1, props.total) }}</span>
        至
        <span class="pagination-num">{{ Math.min(props.currentPage * props.pageSize, props.total) }}</span>
        条
      </div>
      <div class="pagination-controls">
        <button
          @click="goToPage(props.currentPage - 1)"
          :disabled="props.currentPage <= 1"
          class="page-button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
        <template v-for="p in getPageNumbers()" :key="p">
          <span v-if="p === '...'" class="page-ellipsis">…</span>
          <button
            v-else
            @click="goToPage(p as number)"
            class="page-button"
            :class="{ 'page-button-active': p === props.currentPage }"
          >
            {{ p }}
          </button>
        </template>
        <button
          @click="goToPage(props.currentPage + 1)"
          :disabled="props.currentPage >= totalPages"
          class="page-button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.defect-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bg-muted);
  padding: 0 16px;
}

.search-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 0;
  background-color: var(--bg-card);
  margin-left: 16px;
  flex-shrink: 0;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background-color: var(--input-bg);
  border-radius: var(--radius-sm);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  flex: 1;
  max-width: 400px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.search-input-wrapper:focus-within {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: var(--font);
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.quick-filters {
  display: flex;
  gap: 2px;
  align-items: center;
  padding: 3px;
  background-color: var(--input-bg);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm);
  overflow: hidden;
}

.quick-filter-button {
  padding: 6px 14px;
  border: 2px solid transparent;
  background: transparent;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.quick-filter-button:hover {
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
}

.quick-filter-active {
  background-color: var(--color-primary);
  border-color: var(--outline);
  color: var(--text-primary);
  font-weight: 600;
  box-shadow: var(--shadow-hard-sm);
}

.quick-filter-active:hover {
  background-color: var(--color-primary);
  color: var(--text-primary);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 0;
  background-color: var(--bg-card);
  border-bottom: 2px solid var(--outline);
  flex-shrink: 0;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.filter-buttons {
  display: flex;
  gap: 4px;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 2px;
}

.filter-button {
  padding: 6px 12px;
  border: none;
  background: transparent;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-button:hover {
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
}

.filter-button-active {
  background-color: var(--color-primary);
  color: var(--bg-card);
}

.filter-button-active:hover {
  background-color: var(--color-primary);
  color: var(--bg-card);
  filter: brightness(1.1);
}

.filter-button-severity {
  font-weight: 700;
}

.filter-more {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
}

.filter-more:hover {
  color: var(--color-primary);
}

.more-filters {
  padding: 12px 16px;
  background-color: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-row-label {
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.filter-select {
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--outline);
  font-size: 13px;
  font-family: var(--font);
  background-color: var(--input-bg);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
  min-width: 150px;
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.filter-select:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 12px;
  color: var(--text-muted);
  font-family: var(--font);
  font-size: 13px;
  flex: 1;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid var(--border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 12px;
  color: var(--text-muted);
  flex: 1;
}

.empty-icon {
  opacity: 0.5;
}

.empty-text {
  font-family: var(--font);
  font-size: 14px;
  font-weight: 500;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
  background-color: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border);
}

.defect-table {
  width: 100%;
  font-family: var(--font);
  border-collapse: collapse;
}

.defect-table thead {
  position: sticky;
  top: 0;
  z-index: 5;
  background-color: var(--bg-muted);
}

.defect-table th {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  background-color: var(--bg-muted);
  text-align: left;
}

.col-checkbox {
  width: 40px;
}

.col-id {
  width: 70px;
}

.col-title {
  width: auto;
  min-width: 180px;
}

.col-severity {
  width: 90px;
}

.col-status {
  width: 120px;
}

.col-assignee {
  width: 100px;
}

.col-creator {
  width: 100px;
}

.col-time {
  width: 185px;
}

.defect-row {
  border-bottom: 1px solid var(--border);
  transition: background 0.15s ease;
}

.defect-row:hover {
  background-color: var(--color-primary-soft);
}

.defect-row-selected {
  background-color: var(--color-primary-soft);
}

.defect-row td {
  padding: 14px 20px;
  vertical-align: middle;
}

.table-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  border: 2px solid var(--outline);
  border-radius: 4px;
  accent-color: var(--color-primary);
}

.cell-id {
  font-weight: 700;
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-mono);
}

.cell-title {
  font-weight: 500;
  color: var(--text-primary);
}

.cell-title-main {
  font-size: 13px;
  line-height: 18px;
}

.cell-title-clickable {
  cursor: pointer;
  color: var(--text-primary);
  transition: color 0.15s;
}

.cell-title-clickable:hover {
  color: var(--color-primary);
  text-decoration: underline;
}

.cell-title-sub {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 16px;
}

.cell-time {
  white-space: nowrap;
}

.severity-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.assignee-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.assignee-cell-clickable {
  cursor: pointer;
  transition: opacity 0.15s ease;
  border-radius: 100px;
  padding: 2px 6px 2px 2px;
  margin-left: -2px;
}

.assignee-cell-clickable:hover {
  background-color: var(--color-primary-soft);
}

.assignee-cell-clickable.text-muted:hover {
  color: var(--color-primary);
}

.assignee-cell-unassigned {
  color: var(--text-muted);
}

.assignee-cell-unassigned .assignee-cell-name {
  color: var(--text-muted);
  font-weight: 400;
}

.assignee-cell-unassigned:hover .assignee-cell-name {
  color: var(--color-primary);
}

.assignee-cell-name {
  font-size: 12px;
  color: var(--text-primary);
  font-family: var(--font);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-muted {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  flex-shrink: 0;
  background-color: var(--bg-card);
}

.pagination-info {
  font-size: 13px;
  color: var(--text-muted);
  font-family: var(--font);
  line-height: 18px;
}

.pagination-num {
  color: var(--text-primary);
  font-weight: 600;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease, color 0.15s ease;
  font-family: var(--font);
  background: var(--card-bg-2);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
}

.page-button:hover:not(:disabled):not(.page-button-active) {
  background-color: var(--bg-card-hover);
  border-color: var(--outline);
  color: var(--text-primary);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.page-button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-button-active {
  background-color: var(--color-primary);
  color: var(--text-primary);
  font-weight: 600;
  border-color: var(--outline);
}

.page-button-active:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.page-ellipsis {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 32px;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 1px;
}

.cell-actions {
  text-align: center;
}

.action-buttons {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.action-btn:hover:not(:disabled) {
  background-color: var(--color-primary-soft);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.action-btn.action-disabled,
.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  background: var(--bg-muted);
}
</style>
