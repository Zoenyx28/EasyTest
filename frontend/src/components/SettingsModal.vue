<script setup lang="ts">
import { ref, onMounted } from 'vue';

defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'showToast', msg: string): void;
}>();

const STORAGE_KEY = 'pytest_pro_settings';

interface AppSettings {
  clusterName: string;
  timeoutSec: number;
  autoRetry: boolean;
  enableLiveLogs: boolean;
}

function loadSettings(): AppSettings {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return { clusterName: 'default', timeoutSec: 30, autoRetry: true, enableLiveLogs: true };
}

function persistSettings(settings: AppSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

const clusterName = ref('default');
const timeoutSec = ref(30);
const autoRetry = ref(true);
const enableLiveLogs = ref(true);

onMounted(() => {
  const s = loadSettings();
  clusterName.value = s.clusterName;
  timeoutSec.value = s.timeoutSec;
  autoRetry.value = s.autoRetry;
  enableLiveLogs.value = s.enableLiveLogs;
});

const handleSave = () => {
  persistSettings({
    clusterName: clusterName.value,
    timeoutSec: timeoutSec.value,
    autoRetry: autoRetry.value,
    enableLiveLogs: enableLiveLogs.value,
  });
  emit('showToast', '设置已保存');
  emit('close');
};
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 flex items-center justify-center z-50 p-4" style="background: rgba(0,0,0,.32);">
    <div 
      class="w-[380px] max-w-[90vw] rounded-[14px] border overflow-hidden"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 20px 50px rgba(0,0,0,.3);"
    >
      <div 
        class="flex items-center justify-between px-[18px] py-[14px] border-b"
        style="border-color: var(--border);"
      >
        <h3 class="text-[15px] font-semibold" style="color: var(--text-primary);">执行设置</h3>
        <button 
          @click="emit('close')" 
          class="cursor-pointer text-[15px]"
          style="color: var(--text-tertiary);"
        >
          ✕
        </button>
      </div>

      <div class="px-[18px] py-[16px] text-[13px]" style="color: var(--text-secondary);">
        <div class="mb-[16px]">
          <div class="text-[12px] font-semibold mb-[8px]" style="color: var(--text-primary);">并发数</div>
          <div class="flex items-center gap-[10px]">
            <button 
              @click="timeoutSec = Math.max(1, timeoutSec - 1)" 
              class="w-[26px] h-[26px] rounded-[7px] border text-[14px] cursor-pointer"
              style="border-color: var(--border-strong); background-color: var(--card-bg-2); color: var(--text-primary);"
            >
              −
            </button>
            <span class="text-[14px] font-semibold min-w-[24px] text-center" style="color: var(--text-primary);">{{ timeoutSec }}</span>
            <button 
              @click="timeoutSec = Math.min(10, timeoutSec + 1)" 
              class="w-[26px] h-[26px] rounded-[7px] border text-[14px] cursor-pointer"
              style="border-color: var(--border-strong); background-color: var(--card-bg-2); color: var(--text-primary);"
            >
              +
            </button>
            <span class="text-[11.5px]" style="color: var(--text-tertiary);">最多 10 个并发</span>
          </div>
        </div>

        <div>
          <div class="text-[12px] font-semibold mb-[8px]" style="color: var(--text-primary);">执行模式</div>
          <div class="flex gap-[8px]">
            <div 
              @click="autoRetry = true"
              class="flex-1 text-center px-2 py-[8px] rounded-[8px] border text-[12.5px] cursor-pointer"
              :class="autoRetry ? 'border-[var(--accent)] bg-[var(--selected-bg)] text-[var(--accent)] font-semibold' : 'border-[var(--border)] text-[var(--text-secondary)]'"
            >
              并发执行
            </div>
            <div 
              @click="autoRetry = false"
              class="flex-1 text-center px-2 py-[8px] rounded-[8px] border text-[12.5px] cursor-pointer"
              :class="!autoRetry ? 'border-[var(--accent)] bg-[var(--selected-bg)] text-[var(--accent)] font-semibold' : 'border-[var(--border)] text-[var(--text-secondary)]'"
            >
              顺序执行
            </div>
          </div>
        </div>
      </div>

      <div 
        class="flex justify-end gap-[8px] px-[18px] py-[12px] border-t"
        style="border-color: var(--border);"
      >
        <button 
          @click="emit('close')" 
          class="px-4 py-1.5 text-sm font-medium rounded cursor-pointer transition-colors"
          style="background-color: var(--card-bg-2); border: 1px solid var(--border-strong); color: var(--text-primary);"
        >
          取消
        </button>
        <button 
          @click="handleSave" 
          class="px-4 py-1.5 text-sm font-medium rounded cursor-pointer transition-colors"
          style="background-color: var(--accent); border-color: var(--accent); color: #fff;"
        >
          保存
        </button>
      </div>
    </div>
  </div>
</template>