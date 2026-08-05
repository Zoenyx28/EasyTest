<script setup lang="ts">
import { ref, watch } from 'vue';
import { useDefect } from '../composables/useDefect';
import { useProjectMembers } from '../composables/useProjectMembers';
import { useBranch } from '../composables/useBranch';
import type { DefectInfo, ProjectMemberInfo, BranchInfo } from '../types';

const props = defineProps<{
  isOpen: boolean;
  defect: DefectInfo | null;
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'done'): void;
  (e: 'showToast', msg: string): void;
}>();

const defectApi = useDefect(props.projectId);
const membersApi = useProjectMembers();
const { branches, loadBranches } = useBranch(props.projectId);

const members = ref<ProjectMemberInfo[]>([]);
const resolution = ref('fixed');
const resolvedVersion = ref(0);
const assigneeId = ref(0);
const comment = ref('');
const file = ref<File | null>(null);
const saving = ref(false);

const resolutionOptions = [
  { value: 'fixed', label: '已解决' },
  { value: 'duplicate', label: '重复Bug' },
  { value: 'not_issue', label: '不是问题' },
  { value: 'cannot_reproduce', label: '无法重现' },
  { value: 'design', label: '设计如此' },
  { value: 'external', label: '外部原因' },
  { value: 'deferred', label: '延期处理' },
];

async function loadMembers() {
  try {
    members.value = await membersApi.getMembers(props.projectId);
  } catch { /* ignore */ }
}

async function loadBranchesForResolve() {
  if (!props.projectId) return;
  try {
    await loadBranches(props.projectId);
  } catch { /* ignore */ }
}

function resetForm() {
  if (!props.defect) return;
  resolution.value = 'fixed';
  resolvedVersion.value = props.defect.branch_id || 0;
  assigneeId.value = props.defect.assignee_id || 0;
  comment.value = '';
  file.value = null;
}

async function handleSubmit() {
  if (!props.defect) return;
  saving.value = true;
  try {
    await defectApi.transitionDefect(
      props.defect.id,
      'resolve',
      assigneeId.value,
      resolution.value,
      comment.value,
      resolvedVersion.value,
    );

    // Upload attachment if provided
    if (file.value) {
      await defectApi.uploadAttachment(props.defect.id, file.value);
    }

    emit('done');
    emit('showToast', 'Bug解决成功');
    emit('close');
  } catch (e: any) {
    emit('showToast', e.message || '解决失败');
  } finally {
    saving.value = false;
  }
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  file.value = target.files?.[0] || null;
}

watch(() => props.isOpen, async (newVal) => {
  if (newVal) {
    resetForm();
    await Promise.all([loadMembers(), loadBranchesForResolve()]);
  }
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog-container">
        <div class="dialog-header">
          <h2 class="dialog-title">解决 Bug #{{ defect?.id }}</h2>
          <button class="dialog-close-btn" @click="emit('close')">×</button>
        </div>

        <div class="dialog-body">
          <div class="form-group">
            <label class="form-label">解决方案 <span class="required">*</span></label>
            <select class="form-select" v-model="resolution">
              <option v-for="r in resolutionOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">解决版本</label>
              <select class="form-select" v-model="resolvedVersion">
                <option :value="0">-- 选择版本 --</option>
                <option v-for="b in (branches || [])" :key="b.id" :value="b.id">{{ b.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">指派给</label>
              <select class="form-select" v-model="assigneeId">
                <option :value="0">未指派</option>
                <option v-for="m in members" :key="m.id" :value="m.user_id">
                  {{ m.nickname || m.username }}
                </option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">附件</label>
            <label class="upload-btn">
              <input type="file" @change="handleFileChange" class="hidden-input" />
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              {{ file ? file.name : '选择文件' }}
            </label>
          </div>

          <div class="form-group">
            <label class="form-label">备注</label>
            <textarea
              class="form-textarea"
              v-model="comment"
              rows="3"
              placeholder="添加备注（可选）..."
            ></textarea>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn btn-cancel" @click="emit('close')">取消</button>
          <button class="btn btn-save" @click="handleSubmit" :disabled="saving">
            {{ saving ? '解决中...' : '解决' }}
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
  z-index: 210;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
}

.dialog-container {
  width: 500px;
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
  font-size: 18px;
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
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-group {
  flex: 1;
  min-width: 0;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: var(--font);
}

.required {
  color: var(--color-danger);
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
  min-height: 80px;
  line-height: 20px;
}

.form-textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
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

.upload-btn:hover {
  background: var(--color-primary-soft);
}

.hidden-input {
  display: none;
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
