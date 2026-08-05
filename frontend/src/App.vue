<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth } from './composables/useAuth';
import Header from './components/Header.vue';
import SettingsModal from './components/SettingsModal.vue';
import HelpModal from './components/HelpModal.vue';
import ToastNotification from './components/ToastNotification.vue';

const router = useRouter();
const route = useRoute();
const auth = useAuth();

const globalSearch = ref('');
const selectedUids = ref<string[]>([]);

const isSettingsOpen = ref(false);
const isHelpOpen = ref(false);
const toastMessage = ref<string | null>(null);

const isAuthPage = computed(() => ['login', 'register'].includes(route.name as string));

// Initialize auth state
auth.init();

const showToast = (msg: string) => {
  toastMessage.value = msg;
};

const dismissToast = () => {
  toastMessage.value = null;
};

const handleRunSelected = (uids: string[]) => {
  selectedUids.value = uids;
  router.push('/execution');
  setTimeout(() => { selectedUids.value = []; }, 100);
};

const handleRunAll = (uids: string[]) => {
  selectedUids.value = uids;
  router.push('/execution');
  setTimeout(() => { selectedUids.value = []; }, 100);
};

watch(() => route.path, () => {
}, { immediate: true });
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden select-none" style="background-color: var(--bg-window); color: var(--text-primary); font-family: var(--font);">
    <template v-if="!isAuthPage">
      <Header 
        :currentRoute="route.name as string"
        v-model:globalSearch="globalSearch"
        @openSettings="isSettingsOpen = true"
        @openHelp="isHelpOpen = true"
        @showToast="showToast"
      />
    </template>

    <main class="flex-1 min-h-0" :class="isAuthPage ? '' : 'pt-[56px]'" style="display: flex; flex-direction: column; overflow: hidden; position: relative;">
      <router-view :selectedUids="selectedUids" :globalSearch="globalSearch" @showToast="showToast" @runSelected="handleRunSelected" @runAll="handleRunAll" @rerun="handleRunSelected" />
    </main>

    <template v-if="!isAuthPage">
      <SettingsModal 
        :isOpen="isSettingsOpen" 
        @close="isSettingsOpen = false" 
        @showToast="showToast"
      />

      <HelpModal 
        :isOpen="isHelpOpen" 
        @close="isHelpOpen = false" 
      />
    </template>

    <ToastNotification :message="toastMessage" @dismiss="dismissToast" />
  </div>
</template>