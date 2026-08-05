import { ref, watch } from 'vue';
import { useApi } from './useApi';

export interface ProjectInfo {
  id: number;
  name: string;
  source_type: string;
  server_path: string;
  is_active: boolean;
  case_count: number;
  new_case_count: number;
  last_synced_at: string;
  created_at: string;
  source_path?: string;
  report_path?: string;
}

const activeProject = ref<ProjectInfo | null>(null);
const projects = ref<ProjectInfo[]>([]);

export function useProject() {
  const { get, post } = useApi();

  async function loadProjects() {
    try {
      projects.value = await get<ProjectInfo[]>('/projects');
      activeProject.value = projects.value.find(p => p.is_active) || null;
    } catch {
      projects.value = [];
      activeProject.value = null;
    }
  }

  async function getActiveProject(): Promise<ProjectInfo | null> {
    try {
      const data = await get<ProjectInfo>('/projects/active');
      activeProject.value = data;
      return data;
    } catch {
      return null;
    }
  }

  async function activateProject(projectId: number) {
    try {
      await post(`/projects/${projectId}/activate`);
      activeProject.value = projects.value.find(p => p.id === projectId) || null;
      for (const p of projects.value) {
        p.is_active = p.id === projectId;
      }
    } catch (e: any) {
      throw new Error(e.message || '激活项目失败');
    }
  }

  async function refreshActiveProject() {
    activeProject.value = null;
    await getActiveProject();
  }

  watch(activeProject, (newProject) => {
    if (newProject) {
      localStorage.setItem('active_project_id', String(newProject.id));
    } else {
      localStorage.removeItem('active_project_id');
    }
  });

  return {
    activeProject,
    projects,
    loadProjects,
    getActiveProject,
    activateProject,
    refreshActiveProject,
  };
}