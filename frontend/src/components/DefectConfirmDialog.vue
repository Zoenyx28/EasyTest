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
  if (!assigneeId.value) {
    emit('showToast', '请选择指派对象');
    return;
  }
  saving.value = true;
  try {
    await defectApi.transitionDefect(
      props.defect.id,
      'confirm',
      assigneeId.value,
      undefined,
      comment.value,
      undefined,
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
            <label class="form-label">指派给 <span class="required-mark">*</span></label>
            <select class="form-select" v-model="assigneeId">
              <option :value="0" disabled>请选择指派对象</option>
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
              placeholder="添加备注"
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
  background-color: var(--overlay-bg);
  backdrop-filter: blur(4px);
}

.dialog-container {
  width: 500px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  background-color: var(--bg-card);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
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
  font-family: var(--font-heading);
}

.dialog-close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background: var(--bg-soft);
  color: var(--text-muted);
  font-size: 20px;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: all 0.15s ease;
}

.dialog-close-btn:hover {
  background: var(--color-primary-soft);
  color: var(--text-primary);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
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
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
  font-family: var(--font);
}

.required-mark {
  color: var(--color-danger);
}

.form-select {
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: var(--font);
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.form-select:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.form-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: var(--font);
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
  resize: vertical;
  min-height: 80px;
  line-height: 20px;
}

.form-textarea:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
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
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
  line-height: 20px;
}

.btn-cancel {
  background-color: var(--bg-soft);
  color: var(--text-secondary);
  font-weight: 500;
}

.btn-cancel:hover:not(:disabled) {
  background-color: var(--bg-muted);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.btn-save {
  background-color: var(--cta);
  color: #fff;
}

.btn-save:hover:not(:disabled) {
  background-color: var(--cta-dark);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
