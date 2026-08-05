import { ref, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useApi } from './useApi';
import type { BranchInfo } from '../types';

const branches = ref<BranchInfo[]>([]);
const activeBranch = ref<BranchInfo | null>(null);

export function useBranch(projectId?: number) {
  const router = useRouter();
  const route = useRoute();
  const api = computed(() => useApi(projectId));

  async function loadBranches(pid: number) {
    try {
      const { get } = useApi(pid);
      branches.value = await get<BranchInfo[]>(`/projects/${pid}/branches`);
      // Auto-select from URL or default
      const versionParam = route.query.version;
      if (versionParam) {
        const found = branches.value.find(b => b.id === Number(versionParam));
        if (found) activeBranch.value = found;
      }
      if (!activeBranch.value) {
        activeBranch.value = branches.value.find(b => b.is_default) || branches.value[0] || null;
      }
    } catch {
      branches.value = [];
      activeBranch.value = null;
    }
  }

  function switchBranch(branch: BranchInfo) {
    activeBranch.value = branch;
    // Update URL with version param, preserve existing query
    const query = { ...route.query, version: String(branch.id) };
    router.replace({ query });
  }

  async function createBranch(name: string, sourceBranchId?: number): Promise<number | null> {
    if (!projectId) return null;
    try {
      const { post } = useApi(projectId);
      const result = await post<{ id: number }>(`/projects/${projectId}/branches`, {
        name,
        source_branch_id: sourceBranchId ?? null,
      });
      await loadBranches(projectId);
      return result.id;
    } catch {
      return null;
    }
  }

  async function deleteBranch(branchId: number): Promise<boolean> {
    if (!projectId) return false;
    try {
      const { del } = useApi(projectId);
      await del(`/branches/${branchId}`);
      if (activeBranch.value?.id === branchId) {
        activeBranch.value = null;
      }
      await loadBranches(projectId);
      return true;
    } catch {
      return false;
    }
  }

  async function setDefaultBranch(branchId: number): Promise<boolean> {
    if (!projectId) return false;
    try {
      const { post } = useApi(projectId);
      await post(`/branches/${branchId}/set-default`);
      await loadBranches(projectId);
      return true;
    } catch {
      return false;
    }
  }

  // Watch for project changes to reload branches
  watch(() => projectId, (newPid) => {
    if (newPid) {
      loadBranches(newPid);
    } else {
      branches.value = [];
      activeBranch.value = null;
    }
  }, { immediate: false });

  return {
    branches,
    activeBranch,
    loadBranches,
    switchBranch,
    createBranch,
    deleteBranch,
    setDefaultBranch,
  };
}
