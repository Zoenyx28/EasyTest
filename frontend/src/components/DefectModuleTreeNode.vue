<script setup lang="ts">
import type { DefectModuleInfo } from '../types';

const props = defineProps<{
  module: DefectModuleInfo;
  depth: number;
  selectedModuleId: number | null;
  expandedModules: Set<number>;
  renamingModuleId: number | null;
  renameValue: string;
  addingChildParentId: number | null;
  newChildName: string;
}>();

const emit = defineEmits<{
  (e: 'toggleExpand', id: number): void;
  (e: 'select', id: number): void;
  (e: 'startRename', mod: DefectModuleInfo): void;
  (e: 'saveRename'): void;
  (e: 'cancelRename'): void;
  (e: 'deleteModule', id: number): void;
  (e: 'addChild', parentId: number): void;
  (e: 'addChildSave', parentId: number): void;
  (e: 'cancelAddChild'): void;
  (e: 'updateNewChildName', value: string): void;
  (e: 'updateRenameValue', value: string): void;
}>();

const isSelected = props.selectedModuleId === props.module.id;
const isExpanded = props.expandedModules.has(props.module.id);
const hasChildren = props.module.children && props.module.children.length > 0;
const isRenaming = props.renamingModuleId === props.module.id;
const isAddingChild = props.addingChildParentId === props.module.id;
const canAddChild = props.depth < 4;
</script>

<template>
  <!-- Module row -->
  <div
    @click="emit('select', module.id)"
    class="group flex items-center gap-[6px] px-[10px] py-[7px] rounded-[8px] cursor-pointer text-[13px] transition-colors relative"
    :style="isSelected ? { backgroundColor: 'var(--selected-bg)', color: 'var(--accent)', fontWeight: 600 } : { color: 'var(--text-secondary)' }"
    @mouseenter="(e: MouseEvent) => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)' }"
    @mouseleave="(e: MouseEvent) => { if (!isRenaming) (e.currentTarget as HTMLElement).style.backgroundColor = '' }"
  >
    <!-- Expand toggle -->
    <svg
      v-if="hasChildren"
      @click.stop="emit('toggleExpand', module.id)"
      width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
      class="transition-transform duration-150 shrink-0"
      :style="{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', color: 'var(--text-tertiary)' }"
    >
      <polyline points="9 18 15 12 9 6"/>
    </svg>
    <span v-else class="w-[10px] shrink-0"></span>

    <!-- Folder icon -->
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="shrink-0">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>

    <!-- Module name / rename input -->
    <input
      v-if="isRenaming"
      :value="renameValue"
      @input="emit('updateRenameValue', ($event.target as HTMLInputElement).value)"
      type="text"
      class="flex-1 bg-transparent text-[13px] outline-none min-w-0 px-[4px] py-[1px] rounded-[3px]"
      style="color: var(--text-primary); border: 1px solid var(--accent);"
      @click.stop
      @keyup.enter="emit('saveRename')"
      @keyup.escape="emit('cancelRename')"
      @blur="emit('saveRename')"
    />
    <span v-else class="flex-1 truncate">{{ module.name }}</span>

    <!-- Hover actions -->
    <div
      v-if="!isRenaming"
      class="flex items-center gap-[2px] opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
    >
      <button
        v-if="canAddChild"
        @click.stop="emit('addChild', module.id)"
        class="w-[20px] h-[20px] rounded-[4px] flex items-center justify-center cursor-pointer"
        style="color: var(--text-tertiary);"
        @mouseenter="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)'; (e.currentTarget as HTMLElement).style.color = 'var(--accent)' }"
        @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = ''; (e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)' }"
        title="添加子模块"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>
      <button
        @click.stop="emit('startRename', module)"
        class="w-[20px] h-[20px] rounded-[4px] flex items-center justify-center cursor-pointer"
        style="color: var(--text-tertiary);"
        @mouseenter="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)'; (e.currentTarget as HTMLElement).style.color = 'var(--accent)' }"
        @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = ''; (e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)' }"
        title="重命名"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>
      <button
        @click.stop="emit('deleteModule', module.id)"
        class="w-[20px] h-[20px] rounded-[4px] flex items-center justify-center cursor-pointer"
        style="color: var(--text-tertiary);"
        @mouseenter="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--hover-bg)'; (e.currentTarget as HTMLElement).style.color = 'var(--color-danger)' }"
        @mouseleave="(e: MouseEvent) => { (e.currentTarget as HTMLElement).style.backgroundColor = ''; (e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)' }"
        title="删除"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- Add child input -->
  <div v-if="isAddingChild" class="flex items-center gap-[6px] px-[10px] py-[4px]" :style="{ paddingLeft: `${(depth + 1) * 14 + 10}px` }">
    <input
      :value="newChildName"
      @input="emit('updateNewChildName', ($event.target as HTMLInputElement).value)"
      type="text"
      placeholder="输入子模块名称..."
      class="flex-1 bg-transparent text-[12px] outline-none px-[6px] py-[3px] rounded-[4px]"
      style="color: var(--text-primary); border: 1px solid var(--accent);"
      @keyup.enter="emit('addChildSave', module.id)"
      @keyup.escape="emit('cancelAddChild')"
    />
    <button @click="emit('addChildSave', module.id)" class="w-[20px] h-[20px] flex items-center justify-center cursor-pointer" style="color: var(--accent);">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
    </button>
    <button @click="emit('cancelAddChild')" class="w-[20px] h-[20px] flex items-center justify-center cursor-pointer" style="color: var(--text-tertiary);">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>
  </div>

  <!-- Children -->
  <div v-if="hasChildren && isExpanded">
    <DefectModuleTreeNode
      v-for="child in module.children"
      :key="child.id"
      :module="child"
      :depth="depth + 1"
      :selectedModuleId="selectedModuleId"
      :expandedModules="expandedModules"
      :renamingModuleId="renamingModuleId"
      :renameValue="renameValue"
      :addingChildParentId="addingChildParentId"
      :newChildName="newChildName"
      @toggleExpand="emit('toggleExpand', $event)"
      @select="emit('select', $event)"
      @startRename="emit('startRename', $event)"
      @saveRename="emit('saveRename')"
      @cancelRename="emit('cancelRename')"
      @deleteModule="emit('deleteModule', $event)"
      @addChild="emit('addChild', $event)"
      @addChildSave="emit('addChildSave', $event)"
      @cancelAddChild="emit('cancelAddChild')"
      @updateNewChildName="emit('updateNewChildName', $event)"
      @updateRenameValue="emit('updateRenameValue', $event)"
    />
  </div>
</template>
