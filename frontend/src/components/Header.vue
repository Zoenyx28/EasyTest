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

const navTabs = [
  { key: 'projects', label: '项目管理' },
  { key: 'cases', label: '自动化' },
  { key: 'execution', label: '测试执行' },
  { key: 'defects', label: '缺陷管理' },
  { key: 'reports', label: '测试报告' },
];

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
  <header class="header-bar glass">
    <div class="flex items-center gap-2 shrink-0 cursor-pointer select-none" @click="selectTab('execution')" style="white-space: nowrap;">
      <svg viewBox="0 0 24 24" class="w-[22px] h-[22px]" xmlns="http://www.w3.org/2000/svg">
        <line x1="12" y1="5" x2="6" y2="11" stroke="#22C55E" stroke-width="1.8"></line>
        <line x1="6" y1="11" x2="6" y2="17" stroke="#22C55E" stroke-width="1.8"></line>
        <line x1="6" y1="11" x2="15" y2="13" stroke="#22C55E" stroke-width="1.8"></line>
        <line x1="6" y1="17" x2="13" y2="19" stroke="#22C55E" stroke-width="1.8"></line>
        <circle cx="12" cy="5" r="2.3" fill="#FDBCB4"></circle>
        <circle cx="6" cy="11" r="2.7" fill="#22C55E"></circle>
        <circle cx="6" cy="17" r="2.3" fill="#16A34A"></circle>
        <circle cx="15" cy="13" r="1.9" fill="#FDBCB4"></circle>
        <circle cx="13" cy="19" r="1.7" fill="#22C55E"></circle>
      </svg>
      <span class="brand-name">EasyTest</span>
    </div>

    <nav class="nav-pill">
      <button
        v-for="tab in navTabs"
        :key="tab.key"
        @click="selectTab(tab.key)"
        class="nav-tab"
        :class="{ 'nav-tab--active': currentRoute === tab.key }"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div class="flex-1 min-w-0"></div>

    <div class="flex items-center gap-2 shrink-0">
      <!-- Branch selector: only on cases/execution/reports, before settings button -->
      <div
        v-if="['cases', 'execution', 'reports', 'defects'].includes(currentRoute) && activeProject && branches.length > 0"
        class="branch-selector relative"
      >
        <button
          @click.stop="showBranchMenu = !showBranchMenu"
          class="branch-selector-btn"
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
        <div v-if="showBranchMenu" class="branch-dropdown">
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
        <button @click="router.push('/login')" class="login-btn">登录</button>
      </template>

      <button @click="toggleTheme" class="theme-toggle">
        <span>{{ theme === 'light' ? '☀' : '☾' }}</span>
        <span>{{ theme === 'light' ? '浅色' : '深色' }}</span>
      </button>
    </div>

    <!-- Create branch modal -->
    <teleport to="body">
      <div v-if="showCreateBranch" class="fixed inset-0 z-[100] flex items-center justify-center" style="background-color: var(--overlay-bg);">
        <div class="modal-panel w-[380px] p-5">
          <h3 class="modal-title mb-4">新建分支</h3>
          <div class="mb-3">
            <label class="block text-[12px] mb-1" style="color: var(--text-secondary);">分支名称</label>
            <BaseInput
              v-model="newBranchName"
              type="text"
              placeholder="输入分支名称"
              @enter="handleCreateBranch"
            />
          </div>
          <div class="mb-4">
            <label class="block text-[12px] mb-2" style="color: var(--text-secondary);">创建方式</label>
            <div class="flex gap-2">
              <label
                class="option-card flex items-center gap-1.5 px-3 py-2 text-[12px] cursor-pointer"
                :class="{ 'option-card--active': newBranchSource === 'empty' }"
              >
                <input type="radio" v-model="newBranchSource" value="empty" class="hidden" />
                空白分支（需重新导入）
              </label>
              <label
                class="option-card flex items-center gap-1.5 px-3 py-2 text-[12px] cursor-pointer"
                :class="{ 'option-card--active': newBranchSource === 'copy' }"
              >
                <input type="radio" v-model="newBranchSource" value="copy" class="hidden" />
                从当前分支复制
              </label>
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <button @click="showCreateBranch = false; newBranchName = ''" class="btn-cancel">取消</button>
            <button @click="handleCreateBranch" class="btn-primary" :disabled="!newBranchName.trim()">创建</button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Delete branch confirmation -->
    <teleport to="body">
      <div v-if="showDeleteConfirm && branchToDelete" class="fixed inset-0 z-[100] flex items-center justify-center" style="background-color: var(--overlay-bg);">
        <div class="modal-panel w-[340px] p-5">
          <h3 class="modal-title mb-2">确认删除分支</h3>
          <p class="text-[12.5px] mb-4" style="color: var(--text-secondary);">
            删除分支 "<strong style="color: var(--text-primary);">{{ branchToDelete.name }}</strong>" 将同时删除该分支下的所有用例、任务、执行记录和报告。此操作不可撤销。
          </p>
          <div class="flex justify-end gap-2">
            <button @click="showDeleteConfirm = false; branchToDelete = null" class="btn-cancel">取消</button>
            <button @click="confirmDeleteBranch" class="btn-danger">确认删除</button>
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

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 20px;
  height: 56px;
  flex-shrink: 0;
  z-index: 50;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background-color: var(--toolbar-bg);
  border-bottom: 3px solid var(--outline);
}

.brand-name {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── 导航胶囊 ── */
.nav-pill {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: var(--radius-sm);
  background-color: var(--input-bg);
}
.nav-tab {
  padding: 6px 16px;
  border-radius: 10px;
  font-size: 12.5px;
  font-weight: 500;
  border: 2px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.nav-tab:hover {
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
}
.nav-tab--active {
  background-color: var(--color-primary);
  border-color: var(--outline);
  color: var(--text-primary);
  font-weight: 600;
  box-shadow: var(--shadow-hard-sm);
}
.nav-tab--active:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

/* ── 分支选择器 ── */
.branch-selector-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  background-color: var(--card-bg-2);
  border: 2px solid var(--outline);
  color: var(--text-secondary);
  white-space: nowrap;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
}
.branch-selector-btn:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
  color: var(--text-primary);
}
.branch-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 180px;
  border-radius: var(--radius-md);
  padding: 4px 0;
  z-index: 50;
  background-color: var(--card-bg);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-lg), var(--shadow-popover);
}

/* ── 登录 CTA（绿色） ── */
.login-btn {
  display: flex;
  align-items: center;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  background-color: var(--cta);
  border: 2px solid var(--outline);
  color: #fff;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}
.login-btn:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
  filter: brightness(0.95);
}

/* ── 主题切换 ── */
.theme-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 11.5px;
  font-weight: 500;
  background-color: var(--input-bg);
  border: 2px solid var(--outline);
  color: var(--text-secondary);
  white-space: nowrap;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
}
.theme-toggle:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
  color: var(--text-primary);
}

/* ── 弹窗（Clay 面板） ── */
.modal-panel {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
}
.modal-title {
  font-family: var(--font-heading);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.option-card {
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background-color: var(--card-bg);
  box-shadow: var(--shadow-hard-sm);
  color: var(--text-secondary);
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.option-card--active {
  border-color: var(--color-primary);
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
}
.btn-cancel {
  padding: 7px 16px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  background-color: var(--bg-soft);
  border: 2px solid var(--outline);
  color: var(--text-secondary);
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.btn-cancel:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.btn-primary {
  padding: 7px 16px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  background-color: var(--cta);
  border: 2px solid var(--outline);
  color: #fff;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-primary:not(:disabled):hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
  filter: brightness(0.95);
}
.btn-danger {
  padding: 7px 16px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  background-color: var(--color-danger);
  border: 2px solid var(--outline);
  color: #fff;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}
.btn-danger:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
  filter: brightness(0.92);
}
</style>
