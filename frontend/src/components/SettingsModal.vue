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
  <div v-if="isOpen" class="fixed inset-0 flex items-center justify-center z-50 p-4" style="background-color: var(--overlay-bg);">
    <div 
      class="settings-panel w-[380px] max-w-[90vw] overflow-hidden"
    >
      <div 
        class="flex items-center justify-between px-[18px] py-[14px] border-b"
        style="border-color: var(--border);"
      >
        <h3 class="settings-title">执行设置</h3>
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
              class="step-btn w-[26px] h-[26px] text-[14px] cursor-pointer"
            >
              −
            </button>
            <span class="text-[14px] font-semibold min-w-[24px] text-center" style="color: var(--text-primary);">{{ timeoutSec }}</span>
            <button 
              @click="timeoutSec = Math.min(10, timeoutSec + 1)" 
              class="step-btn w-[26px] h-[26px] text-[14px] cursor-pointer"
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
              class="option-card flex-1 text-center px-2 py-[8px] text-[12.5px] cursor-pointer"
              :class="autoRetry ? 'option-card--active' : ''"
            >
              并发执行
            </div>
            <div 
              @click="autoRetry = false"
              class="option-card flex-1 text-center px-2 py-[8px] text-[12.5px] cursor-pointer"
              :class="!autoRetry ? 'option-card--active' : ''"
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
          class="btn-cancel px-4 py-1.5 text-sm font-medium rounded cursor-pointer"
        >
          取消
        </button>
        <button 
          @click="handleSave" 
          class="btn-save px-4 py-1.5 text-sm font-medium rounded cursor-pointer"
        >
          保存
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Claymorphism：弹窗面板（3px 硬描边 + 硬阴影 + 柔和投影） ── */
.settings-panel {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
}

/* ── Claymorphism：弹窗标题 ── */
.settings-title {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Claymorphism：步进按钮 ── */
.step-btn {
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background-color: var(--card-bg-2);
  color: var(--text-primary);
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}
.step-btn:hover {
  background-color: var(--bg-card-hover);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

/* ── Claymorphism：模式选项卡片 ── */
.option-card {
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background-color: var(--card-bg);
  box-shadow: var(--shadow-hard-sm);
  color: var(--text-secondary);
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.option-card:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.option-card--active {
  border-color: var(--color-primary);
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
  font-weight: 600;
}

/* ── Claymorphism：次级按钮 ── */
.btn-cancel {
  background-color: var(--card-bg-2);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}
.btn-cancel:hover {
  background-color: var(--bg-card-hover);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

/* ── Claymorphism：主 CTA 按钮（绿） ── */
.btn-save {
  background-color: var(--cta);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  color: #fff;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease, filter 0.15s ease;
}
.btn-save:hover {
  background-color: var(--cta-dark);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.btn-save:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
}
</style>