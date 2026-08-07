<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAuth } from '../composables/useAuth';
import { defaultAvatars } from '../assets/default-avatars';
import BaseButton from './base/BaseButton.vue';
import BaseInput from './base/BaseInput.vue';

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

function getDefaultSvgFor(url: string): string {
  let num = 0;
  const m = url.match(/^\/avatars\/(\d+)\.svg$/);
  if (m) num = parseInt(m[1], 10);
  else if (url.startsWith('default:')) num = parseInt(url.split(':')[1], 10);
  const av = defaultAvatars[num - 1];
  return av ? av.svg : '';
}

function isDefaultAvatar(url: string): boolean {
  return /^\/avatars\/\d+\.svg$/.test(url) || url.startsWith('default:');
}

// Preview: newly selected default avatar → its SVG; otherwise nothing
const previewDefaultSvg = computed(() => {
  if (selectedAvatar.value) return getDefaultSvgFor(selectedAvatar.value);
  if (currentAvatar.value && isDefaultAvatar(currentAvatar.value)) return getDefaultSvgFor(currentAvatar.value);
  return '';
});

// Preview: newly uploaded image (data URL) or the current custom image
const previewImageUrl = computed(() => {
  if (previewUrl.value) return previewUrl.value;
  if (currentAvatar.value && !isDefaultAvatar(currentAvatar.value)) return currentAvatar.value;
  return '';
});

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

        <!-- Avatar preview (updates live while selecting) -->
        <div class="flex justify-center mb-4">
          <div
            class="w-[64px] h-[64px] rounded-full overflow-hidden flex items-center justify-center text-[24px] font-bold"
            :style="{
              backgroundColor: previewDefaultSvg ? 'transparent' : 'var(--card-bg-2)',
              border: '2px solid var(--border-strong)',
            }"
          >
            <img
              v-if="previewImageUrl"
              :src="previewImageUrl"
              class="w-full h-full object-cover"
              alt="avatar preview"
            />
            <span
              v-else-if="previewDefaultSvg"
              class="avatar-preview-svg"
              v-html="previewDefaultSvg"
            ></span>
            <span v-else style="color: #fff;">{{ auth.currentUser?.nickname?.charAt(0) || '?' }}</span>
          </div>
        </div>

        <!-- Nickname -->
        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-1.5" style="color: var(--text-secondary);">昵称</label>
          <BaseInput
            v-model="nickname"
            type="text"
            placeholder="输入昵称"
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
        <BaseButton
          variant="primary"
          size="md"
          @click="handleSave"
          :disabled="saving"
        >
          {{ saving ? '保存中...' : '保存' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.avatar-preview-svg {
  display: flex;
  width: 100%;
  height: 100%;
}
.avatar-preview-svg :deep(svg) {
  width: 100%;
  height: 100%;
}
</style>