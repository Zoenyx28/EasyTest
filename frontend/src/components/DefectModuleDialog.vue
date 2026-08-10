<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useDefect } from '../composables/useDefect';
import type { DefectModuleInfo } from '../types';

const props = defineProps<{
  isOpen: boolean;
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'showToast', msg: string): void;
}>();

const defectApi = useDefect(props.projectId);

const modules = ref<DefectModuleInfo[]>([]);
const loading = ref(false);
const editingModule = ref<{ id: number; name: string } | null>(null);
const addingParentId = ref<number | null>(null);
const newModuleName = ref('');
const confirmDeleteId = ref<number | null>(null);
const expandedModules = ref<Set<number>>(new Set());
const searchQuery = ref('');

async function loadModules() {
  loading.value = true;
  try {
    modules.value = await defectApi.getModules(props.projectId);
    expandedModules.value = new Set(modules.value.map(m => m.id));
  } catch (e: any) {
    emit('showToast', e.message || '加载模块失败');
  } finally {
    loading.value = false;
  }
}

async function handleAddModule(parentId: number | null) {
  if (!newModuleName.value.trim()) return;
  try {
    await defectApi.createModule({
      project_id: props.projectId,
      name: newModuleName.value.trim(),
      parent_id: parentId || 0,
    });
    newModuleName.value = '';
    addingParentId.value = null;
    emit('showToast', '模块创建成功');
    await loadModules();
  } catch (e: any) {
    emit('showToast', e.message || '创建模块失败');
  }
}

function startEdit(module: DefectModuleInfo) {
  editingModule.value = { id: module.id, name: module.name };
}

async function handleEdit() {
  if (!editingModule.value || !editingModule.value.name.trim()) return;
  try {
    await defectApi.updateModule(editingModule.value.id, { name: editingModule.value.name.trim() });
    editingModule.value = null;
    emit('showToast', '模块名称已更新');
    await loadModules();
  } catch (e: any) {
    emit('showToast', e.message || '更新模块失败');
  }
}

async function handleDelete(id: number) {
  try {
    await defectApi.deleteModule(id);
    confirmDeleteId.value = null;
    emit('showToast', '模块已删除');
    await loadModules();
  } catch (e: any) {
    emit('showToast', e.message || '删除模块失败');
  }
}

function toggleExpand(id: number) {
  if (expandedModules.value.has(id)) {
    expandedModules.value.delete(id);
  } else {
    expandedModules.value.add(id);
  }
  expandedModules.value = new Set(expandedModules.value);
}

function renderTree(list: DefectModuleInfo[], depth = 0): DefectModuleInfo[] {
  const result: DefectModuleInfo[] = [];
  for (const item of list) {
    result.push({ ...item, children: [] });
    if (item.children && item.children.length > 0) {
      result.push(...renderTree(item.children, depth + 1));
    }
  }
  return result;
}

function handleClose() {
  modules.value = [];
  editingModule.value = null;
  addingParentId.value = null;
  newModuleName.value = '';
  confirmDeleteId.value = null;
  searchQuery.value = '';
  emit('close');
}

watch(() => props.isOpen, (open) => {
  if (open) {
    loadModules();
  }
});
</script>

<template>
  <teleport to="body">
    <div v-if="isOpen" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog-container">
        <div class="dialog-header">
          <div class="header-left">
            <h2 class="dialog-title">模块管理</h2>
            <p class="dialog-subtitle">将缺陷分类组织成层级树结构。</p>
          </div>
          <button class="dialog-close-btn" @click="handleClose">×</button>
        </div>
        <div class="dialog-body">
          <!-- Search and add -->
          <div class="search-add-bar">
            <div class="search-input-wrapper">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input
                v-model="searchQuery"
                class="search-input"
                placeholder="搜索模块..."
              />
            </div>
            <button class="btn-add-root" @click="addingParentId = 0; newModuleName = ''">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              添加根模块
            </button>
          </div>

          <!-- Add module input -->
          <div v-if="addingParentId !== null" class="add-input-row">
            <input
              v-model="newModuleName"
              class="add-input"
              placeholder="输入模块名称..."
              @keyup.enter="handleAddModule(addingParentId === 0 ? null : addingParentId)"
              @keyup.escape="addingParentId = null; newModuleName = ''"
              autofocus
            />
            <button class="btn btn-sm btn-confirm" @click="handleAddModule(addingParentId === 0 ? null : addingParentId)">确认</button>
            <button class="btn btn-sm btn-cancel" @click="addingParentId = null; newModuleName = ''">取消</button>
          </div>

          <!-- Loading -->
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>加载中...</span>
          </div>

          <!-- Empty state -->
          <div v-else-if="modules.length === 0" class="empty-state">
            <p class="empty-text">暂无模块。先添加一个根模块开始。</p>
          </div>

          <!-- Module tree -->
          <div v-else class="module-tree-container">
            <template v-for="mod in modules" :key="mod.id">
              <div class="module-item">
                <div class="module-row" @click="toggleExpand(mod.id)">
                  <button class="expand-btn" v-if="mod.children && mod.children.length > 0">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :style="{ transform: expandedModules.has(mod.id) ? 'rotate(0deg)' : 'rotate(-90deg)' }">
                      <polyline points="6 15 12 9 18 15"/>
                    </svg>
                  </button>
                  <span class="expand-placeholder" v-else></span>

                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="module-icon">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>

                  <template v-if="editingModule?.id === mod.id">
                          <input
                            v-model="editingModule.name"
                            class="edit-input"
                            @keyup.enter="handleEdit"
                            @keyup.escape="editingModule = null"
                            @click.stop
                            autofocus
                          />
                          <button class="btn btn-sm btn-confirm" @click.stop="handleEdit">保存</button>
                          <button class="btn btn-sm btn-cancel" @click.stop="editingModule = null">取消</button>
                        </template>

                        <template v-else>
                          <span class="module-name">{{ mod.name }}</span>
                          <div class="module-actions">
                            <button class="icon-btn" title="添加子模块" @click.stop="addingParentId = mod.id; newModuleName = ''">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="12" y1="5" x2="12" y2="19"/>
                                <line x1="5" y1="12" x2="19" y2="12"/>
                              </svg>
                            </button>
                            <button class="icon-btn" title="重命名" @click.stop="startEdit(mod)">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                            </button>
                            <button class="icon-btn icon-btn-danger" title="删除" @click.stop="confirmDeleteId = mod.id">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                              </svg>
                            </button>
                          </div>
                        </template>
                </div>

                <template v-if="mod.children && mod.children.length > 0 && expandedModules.has(mod.id)">
                  <div class="module-children">
                    <div v-for="child in mod.children" :key="child.id" class="module-item">
                      <div class="module-row" @click="toggleExpand(child.id)">
                        <button class="expand-btn" v-if="child.children && child.children.length > 0">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :style="{ transform: expandedModules.has(child.id) ? 'rotate(0deg)' : 'rotate(-90deg)' }">
                            <polyline points="6 15 12 9 18 15"/>
                          </svg>
                        </button>
                        <span class="expand-placeholder" v-else></span>

                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="module-icon">
                          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>

                        <template v-if="editingModule?.id === child.id">
                          <input v-model="editingModule.name" class="edit-input" @keyup.enter="handleEdit" @keyup.escape="editingModule = null" @click.stop autofocus />
                          <button class="btn btn-sm btn-confirm" @click.stop="handleEdit">保存</button>
                          <button class="btn btn-sm btn-cancel" @click.stop="editingModule = null">取消</button>
                        </template>

                        <template v-else>
                          <span class="module-name">{{ child.name }}</span>
                          <div class="module-actions">
                            <button class="icon-btn" title="添加子模块" @click.stop="addingParentId = child.id; newModuleName = ''">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="12" y1="5" x2="12" y2="19"/>
                                <line x1="5" y1="12" x2="19" y2="12"/>
                              </svg>
                            </button>
                            <button class="icon-btn" title="重命名" @click.stop="startEdit(child)">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                            </button>
                            <button class="icon-btn icon-btn-danger" title="删除" @click.stop="confirmDeleteId = child.id">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                              </svg>
                            </button>
                          </div>
                        </template>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </template>
          </div>
        </div>

        <!-- Delete confirmation -->
        <div v-if="confirmDeleteId" class="confirm-overlay" @click.self="confirmDeleteId = null">
          <div class="confirm-box">
            <p class="confirm-text">确定要删除此模块吗？</p>
            <div class="confirm-actions">
              <button class="btn btn-sm btn-cancel" @click="confirmDeleteId = null">取消</button>
              <button class="btn btn-sm btn-danger" @click="handleDelete(confirmDeleteId)">删除</button>
            </div>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn-close" @click="handleClose">关闭</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--overlay-bg);
}

.dialog-container {
  width: 720px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  background-color: var(--bg-card);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
  overflow: hidden;
  position: relative;
}

.dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dialog-title {
  font-family: var(--font-heading);
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  line-height: 28px;
}

.dialog-subtitle {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
  margin: 0;
  line-height: 18px;
}

.dialog-close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 20px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: all 0.15s ease;
  line-height: 1;
}

.dialog-close-btn:hover {
  background: var(--color-primary-soft);
  color: var(--text-primary);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}

.search-add-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: var(--input-bg);
  border-radius: var(--radius-sm);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: all 0.15s ease;
}

.search-input-wrapper:focus-within {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.search-input-wrapper svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-family: var(--font);
  font-size: 13px;
  color: var(--text-primary);
  line-height: 18px;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.btn-add-root {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background-color: var(--cta);
  border: 2px solid var(--outline);
  color: #fff;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn-add-root:hover {
  background-color: var(--cta-dark);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.btn {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm);
  line-height: 18px;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.btn-confirm {
  background-color: var(--cta);
  color: #fff;
}

.btn-confirm:hover {
  background-color: var(--cta-dark);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.btn-cancel {
  background-color: var(--bg-soft);
  color: var(--text-secondary);
}

.btn-cancel:hover {
  background-color: var(--bg-muted);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.btn-danger {
  background-color: var(--color-danger);
  color: #fff;
}

.btn-danger:hover {
  filter: brightness(0.92);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

.add-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background-color: var(--bg-muted);
  border-radius: 8px;
  border: 1px solid var(--border-hover);
}

.add-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-family: var(--font);
  font-size: 13px;
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  outline: none;
  line-height: 18px;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.add-input:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px;
  gap: 12px;
  color: var(--text-muted);
  font-family: var(--font);
  font-size: 13px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid var(--border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-text {
  color: var(--text-muted);
  font-family: var(--font);
  font-size: 13px;
  line-height: 18px;
}

.module-tree-container {
  border: 1px solid var(--border-hover);
  border-radius: 8px;
  padding: 12px 16px;
  min-height: 300px;
}

.module-item {
  margin: 2px 0;
}

.module-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  transition: background 0.15s ease;
  cursor: pointer;
}

.module-row:hover {
  background-color: var(--color-primary-soft);
}

.expand-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
}

.expand-btn svg {
  transition: transform 0.15s ease;
}

.expand-placeholder {
  width: 20px;
  flex-shrink: 0;
}

.module-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.module-name {
  flex: 1;
  font-family: var(--font);
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 18px;
}

.module-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.module-row:hover .module-actions {
  opacity: 1;
}

.icon-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.icon-btn:hover {
  background-color: var(--bg-soft);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.icon-btn-danger:hover {
  background-color: rgba(220, 38, 38, 0.12);
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.module-children {
  margin-left: 20px;
}

.edit-input {
  flex: 1;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-family: var(--font);
  font-size: 13px;
  background-color: var(--input-bg);
  color: var(--text-primary);
  border: 2px solid var(--outline);
  box-shadow: var(--shadow-hard-sm-pressed);
  outline: none;
  line-height: 18px;
  box-sizing: border-box;
  transition: all 0.15s ease;
}

.edit-input:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}

.confirm-overlay {
  position: absolute;
  inset: 0;
  background-color: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: var(--radius-lg);
}

.confirm-box {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
  text-align: center;
}

.confirm-text {
  font-family: var(--font);
  font-size: 14px;
  color: var(--text-primary);
  margin: 0 0 16px;
  font-weight: 500;
  line-height: 20px;
}

.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.btn-close {
  padding: 6px 16px;
  background-color: var(--bg-soft);
  border: 2px solid var(--outline);
  color: var(--text-secondary);
  font-family: var(--font);
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: all 0.15s ease;
}

.btn-close:hover {
  background-color: var(--bg-muted);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
</style>
