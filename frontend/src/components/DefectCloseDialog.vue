<script setup lang="ts">
import { ref, watch } from 'vue';
import { useDefect } from '../composables/useDefect';
import type { DefectInfo } from '../types';

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

const comment = ref('');
const saving = ref(false);

function resetForm() {
  comment.value = '';
}

async function handleSubmit() {
  if (!props.defect) return;
  saving.value = true;
  try {
    await defectApi.transitionDefect(
      props.defect.id,
      'close',
      undefined,
      undefined,
      comment.value,
    );
    emit('done');
    emit('showToast', 'Bug关闭成功');
    emit('close');
  } catch (e: any) {
    emit('showToast', e.message || '关闭失败');
  } finally {
    saving.value = false;
  }
}

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    resetForm();
  }
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog-container">
        <div class="dialog-header">
          <h2 class="dialog-title">关闭 Bug #{{ defect?.id }}</h2>
          <button class="dialog-close-btn" @click="emit('close')">×</button>
        </div>

        <div class="dialog-body">
          <div class="form-group">
            <label class="form-label">备注</label>
            <textarea
              class="form-textarea"
              v-model="comment"
              rows="3"
              placeholder="添加关闭备注（可选）..."
            ></textarea>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn btn-cancel" @click="emit('close')">取消</button>
          <button class="btn btn-save" @click="handleSubmit" :disabled="saving">
            {{ saving ? '关闭中...' : '关闭' }}
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
