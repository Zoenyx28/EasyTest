<script setup lang="ts">
import { ref } from 'vue';
import { useAuth } from '../composables/useAuth';
import BaseInput from './base/BaseInput.vue';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'showToast', msg: string): void;
}>();

const auth = useAuth();

const oldPassword = ref('');
const newPassword = ref('');
const confirmNewPassword = ref('');
const error = ref('');
const loading = ref(false);

function resetForm() {
  oldPassword.value = '';
  newPassword.value = '';
  confirmNewPassword.value = '';
  error.value = '';
}

async function handleSave() {
  error.value = '';
  if (!oldPassword.value) {
    error.value = '请输入当前密码';
    return;
  }
  if (!newPassword.value) {
    error.value = '请输入新密码';
    return;
  }
  if (newPassword.value.length < 6) {
    error.value = '新密码长度至少6位';
    return;
  }
  if (newPassword.value !== confirmNewPassword.value) {
    error.value = '两次新密码输入不一致';
    return;
  }

  loading.value = true;
  try {
    await auth.changePassword(oldPassword.value, newPassword.value);
    emit('showToast', '密码修改成功');
    resetForm();
    emit('close');
  } catch (e: any) {
    error.value = e.message || '密码修改失败';
  } finally {
    loading.value = false;
  }
}

function handleClose() {
  resetForm();
  emit('close');
}
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 flex items-center justify-center z-50 p-4"
    style="background-color: var(--overlay-bg);"
    @click.self="handleClose"
  >
    <div
      class="password-panel w-[380px] max-w-[90vw] overflow-hidden"
    >
      <div
        class="flex items-center justify-between px-[18px] py-[14px] border-b"
        style="border-color: var(--border);"
      >
        <h3 class="password-title">修改密码</h3>
        <button
          @click="handleClose"
          class="cursor-pointer text-[15px]"
          style="color: var(--text-tertiary);"
        >
          ✕
        </button>
      </div>

      <div class="px-[18px] py-[16px]">
        <div v-if="error" class="mb-4 px-3 py-2 rounded-[8px] text-[12.5px]" style="background-color: var(--danger-soft); color: var(--danger);">
          {{ error }}
        </div>

        <div class="mb-3">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">当前密码</label>
          <BaseInput
            v-model="oldPassword"
            type="password"
            placeholder="输入当前密码"
          />
        </div>

        <div class="mb-3">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">新密码</label>
          <BaseInput
            v-model="newPassword"
            type="password"
            placeholder="至少6位新密码"
          />
        </div>

        <div class="mb-3">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">确认新密码</label>
          <BaseInput
            v-model="confirmNewPassword"
            type="password"
            placeholder="再次输入新密码"
          />
        </div>
      </div>

      <div
        class="flex justify-end gap-[8px] px-[18px] py-[12px] border-t"
        style="border-color: var(--border);"
      >
        <button
          @click="handleClose"
          class="px-4 py-1.5 text-sm font-medium rounded cursor-pointer transition-colors"
          style="background-color: var(--card-bg-2); border: 1px solid var(--border-strong); color: var(--text-primary);"
        >
          取消
        </button>
        <button
          @click="handleSave"
          :disabled="loading"
          class="px-4 py-1.5 text-sm font-medium rounded cursor-pointer transition-colors"
          style="background-color: var(--accent); color: #fff;"
          :style="{ opacity: loading ? 0.7 : 1 }"
        >
          {{ loading ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>
