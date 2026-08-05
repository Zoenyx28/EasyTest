<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { DefectInfo, DefectModuleInfo } from '../types';

const props = defineProps<{
  defects: DefectInfo[];
  total: number;
  loading: boolean;
  currentPage: number;
  pageSize: number;
  modules: DefectModuleInfo[];
  currentUserId: number;
}>();

const emit = defineEmits<{
  (e: 'select', defect: DefectInfo): void;
  (e: 'pageChange', page: number): void;
  (e: 'pageSizeChange', size: number): void;
  (e: 'filterChange', filters: { status: string; severity: string; priority: string; moduleId: number | null; assigneeId: number | null; creatorId: number | null; search: string }): void;
  (e: 'confirm', defect: DefectInfo): void;
  (e: 'resolve', defect: DefectInfo): void;
  (e: 'close', defect: DefectInfo): void;
  (e: 'edit', defect: DefectInfo): void;
  (e: 'copy', defect: DefectInfo): void;
}>();

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
  P0: '#ffdad6',
  P1: '#ffd6a5',
  P2: '#fff6cc',
  P3: '#d4edda',
};

const severityTextColors: Record<string, string> = {
  P0: '#93000a',
  P1: '#7a4400',
  P2: '#655500',
  P3: '#155724',
};

const statusLabels: Record<string, string> = {
  unconfirmed: '未确认',
  confirmed: '已确认',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

const statusColors: Record<string, string> = {
  unconfirmed: '#e0e9f2',
  confirmed: '#d8e2ff',
  in_progress: '#ffd6a5',
  resolved: '#d4edda',
  closed: '#e0e9f2',
};

const statusTextColors: Record<string, string> = {
  unconfirmed: '#414754',
  confirmed: '#0059bb',
  in_progress: '#7a4400',
  resolved: '#155724',
  closed: '#414754',
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
  filterAssigneeId.value = filterAssigneeId.value === props.currentUserId ? null : props.currentUserId;
}

function toggleCreatorFilter() {
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
          @change="filterStatus = $event.target.value"
        >
          <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="filter-section">
        <div class="filter-label">严重程度:</div>
        <select
          class="filter-select"
          :value="filterSeverity"
          @change="filterSeverity = $event.target.value"
        >
          <option v-for="opt in severityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="filter-section">
        <div class="filter-label">优先级:</div>
        <select
          class="filter-select"
          :value="filterPriority"
          @change="filterPriority = $event.target.value"
        >
          <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="filter-section">
        <div class="filter-label">模块:</div>
        <select
          class="filter-select"
          :value="filterModuleId || ''"
          @change="filterModuleId = $event.target.value ? Number($event.target.value) : null"
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
              <input type="checkbox" class="table-checkbox" />
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
            @click="emit('select', defect)"
          >
            <td class="col-checkbox">
              <input type="checkbox" class="table-checkbox" @click.stop />
            </td>
            <td class="cell-id">#{{ defect.id }}</td>
            <td class="cell-title">
              <div class="cell-title-main">{{ defect.title }}</div>
              <div class="cell-title-sub">{{ defect.module_name }}</div>
            </td>
            <td class="cell-severity">
              <span
                class="severity-badge"
                :style="{
                  backgroundColor: severityColors[defect.severity] || '#e0e9f2',
                  color: severityTextColors[defect.severity] || '#414754',
                }"
              >
                {{ defect.severity }}
              </span>
            </td>
            <td class="cell-status">
              <span
                class="status-badge"
                :style="{
                  backgroundColor: statusColors[defect.status] || '#e0e9f2',
                  color: statusTextColors[defect.status] || '#414754',
                }"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;">
                  <circle cx="12" cy="12" r="8"></circle>
                </svg>
                {{ statusLabels[defect.status] || defect.status }}
              </span>
            </td>
            <td class="cell-assignee">
              <div v-if="defect.assignee_name" class="user-avatar">
                <span class="user-avatar-text">{{ defect.assignee_name.charAt(0).toUpperCase() }}</span>
              </div>
              <span v-else class="text-muted">--</span>
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
        Showing
        <span class="pagination-num">{{ Math.min((props.currentPage - 1) * props.pageSize + 1, props.total) }}</span>
        to
        <span class="pagination-num">{{ Math.min(props.currentPage * props.pageSize, props.total) }}</span>
        of
        <span class="pagination-num">{{ props.total }}</span>
        defects
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
  background-color: #f6faff;
}

.search-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 0;
  background-color: #ffffff;
  flex-shrink: 0;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background-color: #ecf5fe;
  border-radius: 8px;
  border: 1px solid #e0e9f2;
  flex: 1;
  max-width: 400px;
}

.search-icon {
  color: #717786;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: 'Hanken Grotesk';
  font-size: 14px;
  color: #141d23;
  outline: none;
}

.search-input::placeholder {
  color: #717786;
}

.quick-filters {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 2px;
  background-color: #e6eff8;
  border-radius: 100px;
}

.quick-filter-button {
  padding: 6px 14px;
  border: none;
  background: transparent;
  font-family: 'Hanken Grotesk';
  font-size: 13px;
  font-weight: 600;
  color: #414754;
  border-radius: 100px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.quick-filter-button:hover {
  color: #141d23;
}

.quick-filter-active {
  background-color: #ffffff;
  color: #141d23;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 0;
  background-color: #ffffff;
  flex-shrink: 0;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-family: 'Hanken Grotesk';
  font-size: 11px;
  font-weight: 700;
  color: #717786;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.filter-buttons {
  display: flex;
  gap: 4px;
  align-items: center;
  border: 1px solid #e0e9f2;
  border-radius: 8px;
  padding: 2px;
}

.filter-button {
  padding: 6px 12px;
  border: none;
  background: transparent;
  font-family: 'Hanken Grotesk';
  font-size: 12px;
  font-weight: 500;
  color: #414754;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-button:hover {
  background-color: #ecf5fe;
  color: #141d23;
}

.filter-button-active {
  background-color: #0059bb;
  color: #ffffff;
}

.filter-button-active:hover {
  background-color: #0059bb;
  color: #ffffff;
  filter: brightness(1.1);
}

.filter-button-severity {
  font-weight: 700;
}

.filter-more {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #717786;
  font-family: 'Hanken Grotesk';
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
}

.filter-more:hover {
  color: #0059bb;
}

.more-filters {
  padding: 12px 16px;
  background-color: #ffffff;
  border-bottom: 1px solid #e0e9f2;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-row-label {
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: #717786;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.filter-select {
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #c1c6d7;
  font-size: 13px;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  background-color: #ffffff;
  color: #141d23;
  outline: none;
  cursor: pointer;
  min-width: 150px;
}

.filter-select:focus {
  border-color: #0059bb;
  box-shadow: 0 0 0 3px rgba(0, 89, 187, 0.1);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 12px;
  color: #717786;
  font-family: 'Hanken Grotesk';
  font-size: 13px;
  flex: 1;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid #e0e9f2;
  border-top-color: #0059bb;
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
  color: #717786;
  flex: 1;
}

.empty-icon {
  opacity: 0.5;
}

.empty-text {
  font-family: 'Hanken Grotesk';
  font-size: 14px;
  font-weight: 500;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
  background-color: #ffffff;
  border-radius: 12px;
  border: 1px solid #e0e9f2;
}

.defect-table {
  width: 100%;
  font-family: 'Hanken Grotesk';
  border-collapse: collapse;
}

.defect-table thead {
  position: sticky;
  top: 0;
  z-index: 5;
  background-color: #f6faff;
}

.defect-table th {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 16px 20px;
  border-bottom: 1px solid #e0e9f2;
  color: #717786;
  background-color: #f6faff;
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
  width: 160px;
}

.defect-row {
  border-bottom: 1px solid #e0e9f2;
  cursor: pointer;
  transition: background 0.15s ease;
}

.defect-row:hover {
  background-color: #ecf5fe;
}

.defect-row td {
  padding: 14px 20px;
  vertical-align: middle;
}

.table-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  border: 1px solid #c1c6d7;
  border-radius: 4px;
  accent-color: #0059bb;
}

.cell-id {
  font-weight: 700;
  color: #717786;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

.cell-title {
  font-weight: 500;
  color: #141d23;
}

.cell-title-main {
  font-size: 13px;
  line-height: 18px;
}

.cell-title-sub {
  font-size: 12px;
  color: #717786;
  line-height: 16px;
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

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: #0059bb;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-avatar-text {
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
}

.text-muted {
  font-size: 12px;
  color: #717786;
  font-family: 'Hanken Grotesk';
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  flex-shrink: 0;
  background-color: #ffffff;
}

.pagination-info {
  font-size: 13px;
  color: #717786;
  font-family: 'Hanken Grotesk';
  line-height: 18px;
}

.pagination-num {
  color: #141d23;
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
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: 'Hanken Grotesk';
  background: transparent;
  color: #141d23;
  border: 1px solid #e0e9f2;
}

.page-button:hover:not(:disabled):not(.page-button-active) {
  background-color: #ecf5fe;
  border-color: #c1c6d7;
  color: #141d23;
}

.page-button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-button-active {
  background-color: #141d23;
  color: #ffffff;
  border-color: #141d23;
}

.page-ellipsis {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 32px;
  font-size: 13px;
  color: #717786;
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
  border: 1px solid #e0e9f2;
  border-radius: 6px;
  background: #ffffff;
  color: #717786;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.action-btn:hover:not(:disabled) {
  background-color: #ecf5fe;
  border-color: #0059bb;
  color: #0059bb;
}

.action-btn.action-disabled,
.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  background: #f6faff;
}
</style>
