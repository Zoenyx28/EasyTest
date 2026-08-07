<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useProjectNote } from '../composables/useProjectNote';
import { renderMarkdown } from '../utils/markdown';
import type { ProjectNoteInfo } from '../types';
const emit=defineEmits(['info-back'])
const props = defineProps<{
  projectId: number;
}>();


const { getNote, updateNote } = useProjectNote(props.projectId);

const isEditMode = ref(false);
const noteContent = ref('');
const savedContent = ref('');
const noteInfo = ref<ProjectNoteInfo | null>(null);
const loading = ref(false);
const saving = ref(false);

async function loadNote() {
  loading.value = true;
  try {
    const note = await getNote();
    noteInfo.value = note;
    noteContent.value = note?.content || '';
    savedContent.value = note?.content || '';
    emit('info-back', noteInfo.value);
  } catch {
    noteContent.value = '';
    savedContent.value = '';
    noteInfo.value = null;
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  saving.value = true;
  try {
    const result = await updateNote(noteContent.value);
    noteInfo.value = result;
    savedContent.value = noteContent.value;
    isEditMode.value = false;
  } catch (e: any) {
    
  } finally {
    saving.value = false;
  }
}

function toggleEdit() {
  if (isEditMode.value) {
    // Switching to preview: revert unsaved changes
    noteContent.value = savedContent.value;
  }
  isEditMode.value = !isEditMode.value;
}

function cancelEdit() {
  noteContent.value = savedContent.value;
  isEditMode.value = false;
}

function formatTime(iso: string): string {
  if (!iso) return '';
  return iso.substring(0, 16).replace('T', ' ');
}

onMounted(() => {
  loadNote();
});

watch(() => props.projectId, () => {
  loadNote();
});
</script>

<template>
  <div class="project-note-editor h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-3 shrink-0">
      <div class="flex items-center gap-2">
        <!-- <svg class="w-[16px] h-[16px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--text-secondary);">
          <path d="M12 20h9"></path>
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
        </svg> -->
        <!-- <span class="text-[13px] font-semibold" style="color: var(--text-primary);">项目备注</span> -->
      </div>
      <div class="flex items-center gap-2">
        <!-- <span v-if="noteInfo?.updated_by_name" class="text-[11px]" style="color: var(--text-tertiary);">
          最后编辑：{{ noteInfo.updated_by_name }} · {{ formatTime(noteInfo.updated_at) }}
        </span> -->
        <div class="flex items-center gap-2">
          <button
            v-if="!isEditMode"
            @click="isEditMode = true"
            class="flex items-center gap-1 px-3 py-1.5 rounded-[6px] text-[11.5px] font-medium cursor-pointer transition-all"
            style="background-color: var(--accent); color: #fff;"
            @mouseenter="($event.currentTarget as HTMLElement).style.opacity = '0.9'"
            @mouseleave="($event.currentTarget as HTMLElement).style.opacity = '1'"
          >
            <svg class="w-[12px] h-[12px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            编辑
          </button>
          <button
            v-if="isEditMode"
            @click="handleSave"
            :disabled="saving"
            class="flex items-center gap-1 px-3 py-1.5 rounded-[6px] text-[11.5px] font-medium cursor-pointer transition-all"
            style="background-color: var(--accent); color: #fff;"
            :style="{ opacity: saving ? 0.5 : 1 }"
          >
            <svg class="w-[12px] h-[12px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
              <polyline points="17 21 17 13 7 13 7 21"></polyline>
              <polyline points="7 3 7 8 15 8"></polyline>
            </svg>
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button
            v-if="isEditMode"
            @click="cancelEdit"
            class="flex items-center gap-1 px-3 py-1.5 rounded-[6px] text-[11.5px] font-medium cursor-pointer transition-all"
            style="background-color: var(--input-bg); color: var(--text-secondary); border: 1px solid var(--border);"
          >
            取消
          </button>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center flex-1">
      <span class="text-[12px]" style="color: var(--text-tertiary);">加载中...</span>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!isEditMode && !savedContent"
      class="flex flex-col items-center justify-center flex-1 rounded-[8px] cursor-pointer transition-colors"
      style="border: 1px dashed var(--border);"
      @click="isEditMode = true"
      @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = 'var(--accent)'"
      @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'var(--border)'"
    >
      <!-- <svg class="w-[24px] h-[24px] mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--text-tertiary);">
        <path d="M12 20h9"></path>
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
      </svg> -->
      <!-- <span class="text-[12px]" style="color: var(--text-tertiary);">点击添加项目备注（支持 Markdown）</span> -->
    </div>

    <!-- Edit mode -->
    <div v-else-if="isEditMode" class="flex flex-col flex-1 min-h-0">
      <textarea
        v-model="noteContent"
        class="w-full flex-1 min-h-0 p-3 rounded-[8px] text-[13px] outline-none resize-none overflow-y-auto"
        style="background-color: var(--input-bg); border: 1px solid var(--border); color: var(--text-primary); font-family: var(--font-mono); line-height: 1.6;"
        placeholder="输入 Markdown 内容..."
      ></textarea>
    </div>

    <!-- Preview mode -->
    <div v-else class="markdown-preview flex flex-col flex-1 min-h-0 rounded-[8px] p-3" style="background-color: var(--input-bg); border: 1px solid var(--border);">
      <div
        class="prose prose-sm max-w-none flex-1 min-h-0 overflow-y-auto text-[12px] select-text"
        style="color: var(--text-primary); line-height: 1.75;"
        v-html="renderMarkdown(savedContent)"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.markdown-preview {
  font-family: var(--font);
  font-size: 12px;
}

.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3) {
  margin-top: 0.5em;
  margin-bottom: 0.3em;
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-preview :deep(h1) { font-size: 1.15rem; }
.markdown-preview :deep(h2) { font-size: 1.05rem; }
.markdown-preview :deep(h3) { font-size: 0.95rem; }

.markdown-preview :deep(p) {
  margin: 0.4em 0;
  color: var(--text-primary);
}

.markdown-preview :deep(code) {
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: var(--font-mono);
  background-color: var(--card-bg-2);
  color: var(--text-primary);
}

.markdown-preview :deep(pre) {
  padding: 0.8em;
  border-radius: 6px;
  overflow-x: auto;
  background-color: var(--card-bg-2);
  border: 1px solid var(--border);
}

.markdown-preview :deep(pre code) {
  padding: 0;
  background: none;
}

.markdown-preview :deep(ul) {
  padding-left: 1.5em;
  margin: 0.4em 0;
  list-style: disc;
}

.markdown-preview :deep(li) {
  margin: 0.2em 0;
  color: var(--text-primary);
}

.markdown-preview :deep(a) {
  color: var(--accent);
  text-decoration: none;
  cursor: pointer;
}

.markdown-preview :deep(a:hover) {
  text-decoration: underline;
}

.markdown-preview :deep(strong) {
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-preview :deep(em) {
  font-style: italic;
}
</style>