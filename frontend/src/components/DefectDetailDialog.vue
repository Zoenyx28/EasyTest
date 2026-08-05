<script setup lang="ts">
import { ref, watch } from 'vue';
import { useDefect } from '../composables/useDefect';
import type {
  DefectInfo,
  DefectLogInfo,
  DefectAttachmentInfo,
  DefectCommentInfo,
  DefectModuleInfo,
} from '../types';
import DefectRichEditor from './DefectRichEditor.vue';
import DefectHistoryTimeline from './DefectHistoryTimeline.vue';

const props = defineProps<{
  isOpen: boolean;
  defectId: number | null;
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'updated'): void;
  (e: 'showToast', msg: string): void;
}>();

const defectApi = useDefect(props.projectId);

const defect = ref<DefectInfo | null>(null);
const logs = ref<DefectLogInfo[]>([]);
const attachments = ref<DefectAttachmentInfo[]>([]);
const comments = ref<DefectCommentInfo[]>([]);
const modules = ref<DefectModuleInfo[]>([]);
const loading = ref(false);
const uploading = ref(false);
const saving = ref(false);
const activeTab = ref<'details' | 'activity'>('details');
const isEditing = ref(false);

// Edit form state
const editSeverity = ref('');
const editPriority = ref('');
const editModuleId = ref(0);
const editDescription = ref('');
const editSteps = ref('');
const editBugType = ref('code_error');
const editDeadline = ref('');

const severityOptions = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
];

const priorityOptions = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
];

const bugTypeOptions = [
  { value: 'code_error', label: '代码错误' },
  { value: 'config_error', label: '配置错误' },
  { value: 'ui_error', label: '界面错误' },
  { value: 'performance', label: '性能问题' },
  { value: 'security', label: '安全问题' },
  { value: 'compatibility', label: '兼容性问题' },
  { value: 'document_error', label: '文档错误' },
];

const severityColors: Record<string, string> = {
  P0: 'var(--priority-p0-bg)', P1: 'var(--priority-p1-bg)', P2: 'var(--priority-p2-bg)', P3: 'var(--priority-p3-bg)',
};

const severityTextColors: Record<string, string> = {
  P0: 'var(--priority-p0-text)', P1: 'var(--priority-p1-text)', P2: 'var(--priority-p2-text)', P3: 'var(--priority-p3-text)',
};

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

function flattenModules(list: DefectModuleInfo[], depth = 0): { id: number; name: string; depth: number }[] {
  const result: { id: number; name: string; depth: number }[] = [];
  for (const m of list) {
    result.push({ id: m.id, name: m.name, depth });
    if (m.children && m.children.length > 0) {
      result.push(...flattenModules(m.children, depth + 1));
    }
  }
  return result;
}

async function loadModules() {
  try {
    modules.value = await defectApi.getModules(props.projectId);
  } catch { /* ignore */ }
}

async function loadDefect() {
  if (!props.defectId) return;
  loading.value = true;
  try {
    const detail = await defectApi.getDefectDetail(props.defectId);
    defect.value = detail.defect;
    logs.value = detail.logs;
    attachments.value = detail.attachments;
    comments.value = detail.comments;
  } catch (e: any) {
    emit('showToast', e.message || '加载缺陷详情失败');
  } finally {
    loading.value = false;
  }
}

function enterEditMode() {
  if (!defect.value) return;
  editSeverity.value = defect.value.severity || '';
  editPriority.value = defect.value.priority || '';
  editModuleId.value = defect.value.module_id || 0;
  editDescription.value = defect.value.description || '';
  editSteps.value = defect.value.steps || '';
  editBugType.value = defect.value.bug_type || 'code_error';
  editDeadline.value = defect.value.deadline || '';
  isEditing.value = true;
}

function cancelEdit() {
  isEditing.value = false;
}

async function handleSaveEdit() {
  if (!props.defectId || !defect.value) return;
  saving.value = true;
  try {
    await defectApi.updateDefect(props.defectId, {
      severity: editSeverity.value || '',
      priority: editPriority.value || '',
      module_id: editModuleId.value || 0,
      description: editDescription.value || '',
      steps: editSteps.value || '',
      bug_type: editBugType.value || '',
      deadline: editDeadline.value || '',
    });
    isEditing.value = false;
    await loadDefect();
    emit('updated');
    emit('showToast', '保存成功');
  } catch (e: any) {
    emit('showToast', e.message || '保存失败');
  } finally {
    saving.value = false;
  }
}

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file || !props.defectId) return;
  uploading.value = true;
  try {
    await defectApi.uploadAttachment(props.defectId, file);
    await loadDefect();
    emit('showToast', '附件上传成功');
  } catch (e: any) {
    emit('showToast', e.message || '附件上传失败');
  } finally {
    uploading.value = false;
    target.value = '';
  }
}

async function handleDeleteAttachment(attachmentId: number) {
  try {
    await defectApi.deleteAttachment(attachmentId);
    await loadDefect();
    emit('showToast', '附件删除成功');
  } catch (e: any) {
    emit('showToast', e.message || '附件删除失败');
  }
}

function formatTime(iso: string): string {
  if (!iso) return '--';
  try {
    const date = new Date(iso);
    return date.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function handleClose() {
  defect.value = null;
  logs.value = [];
  attachments.value = [];
  comments.value = [];
  commentContent.value = '';
  activeTab.value = 'details';
  isEditing.value = false;
  emit('close');
}

watch(() => props.isOpen, async (newVal) => {
  if (newVal) {
    await loadModules();
    await loadDefect();
  }
});

watch(() => props.defectId, async () => {
  if (props.isOpen) {
    isEditing.value = false;
    await loadDefect();
  }
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog-container large">
        <div class="dialog-header">
          <div class="defect-header-left">
            <h2 class="dialog-title" v-if="defect">#{{ defect.id }} {{ defect.title }}</h2>
            <h2 class="dialog-title" v-else>加载中...</h2>
          </div>
          <div class="header-actions">
            <button
              v-if="defect && !isEditing"
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

        <!-- Tabs -->
        <div class="tabs-header">
          <button
            class="tab-button"
            :class="{ active: activeTab === 'details' }"
            @click="activeTab = 'details'"
          >
            详情
          </button>
          <button
            class="tab-button"
            :class="{ active: activeTab === 'activity' }"
            @click="activeTab = 'activity'"
          >
            活动记录
            <span v-if="(logs.length + comments.length) > 0" class="tab-badge">
              {{ logs.length + comments.length }}
            </span>
          </button>
        </div>

        <div class="dialog-body">
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>加载中...</span>
          </div>

          <div v-else-if="!defect" class="empty-state">
            <p>未找到缺陷信息</p>
          </div>

          <!-- Details Tab -->
          <div v-else-if="activeTab === 'details'" class="details-tab">
            <div class="details-grid">
              <div class="details-main">
                <!-- Status & Assignee (always read-only) -->
                <div class="info-row">
                  <div class="info-item">
                    <label class="info-label">状态</label>
                    <span
                      class="status-badge-status"
                      :style="{
                        backgroundColor: statusColors[defect.status] || 'var(--border)',
                        color: statusTextColors[defect.status] || 'var(--text-secondary)',
                      }"
                    >
                      {{ statusLabels[defect.status] || defect.status }}
                    </span>
                  </div>
                  <div class="info-item">
                    <label class="info-label">指派给</label>
                    <span class="text-muted">
                      {{ defect.assignee_name || '未指派' }}
                    </span>
                  </div>
                </div>

                <!-- Severity & Priority & Module -->
                <div class="info-row">
                  <div class="info-item">
                    <label class="info-label">严重程度</label>
                    <template v-if="isEditing">
                      <select class="form-select" v-model="editSeverity">
                        <option v-for="s in severityOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
                      </select>
                    </template>
                    <template v-else>
                      <span class="severity-badge" :style="{ backgroundColor: severityColors[defect.severity] || 'var(--border)', color: severityTextColors[defect.severity] || 'var(--text-secondary)' }">
                        {{ defect.severity }}
                      </span>
                    </template>
                  </div>
                  <div class="info-item">
                    <label class="info-label">优先级</label>
                    <template v-if="isEditing">
                      <select class="form-select" v-model="editPriority">
                        <option v-for="p in priorityOptions" :key="p.value" :value="p.value">{{ p.label }}</option>
                      </select>
                    </template>
                    <template v-else>
                      <span class="severity-badge" :style="{ backgroundColor: severityColors[defect.priority] || 'var(--border)', color: severityTextColors[defect.priority] || 'var(--text-secondary)' }">
                        {{ defect.priority }}
                      </span>
                    </template>
                  </div>
                  <div class="info-item">
                    <label class="info-label">模块</label>
                    <template v-if="isEditing">
                      <select class="form-select" v-model="editModuleId">
                        <option :value="0">-- 无 --</option>
                        <option v-for="m in flattenModules(modules)" :key="m.id" :value="m.id">
                          {{ '　'.repeat(m.depth) }}{{ m.name }}
                        </option>
                      </select>
                    </template>
                    <template v-else>
                      <span class="text-muted">{{ defect.module_name || '--' }}</span>
                    </template>
                  </div>
                </div>

                <!-- Bug Type & Deadline -->
                <div class="info-row">
                  <div class="info-item">
                    <label class="info-label">Bug类型</label>
                    <template v-if="isEditing">
                      <select class="form-select" v-model="editBugType">
                        <option v-for="bt in bugTypeOptions" :key="bt.value" :value="bt.value">{{ bt.label }}</option>
                      </select>
                    </template>
                    <template v-else>
                      <span class="text-muted">{{ defect.bug_type_name || '--' }}</span>
                    </template>
                  </div>
                  <div class="info-item">
                    <label class="info-label">截止日期</label>
                    <template v-if="isEditing">
                      <input type="date" class="form-select" v-model="editDeadline" />
                    </template>
                    <template v-else>
                      <span class="text-muted">{{ defect.deadline || '--' }}</span>
                    </template>
                  </div>
                </div>

                <!-- Description -->
                <div class="info-section">
                  <label class="info-label">描述</label>
                  <template v-if="isEditing">
                    <textarea
                      class="form-textarea"
                      v-model="editDescription"
                      rows="4"
                      placeholder="输入描述..."
                    ></textarea>
                  </template>
                  <template v-else>
                    <div class="info-content markdown-content">
                      {{ defect.description || '暂无描述' }}
                    </div>
                  </template>
                </div>

                <!-- Steps -->
                <div class="info-section">
                  <label class="info-label">复现步骤</label>
                  <template v-if="isEditing">
                    <DefectRichEditor
                      :modelValue="editSteps"
                      placeholder="输入复现步骤..."
                      @update:modelValue="editSteps = $event"
                    />
                  </template>
                  <template v-else>
                    <div class="info-content markdown-content" v-html="defect.steps || '暂无步骤'">
                    </div>
                  </template>
                </div>

                <!-- Attachments -->
                <div class="info-section">
                  <label class="info-label">附件</label>
                  <div class="attachments-list">
                    <div v-if="attachments.length === 0" class="text-muted">暂无附件</div>
                    <div v-for="att in attachments" :key="att.id" class="attachment-item">
                      <span class="attachment-name">{{ att.filename }}</span>
                      <span class="attachment-meta">({{ Math.round(att.file_size / 1024) }} KB)</span>
                      <button class="btn-text" @click="handleDeleteAttachment(att.id)">删除</button>
                    </div>
                  </div>
                  <div class="upload-section">
                    <label class="upload-btn" :class="{ disabled: uploading }">
                      <input
                        type="file"
                        @change="handleFileUpload"
                        :disabled="uploading"
                        class="hidden-input"
                      >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                      </svg>
                      {{ uploading ? '上传中...' : '上传附件' }}
                    </label>
                  </div>
                </div>
              </div>

              <div class="details-sidebar">
                <div class="sidebar-card">
                  <h3 class="sidebar-title">缺陷信息</h3>
                  <div class="sidebar-item">
                    <span class="sidebar-label">创建者</span>
                    <span class="sidebar-value">{{ defect.creator_name || '--' }}</span>
                  </div>
                  <div class="sidebar-item">
                    <span class="sidebar-label">创建时间</span>
                    <span class="sidebar-value">{{ formatTime(defect.created_at) }}</span>
                  </div>
                  <div class="sidebar-item">
                    <span class="sidebar-label">更新时间</span>
                    <span class="sidebar-value">{{ formatTime(defect.updated_at) }}</span>
                  </div>
                  <div v-if="defect.resolution" class="sidebar-item">
                    <span class="sidebar-label">解决方案</span>
                    <span class="sidebar-value">{{ defect.resolution }}</span>
                  </div>
                  <div v-if="defect.resolved_version_name" class="sidebar-item">
                    <span class="sidebar-label">解决版本</span>
                    <span class="sidebar-value">{{ defect.resolved_version_name }}</span>
                  </div>
                  <div v-if="defect.resolved_date" class="sidebar-item">
                    <span class="sidebar-label">解决时间</span>
                    <span class="sidebar-value">{{ formatTime(defect.resolved_date) }}</span>
                  </div>
                  <div v-if="defect.branch_name" class="sidebar-item">
                    <span class="sidebar-label">关联版本</span>
                    <span class="sidebar-value">{{ defect.branch_name }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Activity Tab -->
          <DefectHistoryTimeline
            v-else-if="activeTab === 'activity'"
            :logs="logs"
            :comments="comments"
            :defect-id="props.defectId || 0"
          />
        </div>

        <div class="dialog-footer">
          <template v-if="isEditing">
            <button class="btn btn-cancel" @click="cancelEdit" :disabled="saving">取消</button>
            <button class="btn btn-save" @click="handleSaveEdit" :disabled="saving">
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
  width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background-color: var(--bg-card);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.dialog-container.large {
  width: 900px;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.defect-header-left {
  flex: 1;
  min-width: 0;
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.tabs-header {
  display: flex;
  gap: 4px;
  padding: 8px 24px;
  border-bottom: 1px solid var(--border);
  background-color: var(--bg-muted);
  flex-shrink: 0;
}

.tab-button {
  padding: 8px 16px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font);
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-button:hover {
  background: var(--color-primary-soft);
}

.tab-button.active {
  background: var(--bg-card);
  color: var(--color-primary);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.tab-badge {
  padding: 2px 8px;
  border-radius: 100px;
  background: var(--border);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
  color: var(--text-muted);
  font-family: var(--font);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.details-tab {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr 260px;
  gap: 24px;
}

.details-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.info-item {
  flex: 1;
  min-width: 160px;
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

.info-content {
  font-size: 14px;
  line-height: 22px;
  color: var(--text-primary);
  font-family: var(--font);
}

.info-section {
  padding: 16px;
  background: var(--bg-muted);
  border-radius: 12px;
}

.markdown-content {
  white-space: pre-wrap;
  word-wrap: break-word;
}

.severity-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
}

.text-muted {
  color: var(--text-muted);
  font-size: 14px;
}

.form-select {
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

.form-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.form-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

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
  resize: vertical;
  margin-bottom: 0;
  line-height: 20px;
}

.form-textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.attachments-list {
  margin-bottom: 12px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: 8px;
  margin-bottom: 8px;
}

.attachment-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.attachment-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.upload-section {
  margin-top: 12px;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font);
}

.upload-btn:hover:not(.disabled) {
  background: var(--color-primary-soft);
}

.upload-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hidden-input {
  display: none;
}

.btn-text {
  padding: 4px 8px;
  background: transparent;
  border: none;
  color: var(--color-danger);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s ease;
  font-family: var(--font);
}

.btn-text:hover {
  background: rgba(186, 26, 26, 0.1);
}

.details-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-card {
  padding: 16px;
  background: var(--bg-muted);
  border-radius: 12px;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 16px 0;
  font-family: var(--font);
}

.sidebar-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.sidebar-item:last-child {
  border-bottom: none;
}

.sidebar-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  font-family: var(--font);
}

.sidebar-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: var(--font);
  text-align: right;
  max-width: 140px;
  word-break: break-word;
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
