// ── User Types ──

export interface UserInfo {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string;
  created_at: string;
}

export interface UserSearchResult {
  id: number;
  username: string;
  nickname: string;
  avatar_url: string;
}

export interface ProjectMemberInfo {
  id: number;
  user_id: number;
  username: string;
  nickname: string;
  avatar_url: string;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: UserInfo;
}

// ── UI Types ──

export type TabType = 'overview' | 'execution' | 'reports' | 'projects';

export type TestStatus = 'RUNNING' | 'PASSED' | 'FAILED' | 'BROKEN' | 'PENDING' | 'SKIPPED';

// ── Branch Types ──

export interface BranchInfo {
  id: number;
  project_id: number;
  name: string;
  source_branch_id: number | null;
  is_default: boolean;
  is_empty: boolean;
  source_path: string;
  test_path: string;
  created_at: string;
  updated_at: string;
}

export interface LogEntry {
  time: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR';
  message: string;
}

export interface ExecutionHistoryItem {
  id: string;
  status: 'PASSED' | 'FAILED' | 'BROKEN';
  message?: string;
  duration: string;
  time: string;
}

export interface TreeFolder {
  id: string;
  name: string;
  type: 'folder' | 'file' | 'case';
  status?: TestStatus;
  children?: TreeFolder[];
  isOpen?: boolean;
  path?: string;
  uid?: string;
}

// ── Project Note Types ──

export interface ProjectNoteInfo {
  id: number;
  project_id: number;
  content: string;
  updated_by: number;
  updated_by_name: string;
  created_at: string;
  updated_at: string;
}

// ── Backend Discovery Types ──

export interface TestCaseInfo {
  uid: string;
  name: string;
  methodName: string;
  className: string;
  module: string;
  fullName: string;
  description: string;
  tags: string[];
  status: string;
  selected: boolean;
  isNew?: boolean;
  testType?: string;
  filePath?: string;
}

export interface TestClassInfo {
  name: string;
  items: TestCaseInfo[];
  total: number;
  passed: number;
  failed: number;
  broken: number;
  expanded: boolean;
}

export interface TestModuleInfo {
  module: string;
  classes: TestClassInfo[];
  total: number;
  passed: number;
  expanded: boolean;
}

export interface DiscoverResponse {
  modules: TestModuleInfo[];
  total: number;
}

// ── Backend Execution Types ──

export interface RunRequest {
  uids: string[];
  concurrency: number;
  env: string;
  smoke_only: boolean;
  sequential: boolean;
}

export interface RunStatus {
  run_id: string;
  state: string;
  total: number;
  completed: number;
  passed: number;
  failed: number;
  broken: number;
  skipped: number;
  elapsed: string;
}

export interface TestHistoryItem {
  uid: string;
  status: string;
  duration_ms: number;
  message: string;
  executed_at: string;
  run_id: string;
}

export interface RunLogDetail {
  uid: string;
  status: string;
  duration_ms: number;
  message: string;
  trace: string;
  logs: string;
  executed_at: string;
}

export interface TestTask {
  id: number | string;
  name: string;
  status: 'idle' | 'running' | 'done' | 'stopped' | 'error';
  uids: string[];
  total: number;
  passed: number;
  failed: number;
  broken: number;
  skipped: number;
  completed: number;
  execution_id?: string;       // 当前执行实例ID
  run_id?: string;             // 兼容（指向 execution_id）
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

/** Execution summary from GET /api/executions */
export interface ExecutionRecord {
  execution_id: string;
  task_id: number;
  task_name: string;
  status: 'waiting' | 'running' | 'finished' | 'stopped' | 'failed';
  total: number;
  waiting: number;
  running: number;
  success: number;
  fail: number;
  skip: number;
  concurrency: number;
  start_time: string;
  end_time: string;
}

/** Single case from GET /api/executions/{id}/cases */
export interface ExecutionCaseItem {
  id: number;
  uid: string;
  case_name: string;
  method_name: string;
  class_name: string;
  status: string;
  duration_ms: number;
  start_time: string;
  end_time: string;
}

// ── Backend Report Types ──

export interface ReportSummary {
  total: number;
  passed: number;
  failed: number;
  broken: number;
  skipped: number;
  xfailed: number;
  passRate: number;
  totalDuration: string;
  totalDurationMs: number;
  generatedAt: string;
  host: string;
}

export interface ReportItem {
  name: string;
  uid: string;
  methodName: string;
  className: string;
  module: string;
  fullName: string;
  status: string;
  description: string;
  duration: string;
  duration_ms: number;
  message: string;
  trace: string;
  logs: string;
  tags: string[];
  params: string;
  history: Array<{ timestamp: string; status: string; duration: string }>;
  testType?: string;
  steps?: string;
  screenshots?: string;
  start?: string;
}

export interface ReportClassInfo {
  name: string;
  items: ReportItem[];
  total: number;
  passed: number;
  failed: number;
  broken: number;
}

export interface ReportModuleInfo {
  module: string;
  classes: ReportClassInfo[];
  total: number;
  passed: number;
}

export interface ReportData {
  summary: ReportSummary;
  moduleGroups: ReportModuleInfo[];
  allTags: string[];
}

// ── WebSocket Message Types ──

export type WsMessage =
  | { type: 'test_result'; uid: string; status: string; name: string; className: string; methodName: string }
  | { type: 'suite_progress'; total: number; completed: number; passed: number; failed: number; broken: number; skipped: number; elapsed: string }
  | { type: 'run_complete'; summary: any }
  | { type: 'run_error'; message: string }
  | { type: 'heartbeat' };

// ── Report List Summary Type ──

export interface ReportListSummary {
  index: number;
  timestamp: string;
  total: number;
  passed: number;
  failed: number;
  passRate: number;
  totalDuration: string;
}

// ── Historical Report from history.json ──

export interface HistoryReportResult {
  fullName: string;
  status: string;
  duration_ms: number;
  duration: string;
}

export interface HistoryReport {
  timestamp: string;
  summary: ReportSummary;
  results: HistoryReportResult[];
}

// ── Defect Types ──

export interface DefectModuleInfo {
  id: number;
  project_id: number;
  name: string;
  parent_id: number;
  sort_order: number;
  children: DefectModuleInfo[];
}

export interface DefectInfo {
  id: number;
  title: string;
  description: string;
  steps: string;
  project_id: number;
  branch_id: number;
  branch_name: string;
  module_id: number;
  module_name: string;
  severity: string;
  priority: string;
  status: string;
  resolution: string;
  assignee_id: number;
  assignee_name: string;
  creator_id: number;
  creator_name: string;
  bug_type: string;
  bug_type_name: string;
  deadline: string;
  resolved_version: number;
  resolved_version_name: string;
  duplicate_defect_id: number;
  duplicate_defect_title: string;
  resolved_date: string;
  created_at: string;
  updated_at: string;
}

export interface DefectLogInfo {
  id: number;
  field: string;
  old_value: string;
  new_value: string;
  operator_id: number;
  operator_name: string;
  created_at: string;
}

export interface DefectAttachmentInfo {
  id: number;
  filename: string;
  file_size: number;
  mime_type: string;
  created_by: number;
  created_at: string;
}

export interface DefectDetailResponse {
  defect: DefectInfo;
  logs: DefectLogInfo[];
  attachments: DefectAttachmentInfo[];
  comments: DefectCommentInfo[];
}

export interface DefectCreateData {
  title: string;
  description: string;
  steps: string;
  project_id: number;
  branch_id: number;
  module_id: number;
  severity: string;
  priority: string;
  assignee_id: number;
  bug_type?: string;
  deadline?: string;
}

export interface DefectCommentInfo {
  id: number;
  defect_id: number;
  content: string;
  author_id: number;
  author_name: string;
  created_at: string;
  updated_at: string;
}
