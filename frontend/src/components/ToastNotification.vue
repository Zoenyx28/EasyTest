<script setup lang="ts">
import { ref, watch } from 'vue';

const props = defineProps<{
  message: string | null;
  duration?: number;
}>();

const emit = defineEmits<{
  (e: 'dismiss'): void;
}>();

const visible = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;

watch(() => props.message, (msg) => {
  if (timer) { clearTimeout(timer); timer = null; }
  if (msg) {
    visible.value = true;
    timer = setTimeout(() => {
      visible.value = false;
      setTimeout(() => emit('dismiss'), 300);
    }, props.duration ?? 3000);
  } else {
    visible.value = false;
  }
});
</script>

<template>
  <Transition name="toast">
    <div 
      v-if="visible && message" 
      class="fixed right-[20px] bottom-[20px] flex items-center gap-[8px] px-[14px] py-[9px] rounded-[10px] border text-[12.5px] z-[200]"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 10px 24px rgba(0,0,0,.16); color: var(--text-primary);"
    >
      <span class="w-[7px] h-[7px] rounded-full shrink-0" style="background-color: var(--accent);"></span>
      <span>{{ message }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.18s ease-out;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>