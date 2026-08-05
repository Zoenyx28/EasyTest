import { useApi } from './useApi';
import type { ProjectNoteInfo } from '../types';

export function useProjectNote(projectId: number) {
  const { get, put } = useApi(projectId);

  async function getNote(): Promise<ProjectNoteInfo | null> {
    return get<ProjectNoteInfo | null>(`/projects/${projectId}/note`);
  }

  async function updateNote(content: string): Promise<ProjectNoteInfo> {
    return put<ProjectNoteInfo>(`/projects/${projectId}/note`, { content });
  }

  return { getNote, updateNote };
}