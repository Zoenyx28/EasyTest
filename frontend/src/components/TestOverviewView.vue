<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useApi } from '../composables/useApi';
import { useProject } from '../composables/useProject';
import type { TestModuleInfo, TestClassInfo, TestCaseInfo, TestHistoryItem } from '../types';
import CaseDetailDialog from './CaseDetailDialog.vue';

defineProps<{
  globalSearch: string;
  selectedUids?: string[];
}>();

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
  (e: 'runSelected', uids: string[]): void;
  (e: 'runAll', uids: string[]): void;
}>();

const { activeProject, getActiveProject } = useProject();

const getApi = () => useApi(activeProject.value?.id);

const modules = ref<TestModuleInfo[]>([]);
const selectedModule = ref('');
const selectedClass = ref('');
const loading = ref(false);
const syncing = ref(false);
const syncElapsed = ref('0s');
const hasTests = ref(false);
const checkedDb = ref(false);
let syncStart = 0;
let syncTimer: ReturnType<typeof setInterval> | null = null;
const selectedUids = ref<Set<string>>(new Set());
const historyMap = ref<Record<string, TestHistoryItem[]>>({});
const historyMap5 = ref<Record<string, TestHistoryItem[]>>({});
const statusMap = ref<Record<string, string>>({});

const viewedNewUids = ref<Set<string>>(new Set());
const searchQuery = ref('');
const initialLoadDone = ref(false);

const projectId = computed(() => activeProject.value?.id || 0);
const selectedCase = ref<TestCaseInfo | null>(null);
const showCaseDetail = ref(false);

function openCaseDetail(item: TestCaseInfo) {
  selectedCase.value = item;
  markViewed(item.uid);
  showCaseDetail.value = true;
}

function markViewed(uid: string) {
  if (!viewedNewUids.value.has(uid)) {
    const next = new Set(viewedNewUids.value);
    next.add(uid);
    viewedNewUids.value = next;
  }
}

function hasNewInClass(modName: string, clsName: string): boolean {
  const mod = modules.value.find(m => m.module === modName);
  const cls = mod?.classes.find(c => c.name === clsName);
  if (!cls) return false;
  return cls.items.some(i => i.isNew && !viewedNewUids.value.has(i.uid));
}

function hasNewInModule(modName: string): boolean {
  const mod = modules.value.find(m => m.module === modName);
  if (!mod) return false;
  return mod.classes.some(c => c.items.some(i => i.isNew && !viewedNewUids.value.has(i.uid)));
}

function selectedCountInClass(modName: string, clsName: string): number {
  const mod = modules.value.find(m => m.module === modName);
  const cls = mod?.classes.find(c => c.name === clsName);
  if (!cls) return 0;
  return cls.items.filter(i => selectedUids.value.has(i.uid)).length;
}

function selectedCountInModule(modName: string): number {
  const mod = modules.value.find(m => m.module === modName);
  if (!mod) return 0;
  return mod.classes.reduce((sum, c) => sum + c.items.filter(i => selectedUids.value.has(i.uid)).length, 0);
}

function modHasSelected(modName: string): boolean {
  return selectedCountInModule(modName) > 0;
}

function clsHasSelected(modName: string, clsName: string): boolean {
  return selectedCountInClass(modName, clsName) > 0;
}

async function loadTests() {
  loading.value = true;
  try {
    const { get, post } = getApi();
    const data = await get<{ modules: TestModuleInfo[]; total: number }>('/tests');
    modules.value = data.modules.map(m => ({
      ...m,
      expanded: false,
      classes: m.classes.map(c => ({ ...c, expanded: false })),
    }));
    hasTests.value = data.total > 0;
    
    const allUids: string[] = [];
    let newCaseCount = 0;
    for (const mod of modules.value) {
      for (const cls of mod.classes) {
        for (const item of cls.items) {
          allUids.push(item.uid);
          if (item.isNew) newCaseCount++;
        }
      }
    }
    
    if (allUids.length > 0) {
      try {
        const historyData = await post<Record<string, TestHistoryItem[]>>(`/tests/history`, { uids: allUids, limit: 5 });
        historyMap5.value = historyData;
      } catch { /* ignore */ }
    }
    if (data.total > 0) {
      const msg = newCaseCount > 0
        ? `获取用例成功，新增 ${newCaseCount} 条用例`
        : `获取用例成功，共 ${data.total} 条用例`;
      emit('showToast', msg);
    }
  } catch {
    emit('showToast', '无法连接后端服务，请检查服务是否启动');
  } finally {
    loading.value = false;
  }
}

async function syncTests() {
  syncing.value = true;
  syncStart = Date.now();
  syncElapsed.value = '0s';
  syncTimer = setInterval(() => {
    const sec = Math.floor((Date.now() - syncStart) / 1000);
    syncElapsed.value = sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m${sec % 60}s`;
  }, 1000);
  try {
    const { post } = getApi();
    const data = await post<{ modules: TestModuleInfo[]; total: number }>('/tests/refresh');
    modules.value = data.modules.map(m => ({
      ...m,
      expanded: false,
      classes: m.classes.map(c => ({ ...c, expanded: false })),
    }));
    viewedNewUids.value = new Set();
    hasTests.value = data.total > 0;
    
    const newStatusMap: Record<string, string> = {};
    const allUids: string[] = [];
    for (const mod of modules.value) {
      for (const cls of mod.classes) {
        for (const item of cls.items) {
          allUids.push(item.uid);
          if (item.status && item.status !== 'unknown') {
            newStatusMap[item.uid] = item.status;
          }
        }
      }
    }
    statusMap.value = newStatusMap;
    
    if (allUids.length > 0) {
      try {
        const historyData = await post<Record<string, TestHistoryItem[]>>(`/tests/history`, { uids: allUids, limit: 5 });
        historyMap5.value = historyData;
      } catch { /* ignore */ }
    }
    if (data.total > 0) {
      const newCount = data.modules.reduce(
        (sum, m) => sum + m.classes.reduce((cs, c) => cs + c.items.filter(i => (i as any).isNew).length, 0),
        0
      );
      const msg = newCount > 0
        ? `同步完成，发现 ${data.total} 个用例（${newCount} 个新增）`
        : `同步完成，发现 ${data.total} 个用例`;
      emit('showToast', msg);
    } else {
      emit('showToast', '未发现任何测试用例，请检查测试目录配置');
    }
  } catch {
    emit('showToast', '同步失败，请重试');
  } finally {
    syncing.value = false;
    if (syncTimer) { clearInterval(syncTimer); syncTimer = null; }
  }
}

async function initPage() {
  try {
    await getActiveProject();
    checkedDb.value = true;
    await loadTests();
  } catch {
    checkedDb.value = true;
    loading.value = false;
    hasTests.value = false;
  }
}

function toggleModule(moduleName: string) {
  const mod = modules.value.find(m => m.module === moduleName);
  if (!mod) return;
  mod.expanded = !mod.expanded;
  selectModule(moduleName);
}

function selectModule(moduleName: string) {
  // Mark current class as viewed when switching to module view
  if (selectedClass.value) {
    markClassViewed(selectedModule.value, selectedClass.value);
  }
  selectedModule.value = moduleName;
  selectedClass.value = '';
  historyMap.value = {};
}

function selectAll() {
  // Mark current class as viewed when switching to all tests view
  if (selectedClass.value) {
    markClassViewed(selectedModule.value, selectedClass.value);
  }
  selectedModule.value = '';
  selectedClass.value = '';
  historyMap.value = {};
}

function toggleClass(className: string) {
  for (const mod of modules.value) {
    const cls = mod.classes.find(c => c.name === className);
    if (cls) { cls.expanded = !cls.expanded; break; }
  }
}

function selectClass(moduleName: string, className: string) {
  // Mark previous class items as viewed when switching away
  if (selectedClass.value && selectedClass.value !== className) {
    markClassViewed(selectedModule.value, selectedClass.value);
  } else if (selectedModule.value && selectedModule.value !== moduleName && selectedClass.value) {
    markClassViewed(selectedModule.value, selectedClass.value);
  }
  selectedModule.value = moduleName;
  selectedClass.value = className;
  const mod = modules.value.find(m => m.module === moduleName);
  if (mod && !mod.expanded) mod.expanded = true;
  historyMap.value = {};
  loadClassHistory(moduleName, className);
}

function markClassViewed(modName: string, clsName: string) {
  if (!modName || !clsName) return;
  const mod = modules.value.find(m => m.module === modName);
  if (!mod) return;
  const cls = mod.classes.find(c => c.name === clsName);
  if (!cls) return;
  for (const item of cls.items) {
    markViewed(item.uid);
  }
}

async function loadClassHistory(moduleName: string, className: string) {
  const mod = modules.value.find(m => m.module === moduleName);
  const cls = mod?.classes.find(c => c.name === className);
  if (!cls) return;
  const uids = cls.items.map(i => i.uid);
  try {
    const { post } = getApi();
    const results = await post<Record<string, TestHistoryItem[]>>(`/tests/history`, { uids, limit: 1 });
    historyMap.value = results;
  } catch { /* ignore */ }
}

const currentClass = computed<TestClassInfo | null>(() => {
  if (!selectedModule.value || !selectedClass.value) return null;
  const mod = modules.value.find(m => m.module === selectedModule.value);
  if (!mod) return null;
  return mod.classes.find(c => c.name === selectedClass.value) || null;
});

const selectedModuleItems = computed<TestCaseInfo[]>(() => {
  if (!selectedModule.value || selectedClass.value) return [];
  const mod = modules.value.find(m => m.module === selectedModule.value);
  if (!mod) return [];
  return mod.classes.flatMap(c => c.items);
});

const allTests = computed<TestCaseInfo[]>(() => {
  return modules.value.flatMap(m => m.classes.flatMap(c => c.items));
});

// ── Pagination state ──
const currentPage = ref(1);
const pageSize = ref(50);
const pageSizes = [25, 50, 100, 200];

const filteredTests = computed<TestCaseInfo[]>(() => {
  if (selectedClass.value && currentClass.value) {
    return currentClass.value.items;
  }
  if (!selectedClass.value && selectedModule.value) {
    return selectedModuleItems.value;
  }
  return allTests.value;
});

const paginatedTests = computed<TestCaseInfo[]>(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return filteredTests.value.slice(start, end);
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredTests.value.length / pageSize.value)));

function goToPage(page: number) {
  if (page < 1) page = 1;
  if (page > totalPages.value) page = totalPages.value;
  currentPage.value = page;
}

function changePageSize(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
}

function getPageNumbers(): (number | string)[] {
  const pages: (number | string)[] = [];
  const total = totalPages.value;
  const current = currentPage.value;
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

watch([selectedModule, selectedClass, modules], () => {
  currentPage.value = 1;
});

const isAllSelected = computed(() => {
  return filteredTests.value.length > 0 && filteredTests.value.every(c => selectedUids.value.has(c.uid));
});

const filteredModules = computed(() => {
  if (!searchQuery.value) return modules.value;
  const query = searchQuery.value.toLowerCase();
  return modules.value.map(mod => ({
    ...mod,
    classes: mod.classes.filter(cls => 
      cls.name.toLowerCase().includes(query) ||
      cls.items.some(item => item.name.toLowerCase().includes(query))
    )
  })).filter(mod => mod.classes.length > 0);
});

function toggleSelectAll() {
  if (isAllSelected.value) {
    filteredTests.value.forEach(c => selectedUids.value.delete(c.uid));
  } else {
    filteredTests.value.forEach(c => selectedUids.value.add(c.uid));
  }
}

function toggleSelectRow(uid: string) {
  if (selectedUids.value.has(uid)) selectedUids.value.delete(uid);
  else selectedUids.value.add(uid);
}



const STATUS_LABELS: Record<string, string> = {
  pass: '通过', fail: '失败', broken: '异常', skip: '跳过',
};

const DOT_COLORS: Record<string, string> = {
  pass: 'var(--color-success)', fail: 'var(--red)', broken: 'var(--purple)', skip: 'var(--text-muted)',
};

interface ResultDot {
  color: string;
  hint: string;
}

function getResultDots(uid: string): ResultDot[] {
  const history = historyMap5.value[uid];
  if (!history || history.length === 0) return [];
  const items = history.slice(0, 5);
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
          color: DOT_COLORS[curStatus] || 'var(--text-tertiary)',
          hint: (STATUS_LABELS[curStatus] || curStatus) + ': ' + count,
        });
      }
      groupStart = i + 1;
    }
  }
  return dots;
}

function debugLocally(method: string) {
  emit('showToast', `调试命令: pytest -k "${method}" --pdb`);
}

function runSelected() {
  const uids = selectedUids.value.size > 0
    ? [...selectedUids.value]
    : filteredTests.value.map(i => i.uid);
  if (uids.length === 0) { emit('showToast', '请先选择要执行的用例'); return; }
  emit('runSelected', uids);
}

function runAll() {
  const uids = modules.value.flatMap(m => m.classes.flatMap(c => c.items.map(i => i.uid)));
  if (uids.length === 0) { emit('showToast', '没有可执行的用例'); return; }
  emit('runAll', uids);
}

onMounted(async () => {
  await initPage();
  initialLoadDone.value = true;
});

watch(activeProject, async () => {
  if (!initialLoadDone.value) return;
  await loadTests();
});

onUnmounted(() => {
  if (syncTimer) { clearInterval(syncTimer); syncTimer = null; }
});


function formatDuration(ms: number): string {
  if (ms < 1000) return ms + 'ms';
  return (ms / 1000).toFixed(1) + 's';
}

function chineseNameOf(item: TestCaseInfo): string {
  return item.description !== item.name ? (item.description || item.name) : item.name;
}

function formatTime(iso: string): string {
  if (!iso) return '--';
  try { return iso.substring(11, 19); } catch { return iso; }
}
</script>

<template>
  <div class="flex-1 flex min-h-0 w-full overflow-hidden macos-container">
    <!-- macOS Sidebar with traffic light dots -->
    <aside class="macos-sidebar">
      <!-- Traffic light dots -->
      <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0">
        <h3 class="sidebar-title" style="color: var(--text-primary);">测试目录</h3>
      </div>

      <!-- Search + header -->
      <div class="sidebar-header">
        <div class="search-wrapper">
          <svg class="search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索测试类"
            class="search-input"
          />
        </div>
        <!-- <div class="sidebar-section-label">
          
        </div> -->
      </div>

      <!-- Tree view -->
      <div class="sidebar-tree">
        <div v-if="!checkedDb" class="text-center py-8 text-[var(--text-tertiary)] text-sm">加载中...</div>
        <template v-else-if="!hasTests">
          <div class="flex flex-col items-center justify-center py-12 px-4">
            <span class="text-3xl mb-2" style="color: var(--text-tertiary);">▢</span>
            <p class="text-[var(--text-tertiary)] text-xs text-center">暂无测试用例</p>
          </div>
        </template>
        <template v-else>
          <!-- All tests root -->
          <div
            @click="selectAll"
            class="tree-item tree-item-root"
            :class="!selectedModule ? 'tree-item-active' : 'tree-item-hoverable'"
          >
            <svg class="tree-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="tree-item-label">tests</span>
          </div>

          <div class="tree-scroll-area">
            <template v-for="mod in filteredModules" :key="mod.module">
              <!-- Module row -->
              <div
                @click="toggleModule(mod.module)"
                class="tree-item"
                :class="modHasSelected(mod.module) ? 'tree-item-active' : 'tree-item-hoverable'"
              >
                <svg class="tree-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
                  :style="{ transform: mod.expanded ? 'rotate(90deg)' : 'rotate(0deg)' }"
                >
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
                <svg class="tree-item-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <span class="tree-item-label">{{ mod.module }}</span>
                <span v-if="hasNewInModule(mod.module)" class="badge-new">NEW</span>
                <span class="tree-item-count">{{ mod.total }}</span>
              </div>

              <!-- Classes within module -->
              <div v-if="mod.expanded" class="tree-children">
                <div
                  v-for="cls in mod.classes" :key="cls.name"
                  @click="selectClass(mod.module, cls.name)"
                  class="tree-item"
                  :class="clsHasSelected(mod.module, cls.name) || (selectedClass === cls.name && selectedModule === mod.module)
                    ? 'tree-item-active'
                    : 'tree-item-hoverable'"
                  :title="cls.name"
                >
                  <svg class="tree-item-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                  </svg>
                  <span class="tree-item-label truncate">{{ cls.name }}</span>
                  <span v-if="hasNewInClass(mod.module, cls.name)" class="badge-new">NEW</span>
                  <div class="tree-item-meta">
                    <span v-if="selectedCountInClass(mod.module, cls.name) > 0" class="selected-count">{{ selectedCountInClass(mod.module, cls.name) }} / </span>
                    <span class="tree-item-count">{{ cls.total }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </aside>

    <!-- Main content area -->
    <main class="macos-content">
      <!-- Header bar -->
      <div v-if="hasTests && !loading" class="flex justify-between items-end px-[24px] pt-[18px] pb-[10px] shrink-0" style="border-bottom: 2px solid var(--outline);">
        <div class="flex flex-col">
          <h2 class="page-title" style="color: var(--text-primary);">
            {{ selectedClass || selectedModule || 'All Tests' }}
            <span class="text-[13px] font-normal ml-[8px]" style="color: var(--text-tertiary);">({{ filteredTests.length }} cases)</span>
          </h2>
        </div>
        <div class="flex gap-[8px]">
          <button
            @click="runSelected"
            class="btn btn-secondary"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            执行选中
            <span v-if="selectedUids.size" class="selected-badge">{{ selectedUids.size }}</span>
          </button>
          <button
            @click="runAll"
            class="btn btn-primary"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            执行全部
          </button>
        </div>
      </div>

      <!-- Content area -->
      <div class="macos-content-body">
        <!-- Loading spinner -->
        <div v-if="loading" class="loading-overlay">
          <div class="loading-spinner">
            <svg class="animate-spin h-10 w-10 mb-4" style="color: var(--text-tertiary);" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="loading-text">正在拉取项目下的用例...</p>
          </div>
        </div>

        <!-- Empty state -->
        <div v-else-if="checkedDb && !hasTests" class="empty-state">
          <div class="empty-state-inner">
            <span class="empty-icon">▤</span>
            <p class="empty-text">请从左侧选择一个测试目录或测试类查看用例</p>
          </div>
        </div>

        <!-- Test case table -->
        <template v-else-if="hasTests">
          <div class="table-container">
            <table class="macos-table">
              <thead>
                <tr>
                  <th class="col-check">
                    <label class="macos-checkbox">
                      <input
                        type="checkbox"
                        :checked="isAllSelected"
                        @change="toggleSelectAll"
                      />
                      <span class="checkmark"></span>
                    </label>
                  </th>
                  <th class="text-left col-name">用例名称</th>
                  <th class="text-left col-method">方法</th>
                  <th class="text-left col-type">类型</th>
                  <th class="text-left col-result">最新结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="filteredTests.length === 0" class="empty-row">
                  <td colspan="5" class="empty-cell">没有匹配的用例</td>
                </tr>
                <template v-for="item in paginatedTests" :key="item.uid">
                  <tr class="table-row">
                    <td class="cell-check" @click.stop>
                      <label class="macos-checkbox">
                        <input
                          type="checkbox"
                          :checked="selectedUids.has(item.uid)"
                          @change="toggleSelectRow(item.uid)"
                        />
                        <span class="checkmark"></span>
                      </label>
                    </td>
                    <td class="cell-name">
                      <div class="test-name clickable" :class="item.isNew && !viewedNewUids.has(item.uid) ? 'text-new' : ''" @click="openCaseDetail(item)" :title="chineseNameOf(item)">
                        {{ item.description !== item.name ? (item.description || item.name) : item.name }}
                      </div>
                      <div v-if="item.description !== item.name && item.description" class="test-method-name">{{ item.name }}</div>
                      <span v-if="item.isNew && !viewedNewUids.has(item.uid)" class="badge-new badge-sm">NEW</span>
                    </td>
                    <td class="cell-method"><code>{{ item.methodName }}</code></td>
                    <td class="cell-type">
                      <span
                        v-if="item.testType === 'ui'"
                        class="type-badge type-ui"
                      >UI</span>
                      <span
                        v-else
                        class="type-badge type-api"
                      >API</span>
                    </td>
                    <td class="cell-result">
                      <template v-if="getResultDots(item.uid).length > 0">
                        <div class="result-dots">
                          <div
                            v-for="(dot, idx) in getResultDots(item.uid)"
                            :key="idx"
                            class="result-dot"
                            :style="{ backgroundColor: dot.color }"
                          >
                            <div class="dot-tooltip">{{ dot.hint }}</div>
                          </div>
                        </div>
                      </template>
                      <span v-else class="status-badge status-pending">未执行</span>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>

            <!-- Pagination -->
            <div v-if="totalPages > 1" class="pagination">
              <div class="pagination-info">
                <span>共 {{ filteredTests.length }} 条，{{ totalPages }} 页</span>
                <select
                  v-model="pageSize"
                  @change="changePageSize(Number(pageSize))"
                  class="page-size-select"
                >
                  <option v-for="s in pageSizes" :key="s" :value="s">{{ s }} 条/页</option>
                </select>
              </div>
              <div class="pagination-controls">
                <button
                  @click="goToPage(currentPage - 1)"
                  :disabled="currentPage <= 1"
                  class="page-btn"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="15 18 9 12 15 6"/>
                  </svg>
                </button>
                <template v-for="p in getPageNumbers()" :key="p">
                  <span v-if="p === '...'" class="page-ellipsis">…</span>
                  <button
                    v-else
                    @click="goToPage(Number(p))"
                    class="page-btn"
                    :class="p === currentPage ? 'page-btn-active' : ''"
                  >{{ p }}</button>
                </template>
                <button
                  @click="goToPage(currentPage + 1)"
                  :disabled="currentPage >= totalPages"
                  class="page-btn"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>

    <!-- Case Detail Dialog -->
    <CaseDetailDialog
      :isOpen="showCaseDetail"
      :case="selectedCase"
      :projectId="projectId"
      @close="showCaseDetail = false"
      @updated="loadTests"
      @showToast="(msg: string) => emit('showToast', msg)"
    />
  </div>
</template>

<style scoped>
/* ── macOS Container ── */
.macos-container {
  font-family: var(--font);
  letter-spacing: 0.01em;
}

/* ── macOS Sidebar ── */
.macos-sidebar {
  width: 230px;
  min-width: 230px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 40;
  min-height: 0;
  overflow: hidden;
  background-color: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  position: relative;
}

/* ── Sidebar Header ── */
.sidebar-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.sidebar-header {
  padding: 10px 10px 8px;
  border-bottom: 1px solid var(--sidebar-border);
  flex-shrink: 0;
}

.search-wrapper {
  position: relative;
  margin-bottom: 12px;
}

.search-icon {
  position: absolute;
  left: 9px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 6px 10px 6px 30px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  outline: none;
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
  font-family: inherit;
}

.search-input::placeholder {
  color: var(--text-tertiary);
}

.search-input:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.sidebar-section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 4px;
}

.sidebar-section-label span {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

/* ── Tree View ── */
.sidebar-tree {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tree-scroll-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 2px 6px 8px;
}

.tree-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12.5px;
  transition: background 0.12s ease;
  user-select: none;
  color: var(--text-primary);
  min-height: 28px;
}

.tree-item-hoverable:hover {
  background: var(--row-hover);
}

.tree-item-root {
  font-size: 11.5px;
}

.tree-item-root.tree-item-active {
  font-weight: 400;
}

.tree-item-active {
  color: var(--accent);
  font-weight: 500;
  background: var(--selected-bg);
}

.tree-chevron {
  flex-shrink: 0;
  transition: transform 0.18s ease;
  color: var(--text-tertiary);
}

.tree-item-icon {
  flex-shrink: 0;
  color: var(--text-secondary);
  opacity: 0.7;
}

.tree-item-active .tree-item-icon {
  color: var(--accent);
  opacity: 1;
}

.tree-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-item-count {
  font-size: 11.5px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-left: auto;
  padding-left: 4px;
}

.tree-item-meta {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  margin-left: auto;
}

.selected-count {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--accent);
}

.tree-children {
  margin-left: 12px;
  padding-left: 4px;
  border-left: 1px solid var(--border);
}

/* ── Badges ── */
.badge-new {
  display: inline-flex;
  align-items: center;
  padding: 1px 5px;
  background: var(--success-soft);
  color: var(--green);
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  flex-shrink: 0;
  line-height: 1.3;
}

.badge-sm {
  margin-top: 3px;
  display: inline-block;
}

/* ── Main Content ── */
.macos-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  position: relative;
  background-color: var(--content-bg);
}

/* ── 页面大标题 ── */
.page-title {
  font-family: var(--font-heading);
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

/* ── Buttons（Clay 硬阴影 + 按压） ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  font-size: 12.5px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  border: 2px solid var(--outline);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease, color 0.15s ease, filter 0.15s ease;
  font-family: inherit;
  line-height: 1.4;
  white-space: nowrap;
  box-shadow: var(--shadow-hard-sm);
}

.btn:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.btn:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
}

.btn-secondary {
  background-color: var(--color-secondary);
  color: var(--text-primary);
}

.btn-secondary:hover {
  background-color: var(--color-secondary-dark);
}

.btn-primary {
  background-color: var(--cta);
  color: #fff;
}

.btn-primary:hover {
  background-color: var(--cta-dark);
}

.selected-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.25);
  font-size: 10.5px;
  font-weight: 700;
}

/* ── Content Body ── */
.macos-content-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

/* ── Loading ── */
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--content-bg);
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-text {
  color: var(--text-secondary);
  font-size: 13px;
}

/* ── Empty State ── */
.empty-state {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 25vh;
}

.empty-state-inner {
  text-align: center;
  color: var(--text-tertiary);
}

.empty-icon {
  display: block;
  font-size: 56px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 15px;
}

/* ── Table ── */
.table-container {
  position: absolute;
  inset: 0;
  overflow: auto;
  padding: 18px 24px 16px;
}

.macos-table {
  width: 100%;
  font-size: 12.5px;
  border-collapse: collapse;
}

.macos-table thead {
  position: sticky;
  top: 0;
  z-index: 5;
}

.macos-table th {
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  padding: 10px 10px 10px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text-tertiary);
  background-color: var(--content-bg);
  white-space: nowrap;
}

.col-check { width: 32px; }
.col-name { width: auto; }
.col-method { width: 160px; }
.col-type { width: 72px; }
.col-result { width: 120px; }

/* ── macOS Checkbox ── */
.macos-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  cursor: pointer;
  width: 16px;
  height: 16px;
}

.macos-checkbox input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
  width: 0;
  height: 0;
}

.checkmark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 5px;
  border: 2px solid var(--outline);
  background: var(--card-bg);
  transition: all 0.12s ease;
  flex-shrink: 0;
}

.macos-checkbox input:checked ~ .checkmark {
  background: var(--color-primary);
  border-color: var(--outline);
}

.macos-checkbox input:checked ~ .checkmark::after {
  content: '';
  display: block;
  width: 5px;
  height: 8px;
  border: solid var(--text-primary);
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
  margin-top: -1px;
}

.macos-checkbox input:focus-visible ~ .checkmark {
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

/* ── Table Body ── */
.table-row {
  border-bottom: 1px solid var(--border);
  transition: background 0.1s ease;
}

.table-row:hover {
  background: var(--row-hover);
}

.empty-row {
  border-bottom: 1px solid var(--border);
}

.empty-cell {
  text-align: center;
  padding: 40px 8px;
  color: var(--text-tertiary);
}

.cell-check {
  padding: 8px 8px 8px 10px;
  text-align: center;
  vertical-align: middle;
}

.cell-name {
  padding: 8px 10px;
  vertical-align: middle;
}

.cell-method {
  padding: 8px 10px;
  vertical-align: middle;
}

.cell-method code {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-secondary);
}

.cell-type {
  padding: 8px 10px;
  vertical-align: middle;
}

.cell-result {
  padding: 8px 10px;
  vertical-align: middle;
  white-space: nowrap;
}

.test-name {
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.35;
}

.test-name.clickable {
  cursor: pointer;
}

.test-name.clickable:hover {
  color: var(--accent);
  text-decoration: underline;
}

.text-new {
  color: var(--green);
}

.test-method-name {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}

/* ── Type Badges ── */
.type-badge {
  display: inline-block;
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 5px;
  letter-spacing: 0.01em;
}

.type-ui {
  background: rgba(191, 90, 242, 0.14);
  color: var(--purple);
}

.type-api {
  background: var(--color-primary-soft);
  color: var(--accent);
}

/* ── Result Dots ── */
.result-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 14px;
}

.result-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  cursor: default;
}

.dot-tooltip {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 9px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.12s ease;
  z-index: 10;
}

.result-dot:hover .dot-tooltip {
  opacity: 1;
}

/* ── Status Badge ── */
.status-badge {
  display: inline-block;
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
}

.status-pending {
  background: var(--input-bg);
  color: var(--text-secondary);
}

/* ── Pagination ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 4px 8px;
}

.pagination-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
  color: var(--text-secondary);
}

.page-size-select {
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  font-family: inherit;
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  outline: none;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.page-size-select:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 3px;
}

.page-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 28px;
  padding: 0 8px;
  font-size: 12.5px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease, color 0.15s ease;
  font-family: inherit;
  background: var(--card-bg-2);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
}

.page-btn:hover:not(:disabled):not(.page-btn-active) {
  background: var(--bg-card-hover);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-btn-active {
  background: var(--color-primary);
  color: var(--text-primary);
  font-weight: 600;
  border-color: var(--outline);
}

.page-btn-active:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.page-ellipsis {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 28px;
  font-size: 13px;
  color: var(--text-tertiary);
  letter-spacing: 1px;
}
</style>