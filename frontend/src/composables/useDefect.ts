import { useApi } from './useApi';
import type {
  DefectModuleInfo,
  DefectInfo,
  DefectLogInfo,
  DefectAttachmentInfo,
  DefectCommentInfo,
  DefectCreateData,
  DefectDetailResponse,
} from '../types';

export interface TempAttachmentInfo {
  filename: string;
  filepath: string;
  file_size: number;
  mime_type: string;
}

/**
 * Build a full module path like "一级模块/二级模块/三级模块" from the module tree.
 */
export function buildModulePath(modules: DefectModuleInfo[], targetId: number): string {
  if (!targetId) return '';
  function find(children: DefectModuleInfo[], path: string[]): string[] | null {
    for (const m of children) {
      const current = [...path, m.name];
      if (m.id === targetId) return current;
      if (m.children && m.children.length > 0) {
        const found = find(m.children, current);
        if (found) return found;
      }
    }
    return null;
  }
  const result = find(modules, []);
  return result ? result.join(' / ') : '';
}

export function useDefect(projectId?: number) {
  const api = useApi(projectId);

  async function getModules(projectId: number): Promise<DefectModuleInfo[]> {
    return api.get<DefectModuleInfo[]>(`/defects/modules?project_id=${projectId}`);
  }

  async function createModule(data: { project_id: number; name: string; parent_id: number }): Promise<void> {
    await api.post(`/defects/modules?project_id=${data.project_id}`, {
      name: data.name,
      parent_id: data.parent_id,
      sort_order: 0,
    });
  }

  async function updateModule(id: number, data: { name: string }): Promise<void> {
    await api.put(`/defects/modules/${id}`, data);
  }

  async function deleteModule(id: number): Promise<void> {
    await api.del(`/defects/modules/${id}`);
  }

  async function getDefects(params: {
    project_id: number;
    branch_id: number;
    status?: string;
    severity?: string;
    priority?: string;
    module_id?: number | null;
    assignee_id?: number | null;
    creator_id?: number | null;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ total: number; items: DefectInfo[] }> {
    const query = new URLSearchParams();
    query.set('project_id', String(params.project_id));
    query.set('branch_id', String(params.branch_id));
    if (params.status) query.set('status', params.status);
    if (params.severity) query.set('severity', params.severity);
    if (params.priority) query.set('priority', params.priority);
    if (params.module_id != null) query.set('module_id', String(params.module_id));
    if (params.assignee_id != null) query.set('assignee_id', String(params.assignee_id));
    if (params.creator_id != null) query.set('creator_id', String(params.creator_id));
    if (params.search) query.set('search', params.search);
    if (params.page) query.set('page', String(params.page));
    if (params.page_size) query.set('page_size', String(params.page_size));
    const qs = query.toString();
    // Use get with a path that includes query params
    return api.get<{ total: number; items: DefectInfo[] }>(`/defects?${qs}`);
  }

  async function createDefect(data: Record<string, any>): Promise<DefectInfo> {
    return api.post<DefectInfo>('/defects', data);
  }

  async function getDefect(id: number): Promise<DefectInfo> {
    return api.get<DefectInfo>(`/defects/${id}`);
  }

  async function getDefectDetail(id: number): Promise<DefectDetailResponse> {
    return api.get<DefectDetailResponse>(`/defects/${id}/detail`);
  }

  async function updateDefect(id: number, data: Record<string, any>): Promise<void> {
    await api.put(`/defects/${id}`, data);
  }

  async function transitionDefect(
    id: number,
    action: string,
    assignee_id?: number,
    resolution?: string,
    comment?: string,
    resolved_version?: number,
    duplicate_defect_id?: number,
    bug_type?: string,
    priority?: string,
    deadline?: string,
  ): Promise<void> {
    const body: Record<string, any> = { action };
    if (assignee_id !== undefined && assignee_id !== 0) body.assignee_id = assignee_id;
    if (resolution !== undefined) body.resolution = resolution;
    if (comment !== undefined) body.comment = comment;
    if (resolved_version !== undefined && resolved_version !== 0) body.resolved_version = resolved_version;
    if (duplicate_defect_id !== undefined && duplicate_defect_id !== 0) body.duplicate_defect_id = duplicate_defect_id;
    if (bug_type !== undefined) body.bug_type = bug_type;
    if (priority !== undefined) body.priority = priority;
    if (deadline !== undefined) body.deadline = deadline;
    await api.post(`/defects/${id}/transition`, body);
  }

  async function copyDefect(id: number): Promise<{ id: number }> {
    return api.post<{ id: number }>(`/defects/${id}/copy`, {});
  }

  async function getLogs(id: number): Promise<DefectLogInfo[]> {
    return api.get<DefectLogInfo[]>(`/defects/${id}/logs`);
  }

  async function getAttachments(id: number): Promise<DefectAttachmentInfo[]> {
    return api.get<DefectAttachmentInfo[]>(`/defects/${id}/attachments`);
  }

  async function uploadAttachment(id: number, file: File): Promise<{ id: number }> {
    const formData = new FormData();
    formData.append('file', file);
    return api.postFormData<{ id: number }>(`/defects/${id}/attachments`, formData);
  }

  async function uploadTempAttachment(file: File): Promise<TempAttachmentInfo> {
    const formData = new FormData();
    formData.append('file', file);
    return api.postFormData<TempAttachmentInfo>('/defects/attachments/upload', formData);
  }

  async function deleteAttachment(attachmentId: number): Promise<void> {
    await api.del(`/defects/attachments/${attachmentId}`);
  }

  function getAttachmentDownloadUrl(attachmentId: number): string {
    return `/api/defects/attachments/${attachmentId}/download`;
  }

  async function getRecentDefects(
    projectId: number,
    branchId: number,
    limit?: number,
  ): Promise<DefectInfo[]> {
    let path = `/defects/recent?project_id=${projectId}&branch_id=${branchId}`;
    if (limit) path += `&limit=${limit}`;
    return api.get<DefectInfo[]>(path);
  }

  async function getMyDefects(
    projectId: number,
    branchId: number,
  ): Promise<DefectInfo[]> {
    return api.get<DefectInfo[]>(
      `/defects/my?project_id=${projectId}&branch_id=${branchId}`,
    );
  }

  async function getComments(defectId: number): Promise<DefectCommentInfo[]> {
    return api.get<DefectCommentInfo[]>(`/defects/${defectId}/comments`);
  }

  async function createComment(defectId: number, content: string): Promise<{ id: number }> {
    return api.post<{ id: number }>(`/defects/${defectId}/comments`, { content });
  }

  async function updateComment(commentId: number, content: string): Promise<void> {
    await api.put(`/defects/comments/${commentId}`, { content });
  }

  async function deleteComment(commentId: number): Promise<void> {
    await api.del(`/defects/comments/${commentId}`);
  }

  return {
    getModules,
    createModule,
    updateModule,
    deleteModule,
    getDefects,
    createDefect,
    getDefect,
    getDefectDetail,
    updateDefect,
    transitionDefect,
    copyDefect,
    getLogs,
    getAttachments,
    getRecentDefects,
    getMyDefects,
    uploadAttachment,
    uploadTempAttachment,
    deleteAttachment,
    getAttachmentDownloadUrl,
    getComments,
    createComment,
    updateComment,
    deleteComment,
  };
}
