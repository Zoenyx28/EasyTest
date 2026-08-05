<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useAuth } from '../composables/useAuth';
import UserMenu from './UserMenu.vue';
import ChangePasswordModal from './ChangePasswordModal.vue';
import EditProfileModal from './EditProfileModal.vue';
import type { BranchInfo } from '../types';

const props = defineProps<{
  currentRoute: string;
  globalSearch: string;
}>();

const emit = defineEmits<{
  (e: 'update:globalSearch', val: string): void;
  (e: 'openSettings'): void;
  (e: 'openHelp'): void;
  (e: 'showToast', msg: string): void;
}>();

const router = useRouter();
const route = useRoute();
const { activeProject } = useProject();
const auth = useAuth();
const showChangePassword = ref(false);
const showEditProfile = ref(false);

// Use branch composable with current project id
const projectId = computed(() => activeProject.value?.id);
const { branches, activeBranch, loadBranches, switchBranch, createBranch, deleteBranch } = useBranch(projectId.value);

// Load branches when project changes
watch(projectId, (pid) => {
  if (pid) {
    loadBranches(pid);
  }
}, { immediate: true });

const showUserMenu = ref(false);
const showBranchMenu = ref(false);
const showCreateBranch = ref(false);
const showDeleteConfirm = ref(false);
const branchToDelete = ref<BranchInfo | null>(null);
const newBranchName = ref('');
const newBranchSource = ref<'empty' | 'copy'>('empty');
const theme = ref<'light' | 'dark'>('dark');

const selectTab = (tab: string) => {
  const query = route.query.version ? { version: route.query.version } : {};
  router.push({ path: `/${tab}`, query });
};

const toggleTheme = () => {
  theme.value = theme.value === 'light' ? 'dark' : 'light';
  applyTheme();
};

function applyTheme() {
  document.documentElement.setAttribute('data-theme', theme.value);
  localStorage.setItem('theme', theme.value);
}

function selectBranch(branch: BranchInfo) {
  switchBranch(branch);
  showBranchMenu.value = false;
}

async function handleCreateBranch() {
  if (!newBranchName.value.trim() || !projectId.value) return;
  const sourceId = newBranchSource.value === 'copy' ? activeBranch.value?.id : undefined;
  const result = await createBranch(newBranchName.value.trim(), sourceId);
  if (result) {
    emit('showToast', `分支 "${newBranchName.value}" 创建成功`);
    newBranchName.value = '';
    showCreateBranch.value = false;
  } else {
    emit('showToast', '分支创建失败');
  }
}

async function handleDeleteBranch(branch: BranchInfo) {
  branchToDelete.value = branch;
  showDeleteConfirm.value = true;
}

async function confirmDeleteBranch() {
  if (!branchToDelete.value) return;
  const ok = await deleteBranch(branchToDelete.value.id);
  if (ok) {
    emit('showToast', `分支 "${branchToDelete.value.name}" 已删除`);
  } else {
    emit('showToast', '分支删除失败');
  }
  branchToDelete.value = null;
  showDeleteConfirm.value = false;
}

// Close branch menu on outside click
function closeBranchMenu(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('.branch-selector')) {
    showBranchMenu.value = false;
  }
}

onMounted(() => {
  document.addEventListener('click', closeBranchMenu);
  // Initialize theme from localStorage, default to dark
  const saved = localStorage.getItem('theme') as 'light' | 'dark' | null;
  theme.value = saved || 'dark';
  applyTheme();
});
</script>

<template>
  <header 
    class="flex items-center gap-4 px-5 h-14 shrink-0 z-50 fixed top-0 left-0 right-0 border-b"
    style="background-color: var(--toolbar-bg); border-color: var(--border);"
  >
    <div class="flex items-center gap-2 flex-0 shrink-0 cursor-pointer select-none" @click="selectTab('execution')" style="white-space: nowrap;">
      <svg viewBox="0 0 24 24" class="w-[22px] h-[22px]" xmlns="http://www.w3.org/2000/svg">
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
      <span class="text-[14px] font-semibold" style="color: var(--text-primary);">EasyTest</span>
    </div>

    <div class="flex items-center gap-[2px] px-[2px] rounded-[8px]" style="background-color: var(--input-bg);">
      <button
        @click="selectTab('projects')"
        class="px-4 py-[6px] rounded-[6px] text-[12.5px] font-medium transition-all"
        :class="currentRoute === 'projects' 
          ? 'text-[var(--text-primary)]' 
          : 'bg-transparent text-[var(--text-secondary)]'"
        :style="currentRoute === 'projects' ? { backgroundColor: 'var(--card-bg)', boxShadow: 'var(--shadow-card)' } : {}"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--card-bg)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = currentRoute === 'projects' ? 'var(--card-bg)' : 'transparent'"
      >
        项目管理
      </button>
      <button
        @click="selectTab('cases')"
        class="px-4 py-[6px] rounded-[6px] text-[12.5px] font-medium transition-all"
        :class="currentRoute === 'cases' 
          ? 'text-[var(--text-primary)]' 
          : 'bg-transparent text-[var(--text-secondary)]'"
        :style="currentRoute === 'cases' ? { backgroundColor: 'var(--card-bg)', boxShadow: 'var(--shadow-card)' } : {}"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--card-bg)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = currentRoute === 'cases' ? 'var(--card-bg)' : 'transparent'"
      >
        用例总览
      </button>
      <button
        @click="selectTab('execution')"
        class="px-4 py-[6px] rounded-[6px] text-[12.5px] font-medium transition-all"
        :class="currentRoute === 'execution' 
          ? 'text-[var(--text-primary)]' 
          : 'bg-transparent text-[var(--text-secondary)]'"
        :style="currentRoute === 'execution' ? { backgroundColor: 'var(--card-bg)', boxShadow: 'var(--shadow-card)' } : {}"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--card-bg)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = currentRoute === 'execution' ? 'var(--card-bg)' : 'transparent'"
      >
        测试执行
      </button>
      <button
        @click="selectTab('defects')"
        class="px-4 py-[6px] rounded-[6px] text-[12.5px] font-medium transition-all"
        :class="currentRoute === 'defects' 
          ? 'text-[var(--text-primary)]' 
          : 'bg-transparent text-[var(--text-secondary)]'"
        :style="currentRoute === 'defects' ? { backgroundColor: 'var(--card-bg)', boxShadow: 'var(--shadow-card)' } : {}"
        @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--card-bg)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = currentRoute === 'defects' ? 'var(--card-bg)' : 'transparent'"
      >
        缺陷管理
      </button>
      <button
          @click="selectTab('reports')"
          class="px-4 py-[6px] rounded-[6px] text-[12.5px] font-medium transition-all"
          :class="currentRoute === 'reports' 
            ? 'text-[var(--text-primary)]' 
            : 'bg-transparent text-[var(--text-secondary)]'"
          :style="currentRoute === 'reports' ? { backgroundColor: 'var(--card-bg)', boxShadow: 'var(--shadow-card)' } : {}"
          @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--card-bg)'"
          @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = currentRoute === 'reports' ? 'var(--card-bg)' : 'transparent'"
        >
          测试报告
        </button>
      </div>

    <div class="flex-1 min-w-0"></div>

    <div class="flex items-center gap-2 flex-0 shrink-0">
      <!-- Branch selector: only on cases/execution/reports, before settings button -->
      <div
        v-if="['cases', 'execution', 'reports', 'defects'].includes(currentRoute) && activeProject && branches.length > 0"
        class="branch-selector relative"
      >
        <button
          @click.stop="showBranchMenu = !showBranchMenu"
          class="flex items-center gap-1.5 px-3 py-[5px] rounded-[6px] text-[12px] font-medium transition-all cursor-pointer"
          style="background-color: var(--card-bg-2); border: 1px solid var(--border-strong); color: var(--text-secondary); white-space: nowrap;"
          @mouseenter="($event.target as HTMLElement).style.borderColor = 'var(--accent)'"
          @mouseleave="($event.target as HTMLElement).style.borderColor = 'var(--border-strong)'"
        >
          <svg class="w-[14px] h-[14px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M6 3v12"></path><path d="M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"></path>
            <path d="M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"></path><path d="M18 9a3 3 0 0 0-3-3H6"></path>
          </svg>
          <span>{{ activeBranch?.name || 'main' }}</span>
          <span v-if="activeBranch?.is_default" class="text-[10px] opacity-60">(默认)</span>
          <svg class="w-[10px] h-[10px] ml-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m6 9 6 6 6-6"></path>
          </svg>
        </button>

        <!-- Dropdown menu -->
        <div v-if="showBranchMenu"
          class="absolute top-full right-0 mt-1 min-w-[180px] rounded-[8px] py-1 z-50 shadow-lg"
          style="background-color: var(--card-bg); border: 1px solid var(--border);"
        >
          <div class="px-3 py-1.5 text-[11px] font-medium" style="color: var(--text-tertiary);">版本分支</div>
          <div
            v-for="b in branches"
            :key="b.id"
            @click="selectBranch(b)"
            class="flex items-center gap-2 px-3 py-1.5 text-[12.5px] cursor-pointer transition-colors"
            :style="b.id === activeBranch?.id ? { backgroundColor: 'var(--accent-bg)', color: 'var(--accent)' } : { color: 'var(--text-primary)' }"
            @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)'"
            @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = b.id === activeBranch?.id ? 'var(--accent-bg)' : 'transparent'"
          >
            <svg class="w-[12px] h-[12px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 3v12"></path><path d="M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"></path>
              <path d="M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"></path><path d="M18 9a3 3 0 0 0-3-3H6"></path>
            </svg>
            <span class="flex-1">{{ b.name }}</span>
            <span v-if="b.is_default" class="text-[10px] px-1.5 py-0.5 rounded" style="background-color: var(--accent-bg); color: var(--accent);">默认</span>
            <button
              v-if="!b.is_default && branches.length > 1"
              @click.stop="handleDeleteBranch(b)"
              class="w-[18px] h-[18px] flex items-center justify-center rounded text-[12px] opacity-0 hover:opacity-100 transition-opacity"
              style="color: var(--text-tertiary);"
              title="删除分支"
            >
              ×
            </button>
          </div>
          <div class="border-t mt-1 pt-1" style="border-color: var(--border);">
            <button
              @click="showCreateBranch = true; showBranchMenu = false"
              class="flex items-center gap-2 w-full px-3 py-1.5 text-[12px] cursor-pointer transition-colors"
              style="color: var(--accent);"
              @mouseenter="($event.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)'"
              @mouseleave="($event.currentTarget as HTMLElement).style.backgroundColor = 'transparent'"
            >
              + 新建分支
            </button>
          </div>
        </div>
      </div>
      <template v-if="auth.isLoggedIn.value">
        <UserMenu @openChangePassword="showChangePassword = true" @openEditProfile="showEditProfile = true" />
      </template>
      <template v-else>
        <button
          @click="router.push('/login')"
          class="px-3 py-1.5 rounded-[8px] text-[12px] font-medium cursor-pointer transition-colors"
          style="background-color: var(--accent); color: #fff;"
          @mouseenter="($event.target as HTMLElement).style.opacity = '0.9'"
          @mouseleave="($event.target as HTMLElement).style.opacity = '1'"
        >
          登录
        </button>
      </template>

      <button
        @click="toggleTheme"
        class="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11.5px] cursor-pointer transition-colors"
        style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-secondary); white-space: nowrap;"
      >
        <span>{{ theme === 'light' ? '☀' : '☾' }}</span>
        <span>{{ theme === 'light' ? '浅色' : '深色' }}</span>
      </button>
    </div>

    <!-- Create branch modal -->
    <teleport to="body">
      <div v-if="showCreateBranch" class="fixed inset-0 z-[100] flex items-center justify-center" style="background-color: rgba(0,0,0,0.4);">
        <div class="w-[380px] rounded-[12px] p-5 shadow-xl" style="background-color: var(--card-bg); border: 1px solid var(--border);">
          <h3 class="text-[14px] font-semibold mb-4" style="color: var(--text-primary);">新建分支</h3>
          <div class="mb-3">
            <label class="block text-[12px] mb-1" style="color: var(--text-secondary);">分支名称</label>
            <input
              v-model="newBranchName"
              placeholder="输入分支名称"
              class="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
              style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-primary);"
              @keyup.enter="handleCreateBranch"
            />
          </div>
          <div class="mb-4">
            <label class="block text-[12px] mb-2" style="color: var(--text-secondary);">创建方式</label>
            <div class="flex gap-2">
              <label class="flex items-center gap-1.5 px-3 py-2 rounded-[6px] text-[12px] cursor-pointer" :style="{ border: '1px solid ' + (newBranchSource === 'empty' ? 'var(--accent)' : 'var(--border)'), backgroundColor: newBranchSource === 'empty' ? 'var(--accent-bg)' : 'transparent' }">
                <input type="radio" v-model="newBranchSource" value="empty" class="hidden" />
                空白分支（需重新导入）
              </label>
              <label class="flex items-center gap-1.5 px-3 py-2 rounded-[6px] text-[12px] cursor-pointer" :style="{ border: '1px solid ' + (newBranchSource === 'copy' ? 'var(--accent)' : 'var(--border)'), backgroundColor: newBranchSource === 'copy' ? 'var(--accent-bg)' : 'transparent' }">
                <input type="radio" v-model="newBranchSource" value="copy" class="hidden" />
                从当前分支复制
              </label>
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <button @click="showCreateBranch = false; newBranchName = ''" class="px-4 py-2 rounded-[8px] text-[12px]" style="background-color: var(--input-bg); color: var(--text-secondary);">取消</button>
            <button @click="handleCreateBranch" class="px-4 py-2 rounded-[8px] text-[12px] font-medium" :disabled="!newBranchName.trim()" style="background-color: var(--accent); color: white; opacity: newBranchName.trim() ? 1 : 0.5;">创建</button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Delete branch confirmation -->
    <teleport to="body">
      <div v-if="showDeleteConfirm && branchToDelete" class="fixed inset-0 z-[100] flex items-center justify-center" style="background-color: rgba(0,0,0,0.4);">
        <div class="w-[340px] rounded-[12px] p-5 shadow-xl" style="background-color: var(--card-bg); border: 1px solid var(--border);">
          <h3 class="text-[14px] font-semibold mb-2" style="color: var(--text-primary);">确认删除分支</h3>
          <p class="text-[12.5px] mb-4" style="color: var(--text-secondary);">
            删除分支 "<strong style="color: var(--text-primary);">{{ branchToDelete.name }}</strong>" 将同时删除该分支下的所有用例、任务、执行记录和报告。此操作不可撤销。
          </p>
          <div class="flex justify-end gap-2">
            <button @click="showDeleteConfirm = false; branchToDelete = null" class="px-4 py-2 rounded-[8px] text-[12px]" style="background-color: var(--input-bg); color: var(--text-secondary);">取消</button>
            <button @click="confirmDeleteBranch" class="px-4 py-2 rounded-[8px] text-[12px] font-medium" style="background-color: #e74c3c; color: white;">确认删除</button>
          </div>
        </div>
      </div>
    </teleport>

    <ChangePasswordModal
      :isOpen="showChangePassword"
      @close="showChangePassword = false"
      @showToast="(msg: string) => emit('showToast', msg)"
    />
    <EditProfileModal
      v-if="showEditProfile"
      @close="showEditProfile = false"
    />
  </header>
</template>
