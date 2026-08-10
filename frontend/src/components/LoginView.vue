<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';
import BaseButton from './base/BaseButton.vue';
import BaseInput from './base/BaseInput.vue';

const router = useRouter();
const auth = useAuth();

const username = ref('');
const password = ref('');
const error = ref('');
const loading = ref(false);

async function handleLogin() {
  if (!username.value.trim() || !password.value.trim()) {
    error.value = '请输入用户名和密码';
    return;
  }
  error.value = '';
  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    router.push('/projects');
  } catch (e: any) {
    error.value = e.message || '登录失败，请检查用户名和密码';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-page min-h-screen flex items-center justify-center p-4">
    <div class="auth-card w-[380px] max-w-full overflow-hidden">
      <!-- Branding -->
      <div class="flex flex-col items-center pt-10 pb-6">
        <svg viewBox="0 0 24 24" class="auth-logo w-[36px] h-[36px] mb-3" xmlns="http://www.w3.org/2000/svg">
          <line x1="12" y1="5" x2="6" y2="11" stroke="#0EA5A5" stroke-width="1.8"></line>
          <line x1="6" y1="11" x2="6" y2="17" stroke="#0EA5A5" stroke-width="1.8"></line>
          <line x1="6" y1="11" x2="15" y2="13" stroke="#0EA5A5" stroke-width="1.8"></line>
          <line x1="6" y1="17" x2="13" y2="19" stroke="#0EA5A5" stroke-width="1.8"></line>
          <circle cx="12" cy="5" r="2.3" fill="#22D3D3"></circle>
          <circle cx="6" cy="11" r="2.7" fill="#14B8B8"></circle>
          <circle cx="6" cy="17" r="2.3" fill="#0D9D9D"></circle>
          <circle cx="15" cy="13" r="1.9" fill="#22D3D3"></circle>
          <circle cx="13" cy="19" r="1.7" fill="#14B8B8"></circle>
        </svg>
        <h1 class="auth-title">EasyTest</h1>
        <p class="auth-subtitle mt-1">登录以继续使用</p>
      </div>

      <!-- Form -->
      <div class="px-6 pb-6">
        <div v-if="error" class="error-box mb-4 px-3 py-2 rounded-[8px] text-[12.5px]">
          {{ error }}
        </div>

        <div class="mb-4">
          <label class="auth-label block text-[12px] font-medium mb-1.5">用户名</label>
          <BaseInput
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            @enter="handleLogin"
          />
        </div>

        <div class="mb-5">
          <label class="auth-label block text-[12px] font-medium mb-1.5">密码</label>
          <BaseInput
            v-model="password"
            type="password"
            placeholder="请输入密码"
            @enter="handleLogin"
          />
        </div>

        <BaseButton
          variant="primary"
          size="md"
          class="w-full"
          @click="handleLogin"
          :disabled="loading"
        >
          {{ loading ? '登录中...' : '登录' }}
        </BaseButton>

        <div class="mt-4 text-center">
          <span class="text-[12.5px]" style="color: var(--text-secondary);">还没有账号？</span>
          <router-link to="/register" class="auth-link text-[12.5px] font-medium ml-1">注册</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  background-color: var(--bg-window);
  font-family: var(--font);
  background-image:
    radial-gradient(circle at 15% 20%, var(--color-primary-soft) 0%, transparent 45%),
    radial-gradient(circle at 85% 85%, var(--color-primary-soft) 0%, transparent 45%);
}
.auth-card {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
}
.auth-logo line {
  stroke: var(--cta);
}
.auth-logo circle {
  fill: var(--color-primary);
}
.auth-logo circle:nth-of-type(even) {
  fill: var(--cta);
}
.auth-title {
  font-family: var(--font-heading);
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
}
.auth-subtitle {
  font-size: 18px;
  color: var(--text-secondary);
}
.error-box {
  background-color: var(--danger-soft);
  color: var(--danger);
}
.auth-label {
  color: var(--text-secondary);
}
.auth-link {
  color: var(--cta);
  font-weight: 600;
}
</style>
