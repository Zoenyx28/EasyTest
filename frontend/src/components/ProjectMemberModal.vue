<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useProjectMembers } from '../composables/useProjectMembers';
import { useAuth } from '../composables/useAuth';
import type { ProjectMemberInfo, UserSearchResult } from '../types';
import UserAvatar from './UserAvatar.vue';

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
    style="background: var(--overlay-bg);"
    @click.self="handleClose"
  >
    <div
      class="member-modal w-[440px] max-w-[90vw] overflow-hidden"
    >
      <!-- Modal header -->
      <div
        class="modal-header flex items-center justify-between px-[18px] py-[14px]"
      >
        <h3 class="modal-title">项目成员</h3>
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
              <UserAvatar
                :name="member.nickname || member.username"
                :avatar="member.avatar_url"
                :size="28"
              />
              <!-- User info -->
              <div class="flex-1 min-w-0">
                <div class="text-[12.5px] font-medium truncate" style="color: var(--text-primary);">
                  {{ member.nickname || member.username }}
                  <span v-if="member.user_id === creatorId" class="ml-1 text-[10px] px-[5px] py-[1px] rounded-[4px]" style="background-color: var(--warning-soft); color: var(--color-warning);">创建人</span>
                </div>
                <div class="text-[10.5px] truncate" style="color: var(--text-tertiary);">@{{ member.username }}</div>
              </div>
              <!-- Remove button -->
              <button
                v-if="member.user_id !== creatorId"
                @click="handleRemoveMember(member.user_id)"
                class="px-[10px] py-[3px] text-[11px] font-medium rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.95]"
                style="color: var(--color-danger); background-color: var(--danger-soft);"
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

        <!-- Separator -->
        <div class="mb-4" style="height: 1px; background-color: var(--border);"></div>

        <!-- Add member section -->
        <div>
          <label class="block text-[12px] font-medium mb-2" style="color: var(--text-secondary);">添加成员</label>
          <BaseInput
            v-model="searchQuery"
            type="text"
            placeholder="搜索用户昵称或用户名"
            class="mb-2"
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
              <UserAvatar
                :name="user.nickname || user.username"
                :avatar="user.avatar_url"
                :size="28"
              />
              <div class="flex-1 min-w-0">
                <div class="text-[12.5px] font-medium truncate" style="color: var(--text-primary);">{{ user.nickname || user.username }}</div>
                <div class="text-[10.5px] truncate" style="color: var(--text-tertiary);">@{{ user.username }}</div>
              </div>
              <button
                :disabled="addingUserId === user.id"
                class="clay-btn clay-btn-primary px-[10px] py-[3px] text-[11px] font-medium"
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

      <!-- Modal footer -->
      <div
        class="modal-footer flex justify-end px-[18px] py-[12px]"
      >
        <button
          @click="handleClose"
          class="clay-btn clay-btn-secondary px-4 py-1.5 text-sm font-medium"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.member-modal {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
}

.modal-header {
  border-bottom: 2px solid var(--outline);
}

.modal-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-footer {
  border-top: 2px solid var(--outline);
}

/* ── Clay 按钮 ── */
.clay-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  font-family: var(--font);
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  box-shadow: var(--shadow-hard-sm);
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}
.clay-btn:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.clay-btn:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
}
.clay-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.clay-btn-primary {
  background-color: var(--cta);
  color: #fff;
}
.clay-btn-primary:hover {
  background-color: var(--cta-dark);
}
.clay-btn-secondary {
  background-color: var(--color-secondary);
  color: var(--text-primary);
}
.clay-btn-secondary:hover {
  background-color: var(--color-secondary-dark);
}

.animate-spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>