<script setup lang="ts">
import { ref, nextTick } from 'vue';

const props = defineProps<{
  modelValue: string;
  placeholder?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void;
}>();

const editorRef = ref<HTMLDivElement | null>(null);

function execCommand(cmd: string, value?: string) {
  document.execCommand(cmd, false, value);
  editorRef.value?.focus();
  emitValue();
}

function insertImage() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = async () => {
    const file = input.files?.[0];
    if (!file) return;
    // For standalone image insertion without a defect context, we insert a placeholder
    // In actual usage within DefectCreateDialog, the image will be uploaded after defect creation
    const reader = new FileReader();
    reader.onload = (e) => {
      const url = e.target?.result as string;
      execCommand('insertImage', url);
    };
    reader.readAsDataURL(file);
  };
  input.click();
}

function insertLink() {
  const url = prompt('请输入链接地址:');
  if (url) {
    execCommand('createLink', url);
  }
}

function emitValue() {
  const html = editorRef.value?.innerHTML || '';
  emit('update:modelValue', html);
}

function onPaste(e: ClipboardEvent) {
  e.preventDefault();
  const text = e.clipboardData?.getData('text/plain') || '';
  document.execCommand('insertText', false, text);
}

function onInput() {
  emitValue();
}

function focusEditor() {
  editorRef.value?.focus();
}
</script>

<template>
  <div class="rich-editor" @click="focusEditor">
    <div class="editor-toolbar">
      <button type="button" class="toolbar-btn" title="加粗" @click="execCommand('bold')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M15.6 11.79A5.12 5.12 0 0 0 18 7.5C18 4.46 15.54 2 12.5 2h-6v20h7c3.04 0 5.5-2.46 5.5-5.5 0-2.09-1.17-3.91-2.9-4.71zM9.5 5.5h3a2 2 0 0 1 0 4h-3V5.5zm3.5 13H9.5v-5.5h3.5a2 2 0 0 1 0 4z"/></svg>
      </button>
      <button type="button" class="toolbar-btn" title="斜体" @click="execCommand('italic')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4v3h2.21l-3.42 8H6v3h8v-3h-2.21l3.42-8H18V4z"/></svg>
      </button>
      <button type="button" class="toolbar-btn" title="下划线" @click="execCommand('underline')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 3v7a6 6 0 0 0 12 0V3"/><line x1="4" y1="21" x2="20" y2="21"/></svg>
      </button>
      <span class="toolbar-separator"></span>
      <button type="button" class="toolbar-btn" title="插入图片" @click="insertImage">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      </button>
      <button type="button" class="toolbar-btn" title="插入链接" @click="insertLink">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
      </button>
    </div>
    <div
      ref="editorRef"
      class="editor-content"
      contenteditable="true"
      :data-placeholder="placeholder"
      @input="onInput"
      @paste="onPaste"
      v-html="modelValue"
    ></div>
  </div>
</template>

<style scoped>
.rich-editor {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background-color: var(--input-bg);
  transition: border-color 0.15s ease;
}

.rich-editor:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 2.5px rgba(10, 132, 255, 0.18);
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 6px;
  border-bottom: 1px solid var(--border);
  background-color: var(--card-bg-2);
  flex-wrap: wrap;
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  background: transparent;
  color: var(--text-secondary);
  transition: all 0.1s ease;
}

.toolbar-btn:hover {
  background-color: var(--row-hover);
  color: var(--text-primary);
}

.toolbar-separator {
  width: 1px;
  height: 16px;
  background-color: var(--border);
  margin: 0 4px;
}

.editor-content {
  min-height: 120px;
  max-height: 300px;
  overflow-y: auto;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  outline: none;
  font-family: inherit;
}

.editor-content:empty::before {
  content: attr(data-placeholder);
  color: var(--text-tertiary);
  pointer-events: none;
}

.editor-content :deep(img) {
  max-width: 100%;
  border-radius: 4px;
  margin: 4px 0;
}

.editor-content :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}
</style>