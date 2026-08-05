<script setup lang="ts">
import { ref, watch } from 'vue';
import { useDefect } from '../composables/useDefect';
import { useProjectMembers } from '../composables/useProjectMembers';
import type { DefectInfo, ProjectMemberInfo } from '../types';

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

const members = ref<ProjectMemberInfo[]>([]);
const assigneeId = ref(0);
const bugType = ref('code_error');
const priority = ref('P3');
const deadline = ref('');
const comment = ref('');
const saving = ref(false);

const bugTypeOptions = [
  { value: 'code_error', label: '代码错误' },
  { value: 'config_error', label: '配置错误' },
  { value: 'ui_error', label: '界面错误' },
  { value: 'performance', label: '性能问题' },
  { value: 'security', label: '安全问题' },
  { value: 'compatibility', label: '兼容性问题' },
  { value: 'document_error', label: '文档错误' },
];

const priorityOptions = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
];

async function loadMembers() {
  try {
    members.value = await membersApi.getMembers(props.projectId);
  } catch { /* ignore */ }
}

function resetForm() {
  if (!props.defect) return;
  assigneeId.value = props.defect.assignee_id || 0;
  bugType.value = props.defect.bug_type || 'code_error';
  priority.value = props.defect.priority || 'P3';
  deadline.value = props.defect.deadline || '';
  comment.value = '';
}

async function handleSubmit() {
  if (!props.defect) return;
  saving.value = true;
  try {
    await defectApi.transitionDefect(
      props.defect.id,
      'confirm',
      assigneeId.value,
      undefined,
      comment.value,
      undefined,
      bugType.value,
      priority.value,
      deadline.value,
    );
    emit('done');
    emit('showToast', 'Bug确认成功');
    emit('close');
  } catch (e: any) {
    emit('showToast', e.message || '确认失败');
  } finally {
    saving.value = false;
  }
}

watch(() => props.isOpen, async (newVal) => {
  if (newVal) {
    resetForm();
    await loadMembers();
  }
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog-container">
        <div class="dialog-header">
          <h2 class="dialog-title">确认 Bug #{{ defect?.id }}</h2>
          <button class="dialog-close-btn" @click="emit('close')">×</button>
        </div>

        <div class="dialog-body">
          <div class="form-group">
            <label class="form-label">指派给</label>
            <select class="form-select" v-model="assigneeId">
              <option :value="0">未指派</option>
              <option v-for="m in members" :key="m.id" :value="m.user_id">
                {{ m.nickname || m.username }}
              </option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Bug类型</label>
              <select class="form-select" v-model="bugType">
                <option v-for="bt in bugTypeOptions" :key="bt.value" :value="bt.value">{{ bt.label }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">优先级</label>
              <select class="form-select" v-model="priority">
                <option v-for="p in priorityOptions" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">截止日期</label>
            <input type="date" class="form-select" v-model="deadline" />
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
            {{ saving ? '确认中...' : '确认' }}
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
