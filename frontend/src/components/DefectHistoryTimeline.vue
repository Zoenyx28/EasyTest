<script setup lang="ts">
import { computed } from 'vue';
import type { DefectLogInfo, DefectCommentInfo } from '../types';

const props = defineProps<{
  logs: DefectLogInfo[];
  comments: DefectCommentInfo[];
  defectId: number;
  loading: boolean;
  commentContent: string;
}>();

const emit = defineEmits<{
  (e: 'update:commentContent', val: string): void;
  (e: 'addComment'): void;
}>();

const statusLabels: Record<string, string> = {
  unconfirmed: '未确认',
  confirmed: '已确认',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
};

const fieldLabels: Record<string, string> = {
  status: '状态',
  assignee_id: '指派人',
  resolution: '解决方案',
  severity: '严重程度',
  priority: '优先级',
  module_id: '模块',
  title: '标题',
  description: '描述',
  steps: '复现步骤',
  bug_type: 'Bug类型',
  deadline: '截止日期',
};

function formatTime(iso: string): string {
  if (!iso) return '--';
  try {
    const date = new Date(iso);
    return date.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function getOperationName(log: DefectLogInfo): string {
  if (log.field === 'status') {
    const oldLabel = statusLabels[log.old_value] || log.old_value;
    const newLabel = statusLabels[log.new_value] || log.new_value;
    if (!log.old_value) return `创建了缺陷`;
    if (oldLabel === '未确认' && newLabel === '已确认') return `确认了缺陷`;
    if (newLabel === '处理中') return `开始处理缺陷`;
    if (newLabel === '已解决') return `解决了缺陷`;
    if (newLabel === '已关闭') return `关闭了缺陷`;
    return `将状态从"${oldLabel}"改为"${newLabel}"`;
  }
  const fieldLabel = fieldLabels[log.field] || log.field;
  if (log.field === 'assignee_id') return `修改了${fieldLabel}`;
  return `修改了${fieldLabel}`;
}

function getOperationIcon(log: DefectLogInfo): string {
  if (log.field === 'status') {
    const newLabel = statusLabels[log.new_value] || '';
    if (!log.old_value) return 'create';
    if (newLabel === '已确认') return 'confirm';
    if (newLabel === '处理中') return 'assign';
    if (newLabel === '已解决') return 'resolve';
    if (newLabel === '已关闭') return 'close';
    return 'edit';
  }
  return 'edit';
}

const timelineItems = computed(() => {
  const items: Array<
    { type: 'log'; data: DefectLogInfo } | { type: 'comment'; data: DefectCommentInfo }
  > = [
    ...props.logs.map(l => ({ type: 'log' as const, data: l })),
    ...props.comments.map(c => ({ type: 'comment' as const, data: c })),
  ];
  items.sort((a, b) =>
    new Date(a.data.created_at).getTime() - new Date(b.data.created_at).getTime()
  );
  return items;
});

const operationColors: Record<string, { bg: string; icon: string }> = {
  create: { bg: '#d4edda', icon: '#155724' },
  confirm: { bg: '#d8e2ff', icon: '#0059bb' },
  assign: { bg: '#ffd6a5', icon: '#7a4400' },
  resolve: { bg: '#d4edda', icon: '#155724' },
  close: { bg: '#e0e9f2', icon: '#414754' },
  edit: { bg: '#fff6cc', icon: '#655500' },
};
</script>

<template>
  <div class="history-timeline">
    <!-- Add Comment -->
    <div class="comment-add-section">
      <textarea
        :value="commentContent"
        class="form-textarea"
        placeholder="添加评论..."
        rows="3"
        @input="emit('update:commentContent', ($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <div class="comment-actions">
        <button
          class="btn btn-save"
          :disabled="loading || !commentContent.trim()"
          @click="emit('addComment')"
        >
          {{ loading ? '发送中...' : '发送' }}
        </button>
      </div>
    </div>

    <!-- Timeline -->
    <div class="timeline-list">
      <div v-if="timelineItems.length === 0" class="empty-state">
        <p>暂无活动记录</p>
      </div>

      <div
        v-for="item in timelineItems"
        :key="item.type + '-' + item.data.id"
        class="timeline-item"
      >
        <!-- Log entry -->
        <template v-if="item.type === 'log'">
          <div class="timeline-dot" :style="{
            backgroundColor: (operationColors[getOperationIcon(item.data as DefectLogInfo)] || operationColors.edit).bg,
            color: (operationColors[getOperationIcon(item.data as DefectLogInfo)] || operationColors.edit).icon,
          }">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <template v-if="getOperationIcon(item.data as DefectLogInfo) === 'create'">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </template>
              <template v-else-if="getOperationIcon(item.data as DefectLogInfo) === 'confirm'">
                <polyline points="20 6 9 17 4 12" />
              </template>
              <template v-else-if="getOperationIcon(item.data as DefectLogInfo) === 'assign'">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="8.5" cy="7" r="4" />
                <polyline points="17 11 19 13 23 9" />
              </template>
              <template v-else-if="getOperationIcon(item.data as DefectLogInfo) === 'resolve'">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </template>
              <template v-else-if="getOperationIcon(item.data as DefectLogInfo) === 'close'">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </template>
              <template v-else>
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </template>
            </svg>
          </div>
          <div class="timeline-content">
            <div class="timeline-header">
              <span class="timeline-operator">{{ item.data.operator_name || '系统' }}</span>
              <span class="timeline-action">{{ getOperationName(item.data as DefectLogInfo) }}</span>
              <span class="timeline-time">{{ formatTime(item.data.created_at) }}</span>
            </div>
            <div v-if="(item.data as DefectLogInfo).field !== 'status' || (item.data as DefectLogInfo).old_value" class="timeline-detail">
              <span v-if="(item.data as DefectLogInfo).old_value" class="detail-old">{{ (item.data as DefectLogInfo).old_value }}</span>
              <svg v-if="(item.data as DefectLogInfo).old_value" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="color: #717786; flex-shrink: 0;">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
              <span class="detail-new">{{ (item.data as DefectLogInfo).new_value }}</span>
            </div>
          </div>
        </template>

        <!-- Comment entry -->
        <template v-else>
          <div class="timeline-dot comment-dot">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div class="timeline-content">
            <div class="timeline-header">
              <span class="timeline-operator">{{ item.data.author_name || '未知用户' }}</span>
              <span class="timeline-action">发表了评论</span>
              <span class="timeline-time">{{ formatTime(item.data.created_at) }}</span>
            </div>
            <div class="timeline-comment-body">{{ item.data.content }}</div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-timeline {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.comment-add-section {
  background: #f6faff;
  padding: 16px;
  border-radius: 12px;
}

.form-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  background-color: #ffffff;
  color: #141d23;
  border: 1px solid #c1c6d7;
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
  resize: vertical;
  min-height: 80px;
  line-height: 20px;
  margin-bottom: 12px;
}

.form-textarea:focus {
  border-color: #0059bb;
  box-shadow: 0 0 0 3px rgba(0, 89, 187, 0.1);
}

.comment-actions {
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  border: none;
  line-height: 20px;
}

.btn-save {
  background-color: #0059bb;
  color: #ffffff;
}

.btn-save:hover:not(:disabled) {
  background-color: #004493;
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.timeline-list {
  display: flex;
  flex-direction: column;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #717786;
  font-size: 14px;
}

.timeline-item {
  display: flex;
  gap: 14px;
  padding: 0 0 20px 0;
  position: relative;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.comment-dot {
  background-color: #d8e2ff;
  color: #0059bb;
}

.timeline-content {
  flex: 1;
  min-width: 0;
  padding-top: 6px;
}

.timeline-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.timeline-operator {
  font-size: 13px;
  font-weight: 700;
  color: #141d23;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.timeline-action {
  font-size: 13px;
  color: #414754;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.timeline-time {
  font-size: 12px;
  color: #717786;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
}

.timeline-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.detail-old {
  padding: 2px 8px;
  background: #e0e9f2;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #414754;
}

.detail-new {
  padding: 2px 8px;
  background: #d4edda;
  color: #155724;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.timeline-comment-body {
  margin-top: 6px;
  font-size: 14px;
  line-height: 22px;
  color: #141d23;
  font-family: 'Hanken Grotesk', system-ui, -apple-system, sans-serif;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
