<script setup lang="ts">
import { ref } from 'vue';
import { useAuth } from '../composables/useAuth';

const emit = defineEmits<{
  (e: 'openChangePassword'): void;
  (e: 'openEditProfile'): void;
  (e: 'close'): void;
}>();

const auth = useAuth();
const showMenu = ref(false);

function toggleMenu() {
  showMenu.value = !showMenu.value;
}

function handleChangePassword() {
  showMenu.value = false;
  emit('openChangePassword');
}

function handleEditProfile() {
  showMenu.value = false;
  emit('openEditProfile');
}

function handleLogout() {
  showMenu.value = false;
  auth.logout();
}

function handleClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('.user-menu-container')) {
    showMenu.value = false;
  }
}

import { onMounted, onUnmounted } from 'vue';

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

function getAvatarDisplay(): string {
  if (auth.currentUser.value?.avatar_url) {
    const url = auth.currentUser.value.avatar_url;
    if (url.startsWith('default:')) {
      return '';
    }
    return url;
  }
  return '';
}

function getInitial(): string {
  const nick = auth.currentUser.value?.nickname;
  return nick ? nick.charAt(0) : '?';
}

function getDefaultAvatarColor(): string {
  if (auth.currentUser.value?.avatar_url?.startsWith('default:')) {
    const id = auth.currentUser.value.avatar_url;
    const colors: Record<string, string> = {
      'default:1': '#FF6B6B',
      'default:2': '#4ECDC4',
      'default:3': '#45B7D1',
      'default:4': '#96CEB4',
      'default:5': '#FFEAA7',
    };
    return colors[id] || 'var(--accent)';
  }
  return 'var(--accent)';
}

function isDefaultAvatar(): boolean {
  return auth.currentUser.value?.avatar_url?.startsWith('default:') ?? false;
}
</script>

<template>
  <div class="user-menu-container relative">
    <!-- Avatar button -->
    <button
      @click.stop="toggleMenu"
      class="w-[30px] h-[30px] rounded-full flex items-center justify-center cursor-pointer overflow-hidden transition-all"
      :style="{
        border: '1.5px solid var(--border-strong)',
        backgroundColor: isDefaultAvatar() ? getDefaultAvatarColor() : 'var(--card-bg-2)',
      }"
      :title="auth.currentUser.value?.nickname || '用户'"
    >
      <img
        v-if="getAvatarDisplay() && !isDefaultAvatar()"
        :src="getAvatarDisplay()"
        class="w-full h-full object-cover"
        alt="avatar"
      />
      <span
        v-else
        class="text-[12px] font-semibold"
        :style="{ color: isDefaultAvatar() ? '#fff' : 'var(--text-primary)' }"
      >
        {{ getInitial() }}
      </span>
    </button>

    <!-- Dropdown menu -->
    <div
      v-if="showMenu"
      class="absolute top-full right-0 mt-1.5 min-w-[160px] rounded-[10px] py-1 z-50 shadow-lg"
      style="background-color: var(--card-bg); border: 1px solid var(--border);"
    >
      <div
        class="px-3 py-2 text-[12.5px] font-medium border-b truncate"
        style="color: var(--text-primary); border-color: var(--border);"
      >
        {{ auth.currentUser.value?.nickname || '用户' }}
      </div>

      <button
        @click="handleEditProfile"
        class="flex items-center gap-2 w-full px-3 py-2 text-[12.5px] text-left cursor-pointer transition-colors"
        style="color: var(--text-primary);"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--row-hover)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = 'transparent'"
      >
        <svg class="w-[14px] h-[14px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
        修改个人资料
      </button>

      <button
        @click="handleChangePassword"
        class="flex items-center gap-2 w-full px-3 py-2 text-[12.5px] text-left cursor-pointer transition-colors"
        style="color: var(--text-primary);"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--row-hover)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = 'transparent'"
      >
        <svg class="w-[14px] h-[14px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        修改密码
      </button>

      <div class="border-t mx-2" style="border-color: var(--border);"></div>

      <button
        @click="handleLogout"
        class="flex items-center gap-2 w-full px-3 py-2 text-[12.5px] text-left cursor-pointer transition-colors"
        style="color: var(--danger);"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--row-hover)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = 'transparent'"
      >
        <svg class="w-[14px] h-[14px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
          <polyline points="16 17 21 12 16 7"></polyline>
          <line x1="21" y1="12" x2="9" y2="12"></line>
        </svg>
        退出登录
      </button>
    </div>
  </div>
</template>