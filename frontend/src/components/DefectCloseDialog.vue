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
  background-color: rgba(41, 49, 56, 0.6);
  backdrop-filter: blur(4px);
}

.dialog-container {
  width: 500px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background-color: #ffffff;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid #e0e9f2;
  flex-shrink: 0;
}

.dialog-title {
  font-size: 18px;
  font-weight: 700;
  color: #141d23;
  margin: 0;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
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
  font-size: 12px;
  font-weight: 700;
  color: #717786;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
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
  min-height: 80px;
  line-height: 20px;
}

.form-textarea:focus {
  border-color: #0059bb;
  box-shadow: 0 0 0 3px rgba(0, 89, 187, 0.1);
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
