<script setup lang="ts">
import { ref, computed } from 'vue';
import type { DefectLogInfo, DefectCommentInfo } from '../types';

const props = defineProps<{
  logs: DefectLogInfo[];
  comments: DefectCommentInfo[];
  defectId: number;
  /** 缺陷当前指派人名称（解决操作未改指派时，用于"交给xxx确认"） */
  assigneeName?: string;
}>();

const expandedGroups = ref<Set<number>>(new Set());

function toggleGroup(idx: number) {
  const s = new Set(expandedGroups.value);
  if (s.has(idx)) s.delete(idx); else s.add(idx);
  expandedGroups.value = s;
}

// ── Labels ──

const fieldLabels: Record<string, string> = {
  status: '状态',
  assignee_id: '指派给',
  resolution: '解决方案',
  severity: '严重程度',
  priority: '优先级',
  module_id: '模块',
  title: '标题',
  description: '描述',
  steps: '复现步骤',
  bug_type: 'Bug类型',
  deadline: '截止日期',
  resolved_version: '解决版本',
  duplicate_defect_id: '关联缺陷',
};

const statusLabels: Record<string, string> = {
  unconfirmed: '未确认',
  confirmed: '已确认',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

const resolutionLabels: Record<string, string> = {
  fixed: '已解决',
  duplicate: '重复Bug',
  not_issue: '不是问题',
  cannot_reproduce: '无法重现',
  design: '设计如此',
  external: '外部原因',
  deferred: '延期处理',
};

const bugTypeLabels: Record<string, string> = {
  code_error: '代码错误',
  design_defect: '设计缺陷',
  performance: '性能问题',
  security: '安全问题',
  experience: '体验问题',
  compatibility: '兼容性',
  other: '其他',
};

const severityLabels: Record<string, string> = {
  P0: 'P0-致命',
  P1: 'P1-严重',
  P2: 'P2-一般',
  P3: 'P3-轻微',
};

const priorityLabels: Record<string, string> = {
  P0: 'P0-紧急',
  P1: 'P1-高',
  P2: 'P2-中',
  P3: 'P3-低',
};

// ── Value formatting ──

function fmtVal(field: string, val: string): string {
  if (!val) return '（空）';
  if (field === 'status') return statusLabels[val] || val;
  if (field === 'resolution') return resolutionLabels[val] || val;
  if (field === 'bug_type') return bugTypeLabels[val] || val;
  if (field === 'severity') return severityLabels[val] || val;
  if (field === 'priority') return priorityLabels[val] || val;
  return val;
}

/** 格式化单条日志某一侧的取值（指派给显示用户名称） */
function fmtLogVal(log: DefectLogInfo, which: 'old' | 'new'): string {
  const raw = which === 'old' ? log.old_value : log.new_value;
  if (log.field === 'assignee_id') {
    const name = which === 'old' ? log.old_value_name : log.new_value_name;
    if (name) return name;
    return raw && raw !== '0' ? raw : '（空）';
  }
  return fmtVal(log.field, raw);
}

function formatDatetime(iso: string): string {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    const y = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    const da = String(d.getDate()).padStart(2, '0');
    const h = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    const s = String(d.getSeconds()).padStart(2, '0');
    return `${y}-${mo}-${da} ${h}:${mi}:${s}`;
  } catch {
    return iso;
  }
}

// ── Group logs into operations ──
// Logs from the same operator within 1 second are treated as one operation.

interface Operation {
  operatorId: number;
  operatorName: string;
  time: string;       // ISO timestamp
  logs: DefectLogInfo[];
  comments: DefectCommentInfo[];
  summary: string;    // 自然语言活动描述，如 "张三创建了bug，指派给李四"
}

/** 根据一组日志生成主动作与自然语言描述 */
function buildSummary(operatorName: string, groupLogs: DefectLogInfo[]): string {
  const statusLog = groupLogs.find(l => l.field === 'status');
  const assigneeLog = groupLogs.find(l => l.field === 'assignee_id');
  const resolutionLog = groupLogs.find(l => l.field === 'resolution');

  if (statusLog) {
    const oldS = statusLog.old_value;
    const newS = statusLog.new_value;
    const assigneeName = assigneeLog ? (assigneeLog.new_value_name || '') : '';

    if (!oldS) {
      // 创建
      return assigneeName
        ? `${operatorName}创建了bug，指派给${assigneeName}`
        : `${operatorName}创建了bug`;
    }
    if ((oldS === 'resolved' || oldS === 'closed') && newS === 'unconfirmed') {
      // 激活 bug（激活后回到未确认，重新走确认流程）
      return assigneeName
        ? `${operatorName}激活了bug，指派给${assigneeName}`
        : `${operatorName}激活了bug`;
    }
    if (oldS === 'unconfirmed' && newS === 'confirmed') {
      // 确认 bug
      return assigneeName
        ? `${operatorName}确认了bug，指派给${assigneeName}`
        : `${operatorName}确认了bug`;
    }
    if (newS === 'in_progress') {
      // 指派（confirmed -> in_progress）
      return assigneeName
        ? `${operatorName}将bug指派给${assigneeName}`
        : `${operatorName}指派了bug`;
    }
    if (newS === 'resolved') {
      // 解决 bug
      let s = `${operatorName}解决了bug`;
      const resLabel = resolutionLog
        ? (resolutionLabels[resolutionLog.new_value] || resolutionLog.new_value)
        : '';
      if (resLabel) s += `，解决方案为${resLabel}`;
      const confirmName = assigneeName || props.assigneeName || '';
      if (confirmName) s += `，交给${confirmName}确认`;
      return s;
    }
    if (newS === 'closed') {
      return `${operatorName}关闭了bug`;
    }
  }

  // 无状态变更
  if (assigneeLog && groupLogs.length === 1) {
    // 仅修改指派人
    return assigneeLog.new_value_name
      ? `${operatorName}将bug指派给${assigneeLog.new_value_name}`
      : `${operatorName}取消了bug的指派`;
  }

  // 其余字段编辑
  return `${operatorName}编辑了bug`;
}

const operations = computed<Operation[]>(() => {
  const sorted = [...props.logs].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  const groups: DefectLogInfo[][] = [];
  for (const log of sorted) {
    const last = groups[groups.length - 1];
    if (last && last.length > 0) {
      const lastTime = new Date(last[0].created_at).getTime();
      const thisTime = new Date(log.created_at).getTime();
      if (
        last[0].operator_id === log.operator_id &&
        Math.abs(thisTime - lastTime) <= 1000
      ) {
        last.push(log);
        continue;
      }
    }
    groups.push([log]);
  }

  // Sort comments and assign to nearest-in-time operation group
  const sortedComments = [...props.comments].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  return groups.map((groupLogs, gi) => {
    const mainLog = groupLogs[0];
    const opTime = new Date(mainLog.created_at).getTime();
    const nextOpTime = gi + 1 < groups.length
      ? new Date(groups[gi + 1][0].created_at).getTime()
      : Infinity;

    // Comments belong to this operation if they fall between its time and the next operation's time
    const opComments = sortedComments.filter(c => {
      const ct = new Date(c.created_at).getTime();
      return ct >= opTime && ct < nextOpTime;
    });

    // Determine natural-language summary from the group's logs
    const summary = buildSummary(mainLog.operator_name || '系统', groupLogs);

    return {
      operatorId: mainLog.operator_id,
      operatorName: mainLog.operator_name || '系统',
      time: mainLog.created_at,
      logs: groupLogs,
      comments: opComments,
      summary,
    };
  });
});
</script>

<template>
  <div class="history-timeline">
    <div v-if="operations.length === 0" class="empty-state">
      <p>暂无活动记录</p>
    </div>

    <div
      v-for="(op, idx) in operations"
      :key="'op' + idx"
      class="timeline-op"
    >
      <!-- Collapsed row -->
      <div class="op-header" @click="toggleGroup(idx)">
        <div class="op-summary">
          <span class="op-time">{{ formatDatetime(op.time) }}</span>
          <span class="op-operator">{{ op.operatorName }}</span>
          <span class="op-action">{{ op.summary }}</span>
          <span v-if="op.logs.length > 1 && !expandedGroups.has(idx)" class="op-extra-hint">
            {{ op.logs.length - 1 }} 项变更
          </span>
        </div>
        <button class="op-toggle-btn" :class="{ expanded: expandedGroups.has(idx) }">
          <svg v-if="!expandedGroups.has(idx)" width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      <!-- Expanded detail -->
      <div v-if="expandedGroups.has(idx)" class="op-detail">
        <div
          v-for="log in op.logs"
          :key="'l' + log.id"
          class="op-change"
        >
          <span class="change-label">修改了【{{ fieldLabels[log.field] || log.field }}】</span>
          <span class="change-old">，旧值为 {{ fmtLogVal(log, 'old') }}</span>
          <span class="change-new">，新值为 {{ fmtLogVal(log, 'new') }}</span>
        </div>

        <!-- Comments -->
        <div v-if="op.comments.length > 0" class="op-comments">
          <div
            v-for="c in op.comments"
            :key="'c' + c.id"
            class="op-comment"
          >
            <div class="comment-header">
              <span class="comment-author">{{ c.author_name || '未知用户' }}</span>
              <span class="comment-time">{{ formatDatetime(c.created_at) }}</span>
            </div>
            <div class="comment-body">{{ c.content }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-timeline {
  display: flex;
  flex-direction: column;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.timeline-op {
  border-bottom: 1px solid var(--border);
}

.timeline-op:last-child {
  border-bottom: none;
}

.op-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  cursor: pointer;
  transition: background 0.1s;
  min-height: 40px;
}

.op-header:hover {
  background: var(--bg-muted);
  margin: 0 -12px;
  padding: 10px 12px;
  border-radius: 6px;
}

.op-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
  line-height: 22px;
}

.op-time {
  color: var(--text-muted);
  font-size: 12px;
  font-family: var(--font-mono);
}

.op-operator {
  color: var(--text-primary);
  font-weight: 600;
}

.op-action {
  color: var(--color-primary);
  font-weight: 600;
}

.op-extra-hint {
  color: var(--text-muted);
  font-size: 11px;
}

.op-toggle-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: var(--bg-muted);
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}

.op-toggle-btn:hover {
  background: var(--border-hover);
  color: var(--text-primary);
}

.op-toggle-btn.expanded {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.op-detail {
  padding: 6px 0 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.op-change {
  padding: 6px 12px;
  background: var(--bg-muted);
  border-radius: 6px;
  font-size: 13px;
  line-height: 22px;
  border-left: 3px solid var(--color-primary);
}

.change-label {
  color: var(--color-primary);
  font-weight: 600;
}

.change-old {
  color: var(--text-muted);
}

.change-new {
  color: var(--text-primary);
}

/* Comments */
.op-comments {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.op-comment {
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.comment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.comment-author {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.comment-time {
  font-size: 11px;
  color: var(--text-muted);
}

.comment-body {
  font-size: 14px;
  line-height: 22px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
