<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';
import { defaultAvatars } from '../assets/default-avatars';
import BaseButton from './base/BaseButton.vue';
import BaseInput from './base/BaseInput.vue';

const router = useRouter();
const auth = useAuth();

const username = ref('');
const nickname = ref('');
const password = ref('');
const confirmPassword = ref('');
const selectedAvatar = ref<string | null>(null);
const customAvatarUrl = ref<string | null>(null);
const error = ref('');
const loading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

function selectAvatar(id: string) {
  selectedAvatar.value = id;
  customAvatarUrl.value = null;
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = (ev) => {
      customAvatarUrl.value = ev.target?.result as string;
      selectedAvatar.value = null;
    };
    reader.readAsDataURL(file);
  }
}

function getAvatarUrl(avatarId: string): string {
  const found = defaultAvatars.find(a => a.id === avatarId);
  return found ? `data:image/svg+xml,${encodeURIComponent(found.svg)}` : '';
}

async function handleRegister() {
  error.value = '';
  if (!username.value.trim()) {
    error.value = '请输入用户名';
    return;
  }
  if (!nickname.value.trim()) {
    error.value = '请输入昵称';
    return;
  }
  if (!password.value) {
    error.value = '请输入密码';
    return;
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次密码输入不一致';
    return;
  }
  if (password.value.length < 6) {
    error.value = '密码长度至少6位';
    return;
  }

  loading.value = true;
  try {
    let avatar = selectedAvatar.value || undefined;
    if (customAvatarUrl.value && !selectedAvatar.value) {
      avatar = customAvatarUrl.value;
    }
    await auth.register(username.value.trim(), nickname.value.trim(), password.value, avatar);
    router.push('/projects');
  } catch (e: any) {
    error.value = e.message || '注册失败';
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
      class="w-[420px] max-w-full rounded-[14px] border overflow-hidden"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 20px 50px rgba(0,0,0,.15);"
    >
      <!-- Branding -->
      <div class="flex flex-col items-center pt-8 pb-4">
        <svg viewBox="0 0 24 24" class="w-[30px] h-[30px] mb-2" xmlns="http://www.w3.org/2000/svg">
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
        <h1 class="text-[18px] font-semibold" style="color: var(--text-primary);">创建账号</h1>
        <p class="text-[12px] mt-0.5" style="color: var(--text-secondary);">注册 EasyTest 账号</p>
      </div>

      <!-- Form -->
      <div class="px-6 pb-6">
        <div v-if="error" class="mb-4 px-3 py-2 rounded-[8px] text-[12.5px]" style="background-color: rgba(255, 69, 58, 0.1); color: var(--danger);">
          {{ error }}
        </div>

        <div class="mb-3">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">用户名</label>
          <BaseInput
            v-model="username"
            type="text"
            placeholder="输入用户名"
          />
        </div>

        <div class="mb-3">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">昵称</label>
          <BaseInput
            v-model="nickname"
            type="text"
            placeholder="输入昵称"
          />
        </div>

        <div class="mb-3">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">密码</label>
          <BaseInput
            v-model="password"
            type="password"
            placeholder="至少6位密码"
          />
        </div>

        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-1" style="color: var(--text-secondary);">确认密码</label>
          <BaseInput
            v-model="confirmPassword"
            type="password"
            placeholder="再次输入密码"
          />
        </div>

        <!-- Avatar Selection -->
        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-2" style="color: var(--text-secondary);">选择头像</label>
          <div class="flex items-center gap-2.5 flex-wrap">
            <div
              v-for="av in defaultAvatars"
              :key="av.id"
              @click="selectAvatar(av.id)"
              class="w-[38px] h-[38px] rounded-full cursor-pointer transition-all"
              :style="{
                border: selectedAvatar === av.id ? '2.5px solid var(--accent)' : '2.5px solid transparent',
                transform: selectedAvatar === av.id ? 'scale(1.1)' : 'scale(1)',
              }"
              v-html="av.svg"
            ></div>

            <!-- Custom upload -->
            <div
              @click="fileInput?.click()"
              class="w-[38px] h-[38px] rounded-full flex items-center justify-center cursor-pointer text-[16px] transition-all"
              :style="{
                border: customAvatarUrl ? '2.5px solid var(--accent)' : '2.5px dashed var(--border-strong)',
                backgroundColor: 'var(--card-bg-2)',
                color: 'var(--text-tertiary)',
                transform: customAvatarUrl ? 'scale(1.1)' : 'scale(1)',
              }"
              title="上传自定义头像"
            >
              <img v-if="customAvatarUrl" :src="customAvatarUrl" class="w-full h-full rounded-full object-cover" />
              <span v-else>+</span>
            </div>
            <input
              ref="fileInput"
              type="file"
              accept="image/png,image/svg+xml,image/jpeg,image/gif"
              class="hidden"
              @change="handleFileSelect"
            />
          </div>
        </div>

        <BaseButton
          variant="primary"
          size="md"
          class="w-full"
          @click="handleRegister"
          :disabled="loading"
        >
          {{ loading ? '注册中...' : '注册' }}
        </BaseButton>

        <div class="mt-4 text-center">
          <span class="text-[12.5px]" style="color: var(--text-secondary);">已有账号？</span>
          <router-link to="/login" class="text-[12.5px] font-medium ml-1" style="color: var(--accent);">登录</router-link>
        </div>
      </div>
    </div>
  </div>
</template>
