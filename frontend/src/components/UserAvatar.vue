<script setup lang="ts">
import { computed } from 'vue';
import { defaultAvatars } from '../assets/default-avatars';

const props = withDefaults(defineProps<{
  name: string;
  avatar?: string;
  size?: number;
  borderColor?: string;
  borderWidth?: number;
}>(), {
  avatar: '',
  size: 28,
  borderColor: '',
  borderWidth: 2,
});

function getDefaultIndex(url: string): number {
  const m = url.match(/^\/avatars\/(\d+)\.svg$/);
  if (m) return parseInt(m[1], 10);
  if (url.startsWith('default:')) return parseInt(url.split(':')[1], 10);
  return 0;
}

const defaultSvg = computed(() => {
  if (!props.avatar) return '';
  const idx = getDefaultIndex(props.avatar);
  const av = defaultAvatars[idx - 1];
  return av ? av.svg : '';
});

const isImage = computed(() => {
  if (!props.avatar) return false;
  return !defaultSvg.value;
});

const initial = computed(() => {
  const n = props.name || '?';
  return n.charAt(0).toUpperCase();
});
</script>

<template>
  <div
    class="user-avatar"
    :style="{
      width: size + 'px',
      height: size + 'px',
      fontSize: Math.round(size * 0.42) + 'px',
      backgroundColor: defaultSvg ? 'transparent' : 'var(--accent)',
      border: borderColor ? `${borderWidth}px solid ${borderColor}` : 'none',
    }"
  >
    <img v-if="isImage" :src="avatar" class="avatar-img" alt="" />
    <span v-else-if="defaultSvg" class="avatar-svg" v-html="defaultSvg"></span>
    <span v-else class="avatar-initial">{{ initial }}</span>
  </div>
</template>

<style scoped>
.user-avatar {
  border-radius: 50%;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  line-height: 1;
}
.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-svg {
  display: flex;
  width: 100%;
  height: 100%;
}
.avatar-svg :deep(svg) {
  width: 100%;
  height: 100%;
}
.avatar-initial {
  font-weight: 600;
}
</style>
