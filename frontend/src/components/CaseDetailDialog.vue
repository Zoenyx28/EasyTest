<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { useApi } from '../composables/useApi';
import { useDefect } from '../composables/useDefect';
import type { TestCaseInfo, DefectInfo } from '../types';

const props = defineProps<{
  isOpen: boolean;
  case: TestCaseInfo | null;
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'updated'): void;
  (e: 'showToast', msg: string): void;
}>();

const api = useApi(props.projectId);
const defectApi = useDefect(props.projectId);

const relatedBugs = ref<DefectInfo[]>([]);
const bugsLoading = ref(false);
const isEditing = ref(false);
const saving = ref(false);

// Edit form state
const editDescription = ref('');
const editSteps = ref('');
const editModule = ref('');

const caseDisplay = computed<TestCaseInfo | null>(() => props.case);

const chineseName = computed(() => {
  const c = props.case;
  if (!c) return '';
  return c.description && c.description !== c.name ? c.description : c.name;
});

interface StepItem {
  type?: string;
  description?: string;
  code?: string;
}

const parsedSteps = computed<StepItem[]>(() => {
  const c = props.case;
  if (!c || !c.steps) return [];
  try {
    const parsed = JSON.parse(c.steps);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
});

const methodName = computed(() => {
  const c = props.case;
  if (!c) return '';
  return c.methodName || c.name || '';
});

const statusColors: Record<string, string> = {
  unconfirmed: 'var(--border)', confirmed: 'var(--status-confirmed-bg)', in_progress: 'var(--status-in-progress-bg)',
  resolved: 'var(--status-resolved-bg)', closed: 'var(--border)',
};
const statusTextColors: Record<string, string> = {
  unconfirmed: 'var(--text-secondary)', confirmed: 'var(--status-confirmed-text)', in_progress: 'var(--status-in-progress-text)',
  resolved: 'var(--status-resolved-text)', closed: 'var(--text-secondary)',
};
const statusLabels: Record<string, string> = {
  unconfirmed: '未确认', confirmed: '已确认', in_progress: '处理中', resolved: '已解决', closed: '已关闭',
};

async function loadRelatedBugs() {
  const c = props.case;
  if (!c || !props.projectId) {
    relatedBugs.value = [];
    return;
  }
  bugsLoading.value = true;
  try {
    relatedBugs.value = await defectApi.getDefectsByCase(props.projectId, c.uid);
  } catch {
    relatedBugs.value = [];
  } finally {
    bugsLoading.value = false;
  }
}

function enterEditMode() {
  const c = props.case;
  if (!c) return;
  editDescription.value = c.description || '';
  editSteps.value = c.steps || '';
  editModule.value = c.module || '';
  isEditing.value = true;
}

function cancelEdit() {
  isEditing.value = false;
}

async function handleSave() {
  const c = props.case;
  if (!c) return;
  saving.value = true;
  try {
    const payload: Record<string, string> = {
      description: editDescription.value,
      steps: editSteps.value,
      module: editModule.value,
    };
    await api.put(`/tests/${c.uid}`, payload);
    isEditing.value = false;
    emit('updated');
    emit('showToast', '用例保存成功');
  } catch (e: any) {
    emit('showToast', e.message || '保存失败');
  } finally {
    saving.value = false;
  }
}

function handleClose() {
  isEditing.value = false;
  relatedBugs.value = [];
  emit('close');
}

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    isEditing.value = false;
    loadRelatedBugs();
  }
});

watch(() => props.case, () => {
  if (props.isOpen) {
    isEditing.value = false;
    loadRelatedBugs();
  }
});

function formatTime(iso: string): string {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen && caseDisplay" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog-container large">
        <div class="dialog-header">
          <h2 class="dialog-title">用例详情</h2>
          <div class="header-actions">
            <button
              v-if="!isEditing"
              class="btn btn-edit"
              @click="enterEditMode"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
              编辑
            </button>
            <button class="dialog-close-btn" @click="handleClose">×</button>
          </div>
        </div>

        <div class="dialog-body">
          <!-- 中文名称 -->
          <div class="info-section">
            <label class="info-label">用例名称</label>
            <template v-if="isEditing">
              <input v-model="editDescription" class="form-input title-input" placeholder="请输入中文用例名称" />
            </template>
            <template v-else>
              <span class="title-text">{{ chineseName }}</span>
            </template>
          </div>

          <!-- 方法 -->
          <div class="info-section">
            <label class="info-label">方法</label>
            <div class="info-content">
              <code class="method-code">{{ methodName }}</code>
            </div>
          </div>

          <!-- 模块 -->
          <div class="info-section">
            <label class="info-label">所属模块</label>
            <template v-if="isEditing">
              <input v-model="editModule" class="form-input" placeholder="请输入模块名称" />
            </template>
            <template v-else>
              <span class="text-muted">{{ caseDisplay.module || '--' }}</span>
            </template>
          </div>

          <!-- Mark 信息 -->
          <div class="info-section">
            <label class="info-label">Mark 信息</label>
            <div v-if="caseDisplay.tags && caseDisplay.tags.length > 0" class="tags-list">
              <span v-for="tag in caseDisplay.tags" :key="tag" class="tag-badge">{{ tag }}</span>
            </div>
            <span v-else class="text-muted">--</span>
          </div>

          <!-- 步骤 -->
          <div class="info-section">
            <label class="info-label">用例步骤</label>
            <template v-if="isEditing">
              <textarea v-model="editSteps" class="form-textarea" rows="8" placeholder="请输入用例步骤"></textarea>
            </template>
            <template v-else>
              <div v-if="parsedSteps.length > 0" class="steps-list">
                <div v-for="(step, idx) in parsedSteps" :key="idx" class="step-item">
                  <span class="step-index">{{ idx + 1 }}.</span>
                  <div class="step-content">
                    <span class="step-desc">{{ step.description }}</span>
                    <code v-if="step.code" class="step-code">{{ step.code }}</code>
                  </div>
                </div>
              </div>
              <div v-else class="info-content markdown-content">{{ caseDisplay.steps || '暂无步骤' }}</div>
            </template>
          </div>

          <!-- 相关 Bug -->
          <div class="info-section">
            <label class="info-label">相关 Bug</label>
            <div v-if="bugsLoading" class="text-muted">加载中...</div>
            <div v-else-if="relatedBugs.length === 0" class="text-muted">暂无关联缺陷</div>
            <div v-else class="bugs-list">
              <div v-for="bug in relatedBugs" :key="bug.id" class="bug-item">
                <span class="bug-id">#{{ bug.id }}</span>
                <span
                  class="status-badge-status"
                  :style="{
                    backgroundColor: statusColors[bug.status] || 'var(--border)',
                    color: statusTextColors[bug.status] || 'var(--text-secondary)',
                  }"
                >{{ statusLabels[bug.status] || bug.status }}</span>
                <span class="bug-title">{{ bug.title }}</span>
                <span v-if="bug.severity" class="bug-severity">{{ bug.severity }}</span>
                <span class="bug-time">{{ formatTime(bug.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="dialog-footer">
          <template v-if="isEditing">
            <button class="btn btn-cancel" @click="cancelEdit" :disabled="saving">取消</button>
            <button class="btn btn-save" @click="handleSave" :disabled="saving">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </template>
          <template v-else>
            <button class="btn btn-cancel" @click="handleClose">关闭</button>
          </template>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}
.dialog-container {
  width: 680px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background-color: var(--bg-card);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}
.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.dialog-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  font-family: var(--font);
}
.dialog-close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 20px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.dialog-close-btn:hover {
  background: var(--color-primary-soft);
  color: var(--text-primary);
}
.btn-edit {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font);
  background-color: var(--color-primary-soft);
  color: var(--color-primary);
  border: none;
}
.btn-edit:hover {
  background-color: var(--color-primary-soft);
}
.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.info-section {
  padding: 16px;
  background: var(--bg-muted);
  border-radius: 12px;
}
.info-label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: var(--font);
}
.title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 22px;
  word-break: break-word;
}
.title-input {
  width: 100%;
  font-size: 14px;
  font-weight: 600;
  padding: 8px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--bg-input, #fff);
  color: var(--text-primary);
  font-family: var(--font);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
}
.title-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 20%, transparent);
}
.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  font-family: var(--font);
  background-color: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-hover);
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
}
.form-input:focus,
.form-textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}
.form-textarea {
  resize: vertical;
  min-height: 100px;
  line-height: 20px;
}
.info-content {
  font-size: 14px;
  line-height: 22px;
  color: var(--text-primary);
  font-family: var(--font);
}
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: 8px;
  border-left: 3px solid var(--color-primary);
}
.step-index {
  font-weight: 700;
  color: var(--color-primary);
  flex-shrink: 0;
  font-size: 13px;
}
.step-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.step-desc {
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-word;
}
.step-code {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  word-break: break-all;
}
.markdown-content {
  white-space: pre-wrap;
  word-wrap: break-word;
}
.text-muted {
  color: var(--text-muted);
  font-size: 14px;
}
.method-code {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-primary);
}
.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 11.5px;
  font-weight: 600;
  background: var(--color-primary-soft);
  color: var(--accent);
}
.bugs-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bug-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: 8px;
  font-size: 13px;
}
.bug-id {
  font-weight: 700;
  color: var(--text-secondary);
}
.status-badge-status {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.bug-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}
.bug-severity {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
}
.bug-time {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font);
  border: none;
  line-height: 20px;
}
.btn-cancel {
  background-color: transparent;
  color: var(--text-primary);
  font-weight: 500;
}
.btn-cancel:hover {
  background-color: var(--bg-muted);
}
.btn-save {
  background-color: var(--color-primary);
  color: var(--bg-card);
}
.btn-save:hover:not(:disabled) {
  background-color: var(--color-primary-dark);
}
.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
