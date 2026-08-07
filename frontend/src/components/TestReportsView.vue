<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useApi } from '../composables/useApi';
import { useProject } from '../composables/useProject';
import BaseTag from './base/BaseTag.vue';
import type { ReportListSummary, HistoryReport, ReportSummary, HistoryReportResult } from '../types';

defineProps<{
  globalSearch: string;
  selectedUids?: string[];
}>();

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
  (e: 'rerun', uids: string[]): void;
}>();

const { activeProject, getActiveProject } = useProject();

const getApi = () => useApi(activeProject.value?.id);

const reportList = ref<ReportListSummary[]>([]);
const selectedIndex = ref(-1);
const report = ref<HistoryReport | null>(null);
const loading = ref(false);
const expandedFullName = ref('');
const expandedModules = ref<Record<string, boolean>>({});

async function loadReportList() {
  try {
    const { get } = getApi();
    const projectId = activeProject.value?.id;
    const url = projectId ? `/reports?project_id=${projectId}` : '/reports';
    const result = await get<{ items: ReportListSummary[]; total: number; page: number; pages: number }>(url);
    reportList.value = result.items || [];
  } catch {
    // no reports yet
  }
}

async function selectReport(reportId: number) {
  selectedIndex.value = reportId;
  loading.value = true;
  expandedFullName.value = '';
  expandedModules.value = {};
  try {
    const { get } = getApi();
    report.value = await get<HistoryReport>(`/reports/${reportId}`);
  } catch {
    report.value = null;
    emit('showToast', '加载报告失败');
  }
  loading.value = false;
}

async function deleteReport(reportId: number) {
  try {
    const { del } = getApi();
    await del(`/reports/${reportId}`);
    if (selectedIndex.value === reportId) {
      selectedIndex.value = -1;
      report.value = null;
    }
    emit('showToast', '报告已删除');
    loadReportList();
  } catch { /* ignore */ }
}

async function initPage() {
  await getActiveProject();
  await loadReportList();
}

onMounted(() => {
  initPage();
});

watch(activeProject, () => {
  loadReportList();
});

const passRateLabel = computed(() => {
  if (!report.value) return 'bad';
  const r = report.value.summary.passRate;
  return r >= 80 ? 'good' : r >= 50 ? 'warn' : 'bad';
});

const groupedResults = computed(() => {
  if (!report.value) return [];
  const groups: Record<string, Record<string, HistoryReportResult[]>> = {};
  for (const r of report.value.results) {
    const parts = r.fullName.split('.');
    const mod = parts.length >= 3 ? parts[parts.length - 3] : 'unknown';
    let cls = parts[parts.length - 1];
    if (cls.includes('#')) cls = cls.split('#')[0];
    else if (parts.length >= 2) cls = parts[parts.length - 2];
    if (!groups[mod]) groups[mod] = {};
    if (!groups[mod][cls]) groups[mod][cls] = [];
    groups[mod][cls].push(r);
  }
  const result: { module: string; classes: { name: string; items: HistoryReportResult[]; total: number; passed: number; failed: number }[] }[] = [];
  for (const mod of Object.keys(groups).sort()) {
    const classes = [];
    for (const cls of Object.keys(groups[mod]).sort()) {
      const items = groups[mod][cls];
      classes.push({
        name: cls,
        items,
        total: items.length,
        passed: items.filter(i => i.status === 'passed').length,
        failed: items.filter(i => i.status === 'failed').length,
      });
    }
    result.push({ module: mod, classes });
  }
  return result;
});

function toggleModule(moduleName: string) {
  expandedModules.value[moduleName] = !expandedModules.value[moduleName];
}

function expandAll() {
  for (const g of groupedResults.value) {
    expandedModules.value[g.module] = true;
  }
  emit('showToast', '已展开所有模块层级');
}

function collapseAll() {
  expandedModules.value = {};
  emit('showToast', '已折叠所有模块层级');
}

function rerunReport() {
  if (!report.value) return;
  const uids = report.value.results.map((r: any) => r.uid);
  emit('rerun', uids);
}

function extractMName(fullName: string): string {
  const parts = fullName.split('.');
  let last = parts[parts.length - 1];
  return last.includes('#') ? last.split('#')[1] : last;
}

const STATUS_LABELS: Record<string, string> = {
  passed: '通过', failed: '失败', broken: '异常', skipped: '跳过', xfailed: '预期失败',
};
</script>

<template>
  <div class="flex-1 flex min-h-0 w-full overflow-hidden">
    <aside 
      class="w-[230px] flex flex-col shrink-0 min-h-0"
      style="background-color: var(--sidebar-bg); border-right: 1px solid var(--sidebar-border);"
    >
      <div class="p-[14px] px-[10px] border-b" style="border-color: var(--sidebar-border);">
        <div class="flex justify-between items-center">
          <h3 class="text-[15px] font-semibold tracking-[-0.01em]" style="color: var(--text-primary);">历史报告</h3>
          <button
            @click="loadReportList()"
            class="text-[12px] cursor-pointer transition-colors"
            style="color: var(--text-tertiary);"
            title="刷新"
          >
            ↻
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-[10px] space-y-[6px] select-none">
        <div v-if="reportList.length === 0" class="text-center py-8 text-[var(--text-tertiary)] text-xs">
          暂无历史报告<br/>请先执行测试
        </div>
        <div
          v-for="rep in reportList"
          :key="rep.index"
          @click="selectReport(rep.index)"
          class="group p-[9px_11px] rounded-[10px] cursor-pointer transition-all border relative"
          :class="[
            selectedIndex === rep.index
              ? 'border-[var(--accent)]'
              : 'border-transparent hover:bg-[var(--row-hover)]'
          ]"
          :style="selectedIndex === rep.index ? { backgroundColor: 'var(--selected-bg)' } : {}"
        >
          <div class="flex items-center justify-between">
            <div class="text-[12.5px] font-medium" style="color: var(--text-primary);">
              {{ rep.timestamp?.substring(0, 16) || '--' }}
            </div>
            <button
              @click.stop="deleteReport(rep.index)"
              class="opacity-0 group-hover:opacity-100 text-[14px] leading-none px-1 rounded transition-all cursor-pointer"
              style="color: var(--text-tertiary);"
              @mouseenter="($event.currentTarget as HTMLElement).style.color = 'var(--red)'"
              @mouseleave="($event.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)'"
              title="删除报告"
            >
              &times;
            </button>
          </div>
          <div class="flex justify-between items-center mt-[3px]">
            <span class="text-[11px]" style="color: var(--text-tertiary);">
              #{{ rep.index }} · {{ rep.passed }}/{{ rep.total }} 通过
            </span>
            <span
              class="text-[10.5px] font-semibold px-2 py-[1px] rounded-full"
              :class="{
                'bg-[var(--green)]/16 text-[var(--color-success)]': rep.passRate >= 80,
                'bg-[var(--amber)]/16 text-[var(--amber)]': rep.passRate >= 50 && rep.passRate < 80,
                'bg-[var(--red)]/15 text-[var(--red)]': rep.passRate < 50
              }"
            >
              {{ rep.passRate }}% PASS
            </span>
          </div>
        </div>
      </div>
    </aside>

    <main class="flex-1 flex flex-col min-h-0 overflow-hidden" style="background-color: var(--content-bg);">
      <div class="flex-1 min-h-0 overflow-y-auto p-[20px_24px]">
        <div v-if="!report && !loading" class="flex items-center justify-center h-full" style="color: var(--text-tertiary);">
          <div class="text-center">
            <span class="text-6xl block mb-4">▢</span>
            <p class="text-lg">请从左侧选择一个报告查看详情</p>
          </div>
        </div>

        <div v-if="loading" class="text-center py-8" style="color: var(--text-tertiary);">加载报告中...</div>

        <template v-if="report">
          <div class="space-y-[16px]">
            <div 
              class="flex items-center gap-[30px] p-[18px_24px] rounded-[12px] border"
              style="background-color: var(--card-bg-2); border-color: var(--border);"
            >
              <div class="w-[80px] h-[80px] relative shrink-0">
                <svg width="80" height="80" class="transform -rotate-90">
                  <circle cx="40" cy="40" r="34" stroke="var(--input-bg)" stroke-width="7" fill="none"/>
                  <circle
                    cx="40" cy="40" r="34" fill="none" stroke-width="7"
                    :class="{
                      'stroke-[var(--green)]': passRateLabel === 'good',
                      'stroke-[var(--amber)]': passRateLabel === 'warn',
                      'stroke-[var(--red)]': passRateLabel === 'bad'
                    }"
                    :stroke-dasharray="214"
                    :stroke-dashoffset="214 * (1 - report.summary.passRate / 100)"
                    stroke-linecap="round"
                  ></circle>
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="text-[17px] font-bold" style="color: var(--text-primary);">{{ report.summary.passRate }}%</span>
                  <span class="text-[9.5px]" style="color: var(--text-tertiary);">PASS RATE</span>
                </div>
              </div>

              <div class="grid grid-cols-4 gap-[28px] text-[12px]" style="color: var(--text-tertiary);">
                <div>
                  <div class="text-[13px] font-semibold mt-[2px]" style="color: var(--text-primary);">{{ report.timestamp || '--' }}</div>
                </div>
                <div>
                  <div class="text-[13px] font-semibold mt-[2px]" style="color: var(--text-primary);">{{ report.summary.host || '--' }}</div>
                </div>
                <div>
                  <div class="text-[13px] font-semibold mt-[2px]" style="color: var(--text-primary);">{{ report.summary.totalDuration || '--' }}</div>
                </div>
                <div>
                  <div class="text-[13px] font-semibold mt-[2px]" style="color: var(--text-primary);">{{ report.summary.generatedAt || '--' }}</div>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-4 gap-[10px]">
              <div 
                class="p-[12px_14px] rounded-[10px] border"
                style="background-color: var(--card-bg-2); border-color: var(--border);"
              >
                <div class="text-[22px] font-semibold" style="color: var(--text-primary);">{{ report.summary.total }}</div>
                <div class="text-[11.5px]" style="color: var(--text-tertiary);">TOTAL</div>
              </div>
              <div 
                class="p-[12px_14px] rounded-[10px] border"
                style="background-color: var(--card-bg-2); border-color: var(--border);"
              >
                <div class="text-[22px] font-semibold" style="color: #2AA84A;">{{ report.summary.passed }}</div>
                <div class="text-[11.5px]" style="color: var(--text-tertiary);">通过 · {{ report.summary.total > 0 ? Math.round(report.summary.passed / report.summary.total * 100) : 0 }}%</div>
              </div>
              <div 
                class="p-[12px_14px] rounded-[10px] border"
                style="background-color: var(--card-bg-2); border-color: var(--border);"
              >
                <div class="text-[22px] font-semibold" style="color: var(--red);">{{ report.summary.failed }}</div>
                <div class="text-[11.5px]" style="color: var(--text-tertiary);">失败 · {{ report.summary.total > 0 ? Math.round(report.summary.failed / report.summary.total * 100) : 0 }}%</div>
              </div>
              <div 
                class="p-[12px_14px] rounded-[10px] border"
                style="background-color: var(--card-bg-2); border-color: var(--border);"
              >
                <div class="text-[22px] font-semibold" style="color: var(--purple);">{{ report.summary.broken }}</div>
                <div class="text-[11.5px]" style="color: var(--text-tertiary);">异常 · {{ report.summary.total > 0 ? Math.round(report.summary.broken / report.summary.total * 100) : 0 }}%</div>
              </div>
            </div>

            <div class="flex justify-end gap-2">
              <button
                @click="rerunReport"
                class="px-4 py-1.5 text-sm font-semibold rounded flex items-center gap-2 cursor-pointer transition-colors"
                style="background-color: var(--accent); color: #fff;"
              >
                ↻ 重新执行
              </button>
            </div>

            <div 
              class="border rounded-[12px] overflow-hidden"
              style="border-color: var(--border);"
            >
              <div 
                class="px-[14px] py-[10px] border-b flex justify-between items-center"
                style="background-color: var(--card-bg-2); border-color: var(--border);"
              >
                <h3 class="text-[13.5px] font-semibold" style="color: var(--text-primary);">Test Results Details</h3>
                <span class="text-[11.5px]" style="color: var(--text-tertiary);">Expand all · Collapse all</span>
              </div>

              <div v-if="groupedResults.length === 0" class="text-center py-8 text-[var(--text-tertiary)] text-xs">
                {{ report.results.length === 0 ? '暂无测试结果数据' : '无法解析报告数据' }}
              </div>

              <div v-else>
                <div
                  v-for="mod in groupedResults"
                  :key="mod.module"
                >
                  <div
                    class="flex items-center justify-between px-[14px] py-[10px] border-b cursor-pointer transition-colors"
                    :class="{ 'bg-[var(--card-bg-2)]': true }"
                    :style="{ borderColor: 'var(--border)' }"
                    @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--row-hover)'"
                    @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--card-bg-2)'"
                    @click="toggleModule(mod.module)"
                  >
                    <div class="text-[12.5px] font-medium" style="color: var(--text-primary);">
                      {{ expandedModules[mod.module] ? '▾' : '▸' }} {{ mod.module }}
                    </div>
                    <span 
                      class="text-[10.5px] font-semibold px-2 py-[2px] rounded-full"
                      style="background: var(--input-bg); color: var(--text-secondary);"
                    >
                      {{ mod.classes.reduce((s, c) => s + c.passed, 0) }} 通过 · {{ mod.classes.reduce((s, c) => s + c.total, 0) }} cases
                    </span>
                  </div>

                  <template v-if="expandedModules[mod.module]">
                    <template v-for="cls in mod.classes" :key="cls.name">
                      <div
                        class="flex items-center justify-between px-[14px] py-[10px] border-b"
                        :style="{ borderColor: 'var(--border)', paddingLeft: '26px' }"
                      >
                        <div class="text-[12.5px]" style="color: var(--text-primary);">{ } {{ cls.name }}</div>
                        <span class="text-[11.5px]" style="color: var(--text-tertiary);">{{ cls.passed }} / {{ cls.total }}</span>
                      </div>

                      <div
                        v-for="item in cls.items"
                        :key="item.fullName"
                        class="flex items-center justify-between px-[14px] py-[10px] border-b cursor-pointer transition-colors"
                        :style="{ borderColor: 'var(--border)', paddingLeft: '40px' }"
                        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--row-hover)'"
                        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = ''"
                        @click="expandedFullName = expandedFullName === item.fullName ? '' : item.fullName"
                      >
                        <div>
                          <div class="text-[12.5px]" style="color: var(--text-primary);">{{ extractMName(item.fullName) }}</div>
                          <div class="text-[11px] font-code mt-[1px]" style="color: var(--text-tertiary);">{{ item.fullName }}</div>
                        </div>
                        <BaseTag
                          size="sm"
                          :tone="item.status === 'passed' ? 'green' : item.status === 'failed' ? 'red' : item.status === 'broken' ? 'purple' : 'gray'"
                        >
                          {{ STATUS_LABELS[item.status] || item.status }}
                        </BaseTag>
                      </div>
                    </template>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>