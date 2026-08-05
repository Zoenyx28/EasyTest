<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useProjectMembers } from '../composables/useProjectMembers';
import { useAuth } from '../composables/useAuth';
import type { ProjectMemberInfo, UserSearchResult } from '../types';

const props = defineProps<{
  isOpen: boolean;
  projectId: number;
  creatorId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'showToast', msg: string): void;
  (e: 'updated'): void;
}>();

const { getMembers, addMember, removeMember, searchUsers } = useProjectMembers();
const auth = useAuth();

const members = ref<ProjectMemberInfo[]>([]);
const loading = ref(false);
const searchQuery = ref('');
const searchResults = ref<UserSearchResult[]>([]);
const searchLoading = ref(false);
const addingUserId = ref<number | null>(null);

async function loadMembers() {
  if (!props.projectId) return;
  loading.value = true;
  try {
    members.value = await getMembers(props.projectId);
  } catch (e: any) {
    emit('showToast', e.message || '加载成员列表失败');
  } finally {
    loading.value = false;
  }
}

async function handleSearch() {
  const q = searchQuery.value.trim();
  if (!q) {
    searchResults.value = [];
    return;
  }
  searchLoading.value = true;
  try {
    searchResults.value = await searchUsers(props.projectId, q);
  } catch (e: any) {
    searchResults.value = [];
  } finally {
    searchLoading.value = false;
  }
}

async function handleAddMember(userId: number) {
  addingUserId.value = userId;
  try {
    await addMember(props.projectId, userId);
    emit('showToast', '添加成功');
    searchQuery.value = '';
    searchResults.value = [];
    await loadMembers();
    emit('updated');
  } catch (e: any) {
    emit('showToast', e.message || '添加失败');
  } finally {
    addingUserId.value = null;
  }
}

async function handleRemoveMember(userId: number) {
  if (userId === props.creatorId) {
    emit('showToast', '不能移除项目创建人');
    return;
  }
  try {
    await removeMember(props.projectId, userId);
    emit('showToast', '移除成功');
    await loadMembers();
    emit('updated');
  } catch (e: any) {
    emit('showToast', e.message || '移除失败');
  }
}

function handleClose() {
  searchQuery.value = '';
  searchResults.value = [];
  emit('close');
}

watch(() => props.isOpen, (val) => {
  if (val && props.projectId) {
    loadMembers();
  }
});

watch(searchQuery, () => {
  handleSearch();
});
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 flex items-center justify-center z-50 p-4"
    style="background: rgba(0,0,0,.32);"
    @click.self="handleClose"
  >
    <div
      class="w-[440px] max-w-[90vw] rounded-[14px] border overflow-hidden"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 20px 50px rgba(0,0,0,.3);"
    >
      <!-- macOS-style header -->
      <div
        class="flex items-center justify-between px-[18px] py-[14px] border-b"
        style="border-color: var(--border);"
      >
        <h3 class="text-[15px] font-semibold" style="color: var(--text-primary);">项目成员</h3>
        <button
          @click="handleClose"
          class="cursor-pointer text-[15px]"
          style="color: var(--text-tertiary);"
        >
          ✕
        </button>
      </div>

      <div class="px-[18px] py-[16px]">
        <!-- Member list -->
        <div class="mb-4">
          <label class="block text-[12px] font-medium mb-2" style="color: var(--text-secondary);">成员列表 ({{ members.length }})</label>
          <div class="max-h-[200px] overflow-y-auto space-y-1">
            <div v-if="loading" class="flex items-center justify-center py-4">
              <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" style="color: var(--text-tertiary);">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.2"/>
                <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
              </svg>
            </div>
            <div
              v-for="member in members"
              :key="member.id"
              class="flex items-center gap-[10px] px-[10px] py-[8px] rounded-[8px]"
              style="background-color: var(--input-bg);"
            >
              <!-- Avatar -->
              <div
                class="w-[28px] h-[28px] rounded-full shrink-0 flex items-center justify-center text-[11px] font-medium"
                style="background-color: var(--accent); color: #fff;"
              >
                {{ member.nickname ? member.nickname.charAt(0).toUpperCase() : '?' }}
              </div>
              <!-- User info -->
              <div class="flex-1 min-w-0">
                <div class="text-[12.5px] font-medium truncate" style="color: var(--text-primary);">
                  {{ member.nickname || member.username }}
                  <span v-if="member.user_id === creatorId" class="ml-1 text-[10px] px-[5px] py-[1px] rounded-[4px]" style="background-color: rgba(255,189,46,0.15); color: rgb(255,189,46);">创建人</span>
                </div>
                <div class="text-[10.5px] truncate" style="color: var(--text-tertiary);">@{{ member.username }}</div>
              </div>
              <!-- Remove button -->
              <button
                v-if="member.user_id !== creatorId"
                @click="handleRemoveMember(member.user_id)"
                class="px-[10px] py-[3px] text-[11px] font-medium rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.95]"
                style="color: rgb(255,69,58); background-color: rgba(255,69,58,0.08);"
              >
                移除
              </button>
              <div v-else class="text-[11px]" style="color: var(--text-tertiary);">--</div>
            </div>
            <div v-if="!loading && members.length === 0" class="text-center py-4 text-[12px]" style="color: var(--text-tertiary);">
              暂无成员
            </div>
          </div>
        </div>

        <!-- macOS-style separator -->
        <div class="mb-4" style="height: 0.5px; background-color: var(--border);"></div>

        <!-- Add member section -->
        <div>
          <label class="block text-[12px] font-medium mb-2" style="color: var(--text-secondary);">添加成员</label>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索用户昵称或用户名"
            class="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none transition-all mb-2"
            style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-primary);"
            @focus="($event.target as HTMLElement).style.borderColor = 'var(--accent)'"
            @blur="($event.target as HTMLElement).style.borderColor = 'var(--border)'"
          />
          <!-- Search results -->
          <div class="max-h-[160px] overflow-y-auto space-y-1">
            <div v-if="searchLoading" class="flex items-center justify-center py-3">
              <svg class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" style="color: var(--text-tertiary);">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.2"/>
                <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
              </svg>
            </div>
            <div
              v-for="user in searchResults"
              :key="user.id"
              class="flex items-center gap-[10px] px-[10px] py-[8px] rounded-[8px] cursor-pointer transition-all duration-150 hover:opacity-80"
              style="background-color: var(--input-bg);"
              @click="handleAddMember(user.id)"
            >
              <div
                class="w-[28px] h-[28px] rounded-full shrink-0 flex items-center justify-center text-[11px] font-medium"
                style="background-color: var(--accent); color: #fff;"
              >
                {{ user.nickname ? user.nickname.charAt(0).toUpperCase() : '?' }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-[12.5px] font-medium truncate" style="color: var(--text-primary);">{{ user.nickname || user.username }}</div>
                <div class="text-[10.5px] truncate" style="color: var(--text-tertiary);">@{{ user.username }}</div>
              </div>
              <button
                :disabled="addingUserId === user.id"
                class="px-[10px] py-[3px] text-[11px] font-medium rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.95]"
                style="background-color: var(--accent); color: #fff;"
              >
                {{ addingUserId === user.id ? '添加中...' : '添加' }}
              </button>
            </div>
            <div v-if="searchQuery && !searchLoading && searchResults.length === 0" class="text-center py-3 text-[12px]" style="color: var(--text-tertiary);">
              未找到匹配的用户
            </div>
          </div>
        </div>
      </div>

      <!-- macOS-style footer -->
      <div
        class="flex justify-end px-[18px] py-[12px] border-t"
        style="border-color: var(--border);"
      >
        <button
          @click="handleClose"
          class="px-4 py-1.5 text-sm font-medium rounded cursor-pointer transition-colors"
          style="background-color: var(--card-bg-2); border: 1px solid var(--border-strong); color: var(--text-primary);"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>