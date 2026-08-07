<script setup lang="ts">
withDefaults(defineProps<{
  open?: boolean;
  title?: string;
  /** 面板宽度（px），可传任意数值 */
  width?: number;
  closeOnBackdrop?: boolean;
  showTrafficLights?: boolean;
}>(), {
  open: false,
  title: '',
  width: 520,
  closeOnBackdrop: true,
  showTrafficLights: true,
});

const emit = defineEmits<{
  (e: 'close'): void;
}>();

function onBackdropClick() {
  emit('close');
}
</script>

<template>
  <teleport to="body">
    <transition name="base-dialog">
      <div
        v-if="open"
        class="base-dialog"
        style="background-color: var(--overlay-bg); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);"
        @click.self="onBackdropClick"
      >
        <div class="base-dialog__panel" :style="{ width: width + 'px' }" @click.stop>
          <!-- macOS 风格标题栏 -->
          <div v-if="showTrafficLights || title || $slots.header" class="base-dialog__header">
            <div v-if="showTrafficLights" class="base-dialog__lights">
              <span class="base-dialog__light base-dialog__light--red"></span>
              <span class="base-dialog__light base-dialog__light--yellow"></span>
              <span class="base-dialog__light base-dialog__light--green"></span>
            </div>
            <span v-if="title" class="base-dialog__title">{{ title }}</span>
            <slot name="header" />
          </div>

          <div class="base-dialog__body">
            <slot />
          </div>

          <div v-if="$slots.footer" class="base-dialog__footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.base-dialog {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.base-dialog__panel {
  max-width: calc(100vw - 40px);
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-dialog);
}

.base-dialog__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
  user-select: none;
}

.base-dialog__lights {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.base-dialog__light {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.base-dialog__light--red { background-color: rgb(255, 95, 87); }
.base-dialog__light--yellow { background-color: rgb(255, 189, 46); }
.base-dialog__light--green { background-color: rgb(39, 201, 63); }

.base-dialog__title {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.base-dialog__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.base-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  flex-shrink: 0;
  border-top: 1px solid var(--border);
}

/* transition */
.base-dialog-enter-active,
.base-dialog-leave-active {
  transition: opacity 0.18s ease;
}
.base-dialog-enter-active .base-dialog__panel,
.base-dialog-leave-active .base-dialog__panel {
  transition: transform 0.18s ease;
}
.base-dialog-enter-from,
.base-dialog-leave-to {
  opacity: 0;
}
.base-dialog-enter-from .base-dialog__panel,
.base-dialog-leave-to .base-dialog__panel {
  transform: scale(0.96);
}
</style>
