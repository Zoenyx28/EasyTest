<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useDefect, buildModulePath } from '../composables/useDefect';
import type { TempAttachmentInfo } from '../composables/useDefect';
import type {
  DefectInfo,
  DefectLogInfo,
  DefectAttachmentInfo,
  DefectCommentInfo,
  DefectModuleInfo,
  TestCaseInfo,
} from '../types';
import DefectRichEditor from './DefectRichEditor.vue';
import DefectHistoryTimeline from './DefectHistoryTimeline.vue';
import UserAvatar from './UserAvatar.vue';

const props = defineProps<{
  isOpen: boolean;
  defectId: number | null;
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'updated'): void;
  (e: 'showToast', msg: string): void;
  (e: 'activate', defect: import('../types').DefectInfo): void;
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
const showAssignDialog = ref(false);

// Image lightbox preview (click on images inside rendered steps)
const imagePreviewUrl = ref<string | null>(null);

function handleContentClick(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (target.tagName === 'IMG') {
    const src = (target as HTMLImageElement).getAttribute('src');
    if (src) {
      imagePreviewUrl.value = src;
    }
  }
}

// Attachment edit state
const originalAttachments = ref<DefectAttachmentInfo[]>([]);
const pendingFiles = ref<(TempAttachmentInfo & { _localId: number })[]>([]);
const deletedAttachmentIds = ref<Set<number>>(new Set());
let pendingFileIdCounter = 0;

// Edit form state
const editSeverity = ref('');
const editPriority = ref('');
const editTitle = ref('');
const editModuleId = ref(0);
const editDescription = ref('');
const editSteps = ref('');
const editBugType = ref('code_error');
const editDeadline = ref('');
const editCaseUid = ref('');

// Case association state (edit mode)
const cases = ref<TestCaseInfo[]>([]);
const caseSearch = ref('');
const caseDropdownOpen = ref(false);

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
  unconfirmed: '未确认',
  confirmed: '已确认',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

const resolutionLabels: Record<string, string> = {
  fixed: '已解决',
  duplicate: '重复Bug',
  not_issue: '不是问题',
  cannot_reproduce: '无法重现',
  design: '设计如此',
  external: '外部原因',
  deferred: '延期处理',
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
    modules.value = await defectApi.getModules(props.projectId, defect.value?.branch_id || 0);
  } catch { /* ignore */ }
}

async function loadCases() {
  const branchId = defect.value?.branch_id || 0;
  if (!props.projectId || !branchId) {
    cases.value = [];
    return;
  }
  try {
    cases.value = await defectApi.loadCases(props.projectId, branchId);
  } catch {
    cases.value = [];
  }
}

function caseDisplayName(c: TestCaseInfo): string {
  return c.description && c.description !== c.name ? c.description : c.name;
}

const filteredCases = computed(() => {
  if (!caseSearch.value.trim()) return cases.value;
  const q = caseSearch.value.trim().toLowerCase();
  return cases.value.filter(c => {
    const chinese = c.description && c.description !== c.name ? c.description : c.name;
    return chinese.toLowerCase().includes(q)
      || c.name.toLowerCase().includes(q)
      || c.methodName.toLowerCase().includes(q)
      || (c.module || '').toLowerCase().includes(q);
  });
});

const selectedCaseInfo = computed(() => cases.value.find(c => c.uid === editCaseUid.value) || null);

function selectCase(c: TestCaseInfo) {
  editCaseUid.value = c.uid;
  caseDropdownOpen.value = false;
  caseSearch.value = '';
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

async function handleAssignDone() {
  await loadDefect();
  emit('updated');
}

function enterEditMode() {
  if (!defect.value) return;
  editTitle.value = defect.value.title || '';
  editSeverity.value = defect.value.severity || '';
  editPriority.value = defect.value.priority || '';
  editModuleId.value = defect.value.module_id || 0;
  editDescription.value = defect.value.description || '';
  editSteps.value = defect.value.steps || '';
  editBugType.value = defect.value.bug_type || 'code_error';
  editDeadline.value = defect.value.deadline || '';
  editCaseUid.value = defect.value.case_uid || '';
  // Snapshot current attachments
   originalAttachments.value = [...attachments.value];
   pendingFiles.value = [];
   deletedAttachmentIds.value = new Set();
   pendingFileIdCounter = 0;
   isEditing.value = true;
}

function cancelEdit() {
  // Revert attachment changes
  attachments.value = [...originalAttachments.value];
  pendingFiles.value = [];
  deletedAttachmentIds.value = new Set();
  pendingFileIdCounter = 0;
  isEditing.value = false;
}

async function handleSaveEdit() {
  if (!props.defectId || !defect.value) return;
  saving.value = true;
  try {
    await defectApi.updateDefect(props.defectId, {
      title: editTitle.value || '',
      severity: editSeverity.value || '',
      priority: editPriority.value || '',
      module_id: editModuleId.value || 0,
      description: editDescription.value || '',
      steps: editSteps.value || '',
      bug_type: editBugType.value || '',
      deadline: editDeadline.value || '',
      case_uid: editCaseUid.value || '',
      attachments: pendingFiles.value,
    });
    // Delete marked attachments
    for (const id of deletedAttachmentIds.value) {
      await defectApi.deleteAttachment(id);
    }
    // Clear edit state and reload
    deletedAttachmentIds.value = new Set();
    pendingFiles.value = [];
    await loadDefect();
    isEditing.value = false;
    emit('updated');
    emit('showToast', '保存成功');
  } catch (e: any) {
    emit('showToast', e.message || '保存失败');
  } finally {
    saving.value = false;
  }
}

function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) return;
  uploading.value = true;
  const tasks: Promise<void>[] = [];
  for (let i = 0; i < files.length; i++) {
    tasks.push(
      defectApi.uploadTempAttachment(files[i]).then(info => {
        pendingFiles.value.push({ ...info, _localId: ++pendingFileIdCounter });
      })
    );
  }
  Promise.all(tasks).finally(() => {
    uploading.value = false;
  });
  target.value = '';
}

/** 编辑器内（粘贴/插入）图片上传：临时附件，返回可预览的临时 URL */
async function uploadEditorImage(file: File): Promise<string> {
  const info = await defectApi.uploadTempAttachment(file);
  return `/api/defects/attachments/temp/${encodeURIComponent(info.filename)}`;
}

function handleDeleteAttachment(attachmentId: number) {
  // If it's a server-side attachment, mark for deletion
  if (originalAttachments.value.some(a => a.id === attachmentId)) {
    deletedAttachmentIds.value = new Set([...deletedAttachmentIds.value, attachmentId]);
    attachments.value = attachments.value.filter(a => a.id !== attachmentId);
  } else {
    // It's a pending file, just remove it
    pendingFiles.value = pendingFiles.value.filter(f => f._localId !== attachmentId);
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
  activeTab.value = 'details';
  isEditing.value = false;
  caseDropdownOpen.value = false;
  emit('close');
}

watch(() => props.isOpen, async (newVal) => {
  if (newVal) {
    await loadModules();
    await loadDefect();
    await loadCases();
  } else {
    caseDropdownOpen.value = false;
  }
});

watch(() => props.defectId, async () => {
  if (props.isOpen) {
    isEditing.value = false;
    await loadDefect();
    await loadCases();
  }
});

function handleDocumentClick(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (caseDropdownOpen.value && !target.closest('.case-selector')) {
    caseDropdownOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick);
});

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick);
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog-container large">
        <div class="dialog-header">
          <div class="defect-header-left">
            <h2 class="dialog-title">缺陷详情</h2>
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
            <button
              v-if="defect && !isEditing && (defect.status === 'resolved' || defect.status === 'closed')"
              class="btn btn-activate"
              @click="emit('activate', defect!)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              激活
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
                <!-- Title (editable in edit mode) -->
                <div class="info-item title-info-item">
                  <label class="info-label">缺陷标题</label>
                  <template v-if="isEditing">
                    <input
                      v-model="editTitle"
                      class="form-input title-input"
                      placeholder="请输入缺陷标题"
                    />
                  </template>
                  <template v-else>
                    <span class="title-text">#{{ defect.id }} {{ defect.title }}</span>
                  </template>
                </div>

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
                    <div
                      class="assignee-tag"
                      :class="{ 'assignee-tag-readonly': isEditing }"
                      :title="isEditing ? '' : '点击重新指派'"
                      @click="!isEditing && (showAssignDialog = true)"
                    >
                      <UserAvatar
                        :name="defect.assignee_name || '未指派'"
                        :avatar="defect.assignee_avatar || ''"
                        :size="22"
                      />
                      <span class="assignee-name">{{ defect.assignee_name || '未指派' }}</span>
                    </div>
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
                      <span class="text-muted">{{ buildModulePath(modules, defect.module_id) || '--' }}</span>
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

                <!-- Associated Case -->
                <div class="info-section">
                  <label class="info-label">关联用例</label>
                  <template v-if="isEditing">
                    <div class="case-selector">
                      <div
                        class="case-selector-input"
                        :class="{ 'case-selector-open': caseDropdownOpen }"
                        @click="caseDropdownOpen = !caseDropdownOpen"
                      >
                        <template v-if="editCaseUid && selectedCaseInfo">
                          <span class="case-selected-name">{{ caseDisplayName(selectedCaseInfo) }}</span>
                          <code class="case-selected-method">{{ selectedCaseInfo.methodName }}</code>
                        </template>
                        <span v-else-if="editCaseUid && !selectedCaseInfo" class="case-selected-name">关联用例 #{{ editCaseUid }}</span>
                        <span v-else class="case-placeholder">选择关联用例（可选）</span>
                        <svg class="case-chevron" :class="{ 'case-chevron-open': caseDropdownOpen }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                          <polyline points="6 9 12 15 18 9"/>
                        </svg>
                      </div>
                      <div v-if="caseDropdownOpen" class="case-dropdown">
                        <div class="case-dropdown-search">
                          <input
                            v-model="caseSearch"
                            type="text"
                            placeholder="搜索用例名称/方法/模块"
                            class="form-input"
                            @click.stop
                          />
                        </div>
                        <div class="case-dropdown-list">
                          <div v-if="filteredCases.length === 0" class="case-dropdown-empty">暂无用例（当前版本下没有已同步的用例）</div>
                          <div
                            v-for="c in filteredCases"
                            :key="c.uid"
                            class="case-dropdown-item"
                            :class="{ 'case-dropdown-item-active': c.uid === editCaseUid }"
                            @click="selectCase(c)"
                          >
                            <div class="case-dropdown-name">{{ caseDisplayName(c) }}</div>
                            <code class="case-dropdown-method">{{ c.methodName }}</code>
                            <span v-if="c.module" class="case-dropdown-module">{{ c.module }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-if="editCaseUid" class="case-clear" @click="editCaseUid = ''; caseSearch = ''">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18"/>
                          <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                        清除关联
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    <template v-if="defect.case_name || defect.case_uid">
                      <div class="case-chip">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                          <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        <span class="case-chip-name">{{ defect.case_name || '未命名用例' }}</span>
                        <code class="case-chip-method">{{ defect.case_uid }}</code>
                      </div>
                    </template>
                    <span v-else class="text-muted">未关联用例</span>
                  </template>
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
                      :uploadImage="uploadEditorImage"
                      @update:modelValue="editSteps = $event"
                      @error="emit('showToast', $event)"
                    />
                  </template>
                  <template v-else>
                    <div class="info-content markdown-content" v-html="defect.steps || '暂无步骤'" @click="handleContentClick">
                    </div>
                  </template>
                </div>

                <!-- Attachments -->
                <div class="info-section">
                  <label class="info-label">附件</label>
                  <div class="attachments-list">
                    <div v-if="attachments.length === 0 && pendingFiles.length === 0" class="text-muted">暂无附件</div>
                    <div v-for="att in attachments" :key="'a' + att.id" class="attachment-item">
                      <a
                        class="attachment-name attachment-link"
                        :href="defectApi.getAttachmentDownloadUrl(att.id)"
                        :download="att.filename"
                      >{{ att.filename }}</a>
                      <span class="attachment-meta">({{ Math.round(att.file_size / 1024) }} KB)</span>
                      <button
                        v-if="isEditing"
                        class="btn-text"
                        @click="handleDeleteAttachment(att.id)"
                      >删除</button>
                    </div>
                    <div v-for="pf in pendingFiles" :key="'p' + pf._localId" class="attachment-item">
                      <span class="attachment-name">{{ pf.filename }}</span>
                      <span class="attachment-meta">({{ Math.round(pf.file_size / 1024) }} KB)</span>
                      <button
                        v-if="isEditing"
                        class="btn-text"
                        @click="handleDeleteAttachment(pf._localId)"
                      >删除</button>
                    </div>
                  </div>
                  <div v-if="isEditing" class="upload-section">
                    <label class="upload-btn" :class="{ disabled: uploading }">
                      <input
                        type="file"
                        multiple
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
                    <span class="sidebar-value">{{ resolutionLabels[defect.resolution] || defect.resolution }}</span>
                  </div>
                  <div v-if="defect.resolution === 'duplicate' && defect.duplicate_defect_id" class="sidebar-item">
                    <span class="sidebar-label">关联缺陷</span>
                    <span class="sidebar-value">#{{ defect.duplicate_defect_id }} {{ defect.duplicate_defect_title }}</span>
                  </div>
                  <div v-if="defect.resolved_version_name" class="sidebar-item">
                    <span class="sidebar-label">解决版本</span>
                    <span class="sidebar-value">{{ defect.resolved_version_name }}</span>
                  </div>
                  <div v-if="defect.resolved_date" class="sidebar-item">
                    <span class="sidebar-label">解决日期</span>
                    <span class="sidebar-value">{{ formatTime(defect.resolved_date) }}</span>
                  </div>
                  <div v-if="defect.branch_name && defect.branch_name !== defect.resolved_version_name" class="sidebar-item">
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

  <!-- Assign dialog -->
  <DefectAssignDialog
    :isOpen="showAssignDialog"
    :defect="defect"
    :projectId="projectId"
    @close="showAssignDialog = false"
    @done="handleAssignDone"
    @showToast="(msg: string) => emit('showToast', msg)"
  />

  <!-- Image lightbox preview -->
  <Teleport to="body">
    <div
      v-if="imagePreviewUrl"
      class="image-lightbox"
      @click="imagePreviewUrl = null"
    >
      <img :src="imagePreviewUrl" class="image-lightbox-img" alt="预览" @click.stop />
    </div>
  </Teleport>
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

.btn-activate {
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
  background-color: var(--color-warning);
  color: #fff;
  border: none;
}

.btn-activate:hover {
  opacity: 0.85;
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

.title-info-item {
  margin-bottom: 16px;
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
}

.title-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.assignee-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 6px;
  border: 1px solid var(--border);
  border-radius: 100px;
  background-color: var(--color-primary-soft);
  cursor: pointer;
  transition: all 0.15s ease;
}

.assignee-tag:hover {
  border-color: var(--color-primary);
}

.assignee-tag-readonly {
  cursor: default;
  opacity: 0.75;
}

.assignee-tag-readonly:hover {
  border-color: var(--border);
}

.assignee-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
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

.markdown-content :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  cursor: zoom-in;
}

.image-lightbox {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.image-lightbox-img {
  max-width: 92vw;
  max-height: 92vh;
  object-fit: contain;
  border-radius: 6px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
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

.attachment-link {
  color: var(--color-primary);
  text-decoration: none;
  cursor: pointer;
}

.attachment-link:hover {
  text-decoration: underline;
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

/* ── 关联用例选择器 ── */
.case-selector {
  position: relative;
}

.case-selector-input {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 14px;
  font-family: var(--font);
  background-color: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-hover);
  cursor: pointer;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.case-selector-open {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.case-selected-name {
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-selected-method {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 11.5px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.case-placeholder {
  flex: 1;
  color: var(--text-muted);
}

.case-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.18s ease;
}

.case-chevron-open {
  transform: rotate(180deg);
}

.case-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 300;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.case-dropdown-search {
  padding: 8px;
  border-bottom: 1px solid var(--border);
}

.case-dropdown-search .form-input {
  padding: 8px 12px;
}

.case-dropdown-list {
  max-height: 260px;
  overflow-y: auto;
}

.case-dropdown-empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 12.5px;
  color: var(--text-muted);
}

.case-dropdown-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 9px 14px;
  cursor: pointer;
  transition: background 0.1s ease;
}

.case-dropdown-item:hover {
  background: var(--color-primary-soft);
}

.case-dropdown-item-active {
  background: var(--color-primary-soft);
}

.case-dropdown-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.case-dropdown-method {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 11px;
  color: var(--text-secondary);
}

.case-dropdown-module {
  font-size: 11px;
  color: var(--text-tertiary);
}

.case-clear {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
}

.case-clear:hover {
  color: var(--color-danger);
}

.case-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--accent);
}

.case-chip-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.case-chip-method {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
