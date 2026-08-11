<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useApi } from '../composables/useApi';
import { useBranch } from '../composables/useBranch';
import BaseDialog from './base/BaseDialog.vue';
import BaseButton from './base/BaseButton.vue';
import BaseInput from './base/BaseInput.vue';
import BaseTag from './base/BaseTag.vue';
import type {
  RequirementInfo,
  RequirementReviewInfo,
  RequirementSourceInfo,
  RequirementStoryInfo,
  GeneratedCaseInfo,
  CaseBindingInfo,
  AutomationCasePage,
} from '../types';

const props = defineProps<{
  open: boolean;
  reqId: number | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved'): void;
  (e: 'showToast', msg: string): void;
}>();

const { get, post, put, del } = useApi();
const { branches, loadBranches } = useBranch();

// ── 元信息 ──
const STATUS_META: Record<string, { label: string; tone: 'yellow' | 'blue' | 'purple' | 'green' }> = {
  pending_review: { label: '待评审', tone: 'yellow' },
  review_passed: { label: '评审通过', tone: 'blue' },
  story_confirmed: { label: 'Story 已确认', tone: 'purple' },
  cases_generated: { label: '用例已生成', tone: 'green' },
  done: { label: '已完成', tone: 'green' },
};
const PRIORITIES = ['P0', 'P1', 'P2', 'P3'];

function statusLabel(s: string): string {
  return STATUS_META[s]?.label ?? s;
}
function statusTone(s: string): 'yellow' | 'blue' | 'purple' | 'green' | 'gray' {
  return STATUS_META[s]?.tone ?? 'gray';
}
function priorityTone(p: string): 'red' | 'orange' | 'green' {
  if (p === 'P0') return 'red';
  if (p === 'P1') return 'orange';
  return 'green';
}
function isLowScore(score: number | undefined | null): boolean {
  return typeof score === 'number' && score > 0 && score < 60;
}

// ── 数据 ──
const requirement = ref<RequirementInfo | null>(null);
const reviews = ref<RequirementReviewInfo[]>([]);
const stories = ref<RequirementStoryInfo[]>([]);
const cases = ref<GeneratedCaseInfo[]>([]);
const sources = ref<RequirementSourceInfo[]>([]);
const loading = ref(false);

// 飞书授权状态（来源区引导；授权入口在 头像菜单 → 系统设置 → 飞书授权）
const larkAuthRequired = ref(false);

async function loadLarkStatus() {
  try {
    const st = await get<{ auth_required: boolean }>('/settings/lark/status');
    larkAuthRequired.value = !!st.auth_required;
  } catch { /* 忽略，不阻塞来源展示 */ }
}

const latestReview = computed(() => reviews.value[0] ?? null);
const storyScore = computed(() => stories.value[0]?.score ?? 0);
const storyScoreReason = computed(() => stories.value[0]?.score_reason ?? '');
const caseScore = computed(() => cases.value[0]?.score ?? 0);
const caseScoreReason = computed(() => cases.value[0]?.score_reason ?? '');

// 编辑表单（打开时由详情初始化）
const editForm = ref({ title: '', summary: '', priority: 'P2' });
const saving = ref(false);
const metaLoading = ref(false);

// 三步当前步骤（0=评审 1=Story 2=用例），默认由 status 推导
const curStep = ref(0);

function stepFromStatus(s: string): number {
  if (s === 'story_confirmed' || s === 'cases_generated' || s === 'done') return 2;
  if (s === 'review_passed') return 1;
  return 0;
}

// ── 加载 ──
async function loadAll() {
  if (!props.reqId) return;
  loading.value = true;
  try {
    const [req, revs, sts, cs, srcs] = await Promise.all([
      get<RequirementInfo>(`/requirements/${props.reqId}`),
      get<RequirementReviewInfo[]>(`/requirements/${props.reqId}/reviews`),
      get<RequirementStoryInfo[]>(`/requirements/${props.reqId}/stories`),
      get<GeneratedCaseInfo[]>(`/requirements/${props.reqId}/cases`),
      get<RequirementSourceInfo[]>(`/requirements/${props.reqId}/sources`),
    ]);
    requirement.value = req;
    reviews.value = revs;
    stories.value = sts;
    cases.value = cs;
    sources.value = srcs;
    editForm.value = { title: req.title, summary: req.summary || '', priority: req.priority || 'P2' };
    curStep.value = stepFromStatus(req.status);
    if (req.project_id) loadBranches(req.project_id);
    loadLarkStatus();
  } catch (e) {
    emit('showToast', (e as Error).message || '详情加载失败');
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.open, props.reqId] as const,
  ([open, id]) => {
    if (open && id) loadAll();
  },
  { immediate: true },
);

async function refreshRequirement() {
  if (!props.reqId) return;
  try {
    const req = await get<RequirementInfo>(`/requirements/${props.reqId}`);
    requirement.value = req;
    editForm.value = { title: req.title, summary: req.summary || '', priority: req.priority || 'P2' };
    curStep.value = stepFromStatus(req.status);
    emit('saved');
  } catch (e) {
    emit('showToast', (e as Error).message || '刷新失败');
  }
}

function onClose() {
  emit('close');
}

// ── ① 需求编辑 ──
async function saveRequirement() {
  if (!props.reqId) return;
  saving.value = true;
  try {
    await put(`/requirements/${props.reqId}`, {
      title: editForm.value.title.trim(),
      summary: editForm.value.summary,
      priority: editForm.value.priority,
    });
    emit('showToast', '需求已保存');
    await refreshRequirement();
  } catch (e) {
    emit('showToast', (e as Error).message || '保存失败');
  } finally {
    saving.value = false;
  }
}

async function generateMeta() {
  if (!props.reqId) return;
  metaLoading.value = true;
  try {
    await post(`/requirements/${props.reqId}/meta/generate`);
    emit('showToast', 'AI 已提炼需求元信息');
    await refreshRequirement();
  } catch (e) {
    emit('showToast', (e as Error).message || '元信息生成失败');
  } finally {
    metaLoading.value = false;
  }
}

// ── ② 评审（Step1）──
const reviewComment = ref('');
const reviewing = ref(false);

async function doReview() {
  if (!props.reqId) return;
  reviewing.value = true;
  try {
    await post(`/requirements/${props.reqId}/review`, { review_comment: reviewComment.value.trim() });
    emit('showToast', reviewComment.value.trim() ? '重新评审完成' : '评审完成');
    reviewComment.value = '';
    const revs = await get<RequirementReviewInfo[]>(`/requirements/${props.reqId}/reviews`);
    reviews.value = revs;
    await refreshRequirement();
  } catch (e) {
    emit('showToast', (e as Error).message || '评审失败');
  } finally {
    reviewing.value = false;
  }
}

function confirmReview() {
  if (!latestReview.value) {
    emit('showToast', '请先完成 AI 评审');
    return;
  }
  if (latestReview.value.score < 60) {
    emit('showToast', '评分低于 60，建议重新评审后再确认');
    return;
  }
  curStep.value = 1;
  emit('showToast', '评审已确认，进入 Story 拆解');
}

// ── ③ Story（Step2）──
const storiesLoading = ref(false);

async function doStories() {
  if (!props.reqId) return;
  storiesLoading.value = true;
  try {
    await post(`/requirements/${props.reqId}/stories/generate`);
    emit('showToast', 'Story 拆解完成');
    stories.value = await get<RequirementStoryInfo[]>(`/requirements/${props.reqId}/stories`);
    await refreshRequirement();
  } catch (e) {
    emit('showToast', (e as Error).message || 'Story 拆解失败');
  } finally {
    storiesLoading.value = false;
  }
}

function confirmStories() {
  if (!stories.value.length) {
    emit('showToast', '请先生成 Story');
    return;
  }
  if (isLowScore(storyScore.value)) {
    emit('showToast', 'Story 评分低于 60，建议重新拆解后再确认');
    return;
  }
  curStep.value = 2;
  emit('showToast', 'Story 已确认，进入用例生成');
}

// ── ④ 用例（Step3）──
const casesLoading = ref(false);
const regenCaseId = ref<number | null>(null);

async function doCases() {
  if (!props.reqId) return;
  casesLoading.value = true;
  try {
    await post(`/requirements/${props.reqId}/cases/generate`);
    emit('showToast', '用例生成完成');
    cases.value = await get<GeneratedCaseInfo[]>(`/requirements/${props.reqId}/cases`);
    await refreshRequirement();
  } catch (e) {
    emit('showToast', (e as Error).message || '用例生成失败');
  } finally {
    casesLoading.value = false;
  }
}

async function regenerateCase(c: GeneratedCaseInfo) {
  if (!props.reqId) return;
  regenCaseId.value = c.id;
  try {
    await post(`/requirements/${props.reqId}/cases/${c.id}/regenerate`);
    emit('showToast', '用例已重新生成');
    cases.value = await get<GeneratedCaseInfo[]>(`/requirements/${props.reqId}/cases`);
  } catch (e) {
    emit('showToast', (e as Error).message || '重新生成失败');
  } finally {
    regenCaseId.value = null;
  }
}

async function completeReq() {
  if (!props.reqId) return;
  try {
    await post(`/requirements/${props.reqId}/complete`);
    emit('showToast', '需求已标记完成');
    await refreshRequirement();
  } catch (e) {
    emit('showToast', (e as Error).message || '操作失败');
  }
}

// ── ⑤ 绑定自动化用例 ──
const bindCase = ref<GeneratedCaseInfo | null>(null);
const bindings = ref<CaseBindingInfo[]>([]);
const candidates = ref<AutomationCasePage['items']>([]);
const candidateTotal = ref(0);
const bindSearch = ref('');
const bindBranchId = ref(0);
const selectedUids = ref<Set<string>>(new Set());
const bindLoading = ref(false);
const bindingOp = ref(false);

const boundUidSet = computed(() => new Set(bindings.value.map((b) => b.uid)));

async function openBind(c: GeneratedCaseInfo) {
  bindCase.value = c;
  bindings.value = [];
  selectedUids.value = new Set();
  bindSearch.value = '';
  bindBranchId.value = requirement.value?.branch_id || 0;
  await loadBindings(c.id);
  await loadCandidates();
}

async function loadBindings(caseId: number) {
  try {
    bindings.value = await get<CaseBindingInfo[]>(
      `/requirements/${props.reqId}/cases/${caseId}/bindings`,
    );
  } catch {
    bindings.value = [];
  }
}

async function loadCandidates() {
  const pid = requirement.value?.project_id;
  if (!pid) return;
  bindLoading.value = true;
  try {
    const page = await get<AutomationCasePage>(
      `/projects/${pid}/cases?page=1&size=200&search=${encodeURIComponent(bindSearch.value)}`,
    );
    candidates.value = page.items || [];
    candidateTotal.value = page.total || 0;
  } catch {
    candidates.value = [];
  } finally {
    bindLoading.value = false;
  }
}

function toggleUid(uid: string) {
  const next = new Set(selectedUids.value);
  if (next.has(uid)) next.delete(uid);
  else next.add(uid);
  selectedUids.value = next;
}

async function doBind() {
  if (!props.reqId || !bindCase.value) return;
  const pid = requirement.value?.project_id;
  if (!pid || !bindBranchId.value) {
    emit('showToast', '请选择绑定分支');
    return;
  }
  if (!selectedUids.value.size) {
    emit('showToast', '请选择自动化用例');
    return;
  }
  bindingOp.value = true;
  let okCount = 0;
  try {
    for (const uid of selectedUids.value) {
      await post(`/requirements/${props.reqId}/cases/${bindCase.value.id}/bindings`, {
        uid,
        project_id: pid,
        branch_id: bindBranchId.value,
      });
      okCount += 1;
    }
    emit('showToast', `已绑定 ${okCount} 个自动化用例`);
    await loadBindings(bindCase.value.id);
    await loadAll();
  } catch (e) {
    emit('showToast', (e as Error).message || '绑定失败');
  } finally {
    bindingOp.value = false;
  }
}

async function unbind(b: CaseBindingInfo) {
  try {
    await del(`/cases/${bindCase.value?.id}/bindings/${b.id}`);
    emit('showToast', '已取消绑定');
    if (bindCase.value) await loadBindings(bindCase.value.id);
    await loadAll();
  } catch (e) {
    emit('showToast', (e as Error).message || '取消绑定失败');
  }
}

// ── ⑥ 来源（沿用现有逻辑）──
const sourcesLoading = ref(false);
const extractingId = ref<number | null>(null);

async function loadSources() {
  if (!props.reqId) return;
  sourcesLoading.value = true;
  try {
    sources.value = await get<RequirementSourceInfo[]>(`/requirements/${props.reqId}/sources`);
  } catch {
    sources.value = [];
  } finally {
    sourcesLoading.value = false;
  }
}

async function reExtract(s: RequirementSourceInfo) {
  if (!props.reqId || extractingId.value) return;
  extractingId.value = s.id;
  try {
    const res = await post<{ extracted: boolean; extract_error: string }>(
      `/requirements/${props.reqId}/sources/${s.id}/extract`,
      {},
    );
    s.extracted = res.extracted;
    s.extract_error = res.extract_error || '';
    emit('showToast', res.extracted ? '正文提取成功' : '正文提取失败，请检查授权');
  } catch (e) {
    emit('showToast', (e as Error).message || '重新提取失败');
  } finally {
    extractingId.value = null;
  }
}

async function removeSource(s: RequirementSourceInfo) {
  if (!props.reqId) return;
  try {
    await del(`/requirements/sources/${s.id}`);
    sources.value = sources.value.filter((x) => x.id !== s.id);
    emit('showToast', '来源已删除');
  } catch (e) {
    emit('showToast', (e as Error).message || '来源删除失败');
  }
}

function sourceName(s: RequirementSourceInfo): string {
  return s.type === 'file' ? s.filename : s.link;
}

function formatSize(bytes: number): string {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(iso: string): string {
  if (!iso) return '--';
  return iso.substring(0, 16).replace('T', ' ');
}

// ── 步骤定义 ──
const steps = computed(() => [
  {
    key: 0,
    label: '需求评审',
    desc: 'AI 评审打分',
    done: ['review_passed', 'story_confirmed', 'cases_generated', 'done'].includes(
      requirement.value?.status || '',
    ),
  },
  {
    key: 1,
    label: 'Story 拆解',
    desc: '用户故事确认',
    done: ['story_confirmed', 'cases_generated', 'done'].includes(requirement.value?.status || ''),
  },
  {
    key: 2,
    label: '用例生成',
    desc: '测试用例 + 绑定',
    done: ['cases_generated', 'done'].includes(requirement.value?.status || ''),
  },
]);
</script>

<template>
  <BaseDialog
    :open="open"
    :title="requirement?.title || '需求详情'"
    :width="920"
    @close="onClose"
  >
    <div v-if="loading" class="empty-state">加载中…</div>
    <div v-else-if="requirement" class="panel">
      <!-- ═══ ① 需求信息编辑 ═══ -->
      <section class="section">
        <div class="section-head">
          <div class="section-title-row">
            <span class="section-title">需求信息</span>
            <BaseTag :tone="priorityTone(requirement.priority)" size="sm">优先级 {{ requirement.priority }}</BaseTag>
            <BaseTag :tone="statusTone(requirement.status)" size="sm">{{ statusLabel(requirement.status) }}</BaseTag>
            <BaseTag v-if="latestReview && isLowScore(latestReview.score)" tone="red" size="sm" dot>建议重新评审</BaseTag>
          </div>
          <div class="section-ops">
            <BaseButton variant="secondary" size="sm" :loading="metaLoading" @click="generateMeta">
              AI 提炼元信息
            </BaseButton>
            <BaseButton variant="primary" size="sm" :loading="saving" @click="saveRequirement">保存</BaseButton>
          </div>
        </div>
        <div class="form-grid">
          <div class="form-item form-item--wide">
            <label class="field-label">标题</label>
            <BaseInput v-model="editForm.title" type="text" placeholder="需求标题" />
          </div>
          <div class="form-item">
            <label class="field-label">优先级</label>
            <select v-model="editForm.priority" class="select-clay">
              <option v-for="p in PRIORITIES" :key="p" :value="p">{{ p }}</option>
            </select>
          </div>
          <div class="form-item form-item--wide">
            <label class="field-label">摘要</label>
            <textarea v-model="editForm.summary" class="field-textarea" rows="2" placeholder="需求摘要"></textarea>
          </div>
        </div>
      </section>

      <!-- ═══ ② 三步步进器 ═══ -->
      <div class="steps">
        <div
          v-for="s in steps"
          :key="s.key"
          class="step"
          :class="{ 'step--active': curStep === s.key, 'step--done': s.done }"
        >
          <span class="step__num">{{ s.done ? '✓' : s.key + 1 }}</span>
          <span class="step__label">{{ s.label }}</span>
          <span class="step__desc">{{ s.desc }}</span>
        </div>
      </div>

      <!-- ═══ ③ Step1 评审 ═══ -->
      <section class="section">
        <div class="section-head">
          <span class="section-title">① 需求评审</span>
          <div class="section-ops">
            <BaseButton
              v-if="latestReview"
              variant="secondary"
              size="sm"
              :loading="reviewing"
              @click="doReview"
            >
              重新评审
            </BaseButton>
            <BaseButton v-else variant="primary" size="sm" :loading="reviewing" @click="doReview">
              开始评审
            </BaseButton>
            <BaseButton
              v-if="curStep === 0"
              variant="primary"
              size="sm"
              :disabled="!latestReview || (latestReview.score ?? 100) < 60"
              @click="confirmReview"
            >
              确认评审
            </BaseButton>
          </div>
        </div>

        <div v-if="latestReview" class="review-card">
          <div class="review-card__head">
            <span
              class="review-score"
              :class="{ 'review-score--low': isLowScore(latestReview.score) }"
            >
              {{ latestReview.score }}/100
            </span>
            <span class="review-label">{{ formatTime(latestReview.created_at) }}</span>
            <BaseTag v-if="isLowScore(latestReview.score)" tone="red" size="sm" dot>建议重新评审</BaseTag>
            <BaseTag v-else tone="green" size="sm" dot>评审通过</BaseTag>
          </div>
          <p v-if="latestReview.score_reason" class="review-reason">
            <b>评分原因：</b>{{ latestReview.score_reason }}
          </p>
          <p class="review-conclusion">{{ latestReview.conclusion }}</p>
          <div v-if="latestReview.risks?.length" class="review-list">
            <p class="review-list__label">风险点：</p>
            <ul>
              <li v-for="(r, i) in latestReview.risks" :key="i">{{ r }}</li>
            </ul>
          </div>
          <div v-if="latestReview.issues?.length" class="review-list">
            <p class="review-list__label">问题：</p>
            <ul>
              <li v-for="(iss, i) in latestReview.issues" :key="i">
                {{ typeof iss === 'string' ? iss : `${iss.title || ''}${iss.detail ? '：' + iss.detail : ''}` }}
              </li>
            </ul>
          </div>
          <div v-if="latestReview.review_comment" class="review-comment">
            评审评论：{{ latestReview.review_comment }}
          </div>
        </div>
        <div v-else class="empty-block">尚未评审，点击「开始评审」由 AI 打分</div>

        <div v-if="latestReview" class="re-review">
          <BaseInput
            v-model="reviewComment"
            type="text"
            placeholder="输入评审意见后重新评审（覆盖上次结论）"
            @enter="doReview"
          />
        </div>
      </section>

      <!-- ═══ ④ Step2 Story ═══ -->
      <section class="section">
        <div class="section-head">
          <span class="section-title">② Story 拆解</span>
          <div class="section-ops">
            <BaseButton variant="primary" size="sm" :loading="storiesLoading" @click="doStories">
              生成 Story
            </BaseButton>
            <BaseButton
              v-if="curStep === 1"
              variant="primary"
              size="sm"
              :disabled="!stories.length || isLowScore(storyScore)"
              @click="confirmStories"
            >
              确认 Story
            </BaseButton>
          </div>
        </div>

        <div v-if="stories.length" class="score-line">
          <span class="score-line__label">环节评分</span>
          <span class="review-score" :class="{ 'review-score--low': isLowScore(storyScore) }">
            {{ storyScore }}/100
          </span>
          <span v-if="storyScoreReason" class="score-line__reason">{{ storyScoreReason }}</span>
          <BaseTag v-if="isLowScore(storyScore)" tone="red" size="sm" dot>建议重新评审</BaseTag>
        </div>

        <div v-if="stories.length" class="card-list">
          <div v-for="s in stories" :key="s.id" class="flow-card">
            <div class="flow-card__head">
              <span class="flow-card__title">Story {{ s.sort_order + 1 }} · {{ s.title }}</span>
            </div>
            <p class="flow-card__desc">{{ s.description }}</p>
            <p v-if="s.acceptance_criteria" class="flow-card__criteria">
              验收标准：{{ s.acceptance_criteria }}
            </p>
          </div>
        </div>
        <div v-else class="empty-block">尚未拆解 Story，点击「生成 Story」由 AI 拆解</div>
      </section>

      <!-- ═══ ⑤ Step3 用例 ═══ -->
      <section class="section">
        <div class="section-head">
          <span class="section-title">③ 用例生成</span>
          <div class="section-ops">
            <BaseButton variant="primary" size="sm" :loading="casesLoading" @click="doCases">
              生成用例
            </BaseButton>
            <BaseButton
              v-if="curStep === 2 && requirement.status !== 'done'"
              variant="secondary"
              size="sm"
              @click="completeReq"
            >
              标记完成
            </BaseButton>
          </div>
        </div>

        <div v-if="cases.length" class="score-line">
          <span class="score-line__label">环节评分</span>
          <span class="review-score" :class="{ 'review-score--low': isLowScore(caseScore) }">
            {{ caseScore }}/100
          </span>
          <span v-if="caseScoreReason" class="score-line__reason">{{ caseScoreReason }}</span>
          <BaseTag v-if="isLowScore(caseScore)" tone="red" size="sm" dot>建议重新评审</BaseTag>
        </div>

        <div v-if="cases.length" class="card-list">
          <div v-for="c in cases" :key="c.id" class="flow-card">
            <div class="flow-card__head">
              <span class="flow-card__title">{{ c.title }}</span>
              <div class="flow-card__ops">
                <BaseButton variant="secondary" size="sm" @click="openBind(c)">
                  绑定自动化用例<span v-if="c.bound_count" class="bind-count">{{ c.bound_count }}</span>
                </BaseButton>
                <BaseButton
                  variant="ghost"
                  size="sm"
                  :loading="regenCaseId === c.id"
                  @click="regenerateCase(c)"
                >
                  重新生成
                </BaseButton>
              </div>
            </div>
            <p v-if="c.preconditions" class="flow-card__desc">前置：{{ c.preconditions }}</p>
            <p class="flow-card__desc"><b>步骤：</b>{{ c.steps }}</p>
            <p class="flow-card__criteria"><b>预期：</b>{{ c.expected }}</p>
          </div>
        </div>
        <div v-else class="empty-block">尚未生成用例，点击「生成用例」由 AI 生成</div>
      </section>

      <!-- ═══ ⑥ 来源 ═══ -->
      <section class="section">
        <div class="section-head">
          <span class="section-title">需求来源（{{ sources.length }}）</span>
          <div class="section-ops">
            <BaseButton variant="secondary" size="sm" @click="loadSources">刷新</BaseButton>
          </div>
        </div>
        <div
          v-if="larkAuthRequired"
          class="lark-auth-hint"
          title="飞书文档链接提取需要飞书授权"
        >
          飞书未授权，添加飞书链接可能提取失败。请到右上角头像菜单 →「系统设置」→「飞书授权」完成授权。
        </div>
        <div v-if="sourcesLoading" class="empty-block">加载中…</div>
        <div v-else-if="sources.length" class="source-list">
          <div v-for="s in sources" :key="s.id" class="source-item">
            <div class="source-info">
              <span class="source-name">{{ sourceName(s) }}</span>
              <span class="source-sub">
                {{ s.type === 'file' ? `${formatSize(s.file_size)} · ${s.mime_type}` : '飞书链接' }}
                · {{ s.created_by_name || '--' }} · {{ formatTime(s.created_at) }}
              </span>
            </div>
            <span v-if="s.extracted" class="source-status source-status--ok">✓ 已提取</span>
            <span v-else class="source-status source-status--fail" :title="s.extract_error">
              ✕ {{ s.extract_error || '未提取' }}
            </span>
            <div class="source-ops">
              <BaseButton
                v-if="s.type === 'lark_link' && !s.extracted"
                variant="ghost"
                size="sm"
                :loading="extractingId === s.id"
                @click="reExtract(s)"
              >
                重新提取
              </BaseButton>
              <BaseButton variant="ghost" size="sm" @click="removeSource(s)">删除</BaseButton>
            </div>
          </div>
        </div>
        <div v-else class="empty-block">暂无来源</div>
      </section>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="onClose">关闭</BaseButton>
    </template>
  </BaseDialog>

  <!-- 绑定自动化用例弹窗 -->
  <BaseDialog
    :open="!!bindCase"
    :title="`绑定自动化用例 · ${bindCase?.title || ''}`"
    :width="640"
    @close="bindCase = null"
  >
    <div v-if="bindCase" class="modal-body">
      <div class="bind-bar">
        <select v-model.number="bindBranchId" class="select-clay select-clay--sm">
          <option v-for="b in branches" :key="b.id" :value="b.id">
            {{ b.name }}{{ b.is_default ? '（默认）' : '' }}
          </option>
        </select>
        <BaseInput
          v-model="bindSearch"
          type="text"
          placeholder="搜索自动化用例（名称 / 方法 / 描述）"
          @enter="loadCandidates"
        />
        <BaseButton variant="secondary" size="sm" @click="loadCandidates">搜索</BaseButton>
      </div>

      <div v-if="bindings.length" class="bound-tags">
        <span class="bound-tags__label">已绑定：</span>
        <span v-for="b in bindings" :key="b.id" class="bound-tag">
          {{ b.case_name || b.full_name || b.uid }}
          <button class="bound-tag__x" @click="unbind(b)">×</button>
        </span>
      </div>

      <div class="cand-list">
        <div v-if="bindLoading" class="empty-block">加载中…</div>
        <div v-else-if="candidates.length" class="cand-item-wrap">
          <label
            v-for="cand in candidates"
            :key="cand.uid"
            class="cand-item"
            :class="{ 'cand-item--bound': boundUidSet.has(cand.uid) }"
          >
            <input
              type="checkbox"
              :checked="selectedUids.has(cand.uid)"
              :disabled="boundUidSet.has(cand.uid)"
              @change="toggleUid(cand.uid)"
            />
            <span class="cand-item__main">
              <span class="cand-item__name">{{ cand.name }}</span>
              <span class="cand-item__sub">{{ cand.fullName || cand.module }}</span>
            </span>
            <BaseTag v-if="boundUidSet.has(cand.uid)" tone="green" size="sm">已绑定</BaseTag>
          </label>
        </div>
        <div v-else class="empty-block">未找到自动化用例（共 {{ candidateTotal }} 条候选）</div>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="bindCase = null">取消</BaseButton>
      <BaseButton variant="primary" :loading="bindingOp" :disabled="!selectedUids.size" @click="doBind">
        绑定（{{ selectedUids.size }}）
      </BaseButton>
    </template>
  </BaseDialog>
</template>

<style scoped>
.panel {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ── Section ── */
.section {
  padding: 12px;
  background-color: var(--bg-soft);
  border: 2px solid var(--outline);
  border-radius: var(--radius-md);
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.section-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.section-title {
  font-family: var(--font-heading);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.section-ops {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── 表单 ── */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 180px;
  gap: 10px 12px;
}
.form-item--wide {
  grid-column: 1 / -1;
}
.field-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.field-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 12px;
  font-family: var(--font);
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-primary);
  background-color: var(--bg-input);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm-pressed);
  resize: vertical;
}
.field-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
  background-color: var(--bg-card);
}
.select-clay {
  width: 100%;
  padding: 6px 10px;
  font-family: var(--font);
  font-size: 12.5px;
  color: var(--text-primary);
  background-color: var(--bg-input);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.select-clay--sm {
  width: auto;
  flex-shrink: 0;
  padding: 5px 8px;
}
.select-clay:focus {
  outline: none;
  border-color: var(--color-primary);
}

/* ── 步进器 ── */
.steps {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: var(--bg-card);
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm);
  opacity: 0.55;
}
.step--done {
  opacity: 1;
}
.step--active {
  opacity: 1;
  background-color: var(--color-primary-soft);
  border-color: var(--color-primary-dark);
}
.step__num {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background-color: var(--color-primary);
  border: 2px solid var(--outline);
  font-family: var(--font-heading);
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.step__label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.step__desc {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
}

/* ── 评审卡片 ── */
.review-card {
  padding: 10px 12px;
  background-color: var(--success-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.review-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.review-score {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-success);
}
.review-score--low {
  color: var(--color-danger);
}
.review-label {
  font-size: 11px;
  color: var(--text-muted);
}
.review-reason {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.review-conclusion {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.6;
}
.review-list {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
.review-list__label {
  margin: 0 0 2px;
  font-weight: 600;
}
.review-list ul {
  margin: 0;
  padding-left: 18px;
}
.review-comment {
  margin-top: 6px;
  padding: 6px 8px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 11.5px;
  color: var(--text-secondary);
}
.re-review {
  margin-top: 10px;
}

/* ── 评分行 ── */
.score-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.score-line__label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-muted);
}
.score-line__reason {
  flex: 1;
  min-width: 0;
  font-size: 11.5px;
  color: var(--text-secondary);
}

/* ── 流程卡片 ── */
.card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.flow-card {
  padding: 10px 12px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.flow-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.flow-card__title {
  font-family: var(--font-heading);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.flow-card__ops {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.bind-count {
  margin-left: 3px;
  padding: 0 5px;
  border-radius: 999px;
  background-color: var(--color-primary);
  font-size: 10.5px;
  font-weight: 600;
}
.flow-card__desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.flow-card__criteria {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 空态 ── */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: var(--text-muted);
  font-size: 12px;
}
.empty-block {
  padding: 14px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

/* ── 来源 ── */
.lark-auth-hint {
  padding: 8px 10px;
  margin-bottom: 10px;
  font-size: 11.5px;
  color: var(--color-warning);
  background-color: var(--bg-card);
  border: 1.5px solid var(--color-warning);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm);
}
.source-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.source-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.source-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.source-name {
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-sub {
  font-size: 11px;
  color: var(--text-muted);
}
.source-status {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
}
.source-status--ok {
  color: var(--color-success);
}
.source-status--fail {
  color: var(--color-danger);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-ops {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

/* ── 绑定弹窗 ── */
.modal-body {
  padding: 16px 20px;
}
.bind-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.bound-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
  padding: 8px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 11.5px;
}
.bound-tags__label {
  color: var(--text-muted);
}
.bound-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 2px solid var(--outline);
  background-color: var(--success-soft);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}
.bound-tag__x {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  border-radius: 999px;
}
.bound-tag__x:hover {
  background-color: var(--danger-soft);
  color: var(--color-danger);
}
.cand-list {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cand-item-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cand-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.cand-item:hover {
  background-color: var(--bg-card-hover);
}
.cand-item--bound {
  opacity: 0.6;
}
.cand-item__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cand-item__name {
  font-size: 12px;
  color: var(--text-primary);
}
.cand-item__sub {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
