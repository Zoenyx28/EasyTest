<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useApi, authHeaders } from '../composables/useApi';
import { useProject } from '../composables/useProject';
import { timeAgo } from '../utils/time';
import ConfirmDialog from './ConfirmDialog.vue';
import ProjectNoteEditor from './ProjectNoteEditor.vue';
import ProjectMemberModal from './ProjectMemberModal.vue';
import DefectDetailDialog from './DefectDetailDialog.vue';
import UserAvatar from './UserAvatar.vue';
import type { DefectInfo, ProjectMemberInfo } from '../types';

defineProps<{
  globalSearch: string;
}>();

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
}>();

const router = useRouter();
const { get, post, put, del } = useApi();
const { activeProject: sharedActiveProject, activateProject: switchActiveProject } = useProject();
const noteInfo = ref<any | null>(null);


interface Project {
  id: number;
  name: string;
  source_type: string;
  server_path: string;
  is_active: boolean;
  case_count: number;
  new_case_count: number;
  last_synced_at: string;
  created_at: string;
  source_path?: string;
  report_path?: string;
  member_count?: number;
  creator_id?: number;
  creator_name?: string;
}

const projects = ref<Project[]>([]);

function formatTime(iso: string): string {
  if (!iso) return '--';
  return iso.substring(0, 16).replace('T', ' ');
}

const showCreateModal = ref(false);
const showEditModal = ref(false);
const editingProject = ref<Project | null>(null);
const uploading = ref(false);
const uploadProgress = ref('');

// Drag & drop / click-to-select zip file
const zipInputRef = ref<HTMLInputElement | null>(null);
const dragState = ref<'idle' | 'over'>('idle');
const selectedFolderName = ref('');  // use for zip filename
const selectedZipBlob = ref<Blob | null>(null);

const form = ref({
  name: '',
  source_type: 'upload' as 'upload' | 'server',
  server_path: '',
});

// Server-sync: first-level directories under the server projects base dir
const serverDirs = ref<string[]>([]);
const serverDirsLoading = ref(false);

function serverDirName(path: string): string {
  const parts = path.split('/').filter(Boolean);
  return parts[parts.length - 1] || path;
}

async function loadServerDirs() {
  serverDirsLoading.value = true;
  try {
    serverDirs.value = await get<string[]>('/projects/server-directories');
  } catch {
    serverDirs.value = [];
  } finally {
    serverDirsLoading.value = false;
  }
}

watch(
  () => form.value.source_type,
  (type) => {
    if (type === 'server') {
      form.value.server_path = '';
      loadServerDirs();
    }
  }
);

interface SyncState {
  loading: boolean;
  error: string | null;
}
const syncStates = ref<Record<number, SyncState>>({});

function getSyncState(projectId: number): SyncState {
  return syncStates.value[projectId] || { loading: false, error: null };
}

const confirmDialog = ref<InstanceType<typeof ConfirmDialog> | null>(null);

const switchingId = ref<number | null>(null);

async function loadProjects() {
  try {
    projects.value = await get<Project[]>('/projects');
  } catch {
    projects.value = [];
  }
}

async function createProject() {
  if (!form.value.name) {
    emit('showToast', '请输入项目名称');
    return;
  }
  if (form.value.source_type === 'server' && !form.value.server_path) {
    emit('showToast', '请选择服务器项目目录');
    return;
  }
  if (form.value.source_type === 'upload' && !selectedZipBlob.value) {
    emit('showToast', '请先选择 zip 文件');
    return;
  }
  try {
    // Save values before resetForm clears them
    const sourceType = form.value.source_type;
    const zipBlob = selectedZipBlob.value;

    const project = await post<Project>('/projects', form.value);
    emit('showToast', '项目创建成功');
    showCreateModal.value = false;
    resetForm();
    loadProjects();

    if (sourceType === 'upload' && zipBlob) {
      await uploadZip(project.id, zipBlob);
    } else {
      await syncProject(project);
    }
  } catch (e: any) {
    emit('showToast', e.message || '创建失败');
  }
}

async function uploadZip(projectId: number, zipBlob: Blob) {
  uploading.value = true;
  uploadProgress.value = `正在上传 (${(zipBlob.size / 1024 / 1024).toFixed(1)} MB)...`;

  try {
    const formData = new FormData();
    formData.append('file', zipBlob, 'project.zip');

    const res = await fetch(`/api/projects/${projectId}/upload`, {
      method: 'POST',
      headers: { ...authHeaders() },
      body: formData,
    });
    const json = await res.json().catch(() => null);
    if (!res.ok || !json || json.code !== 200) {
      throw new Error(json?.msg || '上传失败');
    }

    emit('showToast', '上传成功，开始同步用例');
    await triggerSync(projectId);
  } catch (e: any) {
    emit('showToast', e.message || '上传失败');
  } finally {
    uploading.value = false;
    uploadProgress.value = '';
  }
}

function openZipPicker() {
  zipInputRef.value?.click();
}

async function handleZipSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;

  const file = files[0];
  if (!file.name.toLowerCase().endsWith('.zip')) {
    emit('showToast', '请选择 .zip 文件');
    return;
  }

  selectedFolderName.value = file.name;
  selectedZipBlob.value = file;
}

async function handleZipDrop(e: DragEvent) {
  dragState.value = 'idle';
  const items = e.dataTransfer?.items;
  if (!items || items.length === 0) {
    emit('showToast', '请拖拽一个 zip 文件');
    return;
  }

  const file = items[0].getAsFile?.();
  if (!file) {
    emit('showToast', '请拖拽 zip 文件');
    return;
  }
  if (!file.name.toLowerCase().endsWith('.zip')) {
    emit('showToast', '请选择 .zip 文件');
    return;
  }

  selectedFolderName.value = file.name;
  selectedZipBlob.value = file;
}

async function triggerSync(projectId: number) {
  syncStates.value[projectId] = { loading: true, error: null };
  try {
    await post(`/projects/${projectId}/sync`);
    syncStates.value[projectId] = { loading: false, error: null };
    loadProjects();
  } catch (e: any) {
    syncStates.value[projectId] = { loading: false, error: e.message || '同步失败' };
    emit('showToast', e.message || '同步失败');
  }
}

async function updateProject() {
  if (!editingProject.value) return;
  if (!form.value.name) {
    emit('showToast', '请输入项目名称');
    return;
  }
  try {
    // Save values before resetForm clears them
    const projectId = editingProject.value.id;
    const sourceType = form.value.source_type;
    const zipBlob = selectedZipBlob.value;

    await put(`/projects/${projectId}`, form.value);
    emit('showToast', '项目更新成功');
    showEditModal.value = false;
    editingProject.value = null;
    resetForm();
    loadProjects();

    // Re-upload if a new zip was selected
    if (sourceType === 'upload' && zipBlob) {
      await uploadZip(projectId, zipBlob);
    } else {
      await syncProject({ id: projectId } as Project);
    }
  } catch (e: any) {
    emit('showToast', e.message || '更新失败');
  }
}

async function deleteProject(project: Project) {
  const confirmed = await confirmDialog.value?.confirm({
    title: '删除项目',
    message: `确定删除项目 "${project.name}" 吗？此操作将删除该项目的所有数据，不可撤销。`,
    confirmText: '删除',
    confirmColor: 'var(--color-danger)',
  });
  if (!confirmed) return;
  try {
    await del(`/projects/${project.id}`);
    emit('showToast', '项目删除成功');
    loadProjects();
  } catch (e: any) {
    emit('showToast', e.message || '删除失败');
  }
}

async function toggleActive(project: Project) {
  if (project.is_active) {
    emit('showToast', '该项目已是活跃项目');
    return;
  }
  if (switchingId.value) {
    return;
  }
  switchingId.value = project.id;
  try {
    await switchActiveProject(project.id);
    // Immediately update local projects ref so UI reflects the change
    projects.value = projects.value.map(p => ({
      ...p,
      is_active: p.id === project.id,
    }));
    emit('showToast', `已切换到项目 "${project.name}"`);
    // 切换到活跃状态后立即同步用例
    await syncProject(project);
  } catch (e: any) {
    emit('showToast', e.message || '切换失败');
  } finally {
    switchingId.value = null;
  }
}

async function syncProject(project: Project) {
  syncStates.value[project.id] = { loading: true, error: null };
  try {
    const result = await post<{ added_count: number; deleted_count: number }>(`/projects/${project.id}/sync`);
    syncStates.value[project.id] = { loading: false, error: null };
    emit('showToast', `同步成功：新增 ${result.added_count} 个，删除 ${result.deleted_count} 个`);
    loadProjects();
  } catch (e: any) {
    syncStates.value[project.id] = { loading: false, error: e.message || '同步失败' };
    emit('showToast', e.message || '同步失败');
  }
}

async function openEditModal(project: Project) {
  editingProject.value = project;
  form.value = {
    name: project.name,
    source_type: project.source_type as 'upload' | 'server',
    server_path: project.server_path,
  };
  showEditModal.value = true;
}

function resetForm() {
  form.value = {
    name: '',
    source_type: 'upload',
    server_path: '',
  };
  selectedFolderName.value = '';
  selectedZipBlob.value = null;
  if (zipInputRef.value) {
    zipInputRef.value.value = '';
  }
}

function closeModal() {
  showCreateModal.value = false;
  showEditModal.value = false;
  editingProject.value = null;
  resetForm();
}

// ── Right panel: project detail ──

interface ProjectDetail {
  project: Project;
  members: ProjectMemberInfo[];
  recent_defects: DefectInfo[];
  recent_tasks: any[];
}

const activeProjectInfo = computed(() => {
  return projects.value.find(p => p.is_active) || null;
});

const detailData = ref<ProjectDetail | null>(null);
const detailLoading = ref(false);
const showMemberModal = ref(false);
const selectedDefect = ref<number | null>(null);
const showDefectDialog = ref(false);

async function loadProjectDetail() {
  const project = activeProjectInfo.value;
  if (!project) {
    detailData.value = null;
    return;
  }
  detailLoading.value = true;
  try {
    detailData.value = await get<ProjectDetail>(`/projects/${project.id}/detail`);
  } catch {
    detailData.value = null;
  } finally {
    detailLoading.value = false;
  }
}

function openDefectDetail(defectId: number) {
  selectedDefect.value = defectId;
  showDefectDialog.value = true;
}

// ── Defect card helpers ──

const defectStatusLabels: Record<string, string> = {
  unconfirmed: '未确认',
  confirmed: '已确认',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

const defectStatusColors: Record<string, string> = {
  unconfirmed: 'var(--border)',
  confirmed: 'var(--status-confirmed-bg)',
  in_progress: 'var(--status-in-progress-bg)',
  resolved: 'var(--status-resolved-bg)',
  closed: 'var(--border)',
};

const defectStatusTextColors: Record<string, string> = {
  unconfirmed: 'var(--text-secondary)',
  confirmed: 'var(--status-confirmed-text)',
  in_progress: 'var(--status-in-progress-text)',
  resolved: 'var(--status-resolved-text)',
  closed: 'var(--text-secondary)',
};

const defectLogFieldLabels: Record<string, string> = {
  status: '状态',
  severity: '严重程度',
  priority: '优先级',
  assignee_id: '处理人',
  module_id: '模块',
  resolution: '解决方案',
  bug_type: '缺陷类型',
  deadline: '截止时间',
  title: '标题',
  description: '描述',
  steps: '复现步骤',
};

function formatLogValue(field: string, value: string): string {
  if (!value) return '--';
  if (field === 'status') return defectStatusLabels[value] || value;
  if (field === 'assignee_id' || field === 'creator_id') return value === '0' ? '--' : `#${value}`;
  return value;
}

function formatLog(log: any): string {
  const fieldLabel = defectLogFieldLabels[log.field] || log.field;
  return `${fieldLabel}: ${formatLogValue(log.field, log.old_value)} → ${formatLogValue(log.field, log.new_value)}`;
}

function navigateToExecution() {
  router.push('/execution');
}

// Refresh detail when active project changes
watch(activeProjectInfo, () => {
  loadProjectDetail();
}, { immediate: true });

onMounted(() => {
  loadProjects();
});
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0 w-full overflow-hidden" style="background-color: var(--content-bg); font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;">
    <!-- Panel header -->
    <div class="flex items-center justify-between px-[16px] py-[12px] shrink-0" style="border-bottom: 1px solid var(--border);">
      <h2 class="text-[15px] font-semibold tracking-[-0.01em]" style="color: var(--text-primary);">项目管理</h2>
      <button
        @click="showCreateModal = true"
        class="flex items-center gap-[4px] px-[12px] py-[6px] text-[12px] font-semibold rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.97]"
        style="background-color: var(--accent); color: #fff;"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        新建项目
      </button>
    </div>

    <!-- Left-right split layout -->
    <div class="flex-1 flex min-h-0 overflow-hidden">
      <!-- Left panel: project cards -->
      <div class="w-[36%] min-w-[300px] max-w-[360px] shrink-0 flex flex-col overflow-hidden" style="border-right: 1px solid var(--border); background-color: var(--content-bg);">
        <div v-if="projects.length === 0" class="flex items-center justify-center flex-1 select-none" style="color: var(--text-tertiary);">
          <div class="text-center">
            <div class="w-[56px] h-[56px] mx-auto mb-[14px] rounded-[14px] flex items-center justify-center text-[24px] opacity-30" style="background-color: var(--input-bg);">📁</div>
            <p class="text-[13px] font-medium" style="color: var(--text-secondary);">暂无项目</p>
            <p class="text-[11px] mt-[4px]" style="color: var(--text-tertiary);">点击上方按钮创建第一个项目</p>
          </div>
        </div>

        <div v-else class="flex-1 overflow-y-auto p-[12px] space-y-[10px]">
          <div
            v-for="project in projects"
            :key="project.id"
            class="group relative rounded-[10px] p-[12px] transition-all duration-200 cursor-pointer"
            :class="project.is_active ? 'active-card' : 'card'"
            :style="{
              backgroundColor: 'var(--card-bg)',
              borderLeft: project.is_active ? '3px solid var(--accent)' : '3px solid transparent',
              border: project.is_active
                ? '1px solid var(--border)'
                : '1px solid var(--border)',
              boxShadow: project.is_active
                ? '0 2px 8px var(--shadow-sm)'
                : '0 1px 3px rgba(0,0,0,0.03)',
            }"
          >
            <!-- Header row: signal dot + name + toggle -->
            <div class="flex items-start justify-between mb-[8px]">
              <div class="flex items-center gap-[8px] min-w-0 flex-1">
                <!-- Signal light -->
                <div
                  class="w-[10px] h-[10px] rounded-full shrink-0 relative group/light"
                  :style="{
                    backgroundColor: getSyncState(project.id).error
                      ? 'var(--color-danger)'
                      : (project.is_active ? 'var(--color-success)' : 'var(--text-tertiary)'),
                    boxShadow: project.is_active && !getSyncState(project.id).error
                      ? '0 0 4px rgba(40,167,69,0.5)'
                      : 'none',
                  }"
                  :title="getSyncState(project.id).error || ''"
                >
                  <div
                    v-if="getSyncState(project.id).error"
                    class="absolute bottom-[12px] left-1/2 -translate-x-1/2 pointer-events-none z-10 opacity-0 group-hover/light:opacity-100 transition-opacity duration-150"
                  >
                    <div class="whitespace-nowrap text-[10px] font-medium px-[8px] py-[4px] rounded-[6px]" style="background-color: var(--color-danger); color: #fff;">
                      {{ getSyncState(project.id).error }}
                    </div>
                  </div>
                </div>
                <h3 class="text-[13px] font-semibold truncate" style="color: var(--text-primary);">{{ project.name }}</h3>
              </div>
              <!-- Toggle switch -->
              <button
                @click.stop="toggleActive(project)"
                :disabled="project.is_active || switchingId === project.id"
                class="relative inline-block w-[32px] h-[16px] shrink-0 cursor-pointer align-middle select-none transition duration-200 ease-in mt-[2px]"
                role="switch"
                :aria-checked="project.is_active"
              >
                <span
                  class="absolute block w-[16px] h-[16px] rounded-full bg-white border-2 z-10 transition-transform duration-200 ease-in-out cursor-pointer"
                  :class="project.is_active ? 'toggle-dot-on' : 'toggle-dot-off'"
                  :style="{
                    borderColor: project.is_active ? 'var(--accent)' : 'var(--border-strong)',
                    transform: project.is_active ? 'translateX(16px)' : 'translateX(0)',
                  }"
                />
                <span
                  class="block h-[16px] rounded-full transition-colors duration-200 ease-in-out"
                  :style="{
                    backgroundColor: project.is_active ? 'var(--accent)' : 'var(--text-muted)',
                  }"
                />
              </button>
            </div>

            <!-- Tags row -->
            <div class="flex flex-wrap gap-[6px] mb-[10px]">
              <span
                class="px-[6px] py-[2px] text-[10px] font-bold rounded-[4px] leading-none tracking-[0.03em]"
                :style="{
                  backgroundColor: project.source_type === 'upload' ? 'var(--success-soft)' : 'var(--color-primary-soft)',
                  color: project.source_type === 'upload' ? 'var(--color-success)' : 'var(--color-primary)',
                  border: project.source_type === 'upload' ? '1px solid var(--success-soft)' : '1px solid var(--color-primary-soft)',
                }"
              >
                {{ project.source_type === 'upload' ? '本地上传' : '服务器同步' }}
              </span>
              <span
                v-if="getSyncState(project.id).loading"
                class="inline-flex items-center gap-[4px] px-[6px] py-[2px] text-[10px] font-bold rounded-[4px] leading-none tracking-[0.03em]"
                style="background-color: var(--warning-soft); color: var(--color-warning); border: 1px solid var(--warning-soft);"
              >
                <svg class="animate-spin" width="10" height="10" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.2"/>
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
                </svg>
                同步中
              </span>
              <span
                v-else
                class="px-[6px] py-[2px] text-[10px] font-bold rounded-[4px] leading-none tracking-[0.03em]"
                :style="{
                  backgroundColor: project.is_active ? 'var(--accent-soft)' : 'var(--card-bg-2)',
                  color: project.is_active ? 'var(--accent)' : 'var(--text-secondary)',
                  border: project.is_active ? '1px solid var(--color-primary-soft)' : '1px solid var(--border)',
                }"
              >
                {{ project.is_active ? '活跃' : '空闲' }}
              </span>
            </div>

            <!-- Info section: case counts -->
            <div class="p-[8px] rounded-[6px] mb-[2px]" style="background-color: var(--card-bg-2); border: 1px dashed var(--border);">
              <div class="flex gap-[16px] mt-[4px] text-[11px] font-mono" style="color: var(--text-secondary);">
                <span>用例: <strong style="color: var(--text-primary);">{{ project.case_count }}</strong></span>
                <span v-if="project.new_case_count > 0" style="color: var(--color-success);">新增 {{ project.new_case_count }}</span>
                <span v-else style="color: var(--text-tertiary);">新增 0</span>
              </div>
            </div>

            <!-- Bottom: sync time + action buttons -->
            <div class="flex items-center justify-between mt-[8px] pt-[8px]" style="border-top: 1px solid var(--border);">
              <span class="text-[11px]" style="color: var(--text-tertiary);">同步时间: {{ formatTime(project.last_synced_at) }}</span>
              <div class="card-actions opacity-0 group-hover:opacity-100 transition-opacity flex gap-[4px] px-[6px] py-[3px] rounded-[6px]" style="background-color: var(--card-bg); border: 1px solid var(--border);">
                <button
                  @click="syncProject(project)"
                  :disabled="getSyncState(project.id).loading"
                  class="p-[4px] rounded-[4px] cursor-pointer transition-colors"
                  style="color: var(--text-secondary);"
                  :title="getSyncState(project.id).loading ? '同步中...' : '同步用例'"
                  @mouseenter="($event.currentTarget as HTMLElement).style.color = 'var(--accent)'"
                  @mouseleave="($event.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                </button>
                <button
                  @click="openEditModal(project)"
                  class="p-[4px] rounded-[4px] cursor-pointer transition-colors"
                  style="color: var(--text-secondary);"
                  title="编辑"
                  @mouseenter="($event.currentTarget as HTMLElement).style.color = 'var(--accent)'"
                  @mouseleave="($event.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button
                  @click="deleteProject(project)"
                  class="p-[4px] rounded-[4px] cursor-pointer transition-colors"
                  style="color: var(--text-secondary);"
                  title="删除"
                  @mouseenter="($event.currentTarget as HTMLElement).style.color = 'var(--color-danger)'"
                  @mouseleave="($event.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right panel: project detail -->
      <div class="flex-1 overflow-y-auto" style="background-color: var(--card-bg);">
        <!-- Empty state -->
        <div v-if="!activeProjectInfo" class="flex items-center justify-center h-full select-none">
          <div class="text-center px-[40px]">
            <div class="w-[56px] h-[56px] mx-auto mb-[14px] rounded-[14px] flex items-center justify-center text-[24px] opacity-30" style="background-color: var(--input-bg);">📋</div>
            <p class="text-[13px] font-medium" style="color: var(--text-secondary);">请选择一个活跃项目</p>
            <p class="text-[11px] mt-[4px]" style="color: var(--text-tertiary);">选择左侧项目卡片中的项目以查看详细信息</p>
          </div>
        </div>

        <!-- Loading state -->
        <div v-else-if="detailLoading" class="flex items-center justify-center h-full">
          <svg class="animate-spin" width="24" height="24" viewBox="0 0 24 24" fill="none" style="color: var(--text-tertiary);">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.2"/>
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
          </svg>
        </div>

        <!-- Detail panel: two-column layout -->
        <div v-else class="p-[16px] h-full overflow-hidden">
          <div class="flex gap-[16px] h-full">

            <!-- Left column: Project Info + Project Notes -->
            <div class="flex-1 flex flex-col gap-[16px] min-h-0">
              <!-- Project Information -->
              <div class="rounded-[10px] p-[16px] relative overflow-hidden shrink-0" style="background-color: var(--content-bg); border: 1px solid var(--border);">
                <div class="absolute top-0 right-0 w-[96px] h-[96px] rounded-bl-full opacity-[0.08]" style="background: linear-gradient(135deg, var(--accent), transparent);"></div>
                <div class="flex justify-between items-start mb-[12px]">
                  <div class="min-w-0">
                    <h1 class="text-[18px] font-bold tracking-[-0.02em] mb-[6px]" style="color: var(--text-primary);">{{ detailData?.project.name }}</h1>
                    <div class="flex flex-wrap items-center gap-x-[16px] gap-y-[4px] text-[11.5px]" style="color: var(--text-secondary);">
                      <div class="flex items-center gap-[4px]">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                        <span>创建者 <strong style="color: var(--text-primary);">{{ detailData?.project.creator_name || '--' }}</strong></span>
                      </div>
                      <div class="flex items-center gap-[4px]">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                        <span class="font-mono text-[11px]">{{ detailData?.project.server_path || detailData?.project.source_path || '--' }}</span>
                      </div>
                    </div>
                  </div>
                  <span class="shrink-0 px-[10px] py-[3px] rounded-full text-[9px] font-bold tracking-[0.05em] flex items-center gap-[4px]"
                    style="background-color: var(--accent-soft); color: var(--accent); border: 1px solid var(--color-primary-soft);"
                  >
                    <span class="w-[5px] h-[5px] rounded-full" style="background-color: var(--accent); animation: pulse-dot 2s infinite;"></span>
                    活跃
                  </span>
                </div>
                <div style="border-top: 1px solid var(--border); padding-top: 12px;" class="flex items-center justify-between">
                  <div>
                    <h4 class="text-[12px] font-bold mb-[8px]" style="color: var(--text-primary);">团队成员</h4>
                    <div class="flex items-center">
                      <div
                        v-for="(member, idx) in detailData?.members?.slice(0, 5) || []"
                        :key="member.id"
                        class="-ml-[5px] first:ml-0 rounded-full"
                        :style="{ zIndex: 5 - idx }"
                        :title="member.nickname || member.username"
                      >
                        <UserAvatar
                          :name="member.nickname || member.username"
                          :avatar="member.avatar_url"
                          :size="26"
                          border-color="var(--content-bg)"
                        />
                      </div>
                      <div
                        v-if="(detailData?.members?.length || 0) > 5"
                        class="w-[26px] h-[26px] -ml-[5px] rounded-full flex items-center justify-center text-[9px] font-bold"
                        :style="{
                          backgroundColor: 'var(--card-bg-2)',
                          color: 'var(--text-secondary)',
                          border: '2px solid var(--content-bg)',
                        }"
                      >
                        +{{ (detailData?.members?.length || 0) - 5 }}
                      </div>
                    </div>
                  </div>
                  <button
                    @click="showMemberModal = true"
                    class="px-[10px] py-[5px] text-[11px] font-semibold rounded-[6px] cursor-pointer transition-all duration-150 active:scale-[0.97]"
                    style="background-color: var(--card-bg); color: var(--text-secondary); border: 1px solid var(--border);"
                    @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = 'var(--accent)'; ($event.currentTarget as HTMLElement).style.color = 'var(--accent)'"
                    @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; ($event.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'"
                  >
                    管理成员
                  </button>
                </div>
              </div>

              <!-- Project Notes (fills remaining height, scrollable) -->
              <div class="rounded-[10px] overflow-hidden flex flex-col flex-1 min-h-0" style="background-color: var(--content-bg); border: 1px solid var(--border);">
                <div class="flex items-center justify-between px-[12px] py-[10px] shrink-0" style="border-bottom: 1px solid var(--border); background-color: var(--card-bg-2);">
                  <h3 class="text-[12px] font-bold flex items-center gap-[6px]" style="color: var(--text-primary);">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                    项目备注
                  </h3>
                  <span v-if="noteInfo?.updated_by_name" class="text-[11px]" style="color: var(--text-tertiary);">
                    最后编辑：{{ noteInfo.updated_by_name }} · {{ formatTime(noteInfo.updated_at) }}
                  </span>
                </div>
                <div class="p-[12px] flex-1 overflow-y-auto">
                  <ProjectNoteEditor :projectId="activeProjectInfo!.id" @info-back="(info: any) => noteInfo = info" />
                </div>
              </div>
            </div>

            <!-- Right column: Defects + Tasks -->
            <div class="flex-1 flex flex-col gap-[16px] min-h-0">
              <!-- Recent Defects -->
              <div class="rounded-[10px] flex flex-col flex-1 min-h-0" style="background-color: var(--content-bg); border: 1px solid var(--border);">
                <div class="flex items-center justify-between px-[12px] py-[10px] shrink-0" style="border-bottom: 1px solid var(--border); background-color: var(--card-bg-2);">
                  <h3 class="text-[12px] font-bold flex items-center gap-[6px]" style="color: var(--text-primary);">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    最近缺陷
                  </h3>
                </div>
                <div class="p-[6px] space-y-[4px] flex-1 overflow-y-auto">
                  <div v-if="!detailData?.recent_defects || detailData.recent_defects.length === 0" class="flex items-center justify-center py-[24px] text-[12px]" style="color: var(--text-tertiary);">
                    暂无缺陷
                  </div>
                  <div
                    v-for="defect in detailData?.recent_defects || []"
                    :key="defect.id"
                    class="p-[8px] rounded-[6px] cursor-pointer transition-all duration-150 hover:shadow-sm"
                    style="background-color: var(--card-bg); border: 1px solid var(--border);"
                    @click="openDefectDetail(defect.id)"
                  >
                    <div class="flex items-center justify-between mb-[2px]">
                      <span class="text-[10px] font-mono font-bold" style="color: var(--accent); background-color: var(--accent-soft); padding: 1px 5px; border-radius: 3px;">
                        BUG-{{ defect.id }}
                      </span>
                      <span class="text-[10px]" style="color: var(--text-tertiary);">{{ timeAgo(defect.created_at) }}</span>
                    </div>
                    <h4 class="text-[11.5px] font-semibold mb-[3px] truncate" style="color: var(--text-primary);">{{ defect.title }}</h4>
                    <div class="flex items-center gap-[4px] text-[10.5px]" style="color: var(--text-secondary);">
                      <span
                        class="px-[4px] py-[1px] rounded-[2px] text-[9px] font-bold"
                        :style="{
                          backgroundColor: defect.severity === 'P0' || defect.severity === 'P1' ? 'var(--danger-soft)' : 'var(--card-bg-2)',
                          color: defect.severity === 'P0' || defect.severity === 'P1' ? 'var(--color-danger)' : 'var(--text-secondary)',
                          border: '1px solid ' + (defect.severity === 'P0' || defect.severity === 'P1' ? 'var(--danger-soft)' : 'var(--border)'),
                        }"
                      >
                        {{ defect.severity || 'P3' }}
                      </span>
                      <span
                        class="px-[4px] py-[1px] rounded-[2px] text-[9px] font-bold"
                        :style="{
                          backgroundColor: defectStatusColors[defect.status] || 'var(--card-bg-2)',
                          color: defectStatusTextColors[defect.status] || 'var(--text-secondary)',
                          border: '1px solid ' + (defectStatusColors[defect.status] || 'var(--border)'),
                        }"
                      >
                        {{ defectStatusLabels[defect.status] || defect.status || '未确认' }}
                      </span>
                      <span>提交者 <strong style="color: var(--text-primary);">{{ defect.creator_name || '--' }}</strong></span>
                    </div>
                    <div v-if="(defect.recent_logs || []).length" class="mt-[6px] pt-[4px] space-y-[2px]" style="border-top: 1px dashed var(--border);">
                      <div v-for="log in defect.recent_logs" :key="log.id" class="text-[10px] leading-[1.5]" style="color: var(--text-tertiary);">
                        <span style="color: var(--text-secondary);">{{ log.operator_name || '--' }}</span> {{ formatLog(log) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Recent Test Tasks -->
              <div class="rounded-[10px] flex flex-col flex-1 min-h-0" style="background-color: var(--content-bg); border: 1px solid var(--border);">
                <div class="flex items-center justify-between px-[12px] py-[10px] shrink-0" style="border-bottom: 1px solid var(--border); background-color: var(--card-bg-2);">
                  <h3 class="text-[12px] font-bold flex items-center gap-[6px]" style="color: var(--text-primary);">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                    最近测试任务
                  </h3>
                </div>
                <div class="p-[6px] space-y-[4px] flex-1 overflow-y-auto">
                  <div v-if="!detailData?.recent_tasks || detailData.recent_tasks.length === 0" class="flex items-center justify-center py-[24px] text-[12px]" style="color: var(--text-tertiary);">
                    暂无测试任务
                  </div>
                  <div
                    v-for="task in detailData?.recent_tasks || []"
                    :key="task.execution_id"
                    class="p-[8px] rounded-[6px] cursor-pointer transition-all duration-150 hover:shadow-sm flex flex-col"
                    style="background-color: var(--card-bg); border: 1px solid var(--border);"
                    @click="navigateToExecution"
                  >
                    <div>
                      <h4 class="text-[11.5px] font-semibold mb-[3px] truncate" style="color: var(--text-primary);">{{ task.task_name }}</h4>
                      <div class="text-[10px] font-mono mb-[4px] flex items-center gap-[4px]" style="color: var(--text-secondary);">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        <span v-if="task.status === 'running'">运行中 ({{ task.duration || '--' }})</span>
                        <span v-else-if="task.status === 'finished'">执行: {{ task.duration || '--' }}</span>
                        <span v-else>{{ task.status === 'failed' ? '失败' : task.status === 'stopped' ? '已停止' : '等待中' }}</span>
                      </div>
                      <div v-if="task.status === 'running'" class="w-full h-[4px] rounded-full" style="background-color: var(--card-bg-2);">
                        <div class="h-[4px] rounded-full" :style="{ width: (task.passed_count && task.total_count ? Math.round(task.passed_count / task.total_count * 100) : 0) + '%', backgroundColor: 'var(--accent)' }"></div>
                      </div>
                    </div>
                    <div class="flex items-center justify-between pt-[4px]" style="border-top: 1px dashed var(--border);">
                      <span class="text-[10px]" style="color: var(--text-tertiary);">{{ timeAgo(task.created_at) }}</span>
                      <span
                        class="px-[4px] py-[1px] text-[9px] font-bold rounded-[2px] flex items-center gap-[2px]"
                        :style="{
                          backgroundColor: task.status === 'finished' ? 'var(--success-soft)' : (task.status === 'running' ? 'var(--accent-soft)' : (task.status === 'failed' ? 'var(--danger-soft)' : 'var(--card-bg-2)')),
                          color: task.status === 'finished' ? 'var(--color-success)' : (task.status === 'running' ? 'var(--accent)' : (task.status === 'failed' ? 'var(--color-danger)' : 'var(--text-secondary)')),
                          border: '1px solid ' + (task.status === 'finished' ? 'var(--success-soft)' : (task.status === 'running' ? 'var(--color-primary-soft)' : (task.status === 'failed' ? 'var(--danger-soft)' : 'var(--border)'))),
                        }"
                      >
                        <svg v-if="task.status === 'finished'" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                        <svg v-else-if="task.status === 'running'" class="animate-spin" width="8" height="8" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>
                        {{ task.status === 'finished' ? '已完成' : (task.status === 'running' ? '运行中' : (task.status === 'failed' ? '失败' : (task.status === 'stopped' ? '已停止' : '等待中'))) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- macOS-style upload progress panel -->
    <div v-if="uploading" class="fixed inset-0 flex items-center justify-center z-50" style="background-color: var(--overlay-bg); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);">
      <div class="w-[300px] p-[24px] rounded-[14px] text-center" style="background-color: var(--card-bg); box-shadow: 0 8px 40px rgba(0,0,0,0.15);">
        <div class="mb-[12px]">
          <svg class="animate-spin mx-auto" width="28" height="28" viewBox="0 0 24 24" fill="none" style="color: var(--accent);"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>
        </div>
        <div class="text-[12px] font-medium mb-[6px]" style="color: var(--text-primary);">上传中</div>
        <div class="text-[11px]" style="color: var(--text-tertiary);">{{ uploadProgress }}</div>
      </div>
    </div>

    <!-- macOS-style modal -->
    <div v-if="showCreateModal || showEditModal" class="fixed inset-0 flex items-center justify-center z-50" style="background-color: var(--overlay-bg); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);">
      <div class="w-[440px] rounded-[14px] overflow-hidden" style="background-color: var(--card-bg); box-shadow: 0 12px 60px rgba(0,0,0,0.2);">
        <!-- macOS traffic-light style header -->
        <div class="flex items-center gap-[8px] px-[16px] py-[12px] select-none" style="border-bottom: 0.5px solid var(--border);">
          <div class="w-[12px] h-[12px] rounded-full" style="background-color: rgb(255,95,87);"></div>
          <div class="w-[12px] h-[12px] rounded-full" style="background-color: rgb(255,189,46);"></div>
          <div class="w-[12px] h-[12px] rounded-full" style="background-color: rgb(39,201,63);"></div>
          <span class="ml-[8px] text-[12px] font-medium" style="color: var(--text-primary);">
            {{ editingProject ? '编辑项目' : '新建项目' }}
          </span>
        </div>

        <div class="p-[18px_20px] space-y-[14px]">
          <!-- Project name -->
          <div>
            <label class="text-[11px] font-medium block mb-[5px] tracking-[-0.01em]" style="color: var(--text-secondary);">项目名称</label>
            <BaseInput
              v-model="form.name"
              type="text"
              placeholder="输入项目名称"
            />
          </div>

          <!-- Source type - macOS segmented control style -->
          <div>
            <label class="text-[11px] font-medium block mb-[5px] tracking-[-0.01em]" style="color: var(--text-secondary);">来源类型</label>
            <div class="flex rounded-[8px] overflow-hidden" :style="{ border: '0.5px solid var(--border)' }">
              <button
                @click="form.source_type = 'upload'"
                class="flex-1 px-3 py-[7px] text-[11.5px] font-medium cursor-pointer transition-all duration-100"
                :style="{
                  backgroundColor: form.source_type === 'upload' ? 'var(--accent)' : 'var(--input-bg)',
                  color: form.source_type === 'upload' ? '#fff' : 'var(--text-secondary)',
                }"
              >
                本地上传
              </button>
              <button
                @click="form.source_type = 'server'"
                class="flex-1 px-3 py-[7px] text-[11.5px] font-medium cursor-pointer transition-all duration-100"
                :style="{
                  backgroundColor: form.source_type === 'server' ? 'var(--accent)' : 'var(--input-bg)',
                  color: form.source_type === 'server' ? '#fff' : 'var(--text-secondary)',
                  borderLeft: '0.5px solid var(--border)',
                }"
              >
                服务器同步
              </button>
            </div>
          </div>

          <!-- Upload zone -->
          <div v-if="form.source_type === 'upload'">
            <label class="text-[11px] font-medium block mb-[5px] tracking-[-0.01em]" style="color: var(--text-secondary);">项目 zip 文件</label>
            <div
              @dragover.prevent="dragState = 'over'"
              @dragenter.prevent="dragState = 'over'"
              @dragleave.prevent="dragState = 'idle'"
              @drop.prevent="handleZipDrop"
              @click="openZipPicker"
              class="px-3 py-[28px] rounded-[10px] text-center cursor-pointer transition-all duration-150"
              :style="{
                backgroundColor: dragState === 'over' ? 'var(--color-primary-soft)' : 'var(--input-bg)',
                border: dragState === 'over' ? '1.5px solid var(--accent)' : '1.5px dashed var(--border)',
                color: 'var(--text-secondary)',
              }"
            >
              <input
                ref="zipInputRef"
                type="file"
                accept=".zip"
                class="hidden"
                @change="handleZipSelected"
              />
              <div v-if="!selectedFolderName">
                <svg class="mx-auto mb-[8px]" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.4;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <div class="text-[11.5px] font-medium">拖拽 zip 文件到此处</div>
                <div class="text-[10px] mt-[4px]" style="opacity: 0.5;">或点击选择 zip 文件</div>
              </div>
              <div v-else>
                <svg class="mx-auto mb-[6px]" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="rgb(52,199,89)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <div class="text-[11.5px] font-medium" style="color: var(--text-primary);">{{ selectedFolderName }}</div>
              </div>
            </div>
          </div>

          <!-- Server directory -->
          <div v-if="form.source_type === 'server'">
            <label class="text-[11px] font-medium block mb-[5px] tracking-[-0.01em]" style="color: var(--text-secondary);">服务器项目目录</label>
            <select
              v-model="form.server_path"
              class="w-full px-[10px] py-[7px] text-[12.5px] rounded-[8px] outline-none transition-all duration-150 cursor-pointer"
              :style="{
                backgroundColor: 'var(--input-bg)',
                border: '0.5px solid var(--border)',
                color: 'var(--text-primary)',
                boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.04)',
              }"
            >
              <option value="" disabled>
                {{ serverDirsLoading ? '加载中...' : (serverDirs.length === 0 ? '当前服务器无项目' : '请选择项目目录') }}
              </option>
              <option v-for="dir in serverDirs" :key="dir" :value="dir">{{ serverDirName(dir) }}</option>
            </select>
          </div>
        </div>

        <!-- macOS-style modal footer -->
        <div class="flex justify-end gap-[8px] px-[20px] py-[14px]" style="border-top: 0.5px solid var(--border);">
          <BaseButton
            variant="secondary"
            size="md"
            @click="closeModal"
          >
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="md"
            :disabled="uploading"
            @click="editingProject ? updateProject() : createProject()"
          >
            {{ uploading ? '上传中...' : (editingProject ? '保存' : '创建') }}
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- macOS-style confirm dialog -->
    <ConfirmDialog ref="confirmDialog" />

    <!-- Project Member Modal -->
    <ProjectMemberModal
      :isOpen="showMemberModal"
      :projectId="activeProjectInfo?.id || 0"
      :creatorId="detailData?.project.creator_id || 0"
      @close="showMemberModal = false"
      @showToast="(msg: string) => emit('showToast', msg)"
      @updated="loadProjectDetail"
    />

    <!-- Defect Detail Dialog -->
    <DefectDetailDialog
      :isOpen="showDefectDialog"
      :defectId="selectedDefect"
      :projectId="activeProjectInfo?.id || 0"
      @close="showDefectDialog = false"
      @updated="() => {
        // 只刷新缺陷数据，不刷新整个项目详情，避免重置状态
        if (detailData) {
          // 标记需要刷新，避免不必要的操作
        }
      }"
      @showToast="(msg: string) => emit('showToast', msg)"
    />
  </div>
</template>

<style scoped>
.card {
  transition: box-shadow 0.2s ease, transform 0.15s ease;
}
.card:hover {
  box-shadow: 0 4px 12px var(--shadow-sm) !important;
  transform: translateY(-1px);
}
.active-card {
  transition: box-shadow 0.2s ease, transform 0.15s ease;
}
.active-card:hover {
  transform: translateY(-1px);
}

@keyframes pulse-dot {
  0% { opacity: 1; }
  50% { opacity: 0.4; }
  100% { opacity: 1; }
}
</style>