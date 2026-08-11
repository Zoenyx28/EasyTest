<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useApi } from '../composables/useApi';
import BaseDialog from './base/BaseDialog.vue';
import BaseButton from './base/BaseButton.vue';
import BaseInput from './base/BaseInput.vue';
import BaseTag from './base/BaseTag.vue';
import ConfirmDialog from './ConfirmDialog.vue';
import RequirementDetailPanel from './RequirementDetailPanel.vue';
import type { RequirementInfo } from '../types';

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
}>();

const { activeProject, getActiveProject } = useProject();
const { activeBranch, loadBranches } = useBranch(activeProject.value?.id);
const { get, post, del, postFormData } = useApi();

// ── 状态元信息 ──
const STATUS_META: Record<string, { label: string; tone: 'yellow' | 'blue' | 'purple' | 'green' }> = {
  pending_review: { label: '待评审', tone: 'yellow' },
  review_passed: { label: '评审通过', tone: 'blue' },
  story_confirmed: { label: 'Story 已确认', tone: 'purple' },
  cases_generated: { label: '用例已生成', tone: 'green' },
  done: { label: '已完成', tone: 'green' },
};

function statusLabel(s: string): string {
  return STATUS_META[s]?.label ?? s;
}
function statusTone(s: string): 'yellow' | 'blue' | 'purple' | 'green' | 'gray' {
  return STATUS_META[s]?.tone ?? 'gray';
}
function priorityTone(p: string): 'red' | 'orange' | 'green' {
  if (p === 'P0') return 'red';
  if (p === 'P1') return 'orange';
  return 'green';
}

// ── 列表 ──
const requirements = ref<RequirementInfo[]>([]);
const loading = ref(false);
const statusFilter = ref('');

const filterTabs = [
  { key: '', label: '全部' },
  { key: 'pending_review', label: '待评审' },
  { key: 'review_passed', label: '评审通过' },
  { key: 'story_confirmed', label: 'Story 已确认' },
  { key: 'cases_generated', label: '用例已生成' },
  { key: 'done', label: '已完成' },
];

const filtered = computed(() => {
  if (!statusFilter.value) return requirements.value;
  return requirements.value.filter((r) => r.status === statusFilter.value);
});

function formatTime(iso: string): string {
  if (!iso) return '--';
  return iso.substring(0, 16).replace('T', ' ');
}

async function loadRequirements() {
  const pid = activeProject.value?.id;
  const bid = activeBranch.value?.id;
  if (!pid || !bid) {
    requirements.value = [];
    return;
  }
  loading.value = true;
  try {
    requirements.value = await get<RequirementInfo[]>(`/requirements?branch_id=${bid}&project_id=${pid}`);
  } catch (e) {
    requirements.value = [];
    emit('showToast', (e as Error).message || '需求列表加载失败');
  } finally {
    loading.value = false;
  }
}

watch([activeProject, activeBranch], () => {
  if (activeProject.value?.id) loadBranches(activeProject.value.id);
  loadRequirements();
});

onMounted(async () => {
  if (!activeProject.value?.id) await getActiveProject();
  if (activeProject.value?.id) loadBranches(activeProject.value.id);
  loadRequirements();
});

// ── 新建需求弹窗 ──
interface PendingSource {
  kind: 'link' | 'file';
  label: string;
  file?: File;
  status: 'pending' | 'ok' | 'fail';
  error: string;
}

const showCreateModal = ref(false);
const creating = ref(false);
const createForm = ref({ title: '' });
const linkInput = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);
const pendingSources = ref<PendingSource[]>([]);

function openCreate() {
  createForm.value.title = '';
  linkInput.value = '';
  pendingSources.value = [];
  showCreateModal.value = true;
}

function closeCreate() {
  if (creating.value) return;
  showCreateModal.value = false;
}

function addLink() {
  const link = linkInput.value.trim();
  if (!link) {
    emit('showToast', '请输入飞书文档链接');
    return;
  }
  pendingSources.value.push({ kind: 'link', label: link, status: 'pending', error: '' });
  linkInput.value = '';
}

function onFileSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  pendingSources.value.push({ kind: 'file', label: file.name, file, status: 'pending', error: '' });
  input.value = '';
}

function removePending(i: number) {
  pendingSources.value.splice(i, 1);
}

async function createRequirement() {
  const pid = activeProject.value?.id;
  const bid = activeBranch.value?.id;
  const title = createForm.value.title.trim();
  if (!title) {
    emit('showToast', '请输入需求标题');
    return;
  }
  if (!pid || !bid) {
    emit('showToast', '请先选择项目与分支');
    return;
  }
  creating.value = true;
  try {
    const { id } = await post<{ id: number }>('/requirements', {
      project_id: pid,
      branch_id: bid,
      title,
    });
    // 逐个提交来源
    for (const s of pendingSources.value) {
      try {
        if (s.kind === 'link') {
          const res = await post<{ extracted: boolean; extract_error: string }>(
            `/requirements/${id}/sources`,
            { type: 'lark_link', link: s.label },
          );
          s.status = 'ok';
          s.error = res.extracted ? '' : res.extract_error || '正文提取失败';
        } else {
          const fd = new FormData();
          if (s.file) fd.append('file', s.file);
          await postFormData(`/requirements/${id}/sources/upload`, fd);
          s.status = 'ok';
        }
      } catch (err) {
        s.status = 'fail';
        s.error = (err as Error).message || '来源添加失败';
      }
    }
    emit('showToast', '需求创建成功');
    showCreateModal.value = false;
    loadRequirements();
  } catch (e) {
    emit('showToast', (e as Error).message || '需求创建失败');
  } finally {
    creating.value = false;
  }
}

// ── 详情弹窗（三步流程面板，RequirementDetailPanel） ──
const detailReqId = ref<number | null>(null);

function openDetail(r: RequirementInfo) {
  detailReqId.value = r.id;
}

function closeDetail() {
  detailReqId.value = null;
}

// ── 删除需求 ──
const confirmDialog = ref<InstanceType<typeof ConfirmDialog> | null>(null);

async function confirmDelete(r: RequirementInfo) {
  const ok = await confirmDialog.value?.confirm({
    title: '确认删除需求',
    message: `删除需求「${r.title}」将同时删除其全部来源、评审记录、Story、用例及自动化用例绑定，且不可撤销。`,
    confirmText: '确认删除',
    confirmColor: 'var(--color-danger)',
  });
  if (!ok) return;
  try {
    await del(`/requirements/${r.id}`);
    emit('showToast', '需求已删除');
    if (detailReqId.value === r.id) closeDetail();
    loadRequirements();
  } catch (e) {
    emit('showToast', (e as Error).message || '需求删除失败');
  }
}
</script>

<template>
  <div class="req-page">
    <!-- 页面标题行 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">需求管理</h2>
        <p class="page-sub">
          项目：{{ activeProject?.name || '未选择' }} · 分支：{{ activeBranch?.name || 'main' }}
          · 共 {{ requirements.length }} 条
        </p>
      </div>
      <BaseButton variant="primary" size="md" @click="openCreate">＋ 新建需求</BaseButton>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <div class="filter-pill">
        <button
          v-for="tab in filterTabs"
          :key="tab.key"
          class="filter-tab"
          :class="{ 'filter-tab--active': statusFilter === tab.key }"
          @click="statusFilter = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- 需求列表 -->
    <div class="req-list">
      <div v-if="loading" class="empty-state">加载中…</div>
      <template v-else-if="filtered.length">
        <div v-for="r in filtered" :key="r.id" class="req-card" @click="openDetail(r)">
          <div class="req-card__main">
            <div class="req-card__title-row">
              <span class="req-card__title">{{ r.title }}</span>
              <BaseTag :tone="priorityTone(r.priority)" size="md">优先级 {{ r.priority }}</BaseTag>
              <BaseTag :tone="statusTone(r.status)" size="md">{{ statusLabel(r.status) }}</BaseTag>
              <BaseTag v-if="r.latest_review?.low_score" tone="red" size="md" dot>建议重新评审</BaseTag>
            </div>
            <p v-if="r.summary" class="req-card__summary">{{ r.summary }}</p>
            <div class="req-card__meta">
              <span>创建人：{{ r.creator_name || '--' }}</span>
              <span>来源 {{ r.source_count }}</span>
              <span>评审 {{ r.review_count }}</span>
              <span>Story {{ r.story_count }}</span>
              <span>用例 {{ r.case_count }}</span>
              <span v-if="r.latest_review">评分 {{ r.latest_review.score }}/100</span>
              <span>{{ formatTime(r.updated_at) }}</span>
            </div>
          </div>
          <div class="req-card__ops" @click.stop>
            <BaseButton variant="ghost" size="sm" @click="confirmDelete(r)">删除</BaseButton>
          </div>
        </div>
      </template>
      <div v-else class="empty-state">
        <div class="empty-icon">📋</div>
        <p>暂无需求，点击右上角「新建需求」开始</p>
      </div>
    </div>

    <!-- 新建需求弹窗 -->
    <BaseDialog :open="showCreateModal" title="新建需求" :width="560" @close="closeCreate">
      <div class="modal-body">
        <label class="field-label">需求标题</label>
        <BaseInput
          v-model="createForm.title"
          type="text"
          placeholder="请输入需求标题"
          @enter="createRequirement"
        />

        <label class="field-label mt-4">添加来源（可选，飞书链接 / 文件）</label>
        <div class="link-row">
          <BaseInput v-model="linkInput" type="text" placeholder="粘贴飞书文档链接" @enter="addLink" />
          <BaseButton variant="secondary" size="sm" @click="addLink">添加链接</BaseButton>
        </div>
        <div class="file-row">
          <input ref="fileInputRef" type="file" hidden @change="onFileSelected" />
          <BaseButton variant="secondary" size="sm" @click="fileInputRef?.click()">选择文件</BaseButton>
          <span class="file-hint">支持 txt / md / json / doc / docx / pdf / 图片</span>
        </div>

        <div v-if="pendingSources.length" class="pending-list">
          <div v-for="(s, i) in pendingSources" :key="i" class="pending-item">
            <span class="pending-label">{{ s.label }}</span>
            <span v-if="s.status === 'ok'" class="pending-ok">✓ 已添加</span>
            <span v-else-if="s.status === 'fail'" class="pending-fail">{{ s.error }}</span>
            <span v-else class="pending-wait">待提交</span>
            <button class="pending-remove" @click="removePending(i)">×</button>
          </div>
        </div>
      </div>

      <template #footer>
        <BaseButton variant="secondary" :disabled="creating" @click="closeCreate">取消</BaseButton>
        <BaseButton variant="primary" :loading="creating" :disabled="!createForm.title.trim()" @click="createRequirement">
          创建
        </BaseButton>
      </template>
    </BaseDialog>

    <!-- 详情弹窗：三步流程面板 -->
    <RequirementDetailPanel
      :open="!!detailReqId"
      :req-id="detailReqId"
      @close="closeDetail"
      @saved="loadRequirements"
      @show-toast="(msg: string) => emit('showToast', msg)"
    />

    <ConfirmDialog ref="confirmDialog" />
  </div>
</template>

<style scoped>
.req-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 20px;
}

/* ── 标题行 ── */
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0 0 16px;
}
.page-title {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.page-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin: 4px 0 0;
}

/* ── 状态筛选 ── */
.filter-bar {
  padding-bottom: 14px;
}
.filter-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: var(--radius-sm);
  background-color: var(--input-bg);
}
.filter-tab {
  padding: 5px 14px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
  border: 2px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.filter-tab:hover {
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
}
.filter-tab--active {
  background-color: var(--color-primary);
  border-color: var(--outline);
  color: var(--text-primary);
  font-weight: 600;
  box-shadow: var(--shadow-hard-sm);
}
.filter-tab--active:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

/* ── 列表 ── */
.req-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.req-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background-color: var(--card-bg);
  border: 2px solid var(--outline);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-hard-sm);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}
.req-card:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
  background-color: var(--card-hover-bg);
}
.req-card__main {
  flex: 1;
  min-width: 0;
}
.req-card__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.req-card__title {
  font-family: var(--font-heading);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.req-card__summary {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}
.req-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}
.req-card__ops {
  flex-shrink: 0;
}

/* ── 空状态 ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px 0;
  color: var(--text-muted);
  font-size: 12px;
}
.empty-icon {
  font-size: 28px;
  opacity: 0.3;
}

/* ── 弹窗内容 ── */
.modal-body {
  padding: 16px 20px;
}
.field-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.mt-4 {
  margin-top: 16px;
}
.link-row {
  display: flex;
  gap: 8px;
}
.file-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.file-hint {
  font-size: 11px;
  color: var(--text-muted);
}
.pending-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pending-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background-color: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.pending-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}
.pending-ok {
  color: var(--color-success);
  font-size: 11px;
}
.pending-fail {
  color: var(--color-danger);
  font-size: 11px;
}
.pending-wait {
  color: var(--text-muted);
  font-size: 11px;
}
.pending-remove {
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
}
.pending-remove:hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}
</style>
