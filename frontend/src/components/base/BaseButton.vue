<script setup lang="ts">
withDefaults(defineProps<{
  /** primary=主色蓝 / secondary=中性描边 / ghost=文字 / danger=危险红 / warning=橙（高风险专用，ADR-0008） */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'warning';
  size?: 'sm' | 'md';
  type?: 'button' | 'submit';
  disabled?: boolean;
  loading?: boolean;
}>(), {
  variant: 'primary',
  size: 'md',
  type: 'button',
  disabled: false,
  loading: false,
});
</script>

<template>
  <button
    :type="type"
    class="base-btn"
    :class="[`base-btn--${variant}`, `base-btn--${size}`, { 'base-btn--disabled': disabled || loading }]"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="base-btn__spinner" aria-hidden="true"></span>
    <slot />
  </button>
</template>

<style scoped>
.base-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font-family: var(--font);
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.1s ease;
}
.base-btn:active:not(.base-btn--disabled) {
  transform: scale(0.97);
}

/* sizes */
.base-btn--sm {
  padding: 5px 12px;
  font-size: 12px;
}
.base-btn--md {
  padding: 7px 14px;
  font-size: 12.5px;
}

/* variants */
.base-btn--primary {
  background-color: var(--accent);
  color: #fff;
}
.base-btn--primary:hover:not(.base-btn--disabled) {
  background-color: var(--color-primary-dark);
}

.base-btn--secondary {
  background-color: var(--input-bg);
  border-color: var(--border);
  color: var(--text-secondary);
}
.base-btn--secondary:hover:not(.base-btn--disabled) {
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.base-btn--ghost {
  background-color: transparent;
  color: var(--text-secondary);
}
.base-btn--ghost:hover:not(.base-btn--disabled) {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

.base-btn--danger {
  background-color: var(--color-danger);
  color: #fff;
}
.base-btn--danger:hover:not(.base-btn--disabled) {
  filter: brightness(0.92);
}

/* 橙：仅用于高风险操作 / 警告 —— ADR-0008 */
.base-btn--warning {
  background-color: var(--color-accent);
  color: #fff;
}
.base-btn--warning:hover:not(.base-btn--disabled) {
  background-color: var(--color-accent-dark);
}

.base-btn--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.base-btn__spinner {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: base-btn-spin 0.6s linear infinite;
}
@keyframes base-btn-spin {
  to { transform: rotate(360deg); }
}
</style>
