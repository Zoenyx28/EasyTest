<script setup lang="ts">
import { ref, watch } from 'vue';
import { useDefect } from '../composables/useDefect';
import { useProjectMembers } from '../composables/useProjectMembers';
import type {
  DefectInfo,
  DefectLogInfo,
  DefectAttachmentInfo,
  DefectCommentInfo,
  DefectModuleInfo,
  ProjectMemberInfo
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
const membersApi = useProjectMembers();

const defect = ref<DefectInfo | null>(null);
const logs = ref<DefectLogInfo[]>([]);
const attachments = ref<DefectAttachmentInfo[]>([]);
const comments = ref<DefectCommentInfo[]>([]);
const members = ref<ProjectMemberInfo[]>([]);
const modules = ref<DefectModuleInfo[]>([]);
const loading = ref(false);
const uploading = ref(false);
const addingComment = ref(false);
const saving = ref(false);
const commentContent = ref('');
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
  P0: '#ffdad6', P1: '#ffd6a5', P2: '#fff6cc', P3: '#d4edda',
};

const severityTextColors: Record<string, string> = {
  P0: '#93000a', P1: '#7a4400', P2: '#655500', P3: '#155724',
};

const statusColors: Record<string, string> = {
  unconfirmed: '#e0e9f2', confirmed: '#d8e2ff', in_progress: '#ffd6a5',
  resolved: '#d4edda', closed: '#e0e9f2',
};

const statusTextColors: Record<string, string> = {
  unconfirmed: '#414754', confirmed: '#0059bb', in_progress: '#7a4400',
  resolved: '#155724', closed: '#414754',
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

async function loadMembers() {
  try {
    members.value = await membersApi.getMembers(props.projectId);
  } catch { /* ignore */ }
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
    [defect.value, logs.value, attachments.value, comments.value] = await Promise.all([
      defectApi.getDefect(props.defectId),
      defectApi.getLogs(props.defectId),
      defectApi.getAttachments(props.defectId),
      defectApi.getComments(props.defectId),
    ]);
  } catch (e: any) {
    emit('showToast', e.message || '加载缺陷详情失败');
  } finally {
    loading.value = false;
  }
}

function enterEditMode() {
  if (!defect.value) return;
  editSeverity.value = defect.value.severity;
  editPriority.value = defect.value.priority;
  editModuleId.value = defect.value.module_id;
  editDescription.value = defect.value.description;
  editSteps.value = defect.value.steps;
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
      severity: editSeverity.value,
      priority: editPriority.value,
      module_id: editModuleId.value,
      description: editDescription.value,
      steps: editSteps.value,
      bug_type: editBugType.value,
      deadline: editDeadline.value,
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

async function handleStatusChange(newStatus: string) {
  if (!props.defectId || !defect.value) return;
  const originalDefect = { ...defect.value };
  try {
    const currentStatus = originalDefect.status;
    let action: string;
    if (currentStatus === 'unconfirmed' && newStatus === 'confirmed') {
      action = 'confirm';
    } else if (newStatus === 'in_progress') {
      action = 'assign';
    } else if (newStatus === 'resolved') {
      action = 'resolve';
    } else if (newStatus === 'closed') {
      action = 'close';
    } else if (currentStatus !== 'unconfirmed' && newStatus === 'unconfirmed') {
      action = 'activate';
    } else {
      await defectApi.updateDefect(props.defectId, { status: newStatus });
    }
    if (action) {
      await defectApi.transitionDefect(props.defectId, action);
    }
    await loadDefect();
    emit('updated');
  } catch (e: any) {
    emit('showToast', e.message || '更新状态失败');
    defect.value = originalDefect;
  }
}

async function handleAssigneeChange(userId: number) {
  if (!props.defectId || !defect.value) return;
  const originalDefect = { ...defect.value };
  try {
    await defectApi.updateDefect(props.defectId, { assignee_id: userId });
    await loadDefect();
    emit('updated');
  } catch (e: any) {
    emit('showToast', e.message || '更新指派人失败');
    defect.value = originalDefect;
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

async function handleAddComment() {
  if (!commentContent.value.trim() || !props.defectId) return;
  addingComment.value = true;
  try {
    await defectApi.createComment(props.defectId, commentContent.value.trim());
    commentContent.value = '';
    await loadDefect();
    emit('showToast', '评论添加成功');
  } catch (e: any) {
    emit('showToast', e.message || '评论添加失败');
  } finally {
    addingComment.value = false;
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
    await Promise.all([loadMembers(), loadModules()]);
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
                <!-- Status & Assignee (always shown, not in edit mode) -->
                <div class="info-row">
                  <div class="info-item">
                    <label class="info-label">状态</label>
                    <select
                      class="form-select"
                      :value="defect.status"
                      @change.prevent="handleStatusChange(($event.target as HTMLSelectElement).value)"
                    >
                      <option value="unconfirmed">未确认</option>
                      <option value="confirmed">已确认</option>
                      <option value="in_progress">处理中</option>
                      <option value="resolved">已解决</option>
                      <option value="closed">已关闭</option>
                    </select>
                  </div>
                  <div class="info-item">
                    <label class="info-label">指派给</label>
                    <select
                      class="form-select"
                      :value="defect.assignee_id || 0"
                      :disabled="defect.status === 'closed'"
                      @change.prevent="handleAssigneeChange(Number(($event.target as HTMLSelectElement).value))"
                    >
                      <option :value="0">未指派</option>
                      <option v-for="m in members" :key="m.id" :value="m.user_id">
                        {{ m.nickname || m.username }}
                      </option>
                    </select>
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
                      <span class="severity-badge" :style="{ backgroundColor: severityColors[defect.severity] || '#e0e9f2', color: severityTextColors[defect.severity] || '#414754' }">
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
                      <span class="severity-badge" :style="{ backgroundColor: severityColors[defect.priority] || '#e0e9f2', color: severityTextColors[defect.priority] || '#414754' }">
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
            :loading="addingComment"
            :comment-content="commentContent"
            @update:comment-content="commentContent = $event"
            @add-comment="handleAddComment"
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
  background-color: rgba(41, 49, 56, 0.6);
  backdrop-filter: blur(4px);
}

.dialog-container {
  width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background-color: #ffffff;
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
  border-bottom: 1px solid #e0e9f2;
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
  color: #141d23;
  margin: 0;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
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
  color: #717786;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dialog-close-btn:hover {
  background: #ecf5fe;
  color: #141d23;
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
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  background-color: #ecf5fe;
  color: #0059bb;
  border: none;
}

.btn-edit:hover {
  background-color: #d8eaff;
}

.tabs-header {
  display: flex;
  gap: 4px;
  padding: 8px 24px;
  border-bottom: 1px solid #e0e9f2;
  background-color: #f6faff;
  flex-shrink: 0;
}

.tab-button {
  padding: 8px 16px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  color: #414754;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-button:hover {
  background: #ecf5fe;
}

.tab-button.active {
  background: #ffffff;
  color: #0059bb;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.tab-badge {
  padding: 2px 8px;
  border-radius: 100px;
  background: #e0e9f2;
  color: #414754;
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
  color: #717786;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e0e9f2;
  border-top-color: #0059bb;
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
  color: #717786;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.info-content {
  font-size: 14px;
  line-height: 22px;
  color: #141d23;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.info-section {
  padding: 16px;
  background: #f6faff;
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
  color: #717786;
  font-size: 14px;
}

.form-select {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  background-color: #ffffff;
  color: #141d23;
  border: 1px solid #c1c6d7;
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.form-select:focus {
  border-color: #0059bb;
  box-shadow: 0 0 0 3px rgba(0, 89, 187, 0.1);
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
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  background-color: #ffffff;
  color: #141d23;
  border: 1px solid #c1c6d7;
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
  resize: vertical;
  margin-bottom: 0;
  line-height: 20px;
}

.form-textarea:focus {
  border-color: #0059bb;
  box-shadow: 0 0 0 3px rgba(0, 89, 187, 0.1);
}

.attachments-list {
  margin-bottom: 12px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #ffffff;
  border-radius: 8px;
  margin-bottom: 8px;
}

.attachment-name {
  font-size: 14px;
  color: #141d23;
  font-weight: 500;
}

.attachment-meta {
  font-size: 12px;
  color: #717786;
}

.upload-section {
  margin-top: 12px;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #ecf5fe;
  color: #0059bb;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.upload-btn:hover:not(.disabled) {
  background: #d8eaff;
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
  color: #ba1a1a;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s ease;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
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
  background: #f6faff;
  border-radius: 12px;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: #141d23;
  margin: 0 0 16px 0;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.sidebar-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e0e9f2;
}

.sidebar-item:last-child {
  border-bottom: none;
}

.sidebar-label {
  font-size: 12px;
  font-weight: 600;
  color: #717786;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.sidebar-value {
  font-size: 13px;
  font-weight: 500;
  color: #141d23;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  text-align: right;
  max-width: 140px;
  word-break: break-word;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e0e9f2;
  flex-shrink: 0;
}

.btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  border: none;
  line-height: 20px;
}

.btn-cancel {
  background-color: transparent;
  color: #141d23;
  font-weight: 500;
}

.btn-cancel:hover {
  background-color: #f6faff;
}

.btn-save {
  background-color: #0059bb;
  color: #ffffff;
}

.btn-save:hover:not(:disabled) {
  background-color: #004493;
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
