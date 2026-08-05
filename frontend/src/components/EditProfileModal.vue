<script setup lang="ts">
import { ref } from 'vue';
import { useAuth } from '../composables/useAuth';
import { defaultAvatars } from '../assets/default-avatars';

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const auth = useAuth();
const nickname = ref(auth.currentUser.value?.nickname || '');
const selectedAvatar = ref<string | null>(null);
const customAvatarUrl = ref<string | null>(null);
const saving = ref(false);
const error = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
const previewUrl = ref<string | null>(null);

const currentAvatar = ref(auth.currentUser.value?.avatar_url || '');

function getDefaultAvatarColor(id: string): string {
  const colors: Record<string, string> = {
    'default:1': '#FF6B6B',
    'default:2': '#4ECDC4',
    'default:3': '#45B7D1',
    'default:4': '#96CEB4',
    'default:5': '#FFEAA7',
  };
  return colors[id] || 'var(--accent)';
}

function selectDefaultAvatar(id: string) {
  selectedAvatar.value = id;
  customAvatarUrl.value = null;
  previewUrl.value = null;
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = (ev) => {
      previewUrl.value = ev.target?.result as string;
      customAvatarUrl.value = URL.createObjectURL(file);
      selectedAvatar.value = null;
    };
    reader.readAsDataURL(file);
  }
}

async function handleSave() {
  error.value = '';
  if (!nickname.value.trim()) {
    error.value = '昵称不能为空';
    return;
  }

  saving.value = true;
  try {
    const updateData: { nickname?: string; avatar_url?: string } = {};
    updateData.nickname = nickname.value.trim();

    if (selectedAvatar.value) {
      updateData.avatar_url = selectedAvatar.value;
    } else if (customAvatarUrl.value && fileInput.value?.files?.[0]) {
      // Upload the file first, then update profile
      const avatarUrl = await auth.uploadAvatar(fileInput.value.files[0]);
      updateData.avatar_url = avatarUrl;
    }

    await auth.updateProfile(updateData);
    emit('close');
  } catch (e: any) {
    error.value = e.message || '保存失败';
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
    style="background-color: rgba(0,0,0,0.4); backdrop-filter: blur(4px);"
    @click.self="emit('close')"
  >
    <div
      class="w-[400px] max-w-full rounded-[14px] border overflow-hidden"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 20px 50px rgba(0,0,0,.15);"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3.5 border-b" style="border-color: var(--border);">
        <h2 class="text-[14px] font-semibold" style="color: var(--text-primary);">修改个人资料</h2>
        <button
          @click="emit('close')"
          class="w-[24px] h-[24px] rounded-full flex items-center justify-center text-[14px] cursor-pointer transition-colors"
          style="color: var(--text-secondary);"
          @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--row-hover)'"
          @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = 'transparent'"
        >
          &times;
        </button>
      </div>

      <!-- Body -->
      <div class="px-5 py-4">
        <div v-if="error" class="mb-4 px-3 py-2 rounded-[8px] text-[12.5px]" style="background-color: rgba(255,69,58,0.1); color: var(--danger);">
          {{ error }}
        </div>

        <!-- Current avatar preview -->
        <div class="flex justify-center mb-4">
          <div
            class="w-[64px] h-[64px] rounded-full overflow-hidden flex items-center justify-center text-[24px] font-bold"
            :style="{
              backgroundColor: currentAvatar.startsWith('default:') ? getDefaultAvatarColor(currentAvatar) : 'var(--card-bg-2)',
              border: '2px solid var(--border-strong)',
            }"
          >
            <img
              v-if="currentAvatar && !currentAvatar.startsWith('default:')"
              :src="currentAvatar"
              class="w-full h-full object-cover"
              alt="current avatar"
            />
            <span v-else style="color: #fff;">{{ auth.currentUser?.nickname?.charAt(0) || '?' }}</span>
          </div>
        </div>

        <!-- Nickname -->
        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-secondary);">昵称</label>
          <input
            v-model="nickname"
            type="text"
            placeholder="输入昵称"
            class="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none transition-all"
            style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-primary);"
            @focus="($event.target as HTMLElement).style.borderColor = 'var(--accent)'"
            @blur="($event.target as HTMLElement).style.borderColor = 'var(--border)'"
          />
        </div>

        <!-- Avatar selection -->
        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-2" style="color: var(--text-secondary);">选择头像</label>
          <div class="flex items-center gap-2.5 flex-wrap">
            <div
              v-for="av in defaultAvatars"
              :key="av.id"
              @click="selectDefaultAvatar(av.id)"
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
                border: previewUrl ? '2.5px solid var(--accent)' : '2.5px dashed var(--border-strong)',
                backgroundColor: 'var(--card-bg-2)',
                color: 'var(--text-tertiary)',
                transform: previewUrl ? 'scale(1.1)' : 'scale(1)',
              }"
              title="上传自定义头像"
            >
              <img v-if="previewUrl" :src="previewUrl" class="w-full h-full rounded-full object-cover" />
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
      </div>

      <!-- Footer -->
      <div class="flex justify-end gap-2 px-5 py-3.5 border-t" style="border-color: var(--border);">
        <button
          @click="emit('close')"
          class="px-4 py-1.5 rounded-[8px] text-[12.5px] cursor-pointer transition-all"
          style="background-color: var(--card-bg-2); color: var(--text-primary); border: 1px solid var(--border);"
          @mouseenter="($event.currentTarget as HTMLElement).style.opacity = '0.8'"
          @mouseleave="($event.currentTarget as HTMLElement).style.opacity = '1'"
        >
          取消
        </button>
        <button
          @click="handleSave"
          :disabled="saving"
          class="px-4 py-1.5 rounded-[8px] text-[12.5px] font-medium cursor-pointer transition-all"
          style="background-color: var(--accent); color: #fff;"
          :style="{ opacity: saving ? 0.7 : 1 }"
        >
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>