<script setup lang="ts">
import { ref, reactive } from 'vue';

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
  <teleport to="body">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-[100] flex items-center justify-center"
      style="background-color: rgba(0,0,0,0.3); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);"
      @click="handleBackdropClick"
    >
      <div
        class="w-[340px] rounded-[14px] overflow-hidden"
        style="background-color: var(--card-bg); box-shadow: 0 12px 60px rgba(0,0,0,0.2);"
        @click.stop
      >
        <!-- macOS traffic-light header -->
        <div class="flex items-center gap-[8px] px-[16px] py-[12px] select-none" style="border-bottom: 0.5px solid var(--border);">
          <div class="w-[12px] h-[12px] rounded-full" style="background-color: rgb(255,95,87);"></div>
          <div class="w-[12px] h-[12px] rounded-full" style="background-color: rgb(255,189,46);"></div>
          <div class="w-[12px] h-[12px] rounded-full" style="background-color: rgb(39,201,63);"></div>
          <span class="ml-[8px] text-[12px] font-medium" style="color: var(--text-primary);">{{ opts.title }}</span>
        </div>

        <!-- Body -->
        <div class="px-[20px] py-[18px]">
          <p class="text-[12.5px] leading-relaxed" style="color: var(--text-secondary);">{{ opts.message }}</p>
        </div>

        <!-- Footer -->
        <div class="flex justify-end gap-[8px] px-[20px] py-[14px]" style="border-top: 0.5px solid var(--border);">
          <button
            @click="handleCancel"
            class="px-[14px] py-[6px] text-[12px] font-medium rounded-[7px] cursor-pointer transition-all duration-150 active:scale-[0.97]"
            :style="{
              backgroundColor: 'var(--input-bg)',
              border: '0.5px solid var(--border)',
              color: 'var(--text-secondary)',
            }"
          >
            {{ opts.cancelText }}
          </button>
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
        </div>
      </div>
    </div>
  </teleport>
</template>