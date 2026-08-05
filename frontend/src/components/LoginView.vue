<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';

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
  <div
    class="min-h-screen flex items-center justify-center p-4"
    style="background-color: var(--bg-window);"
  >
    <div
      class="w-[380px] max-w-full rounded-[14px] border overflow-hidden"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 20px 50px rgba(0,0,0,.15);"
    >
      <!-- Branding -->
      <div class="flex flex-col items-center pt-10 pb-6">
        <svg viewBox="0 0 24 24" class="w-[36px] h-[36px] mb-3" xmlns="http://www.w3.org/2000/svg">
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
        <h1 class="text-[20px] font-semibold" style="color: var(--text-primary);">EasyTest</h1>
        <p class="text-[12.5px] mt-1" style="color: var(--text-secondary);">登录以继续使用</p>
      </div>

      <!-- Form -->
      <div class="px-6 pb-6">
        <div v-if="error" class="mb-4 px-3 py-2 rounded-[8px] text-[12.5px]" style="background-color: rgba(255, 69, 58, 0.1); color: var(--danger);">
          {{ error }}
        </div>

        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-secondary);">用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            class="w-full px-3 py-2.5 rounded-[8px] text-[13px] outline-none transition-all"
            style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-primary);"
            @focus="($event.target as HTMLElement).style.borderColor = 'var(--accent)'"
            @blur="($event.target as HTMLElement).style.borderColor = 'var(--border)'"
            @keyup.enter="handleLogin"
          />
        </div>

        <div class="mb-5">
          <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-secondary);">密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            class="w-full px-3 py-2.5 rounded-[8px] text-[13px] outline-none transition-all"
            style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-primary);"
            @focus="($event.target as HTMLElement).style.borderColor = 'var(--accent)'"
            @blur="($event.target as HTMLElement).style.borderColor = 'var(--border)'"
            @keyup.enter="handleLogin"
          />
        </div>

        <button
          @click="handleLogin"
          :disabled="loading"
          class="w-full py-2.5 rounded-[8px] text-[13px] font-medium cursor-pointer transition-all"
          :style="{
            backgroundColor: loading ? 'var(--accent)' : 'var(--accent)',
            color: '#fff',
            opacity: loading ? 0.7 : 1,
          }"
          @mouseenter="!loading && (($event.target as HTMLElement).style.opacity = '0.9')"
          @mouseleave="!loading && (($event.target as HTMLElement).style.opacity = '1')"
        >
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <div class="mt-4 text-center">
          <span class="text-[12.5px]" style="color: var(--text-secondary);">还没有账号？</span>
          <router-link to="/register" class="text-[12.5px] font-medium ml-1" style="color: var(--accent);">注册</router-link>
        </div>
      </div>
    </div>
  </div>
</template>