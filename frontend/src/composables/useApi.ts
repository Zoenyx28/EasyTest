import { useRoute } from 'vue-router';

const BASE = '/api'
// Backend always responds with HTTP 200 and the unified envelope
// {code, msg, data}; `code` mirrors HTTP-style semantics (200 = success).
const OK_CODE = 200

interface ApiEnvelope<T = any> {
  code: number
  msg?: string
  data?: T
}

function getToken(): string | null {
  return localStorage.getItem('token')
}

export function authHeaders(): Record<string, string> {
  const token = getToken()
  if (token) {
    return { 'Authorization': `Bearer ${token}` }
  }
  return {}
}

function buildUrl(path: string, projectId?: number, version?: number): string {
  let url = BASE + path
  const params: string[] = []
  if (projectId && !path.includes('project_id')) {
    params.push(`project_id=${projectId}`)
  }
  if (version) {
    params.push(`version=${version}`)
  }
  if (params.length) {
    const separator = url.includes('?') ? '&' : '?'
    url += separator + params.join('&')
  }
  return url
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // Reverse-proxy / gateway errors (non-200 HTTP, e.g. 502) bypass the envelope
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `请求失败 (HTTP ${res.status})`)
  }
  const json: ApiEnvelope<T> = await res.json()
  // 只对非登录相关接口处理 401
  const url = res.url || ''
  if (json.code === 401 && !url.includes('/auth/login') && !url.includes('/auth/register')) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error(json.msg || '登录已过期，请重新登录')
  }
  if (json.code !== OK_CODE) {
    throw new Error(json.msg || '请求失败')
  }
  return json.data ?? json as T
}

export function useApi(projectId?: number) {
  const route = useRoute();

  // Auto-detect version from route query
  function getVersion(): number | undefined {
    const v = route?.query?.version
    return v ? Number(v) : undefined
  }

  async function get<T>(path: string): Promise<T> {
    const res = await fetch(buildUrl(path, projectId, getVersion()), {
      headers: { ...authHeaders() },
    })
    return unwrap<T>(res)
  }
  async function post<T>(path: string, body?: any): Promise<T> {
    const res = await fetch(buildUrl(path, projectId, getVersion()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    })
    return unwrap<T>(res)
  }
  async function put<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(buildUrl(path, projectId, getVersion()), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    })
    return unwrap<T>(res)
  }
  async function del<T = any>(path: string): Promise<T> {
    const res = await fetch(buildUrl(path, projectId, getVersion()), {
      method: 'DELETE',
      headers: { ...authHeaders() },
    })
    return unwrap<T>(res)
  }
  async function patch<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(buildUrl(path, projectId, getVersion()), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    })
    return unwrap<T>(res)
  }
  async function postFormData<T = any>(path: string, formData: FormData): Promise<T> {
    const res = await fetch(buildUrl(path, projectId, getVersion()), {
      method: 'POST',
      headers: { ...authHeaders() },
      body: formData,
    })
    return unwrap<T>(res)
  }
  return { get, post, put, del, patch, postFormData }
}
