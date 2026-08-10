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
    style="background-color: var(--overlay-bg); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);"
    @click.self="emit('close')"
  >
    <div
      class="profile-panel w-[400px] max-w-full overflow-hidden"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3.5 border-b" style="border-color: var(--border);">
        <h2 class="profile-title">修改个人资料</h2>
        <button
          @click="emit('close')"
          class="dialog-close-btn"
        >
          ×
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
            <span v-else style="color: #fff;">{{ auth.currentUser?.value?.nickname?.charAt(0) || '?' }}</span>
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
/* ── Claymorphism：弹窗面板（3px 硬描边 + 硬阴影 + 柔和投影） ── */
.profile-panel {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
}

/* ── Claymorphism：弹窗标题 ── */
.profile-title {
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Claymorphism：统一 × 关闭按钮 ── */
.dialog-close-btn {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background: var(--bg-soft);
  color: var(--text-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: all 0.15s ease;
}
.dialog-close-btn:hover {
  background: var(--color-primary-soft);
  color: var(--text-primary);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
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