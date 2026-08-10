<script setup lang="ts">
withDefaults(defineProps<{
  /** primary=绿色 CTA / secondary=浅蓝辅助 / ghost=文字 / danger=危险红 / warning=橙（高风险专用，ADR-0008） */
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
  border: 3px solid var(--outline);
  border-radius: var(--radius-md);
  font-family: var(--font);
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  box-shadow: var(--shadow-hard-md);
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.base-btn:hover:not(.base-btn--disabled) {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-md-pressed);
}
.base-btn:active:not(.base-btn--disabled) {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
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
  background-color: var(--cta-dark);
}

.base-btn--secondary {
  background-color: var(--color-secondary);
  color: var(--text-primary);
}
.base-btn--secondary:hover:not(.base-btn--disabled) {
  background-color: var(--color-secondary-dark);
}

.base-btn--ghost {
  background-color: transparent;
  border-color: transparent;
  box-shadow: none;
  color: var(--text-secondary);
}
.base-btn--ghost:hover:not(.base-btn--disabled) {
  background-color: var(--hover-bg);
  color: var(--text-primary);
  box-shadow: none;
}

.base-btn--danger {
  background-color: var(--color-danger);
  color: #fff;
}
.base-btn--danger:hover:not(.base-btn--disabled) {
  background-color: var(--color-danger);
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
