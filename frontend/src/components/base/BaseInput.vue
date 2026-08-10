<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string | number;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
}>(), {
  modelValue: '',
  type: 'text',
  placeholder: '',
  disabled: false,
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'focus', event: FocusEvent): void;
  (e: 'blur', event: FocusEvent): void;
  (e: 'enter'): void;
}>();
</script>

<template>
  <input
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    class="base-input"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    @focus="emit('focus', $event)"
    @blur="emit('blur', $event)"
    @keydown.enter="emit('enter')"
  />
</template>

<style scoped>
.base-input {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 12px;
  font-family: var(--font);
  font-size: 12.5px;
  color: var(--text-primary);
  background-color: var(--input-bg);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  outline: none;
  box-shadow: var(--shadow-hard-sm-pressed);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}
.base-input::placeholder {
  color: var(--text-muted);
}
.base-input:focus {
  border-color: var(--color-primary);
  background-color: var(--card-bg);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-hard-sm-pressed);
}
.base-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
