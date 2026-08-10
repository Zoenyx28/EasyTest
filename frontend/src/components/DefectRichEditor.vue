<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

const props = defineProps<{
  modelValue: string;
  placeholder?: string;
  /** 上传图片并返回可直接显示的 URL（例如临时附件地址）。未提供时回退为 base64 内嵌。 */
  uploadImage?: (file: File) => Promise<string>;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void;
  (e: 'error', msg: string): void;
}>();

const editorRef = ref<HTMLDivElement | null>(null);

// 链接弹窗状态
const linkOpen = ref(false);
const linkUrl = ref('');

/**
 * 光标修复：不通过 v-html 双向绑定（每次 emit 后 innerHTML 被重设会把光标
 * 重置到内容最前面）。仅在外部 modelValue 与当前内容不一致时同步 DOM，
 * 用户自己输入触发的事件不会重设，从而保留光标位置。
 */
function syncFromModel() {
  const el = editorRef.value;
  if (el && props.modelValue !== el.innerHTML) {
    el.innerHTML = props.modelValue;
  }
}

onMounted(syncFromModel);
watch(() => props.modelValue, syncFromModel);

function emitValue() {
  const html = editorRef.value?.innerHTML || '';
  if (html !== props.modelValue) emit('update:modelValue', html);
}

function execCommand(cmd: string, value?: string) {
  document.execCommand(cmd, false, value);
  editorRef.value?.focus();
  emitValue();
}

function sanitizeHref(url: string): string {
  return url.replace(/["'<>]/g, '').trim();
}

function insertImage(file: File) {
  if (props.uploadImage) {
    props.uploadImage(file)
      .then((url) => execCommand('insertImage', url))
      .catch((e: any) => emit('error', e?.message || '图片上传失败'));
    return;
  }
  // Fallback: inline base64 data URL
  const reader = new FileReader();
  reader.onload = (e) => {
    execCommand('insertImage', e.target?.result as string);
  };
  reader.readAsDataURL(file);
}

function pickImage() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = () => {
    const file = input.files?.[0];
    if (file) insertImage(file);
  };
  input.click();
}

function openLinkDialog() {
  linkUrl.value = '';
  linkOpen.value = true;
  // 下一帧聚焦输入框
  requestAnimationFrame(() => {
    (document.querySelector('.link-input') as HTMLInputElement | null)?.focus();
  });
}

function applyLink() {
  const raw = linkUrl.value.trim();
  linkOpen.value = false;
  if (!raw) return;
  const href = sanitizeHref(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
  if (!href) return;
  const sel = window.getSelection();
  const hasSelection = !!sel && !sel.isCollapsed && !!editorRef.value?.contains(sel.anchorNode);
  if (hasSelection) {
    execCommand('createLink', href);
  } else {
    execCommand(
      'insertHTML',
      `<a href="${href}" target="_blank" rel="noopener">${raw.replace(/[<>]/g, '')}</a>`,
    );
  }
  linkUrl.value = '';
}

function onPaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items;
  if (items) {
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        e.preventDefault();
        const file = items[i].getAsFile();
        if (file) insertImage(file);
        return;
      }
    }
  }
  // Fallback: insert as plain text
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
      <button type="button" class="toolbar-btn" title="插入图片" @click="pickImage">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      </button>
      <button type="button" class="toolbar-btn" title="插入链接" @click="openLinkDialog">
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
    ></div>

    <!-- Link dialog -->
    <div v-if="linkOpen" class="link-overlay" @click.self="linkOpen = false">
      <div class="link-panel">
        <div class="link-title">插入链接</div>
        <input
          v-model="linkUrl"
          class="link-input"
          placeholder="输入链接地址，如 https://example.com"
          @keyup.enter="applyLink"
          @keyup.esc="linkOpen = false"
        />
        <div class="link-actions">
          <button type="button" class="link-btn cancel" @click="linkOpen = false">取消</button>
          <button type="button" class="link-btn ok" @click="applyLink">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rich-editor {
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background-color: var(--input-bg);
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.rich-editor:focus-within {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
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

/* ── Link dialog ── */
.link-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--overlay-bg);
}

.link-panel {
  width: 360px;
  padding: 16px;
  border-radius: var(--radius-lg);
  background-color: var(--bg-card);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
  border: 3px solid var(--outline);
}

.link-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
  font-family: var(--font-heading);
}

.link-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: var(--font);
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  outline: none;
}

.link-input:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.link-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.link-btn {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
  font-family: var(--font);
  transition: all 0.15s ease;
}

.link-btn.cancel {
  background: var(--bg-soft);
  color: var(--text-secondary);
}

.link-btn.cancel:hover {
  background: var(--row-hover);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.link-btn.ok {
  background: var(--cta);
  color: #fff;
}

.link-btn.ok:hover {
  filter: brightness(0.95);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
</style>
