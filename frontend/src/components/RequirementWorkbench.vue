<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useProject } from '../composables/useProject';
import { useBranch } from '../composables/useBranch';
import { useApi } from '../composables/useApi';
import BaseButton from './base/BaseButton.vue';
import BaseTag from './base/BaseTag.vue';
import BaseInput from './base/BaseInput.vue';

const emit = defineEmits<{ (e: 'showToast', msg: string): void }>();

const { activeProject, getActiveProject } = useProject();
const { activeBranch } = useBranch(activeProject.value?.id);
const { get, post, put } = useApi();
const route = useRoute();
const router = useRouter();

// ── 状态元数据 ──
const GAP_STATUS: Record<string, { label: string; tone: 'yellow' | 'green' | 'red' | 'gray' | 'blue' }> = {
  pending: { label: '待确定', tone: 'yellow' },
  confirmed: { label: '已确定', tone: 'green' },
  ignored: { label: '已忽略', tone: 'gray' },
  fixed: { label: '已修复', tone: 'blue' },
  not_applicable: { label: '不涉及', tone: 'gray' },
};
const STAGE_META = [
  { key: 'review', label: '需求评审' },
  { key: 'story', label: 'Story' },
  { key: 'test_point', label: '测试点' },
  { key: 'case', label: '测试用例' },
] as const;

const requirements = ref<any[]>([]);
const selectedReqId = ref<number | null>(null);
const loading = ref(false);
const workbenchData = ref<any>(null);
const wbLoading = ref(false);
const searchQuery = ref('');
const projectId = computed(() => activeProject.value?.id || 0);
const branchId = computed(() => activeBranch.value?.id || 0);

// ── 文档 ──
const docContent = ref('');
const docSaving = ref(false);
const extractingDoc = ref(false);

// ── 新建需求 ──
const showNewReqModal = ref(false);
const newReqTitle = ref('');
const newReqContent = ref('');
const newReqSourceType = ref<'text' | 'lark_link'>('text');
const newReqLarkLink = ref('');

function parseMeta(s: string): any {
  try { return JSON.parse(s || '{}'); } catch { return {}; }
}
// 需求有链接来源但 content 为空（未提取）→ 文档面板提示提取
const docNeedsExtract = computed(() => {
  const req = workbenchData.value?.requirement;
  if (!req) return false;
  if ((req.content || '').trim()) return false;
  return !!parseMeta(req.source_meta).link;
});

async function extractDoc() {
  if (!selectedReqId.value || extractingDoc.value) return;
  const meta = parseMeta(workbenchData.value?.requirement?.source_meta);
  if (!meta.link) return;
  extractingDoc.value = true;
  try {
    const res = await post<any>(`/requirements/${selectedReqId.value}/sources`, {
      type: 'lark_link', link: meta.link,
    });
    if (res.extracted) {
      await loadWorkbench(selectedReqId.value);
      emit('showToast', '文档已加载');
    } else {
      emit('showToast', res.extract_error || '提取失败，请检查飞书授权');
    }
  } catch (e: any) { emit('showToast', e.message || '提取失败'); }
  finally { extractingDoc.value = false; }
}

async function createRequirement() {
  if (!newReqTitle.value.trim()) return;
  const title = newReqTitle.value.trim();
  const sourceType = newReqSourceType.value;
  const link = newReqLarkLink.value.trim();
  try {
    const body: any = {
      project_id: projectId.value, branch_id: branchId.value, title,
      content: newReqContent.value, source_type: sourceType, source_meta: '{}',
    };
    if (sourceType === 'lark_link') {
      body.source_meta = JSON.stringify({ link, extracted: false });
    }
    const created = await post<any>('/requirements', body);
    showNewReqModal.value = false;
    newReqTitle.value = ''; newReqContent.value = ''; newReqLarkLink.value = '';
    await loadRequirements();
    selectReq(created.id);
    if (sourceType === 'lark_link' && link) {
      // 创建后立即提取，把飞书文档加载进左侧文档
      extractingDoc.value = true;
      try {
        const res = await post<any>(`/requirements/${created.id}/sources`, { type: 'lark_link', link });
        if (res.extracted) emit('showToast', '需求已创建，文档已加载');
        else emit('showToast', res.extract_error || '需求已创建，文档提取失败');
      } finally {
        extractingDoc.value = false;
        await loadWorkbench(created.id);
      }
    } else {
      emit('showToast', '需求创建成功');
    }
  } catch (e: any) { emit('showToast', e.message || '创建失败'); }
}

// ── 阶段 ──
const activeStage = ref<'review' | 'story' | 'test_point' | 'case'>('review');
const reviewRunning = ref(false);
const genStoryRunning = ref(false);

// ── 评审 / 问题卡片 ──
const analysisAsset = computed(() =>
  (workbenchData.value?.assets || []).find((a: any) => a.asset_type === 'analysis'),
);
const gapAssets = computed(() =>
  (workbenchData.value?.assets || []).filter((a: any) => a.asset_type === 'gap'),
);
const analysisElements = computed(() => {
  const c = analysisAsset.value?.content;
  if (!c) return null;
  try { return (typeof c === 'string' ? JSON.parse(c) : c)?.elements || null; } catch { return null; }
});
const analysisReason = computed(() => analysisAsset.value?.description || analysisAsset.value?.review_comment || '');

// 解锁：story 有产出 / 测试点有产出 / 用例有产出
const stageUnlocked = computed<Record<string, boolean>>(() => {
  const assets = workbenchData.value?.assets || [];
  return {
    review: true,
    story: assets.some((a: any) => a.asset_type === 'story'),
    test_point: assets.some((a: any) => a.asset_type === 'test_point'),
    case: assets.some((a: any) => a.asset_type === 'case'),
  };
});
const visibleStages = computed(() => STAGE_META.filter(s => stageUnlocked.value[s.key]));

// 评审进行中（analyze 或 re-review 任务 RUNNING）
const reviewActive = computed(() => {
  if (reviewRunning.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) =>
    ['analyze', 're_review'].includes(t.stage) && ['PENDING', 'RUNNING'].includes(t.status),
  );
});
const storyGenActive = computed(() => {
  if (genStoryRunning.value) return true;
  const tasks = workbenchData.value?.ai_tasks || [];
  return tasks.some((t: any) =>
    t.stage === 'stories' && ['PENDING', 'RUNNING'].includes(t.status),
  );
});

// 问题卡片内容解析
function gapContent(g: any): any {
  try { return typeof g.content === 'string' ? JSON.parse(g.content) : g.content; } catch { return {}; }
}
function gapThread(g: any): any[] { return gapContent(g).thread || []; }

// 评论输入状态：gapId -> 是否展开输入框
const commentOpen = ref<Record<number, boolean>>({});
const commentText = ref<Record<number, string>>({});

// ── 加载 ──
async function loadRequirements() {
  if (!projectId.value || !branchId.value) { requirements.value = []; return; }
  loading.value = true;
  try {
    const data = await get<any>(`/requirements?project_id=${projectId.value}&branch_id=${branchId.value}`);
    requirements.value = Array.isArray(data) ? data : (data.items || []);
  } catch (e: any) { emit('showToast', e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function loadWorkbench(reqId: number) {
  wbLoading.value = true;
  try {
    workbenchData.value = await get<any>(`/requirements/${reqId}/workbench`);
    docContent.value = workbenchData.value?.requirement?.content || '';
  } catch (e: any) { emit('showToast', e.message || '加载工作台失败'); }
  finally { wbLoading.value = false; }
}

function selectReq(reqId: number) {
  selectedReqId.value = reqId;
  activeStage.value = 'review';
  loadWorkbench(reqId);
  router.replace({ query: { req_id: reqId } });
}

// 轮询 workbench 直到指定 stage 任务结束
function pollUntilIdle(stage: string, doneMsg: string, runningRef?: any) {
  const timer = setInterval(async () => {
    if (!selectedReqId.value) { clearInterval(timer); return; }
    await loadWorkbench(selectedReqId.value);
    const tasks = workbenchData.value?.ai_tasks || [];
    const failed = tasks.find((t: any) => t.stage === stage && t.status === 'FAILED');
    if (failed) {
      clearInterval(timer);
      if (runningRef) runningRef.value = false;
      emit('showToast', failed.error || `${stage} 任务失败`);
      return;
    }
    const busy = tasks.some((t: any) => t.stage === stage && ['PENDING', 'RUNNING'].includes(t.status));
    if (!busy) {
      clearInterval(timer);
      if (runningRef) runningRef.value = false;
      emit('showToast', doneMsg);
    }
  }, 2000);
}

// ── 文档编辑 ──
async function saveDoc() {
  if (!selectedReqId.value) return;
  docSaving.value = true;
  try {
    await put(`/req/${selectedReqId.value}`, { content: docContent.value });
    await loadWorkbench(selectedReqId.value);
    emit('showToast', '文档已保存（不自动触发评审）');
  } catch (e: any) { emit('showToast', e.message || '保存失败'); }
  finally { docSaving.value = false; }
}

// ── 评审 ──
async function startReview() {
  if (!selectedReqId.value || reviewActive.value) return;
  reviewRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/analyze`, {});
    emit('showToast', 'AI 评审已启动');
    pollUntilIdle('analyze', '评审完成', reviewRunning);
  } catch (e: any) { reviewRunning.value = false; emit('showToast', e.message || '启动评审失败'); }
}

async function reReview() {
  if (!selectedReqId.value || reviewActive.value) return;
  reviewRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/analysis/re-review`, {});
    emit('showToast', '重新评审已启动');
    pollUntilIdle('re_review', '重新评审完成', reviewRunning);
  } catch (e: any) { reviewRunning.value = false; emit('showToast', e.message || '重新评审失败'); }
}

// ── 问题卡片操作 ──
async function gapComment(g: any) {
  const text = (commentText.value[g.id] || '').trim();
  if (!text) return;
  try {
    await post(`/req/${selectedReqId.value}/gaps/${g.id}/comment`, { comment: text });
    commentText.value[g.id] = '';
    commentOpen.value[g.id] = false;
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', 'AI 已回复');
  } catch (e: any) { emit('showToast', e.message || '评论失败'); }
}

async function gapIgnore(g: any) {
  try {
    await post(`/req/${selectedReqId.value}/gaps/${g.id}/ignore`);
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '已忽略');
  } catch (e: any) { emit('showToast', e.message || '操作失败'); }
}

async function gapConfirm(g: any) {
  try {
    await post(`/req/${selectedReqId.value}/gaps/${g.id}/confirm`);
    await loadWorkbench(selectedReqId.value!);
    emit('showToast', '已确定');
  } catch (e: any) { emit('showToast', e.message || '确定失败'); }
}

// ── 生成 Story（#25 只做解锁，详情 #26）──
async function generateStories() {
  if (!selectedReqId.value || storyGenActive.value) return;
  genStoryRunning.value = true;
  try {
    await post(`/req/${selectedReqId.value}/stories/generate`, {});
    emit('showToast', 'Story 生成已启动');
    pollUntilIdle('stories', 'Story 生成完成', genStoryRunning);
  } catch (e: any) { genStoryRunning.value = false; emit('showToast', e.message || '启动失败'); }
}

// ── 初始化 ──
watch(activeBranch, () => { loadRequirements(); selectedReqId.value = null; workbenchData.value = null; });

onMounted(async () => {
  if (!activeProject.value?.id) await getActiveProject();
  await loadRequirements();
  const qReqId = Number(route.query.req_id);
  if (qReqId) selectReq(qReqId);
});
onUnmounted(() => {});
</script>

<template>
  <div class="workbench flex h-full min-h-0">
    <!-- 左侧需求列表 -->
    <aside class="req-sidebar">
      <div class="sidebar-header">
        <h3 class="sidebar-title">需求列表</h3>
        <BaseButton size="sm" @click="showNewReqModal = true">新增需求</BaseButton>
      </div>
      <div class="px-3 pb-2">
        <BaseInput v-model="searchQuery" placeholder="搜索需求" class="w-full text-sm" />
      </div>
      <div class="req-list" v-if="!loading">
        <div v-for="r in requirements.filter(r => r.title.toLowerCase().includes(searchQuery.toLowerCase()))"
          :key="r.id" class="req-item" :class="{ active: r.id === selectedReqId }" @click="selectReq(r.id)">
          <div class="req-item-title">{{ r.title }}</div>
          <BaseTag size="sm" :tone="'gray'">{{ r.status }}</BaseTag>
        </div>
        <div v-if="requirements.length === 0" class="empty-state">暂无需求</div>
      </div>
    </aside>

    <!-- 右侧详情：左文档 + 右阶段 -->
    <div class="wb-main flex-1 min-w-0" v-if="selectedReqId">
      <div class="wb-layout">
        <!-- 左侧需求文档（可编辑） -->
        <div class="doc-panel">
          <div class="panel-head">
            <h4>需求文档</h4>
            <BaseButton v-if="!docNeedsExtract" size="sm" @click="saveDoc" :loading="docSaving">保存</BaseButton>
          </div>
          <div v-if="docNeedsExtract" class="doc-empty">
            <p>该需求来自飞书链接，尚未提取文档。</p>
            <p class="doc-link">{{ parseMeta(workbenchData.requirement.source_meta).link }}</p>
            <BaseButton variant="primary" size="sm" @click="extractDoc" :loading="extractingDoc">
              {{ extractingDoc ? '提取中...' : '提取文档' }}
            </BaseButton>
          </div>
          <textarea v-else v-model="docContent" class="doc-editor" placeholder="需求文档内容（可编辑；编辑不自动触发评审）"></textarea>
        </div>

        <!-- 右侧阶段 -->
        <div class="stage-panel">
          <nav class="stage-tabs">
            <button v-for="s in visibleStages" :key="s.key" class="stage-tab"
              :class="{ active: activeStage === s.key }" @click="activeStage = s.key">
              {{ s.label }}
            </button>
          </nav>

          <div class="stage-content" v-if="wbLoading">加载中…</div>

          <!-- ═══ 需求评审 ═══ -->
          <div v-else-if="activeStage === 'review'" class="stage-content">
            <!-- 无评审结果 -->
            <div v-if="!analysisAsset" class="empty-state">
              <p>尚未发起需求评审。</p>
              <BaseButton variant="primary" @click="startReview" :loading="reviewActive">
                {{ reviewActive ? '评审中...' : '开始评审' }}
              </BaseButton>
            </div>

            <!-- 评审中 -->
            <div v-else-if="reviewActive" class="empty-state">AI 评审进行中…</div>

            <!-- 评审完成 -->
            <div v-else class="review-result">
              <div class="review-analysis card">
                <h4>综合评审分析</h4>
                <div v-if="analysisElements" class="analysis-elems">
                  <span v-for="(v, k) in analysisElements" :key="k" class="elem-chip">
                    {{ k }}: {{ Array.isArray(v) ? v.length : v }}
                  </span>
                </div>
                <p class="reason">{{ analysisReason }}</p>
                <div class="review-actions">
                  <BaseButton size="sm" variant="secondary" @click="reReview" :loading="reviewActive">重新评审</BaseButton>
                  <BaseButton size="sm" variant="primary" @click="generateStories" :loading="storyGenActive">
                    {{ storyGenActive ? '生成中...' : '生成 Story' }}
                  </BaseButton>
                </div>
              </div>

              <!-- 问题卡片 -->
              <h4 class="gap-title">需要确定的问题（{{ gapAssets.length }}）</h4>
              <div v-for="g in gapAssets" :key="g.id" class="gap-card card">
                <div class="gap-head">
                  <BaseTag :tone="gapContent(g).severity === 'CRITICAL' ? 'red' : 'orange'" size="sm">{{ gapContent(g).severity }}</BaseTag>
                  <BaseTag :tone="GAP_STATUS[g.status]?.tone || 'gray'" size="sm">{{ GAP_STATUS[g.status]?.label || g.status }}</BaseTag>
                  <span class="gap-type">{{ g.title }}</span>
                </div>
                <p class="gap-desc">{{ g.description }}</p>
                <p class="gap-question" v-if="gapContent(g).question">{{ gapContent(g).question }}</p>
                <p class="gap-note" v-if="gapContent(g).resolution_note">AI 依据：{{ gapContent(g).resolution_note }}</p>

                <!-- 评论线程 -->
                <div v-if="gapThread(g).length" class="gap-thread">
                  <div v-for="(t, i) in gapThread(g)" :key="i" class="thread-line" :class="t.role">
                    <strong>{{ t.role === 'user' ? '我' : 'AI' }}</strong>: {{ t.text }}
                  </div>
                </div>

                <!-- 评论输入 -->
                <div v-if="commentOpen[g.id]" class="gap-comment-box">
                  <textarea v-model="commentText[g.id]" placeholder="输入评论..." class="comment-input"></textarea>
                  <div class="comment-actions">
                    <BaseButton size="sm" variant="ghost" @click="commentOpen[g.id] = false">取消</BaseButton>
                    <BaseButton size="sm" variant="primary" @click="gapComment(g)">提交</BaseButton>
                  </div>
                </div>

                <!-- 操作 -->
                <div class="gap-actions" v-if="g.status === 'pending' || g.status === 'fixed' || g.status === 'not_applicable' || g.status === 'ignored'">
                  <BaseButton size="sm" variant="ghost" @click="commentOpen[g.id] = !commentOpen[g.id]">
                    {{ commentOpen[g.id] ? '收起' : '评论' }}
                  </BaseButton>
                  <BaseButton size="sm" variant="ghost" @click="gapIgnore(g)" v-if="g.status !== 'ignored'">忽略</BaseButton>
                  <BaseButton size="sm" variant="primary" @click="gapConfirm(g)" v-if="g.status !== 'confirmed'">确定</BaseButton>
                </div>
              </div>
            </div>
          </div>

          <!-- ═══ Story（#26）═══ -->
          <div v-else-if="activeStage === 'story'" class="stage-content empty-state">
            <p>Story 阶段（#26 实现）—— 已生成 {{ (workbenchData.assets || []).filter((a: any) => a.asset_type === 'story').length }} 条 Story。</p>
          </div>

          <!-- ═══ 测试点（#27）═══ -->
          <div v-else-if="activeStage === 'test_point'" class="stage-content empty-state">
            <p>测试点阶段（#27 实现）。</p>
          </div>

          <!-- ═══ 测试用例（#28）═══ -->
          <div v-else class="stage-content empty-state">
            <p>测试用例阶段（#28 实现）。</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="wb-main flex-1 flex items-center justify-center" style="color: var(--text-tertiary);">
      请选择左侧需求
    </div>

    <!-- 新增需求弹窗 -->
    <div v-if="showNewReqModal" class="modal-mask" @click.self="showNewReqModal = false">
      <div class="modal-box">
        <h4>新增需求</h4>
        <label class="modal-label">标题</label>
        <BaseInput v-model="newReqTitle" placeholder="需求标题" />
        <label class="modal-label">来源</label>
        <div class="src-tabs">
          <button :class="{ active: newReqSourceType === 'text' }" @click="newReqSourceType = 'text'">文本</button>
          <button :class="{ active: newReqSourceType === 'lark_link' }" @click="newReqSourceType = 'lark_link'">飞书链接</button>
        </div>
        <label v-if="newReqSourceType === 'text'" class="modal-label">需求内容</label>
        <textarea v-if="newReqSourceType === 'text'" v-model="newReqContent" class="doc-editor modal-content" placeholder="需求文档内容"></textarea>
        <template v-else>
          <label class="modal-label">飞书文档链接</label>
          <BaseInput v-model="newReqLarkLink" placeholder="https://xxx.feishu.cn/wiki/...（保存后自动提取）" />
        </template>
        <div class="modal-actions">
          <BaseButton variant="ghost" @click="showNewReqModal = false">取消</BaseButton>
          <BaseButton variant="primary" @click="createRequirement">创建</BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workbench { overflow: hidden; }
.req-sidebar { width: 260px; min-width: 220px; border-right: 1px solid var(--border); display: flex; flex-direction: column; background: var(--card-bg); }
.sidebar-header { display: flex; justify-content: space-between; align-items: center; padding: 12px; }
.sidebar-title { margin: 0; font-size: 15px; }
.req-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.req-item { padding: 8px 10px; border-radius: var(--radius-md); cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.req-item:hover { background: var(--bg-soft); }
.req-item.active { background: var(--color-primary-soft); }
.req-item-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { display: flex; flex-direction: column; gap: 12px; align-items: center; justify-content: center; padding: 40px; color: var(--text-tertiary); }
.wb-layout { display: flex; gap: 12px; height: 100%; padding: 12px; }
.doc-panel { width: 40%; min-width: 320px; display: flex; flex-direction: column; gap: 8px; }
.stage-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
.doc-editor { flex: 1; resize: none; padding: 10px; border-radius: var(--radius-md); border: 1px solid var(--outline); background: var(--card-bg-2); color: var(--text-primary); font-size: 13px; line-height: 1.6; }
.stage-tabs { display: flex; gap: 6px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.stage-tab { padding: 6px 14px; border-radius: 999px; font-size: 13px; background: var(--bg-soft); color: var(--text-secondary); }
.stage-tab.active { background: var(--color-primary); color: #fff; }
.stage-content { flex: 1; overflow-y: auto; padding-top: 10px; }
.card { background: var(--card-bg-2); border: 1px solid var(--outline); border-radius: var(--radius-md); padding: 12px; }
.review-analysis { margin-bottom: 12px; }
.analysis-elems { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
.elem-chip { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--bg-soft); color: var(--text-secondary); }
.reason { font-size: 13px; color: var(--text-secondary); }
.review-actions { display: flex; gap: 8px; margin-top: 8px; }
.gap-title { margin: 12px 0 8px; }
.gap-card { margin-bottom: 10px; }
.gap-head { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.gap-type { font-size: 12px; color: var(--text-secondary); }
.gap-desc { font-size: 13px; margin: 0 0 4px; }
.gap-question { font-size: 12px; color: var(--color-warning); margin: 0 0 4px; }
.gap-note { font-size: 12px; color: var(--color-success); margin: 0 0 4px; }
.gap-thread { display: flex; flex-direction: column; gap: 4px; margin: 6px 0; }
.thread-line { font-size: 12px; padding: 4px 8px; border-radius: 8px; background: var(--bg-soft); }
.thread-line.user { border-left: 3px solid var(--color-primary); }
.thread-line.ai { border-left: 3px solid var(--color-success); }
.gap-comment-box { margin: 6px 0; }
.comment-input { width: 100%; height: 56px; resize: none; padding: 6px; border-radius: 8px; border: 1px solid var(--outline); background: var(--card-bg-2); color: var(--text-primary); font-size: 12px; }
.comment-actions { display: flex; gap: 6px; justify-content: flex-end; margin-top: 4px; }
.gap-actions { display: flex; gap: 6px; margin-top: 6px; }
.doc-empty { flex: 1; display: flex; flex-direction: column; gap: 10px; align-items: center; justify-content: center; color: var(--text-tertiary); }
.doc-link { font-size: 12px; word-break: break-all; max-width: 90%; }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-box { width: 480px; max-width: 90%; background: var(--card-bg); border-radius: var(--radius-md); padding: 18px; display: flex; flex-direction: column; gap: 8px; box-shadow: var(--shadow-hard); }
.modal-label { font-size: 12px; color: var(--text-secondary); margin-top: 6px; }
.modal-content { min-height: 120px; }
.src-tabs { display: flex; gap: 6px; }
.src-tabs button { padding: 4px 12px; border-radius: 999px; font-size: 12px; background: var(--bg-soft); color: var(--text-secondary); }
.src-tabs button.active { background: var(--color-primary); color: #fff; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
</style>
