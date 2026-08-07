<script setup lang="ts">
import { ref, reactive } from 'vue';
import BaseDialog from './base/BaseDialog.vue';
import BaseButton from './base/BaseButton.vue';

interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: string;
}

const isOpen = ref(false);
const resolvePromise = ref<((value: boolean) => void) | null>(null);
const opts = reactive<ConfirmOptions>({
  title: '',
  message: '',
  confirmText: '确认',
  cancelText: '取消',
  confirmColor: 'var(--accent)',
});

function confirm(options: ConfirmOptions): Promise<boolean> {
  Object.assign(opts, {
    title: options.title,
    message: options.message,
    confirmText: options.confirmText || '确认',
    cancelText: options.cancelText || '取消',
    confirmColor: options.confirmColor || 'var(--accent)',
  });
  isOpen.value = true;
  return new Promise((resolve) => {
    resolvePromise.value = resolve;
  });
}

function handleConfirm() {
  isOpen.value = false;
  resolvePromise.value?.(true);
  resolvePromise.value = null;
}

function handleCancel() {
  isOpen.value = false;
  resolvePromise.value?.(false);
  resolvePromise.value = null;
}

function handleBackdropClick() {
  handleCancel();
}

defineExpose({ confirm });
</script>

<template>
  <BaseDialog :open="isOpen" :title="opts.title" :width="340" @close="handleCancel">
    <!-- Body -->
    <div class="px-[20px] py-[18px]">
      <p class="text-[12.5px] leading-relaxed" style="color: var(--text-secondary);">{{ opts.message }}</p>
    </div>

    <!-- Footer -->
    <template #footer>
      <BaseButton variant="secondary" size="md" @click="handleCancel">
        {{ opts.cancelText }}
      </BaseButton>
      <button
        @click="handleConfirm"
        class="px-[14px] py-[6px] text-[12px] font-medium rounded-[7px] cursor-pointer transition-all duration-150 active:scale-[0.97]"
        :style="{
          backgroundColor: opts.confirmColor,
          color: '#fff',
        }"
      >
        {{ opts.confirmText }}
      </button>
    </template>
  </BaseDialog>
</template>