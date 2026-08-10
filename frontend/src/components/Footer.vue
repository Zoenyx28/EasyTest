<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const backendStatus = ref<'connected' | 'disconnected' | 'checking'>('checking');
const backendInfo = ref('');
let healthTimer: ReturnType<typeof setInterval> | null = null;

async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) {
      backendStatus.value = 'disconnected';
      return;
    }
    const json = await res.json();
    if (json?.code === 200) {
      backendStatus.value = 'connected';
      backendInfo.value = json.data?.service || 'Backend';
    } else {
      backendStatus.value = 'disconnected';
    }
  } catch {
    backendStatus.value = 'disconnected';
  }
}

onMounted(() => {
  checkHealth();
  healthTimer = setInterval(checkHealth, 15000);
});

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer);
});
</script>

<template>
  <footer class="footer-bar fixed bottom-0 left-0 right-0 h-8 flex items-center justify-between px-6 z-40 border-t text-xs font-code">
    <div class="flex items-center gap-2">
      <span
        class="w-2 h-2 rounded-full inline-block"
        :class="{
          'bg-[var(--color-warning)] animate-pulse': backendStatus === 'checking',
          'bg-[var(--color-success)] animate-pulse': backendStatus === 'connected',
          'bg-[var(--color-danger)]': backendStatus === 'disconnected',
        }"
      ></span>
      <span
        :class="{
          'text-[var(--color-warning)]': backendStatus === 'checking',
          'text-[var(--color-success)]': backendStatus === 'connected',
          'text-[var(--color-danger)]': backendStatus === 'disconnected',
        }"
      >
        <template v-if="backendStatus === 'checking'">Checking backend...</template>
        <template v-else-if="backendStatus === 'connected'">Backend Connected: {{ backendInfo }}</template>
        <template v-else>Backend Disconnected</template>
      </span>
    </div>

  </footer>
</template>

<style scoped>
.footer-bar {
  background-color: var(--bg-window);
  border-color: var(--border);
  color: var(--text-tertiary);
}
</style>
