<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'blue' | 'orange' | 'yellow' | 'green' | 'red' | 'purple' | 'gray';
  size?: 'sm' | 'md';
  dot?: boolean;
}>(), {
  tone: 'gray',
  size: 'sm',
  dot: false,
});
</script>

<template>
  <span class="base-tag" :class="[`base-tag--${tone}`, `base-tag--${size}`]">
    <span v-if="dot" class="base-tag__dot" aria-hidden="true"></span>
    <slot />
  </span>
</template>

<style scoped>
.base-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  font-family: var(--font);
  font-weight: 600;
  white-space: nowrap;
  vertical-align: middle;
}

.base-tag--sm {
  padding: 2px 8px;
  font-size: 10.5px;
}
.base-tag--md {
  padding: 3px 10px;
  font-size: 11.5px;
}

.base-tag__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background-color: currentColor;
}

/* tone 映射到既有语义 token（明暗双主题自动适配） */
.base-tag--red {
  background-color: var(--danger-soft);
  color: var(--color-danger);
}
.base-tag--orange {
  background-color: var(--warning-soft);
  color: var(--priority-p1-text);
}
.base-tag--yellow {
  background-color: var(--priority-p2-bg);
  color: var(--priority-p2-text);
}
.base-tag--green {
  background-color: var(--success-soft);
  color: var(--color-success);
}
.base-tag--blue {
  background-color: var(--status-confirmed-bg);
  color: var(--status-confirmed-text);
}
.base-tag--purple {
  background-color: color-mix(in srgb, var(--broken) 12%, transparent);
  color: var(--broken);
}
.base-tag--gray {
  background-color: var(--bg-soft);
  color: var(--text-secondary);
}
</style>
