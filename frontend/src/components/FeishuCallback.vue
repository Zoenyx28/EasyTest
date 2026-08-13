<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useApi } from '../composables/useApi';

const route = useRoute();
const api = useApi();
const status = ref<'processing' | 'success' | 'error'>('processing');
const message = ref('正在完成飞书授权…');

onMounted(async () => {
  const code = (route.query.code as string) || '';
  if (!code) {
    status.value = 'error';
    message.value = '未收到授权回调参数（code），授权未完成。';
    return;
  }
  try {
    await api.post('/settings/feishu/token', { code });
    status.value = 'success';
    message.value = '飞书授权成功，可关闭此页面返回系统。';
  } catch (e: any) {
    status.value = 'error';
    message.value = e.message || '飞书授权失败，请返回系统重试。';
  }
});
</script>

<template>
  <div class="min-h-screen flex items-center justify-center" style="background: var(--bg);">
    <div class="card p-6 text-center" style="max-width: 420px; width: 90%;">
      <h2 class="text-lg font-semibold mb-3" style="color: var(--text-primary);">飞书授权</h2>
      <p class="text-sm" :style="{ color: status === 'success' ? 'var(--color-success)' : status === 'error' ? 'var(--color-warning)' : 'var(--text-secondary)' }">
        {{ message }}
      </p>
      <div v-if="status === 'processing'" class="mt-4 text-sm" style="color: var(--text-tertiary);">请稍候…</div>
      <a
        href="/requirements"
        class="inline-block mt-5 text-sm underline"
        style="color: var(--cta);"
      >返回系统</a>
    </div>
  </div>
</template>
