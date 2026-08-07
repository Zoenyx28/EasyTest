<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useDefect } from '../composables/useDefect';
import type { TempAttachmentInfo } from '../composables/useDefect';
import { useProjectMembers } from '../composables/useProjectMembers';
import type { DefectModuleInfo, ProjectMemberInfo, DefectCreateData, TestCaseInfo } from '../types';
import DefectRichEditor from './DefectRichEditor.vue';

const props = defineProps<{
  isOpen: boolean;
  projectId: number;
  branchId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'created'): void;
  (e: 'showToast', msg: string): void;
}>();

const defectApi = useDefect(props.projectId);
const membersApi = useProjectMembers();

const title = ref('');
const description = ref('');
const severity = ref('P2');
const priority = ref('P2');
const moduleId = ref<number>(0);
const assigneeId = ref<number>(0);
const steps = ref('');

const modules = ref<DefectModuleInfo[]>([]);
const members = ref<ProjectMemberInfo[]>([]);
const cases = ref<TestCaseInfo[]>([]);
const caseSearch = ref('');
const selectedCaseUid = ref('');
const caseDropdownOpen = ref(false);
const saving = ref(false);
const titleError = ref('');
const uploading = ref(false);
const pendingFiles = ref<(TempAttachmentInfo & { _localId: number })[]>([]);
let fileIdCounter = 0;

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
    modules.value = await defectApi.getModules(props.projectId, props.branchId);
  } catch {
    // ignore
  }
}

async function loadCases() {
  if (!props.projectId || !props.branchId) {
    cases.value = [];
    return;
  }
  try {
    cases.value = await defectApi.loadCases(props.projectId, props.branchId);
  } catch {
    cases.value = [];
  }
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

function caseDisplayName(c: TestCaseInfo): string {
  return c.description && c.description !== c.name ? c.description : c.name;
}

function selectCase(c: TestCaseInfo) {
  selectedCaseUid.value = c.uid;
  caseDropdownOpen.value = false;
  caseSearch.value = '';
}

const selectedCaseInfo = computed(() => cases.value.find(c => c.uid === selectedCaseUid.value) || null);

async function loadMembers() {
  try {
    members.value = await membersApi.getMembers(props.projectId);
  } catch {
    // ignore
  }
}

async function handleSave() {
  if (!title.value.trim()) {
    titleError.value = '请输入标题';
    return;
  }
  titleError.value = '';
  saving.value = true;
  try {
    const payload: Record<string, any> = {
      title: title.value.trim(),
      description: description.value,
      steps: steps.value,
      project_id: props.projectId,
      branch_id: props.branchId,
      module_id: moduleId.value,
      severity: severity.value,
      priority: priority.value,
      assignee_id: assigneeId.value,
      case_uid: selectedCaseUid.value,
      attachments: pendingFiles.value.map(pf => ({
        filename: pf.filename,
        filepath: pf.filepath,
        file_size: pf.file_size,
        mime_type: pf.mime_type,
      })),
    };
    await defectApi.createDefect(payload);
    emit('created');
    emit('showToast', '缺陷创建成功');
    handleClose();
  } catch (e: any) {
    emit('showToast', e.message || '创建缺陷失败');
  } finally {
    saving.value = false;
  }
}

function handleAddFile(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) return;
  uploading.value = true;
  const tasks: Promise<void>[] = [];
  for (let i = 0; i < files.length; i++) {
    tasks.push(
      defectApi.uploadTempAttachment(files[i]).then(info => {
        pendingFiles.value.push({ ...info, _localId: ++fileIdCounter });
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

function handleRemoveFile(id: number) {
  pendingFiles.value = pendingFiles.value.filter(f => f._localId !== id);
}

function handleClose() {
  title.value = '';
  description.value = '';
  steps.value = '';
  severity.value = 'P2';
  priority.value = 'P2';
  moduleId.value = 0;
  assigneeId.value = 0;
  selectedCaseUid.value = '';
  caseSearch.value = '';
  caseDropdownOpen.value = false;
  titleError.value = '';
  pendingFiles.value = [];
  fileIdCounter = 0;
  emit('close');
}

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    loadModules();
    loadMembers();
    loadCases();
  } else {
    caseDropdownOpen.value = false;
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
  if (props.isOpen) {
    loadModules();
    loadMembers();
    loadCases();
  }
});

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick);
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog-container">
        <div class="dialog-header">
          <h2 class="dialog-title">创建缺陷</h2>
          <button class="dialog-close-btn" @click="handleClose">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-group">
            <label class="form-label">标题 <span class="required">*</span></label>
            <input
              v-model="title"
              class="form-input"
              :class="{ 'input-error': titleError }"
              placeholder="简要描述问题"
              @input="titleError = ''"
            />
            <span v-if="titleError" class="error-text">{{ titleError }}</span>
          </div>

          <!-- 关联用例（按版本隔离，单选） -->
          <div class="form-group">
            <label class="form-label">关联用例</label>
            <div class="case-selector">
              <div
                class="case-selector-input"
                :class="{ 'case-selector-open': caseDropdownOpen }"
                @click="caseDropdownOpen = !caseDropdownOpen"
              >
                <template v-if="selectedCaseUid && selectedCaseInfo">
                  <span class="case-selected-name">{{ caseDisplayName(selectedCaseInfo) }}</span>
                  <code class="case-selected-method">{{ selectedCaseInfo.methodName }}</code>
                </template>
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
                  <div
                    v-if="filteredCases.length === 0"
                    class="case-dropdown-empty"
                  >暂无用例（当前版本下没有已同步的用例）</div>
                  <div
                    v-for="c in filteredCases"
                    :key="c.uid"
                    class="case-dropdown-item"
                    :class="{ 'case-dropdown-item-active': c.uid === selectedCaseUid }"
                    @click="selectCase(c)"
                  >
                    <div class="case-dropdown-name">{{ caseDisplayName(c) }}</div>
                    <code class="case-dropdown-method">{{ c.methodName }}</code>
                    <span v-if="c.module" class="case-dropdown-module">{{ c.module }}</span>
                  </div>
                </div>
              </div>
              <div v-if="selectedCaseUid" class="case-clear" @click="selectedCaseUid = ''; caseSearch = ''">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
                清除
              </div>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label class="form-label">严重程度</label>
              <select v-model="severity" class="form-select">
                <option v-for="opt in severityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <div class="form-group flex-1">
              <label class="form-label">优先级</label>
              <select v-model="priority" class="form-select">
                <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label class="form-label">模块</label>
              <select v-model="moduleId" class="form-select">
                <option :value="0">选择模块</option>
                <template v-for="item in flattenModules(modules)" :key="item.id">
                  <option :value="item.id">
                    <span v-for="i in item.depth" :key="i">&nbsp;&nbsp;&nbsp;</span>
                    {{ item.name }}
                  </option>
                </template>
              </select>
            </div>
            <div class="form-group flex-1">
              <label class="form-label">指派给</label>
              <select v-model="assigneeId" class="form-select">
                <option :value="0">选择指派对象</option>
                <option v-for="m in members" :key="m.id" :value="m.user_id">{{ m.nickname || m.username }}</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">描述</label>
            <textarea
              v-model="description"
              class="form-textarea"
              placeholder="发生了什么？应该发生什么？"
              rows="4"
            ></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">复现步骤</label>
            <DefectRichEditor
              v-model="steps"
              placeholder="如何复现这个问题？"
              :uploadImage="uploadEditorImage"
              @error="emit('showToast', $event)"
            />
          </div>

          <!-- Attachments -->
          <div class="form-group">
            <label class="form-label">附件</label>
            <div v-if="pendingFiles.length > 0" class="attachments-list">
              <div v-for="pf in pendingFiles" :key="pf._localId" class="attachment-item">
                <span class="attachment-name">{{ pf.filename }}</span>
                <span class="attachment-meta">({{ Math.round(pf.file_size / 1024) }} KB)</span>
                <button class="btn-text" @click="handleRemoveFile(pf._localId)">删除</button>
              </div>
            </div>
            <label class="upload-btn" :class="{ disabled: uploading }">
              <input
                type="file"
                multiple
                @change="handleAddFile"
                :disabled="uploading"
                class="hidden-input"
              />
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              {{ uploading ? '上传中...' : '上传附件' }}
            </label>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-cancel" @click="handleClose">取消</button>
          <button class="btn btn-save" :disabled="saving" @click="handleSave">
            {{ saving ? '创建中...' : '创建缺陷' }}
          </button>
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
  background-color: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
}

.dialog-container {
  width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background-color: var(--bg-card);
  box-shadow: 0 24px 64px rgba(0,0,0,0.25);
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

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
  font-family: var(--font);
}

.required {
  color: var(--color-danger);
}

.form-input,
.form-textarea,
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

.form-input:focus,
.form-textarea:focus,
.form-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.input-error {
  border-color: var(--color-danger) !important;
}

.error-text {
  display: block;
  font-size: 12px;
  color: var(--color-danger);
  margin-top: 6px;
  font-family: var(--font);
}

.form-textarea {
  resize: vertical;
  min-height: 100px;
  line-height: 20px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.flex-1 {
  flex: 1;
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

.attachments-list {
  margin-bottom: 12px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-muted);
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
</style>
