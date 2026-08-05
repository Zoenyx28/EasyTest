import { useApi } from './useApi';
import type { ProjectMemberInfo, UserSearchResult } from '../types';

export function useProjectMembers() {
  const { get, post, del } = useApi();

  async function getMembers(projectId: number): Promise<ProjectMemberInfo[]> {
    return get<ProjectMemberInfo[]>(`/projects/${projectId}/members`);
  }

  async function addMember(projectId: number, userId: number): Promise<void> {
    await post(`/projects/${projectId}/members`, { user_id: userId });
  }

  async function removeMember(projectId: number, userId: number): Promise<void> {
    await del(`/projects/${projectId}/members/${userId}`);
  }

  async function searchUsers(projectId: number, q: string): Promise<UserSearchResult[]> {
    return get<UserSearchResult[]>(`/projects/${projectId}/members/search?q=${encodeURIComponent(q)}`);
  }

  return { getMembers, addMember, removeMember, searchUsers };
}