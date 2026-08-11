<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useApi } from '../composables/useApi';
import BaseButton from './base/BaseButton.vue';
import BaseTag from './base/BaseTag.vue';
import type {
  RequirementInfo,
  RequirementStoryInfo,
  GeneratedCaseInfo,
  LayeredAnalysisInfo,
  InformationGapInfo,
  TestPointInfo,
  LayeredReviewInfo,
  TestScenarioInfo,
  TestStrategyInfo,
  CoverageSnapshotInfo,
  TestGapInfo,
  AITaskInfo,
  RequirementLayersBundle,
} from '../types';

const emit = defineEmits<{
  (e: 'showToast', msg: string): void;
}>();

const route = useRoute();
const router = useRouter();
const { get, post } = useApi();

const reqId = computed(() => Number(route.params.reqId));

// ── 状态元信息 ──
const REQ_STATUS_META: Record<string, { label: string; tone: 'yellow' | 'blue' | 'purple' | 'green' }> = {
  pending_review: { label: '待评审', tone: 'yellow' },
  review_passed: { label: '评审通过', tone: 'blue' },
  story_confirmed: { label: 'Story 已确认', tone: 'purple' },
  cases_generated: { label: '用例已生成', tone: 'green' },
  done: { label: '已完成', tone: 'green' },
};

const GATE_META: Record<string, { label: string; tone: 'green' | 'yellow' | 'red' }> = {
  PASS: { label: 'PASS', tone: 'green' },
  WARNING: { label: 'WARNING', tone: 'yellow' },
  BLOCKED: { label: 'BLOCKED', tone: 'red' },
};

const TASK_META: Record<string, { label: string; tone: 'yellow' | 'blue' | 'purple' | 'orange' | 'green' | 'red' }> = {
  PENDING: { label: '排队中', tone: 'yellow' },
  RUNNING: { label: '执行中', tone: 'blue' },
  REVIEW: { label: '待确认', tone: 'purple' },
  WAITING_HUMAN: { label: '待人工', tone: 'orange' },
  CONFIRMED: { label: '已确认', tone: 'green' },
  NEXT_STAGE: { label: '已流转', tone: 'green' },
  FAILED: { label: '失败', tone: 'red' },
  RETRY: { label: '重试中', tone: 'orange' },
};

const STAGE_LABEL: Record<string, string> = {
  analyze: '需求分析',
  review_stories: 'Story 评审',
  test_points: '测试点生成',
  review_test_points: '测试点评审',
  scenarios: '场景生成',
  review_scenarios: '场景评审',
  cases: '用例评审',
  strategy: '策略推荐',
  coverage: '覆盖率分析',
  supplement: 'AI 补测',
};

function reqStatusLabel(s: string): string {
  return REQ_STATUS_META[s]?.label ?? s;
}
function reqStatusTone(s: string): 'yellow' | 'blue' | 'purple' | 'green' | 'gray' {
  return REQ_STATUS_META[s]?.tone ?? 'gray';
}
function priorityTone(p: string): 'red' | 'orange' | 'green' {
  if (p === 'P0') return 'red';
  if (p === 'P1') return 'orange';
  return 'green';
}
function gateTone(g: string): 'green' | 'yellow' | 'red' | 'gray' {
  return GATE_META[g]?.tone ?? 'gray';
}
function gapSeverityTone(s: string): 'red' | 'orange' | 'yellow' | 'gray' {
  if (s === 'CRITICAL') return 'red';
  if (s === 'HIGH') return 'orange';
  if (s === 'MEDIUM') return 'yellow';
  return 'gray';
}
function gapStatusLabel(s: string): string {
  if (s === 'confirmed') return '已确认';
  if (s === 'ignored') return '已忽略';
  return '待确认';
}
function gapStatusTone(s: string): 'green' | 'gray' | 'yellow' {
  if (s === 'confirmed') return 'green';
  if (s === 'ignored') return 'gray';
  return 'yellow';
}
function testGapSeverityTone(s: string): 'red' | 'orange' | 'green' {
  if (s === 'P0') return 'red';
  if (s === 'P1') return 'orange';
  return 'green';
}
function taskStatusTone(s: string): 'yellow' | 'blue' | 'purple' | 'orange' | 'green' | 'red' | 'gray' {
  return TASK_META[s]?.tone ?? 'gray';
}
function formatTime(iso: string): string {
  if (!iso) return '--';
  return iso.substring(0, 16).replace('T', ' ');
}

function parseJson<T>(raw: string | undefined, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

// ── 数据 ──
const loading = ref(false);
const requirement = ref<RequirementInfo | null>(null);
const analysis = ref<LayeredAnalysisInfo | null>(null);
const informationGaps = ref<InformationGapInfo[]>([]);
const stories = ref<RequirementStoryInfo[]>([]);
const testPoints = ref<TestPointInfo[]>([]);
const testPointReview = ref<LayeredReviewInfo | null>(null);
const testScenarios = ref<TestScenarioInfo[]>([]);
const scenarioReview = ref<LayeredReviewInfo | null>(null);
const cases = ref<GeneratedCaseInfo[]>([]);
const caseReview = ref<LayeredReviewInfo | null>(null);
const strategy = ref<TestStrategyInfo | null>(null);
const coverage = ref<CoverageSnapshotInfo | null>(null);
const testGaps = ref<TestGapInfo[]>([]);
const aiTasks = ref<AITaskInfo[]>([]);

const analysisElements = computed<Record<string, unknown>>(() =>
  parseJson(analysis.value?.elements, {}),
);
const tprCoverage = computed<Record<string, number>>(() =>
  parseJson(testPointReview.value?.coverage, {}),
);
const strategyResult = computed<Record<string, unknown>>(() =>
  parseJson(strategy.value?.result, {}),
);

async function loadAll() {
  loading.value = true;
  try {
    const bundle = await get<RequirementLayersBundle>(`/requirements/${reqId.value}/layers`);
    requirement.value = bundle.requirement;
    analysis.value = bundle.analysis;
    informationGaps.value = bundle.information_gaps;
    testPoints.value = bundle.test_points;
    testPointReview.value = bundle.test_point_review;
    testScenarios.value = bundle.test_scenarios;
    scenarioReview.value = bundle.scenario_review;
    caseReview.value = bundle.case_review;
    strategy.value = bundle.strategy;
    coverage.value = bundle.coverage;
    testGaps.value = bundle.test_gaps;

    const [sts, cs, tasks] = await Promise.all([
      get<RequirementStoryInfo[]>(`/requirements/${reqId.value}/stories`),
      get<GeneratedCaseInfo[]>(`/requirements/${reqId.value}/cases`),
      get<AITaskInfo[]>(`/requirements/${reqId.value}/ai-tasks`),
    ]);
    stories.value = sts;
    cases.value = cs;
    aiTasks.value = tasks;
  } catch (e) {
    emit('showToast', (e as Error).message || '工作台加载失败');
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);

// ── 测试点树 ──
interface TpNode {
  item: TestPointInfo;
  children: TpNode[];
}
function buildTpTree(list: TestPointInfo[]): TpNode[] {
  const byId = new Map<number, TpNode>();
  for (const item of list) byId.set(item.id, { item, children: [] });
  const roots: TpNode[] = [];
  for (const item of list) {
    const node = byId.get(item.id)!;
    const parent = item.parent_id ? byId.get(item.parent_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}
const tpTree = computed<TpNode[]>(() => buildTpTree(testPoints.value));
const tpCategoryTone: Record<string, 'blue' | 'green' | 'purple' | 'yellow' | 'gray' | 'red' | 'orange'> = {
  Functional: 'blue',
  Boundary: 'purple',
  Exception: 'red',
  State: 'yellow',
  Permission: 'orange',
  Data: 'green',
  Concurrency: 'red',
  Security: 'red',
  Performance: 'purple',
  Compatibility: 'blue',
  Dependency: 'gray',
};

// ── 各层操作 loading ──
const analyzing = ref(false);
const storyReviewing = ref(false);
const storyGenerating = ref(false);
const tpGenerating = ref(false);
const tpReviewing = ref(false);
const scGenerating = ref(false);
const scReviewing = ref(false);
const caseReviewing = ref(false);
const strategyLoading = ref(false);
const coverageLoading = ref(false);
const supplementingId = ref<number | null>(null);

async function run<T>(fn: () => Promise<T>, loadingRef: { value: boolean }, msg: string) {
  loadingRef.value = true;
  try {
    await fn();
    emit('showToast', msg);
    await loadAll();
  } catch (e) {
    emit('showToast', (e as Error).message || msg);
  } finally {
    loadingRef.value = false;
  }
}

// ① 需求分析
function doAnalyze() {
  return run(() => post(`/requirements/${reqId.value}/analysis/analyze`, {}), analyzing, '需求分析完成');
}

// ② Story：生成 / 评审
function doStoryGenerate() {
  return run(
    () => post(`/requirements/${reqId.value}/stories/generate`),
    storyGenerating,
    'Story 拆解完成',
  );
}
function doStoryReview() {
  return run(
    () => post(`/requirements/${reqId.value}/stories/review`, {}),
    storyReviewing,
    'Story 评审完成',
  );
}

// ③ 测试点：生成 / 评审
function doTestPointsGenerate() {
  return run(
    () => post(`/requirements/${reqId.value}/test-points/generate`, {}),
    tpGenerating,
    '测试点生成完成',
  );
}
function doTestPointsReview() {
  return run(
    () => post(`/requirements/${reqId.value}/test-points/review`, {}),
    tpReviewing,
    '测试点评审完成',
  );
}

// ④ 场景：生成 / 评审
function doScenariosGenerate() {
  return run(
    () => post(`/requirements/${reqId.value}/test-scenarios/generate`, {}),
    scGenerating,
    '测试场景生成完成',
  );
}
function doScenariosReview() {
  return run(
    () => post(`/requirements/${reqId.value}/test-scenarios/review`, {}),
    scReviewing,
    '场景评审完成',
  );
}

// ⑤ 用例评审
function doCasesReview() {
  return run(
    () => post(`/requirements/${reqId.value}/cases/review`, {}),
    caseReviewing,
    '用例评审完成',
  );
}

// ⑥ 策略 / 覆盖率
function doStrategy() {
  return run(
    () => post(`/requirements/${reqId.value}/strategy/recommend`),
    strategyLoading,
    '自动化策略推荐完成',
  );
}
function doCoverage() {
  return run(
    () => post(`/requirements/${reqId.value}/coverage/analyze`, {}),
    coverageLoading,
    '覆盖率分析完成',
  );
}

// 缺口：AI 补测 / 状态切换
function doSupplement(gap: TestGapInfo) {
  return run(
    () => post(`/test-gaps/${gap.id}/generate`, {}),
    { value: supplementingId.value === gap.id },
    '补充用例已生成',
  ).finally(() => {
    supplementingId.value = null;
  });
}
function doGapStatus(gap: TestGapInfo, status: 'open' | 'closed') {
  return run(
    () => post(`/test-gaps/${gap.id}/status`, { status }),
    { value: false },
    status === 'closed' ? '缺口已关闭' : '缺口已重新打开',
  );
}

// 信息缺口：确认 / 忽略
function doInfoGapConfirm(gap: InformationGapInfo) {
  return run(
    () => post(`/information-gaps/${gap.id}/confirm`),
    { value: false },
    '缺口已确认',
  );
}
function doInfoGapIgnore(gap: InformationGapInfo) {
  return run(
    () => post(`/information-gaps/${gap.id}/ignore`),
    { value: false },
    '缺口已忽略',
  );
}

function goBack() {
  router.push('/requirements');
}

// ── 分析 elements 展示顺序 ──
const ELEMENT_ITEMS: Array<{ key: string; label: string }> = [
  { key: 'business_goal', label: '业务目标' },
  { key: 'roles', label: '角色' },
  { key: 'entities', label: '业务实体' },
  { key: 'flows', label: '核心流程' },
  { key: 'rules', label: '业务规则' },
  { key: 'states', label: '状态' },
  { key: 'inputs_outputs', label: '输入输出' },
  { key: 'exceptions', label: '异常场景' },
  { key: 'permissions', label: '权限' },
  { key: 'dependencies', label: '外部依赖' },
  { key: 'risks', label: '风险' },
];

function elementValue(v: unknown): string {
  if (Array.isArray(v)) return v.join('、');
  return String(v ?? '');
}
</script>

<template>
  <div class="wb-page">
    <!-- ═══ 顶部标题行 ═══ -->
    <div class="wb-header">
      <div class="wb-header__title">
        <BaseButton variant="ghost" size="sm" @click="goBack">← 返回列表</BaseButton>
        <h2 class="wb-title">{{ requirement?.title || '测试设计工作台' }}</h2>
        <BaseTag v-if="requirement" :tone="priorityTone(requirement.priority)" size="md">
          优先级 {{ requirement.priority }}
        </BaseTag>
        <BaseTag v-if="requirement" :tone="reqStatusTone(requirement.status)" size="md">
          {{ reqStatusLabel(requirement.status) }}
        </BaseTag>
      </div>
      <div class="wb-header__ops">
        <BaseButton
          variant="primary"
          size="md"
          :loading="analyzing"
          :disabled="!requirement"
          @click="doAnalyze"
        >
          AI 分析
        </BaseButton>
      </div>
    </div>

    <div v-if="loading && !requirement" class="empty-state">加载中…</div>

    <div v-else class="wb-body">
      <!-- ═══ ① 需求分析 ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">① 需求分析</span>
          <div class="wb-section__ops">
            <BaseButton
              variant="secondary"
              size="sm"
              :loading="analyzing"
              @click="doAnalyze"
            >
              {{ analysis ? '重新分析' : 'AI 分析' }}
            </BaseButton>
          </div>
        </div>

        <template v-if="analysis">
          <div class="wb-score-row">
            <span class="wb-score-label">分析评分</span>
            <span class="wb-score" :class="{ 'wb-score--low': analysis.score > 0 && analysis.score < 60 }">
              {{ analysis.score }}/100
            </span>
            <span v-if="analysis.score_reason" class="wb-score-reason">{{ analysis.score_reason }}</span>
          </div>

          <div class="elem-grid">
            <div
              v-for="el in ELEMENT_ITEMS"
              :key="el.key"
              class="elem-card"
            >
              <span class="elem-card__label">{{ el.label }}</span>
              <span class="elem-card__value">{{ elementValue(analysisElements[el.key]) || '--' }}</span>
            </div>
          </div>

          <!-- 信息缺口 -->
          <div class="gap-block">
            <div class="gap-block__head">
              <span class="gap-block__title">信息缺口（{{ informationGaps.length }}）</span>
              <span class="gap-block__hint">CRITICAL 未确认将阻塞 Story 评审（BLOCKED）</span>
            </div>
            <div v-if="informationGaps.length" class="gap-list">
              <div v-for="g in informationGaps" :key="g.id" class="gap-item">
                <BaseTag :tone="gapSeverityTone(g.severity)" size="sm">{{ g.severity }}</BaseTag>
                <BaseTag :tone="gapStatusTone(g.status)" size="sm">{{ gapStatusLabel(g.status) }}</BaseTag>
                <span class="gap-item__desc">{{ g.description }}</span>
                <span v-if="g.question" class="gap-item__q">待确认：{{ g.question }}</span>
                <div v-if="g.status === 'pending'" class="gap-item__ops">
                  <BaseButton variant="primary" size="sm" @click="doInfoGapConfirm(g)">确认</BaseButton>
                  <BaseButton variant="ghost" size="sm" @click="doInfoGapIgnore(g)">忽略</BaseButton>
                </div>
              </div>
            </div>
            <div v-else class="empty-block">无信息缺口</div>
          </div>
        </template>
        <div v-else class="empty-block">
          尚未进行需求分析，点击「AI 分析」提取业务目标 / 规则 / 风险与信息缺口
        </div>
      </section>

      <!-- ═══ ② Story ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">② Story</span>
          <div class="wb-section__ops">
            <BaseButton
              v-if="!stories.length"
              variant="secondary"
              size="sm"
              :loading="storyGenerating"
              @click="doStoryGenerate"
            >
              生成 Story
            </BaseButton>
            <BaseButton
              v-else
              variant="secondary"
              size="sm"
              :loading="storyReviewing"
              @click="doStoryReview"
            >
              AI 评审
            </BaseButton>
          </div>
        </div>

        <div v-if="stories.length" class="card-list">
          <div v-for="s in stories" :key="s.id" class="wb-card">
            <div class="wb-card__head">
              <span class="wb-card__title">Story {{ s.sort_order + 1 }} · {{ s.title }}</span>
              <div class="wb-card__tags">
                <BaseTag
                  v-if="s.gate_status"
                  :tone="gateTone(s.gate_status)"
                  size="sm"
                  :dot="s.gate_status !== 'PASS'"
                >
                  {{ s.gate_status }}
                </BaseTag>
                <BaseTag v-if="s.score" :tone="s.score >= 60 ? 'green' : 'red'" size="sm">
                  {{ s.score }}
                </BaseTag>
              </div>
            </div>
            <p class="wb-card__desc">{{ s.description }}</p>
            <p v-if="s.acceptance_criteria" class="wb-card__sub">
              验收标准：{{ s.acceptance_criteria }}
            </p>
          </div>
        </div>
        <div v-else class="empty-block">尚未拆解 Story，点击「生成 Story」由 AI 拆解</div>
      </section>

      <!-- ═══ ③ 测试点 ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">③ 测试点</span>
          <div class="wb-section__ops">
            <BaseButton
              variant="secondary"
              size="sm"
              :loading="tpGenerating"
              @click="doTestPointsGenerate"
            >
              {{ testPoints.length ? '重新生成' : 'AI 生成' }}
            </BaseButton>
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="!testPoints.length"
              :loading="tpReviewing"
              @click="doTestPointsReview"
            >
              AI 评审
            </BaseButton>
          </div>
        </div>

        <div v-if="testPointReview" class="wb-score-row">
          <span class="wb-score-label">测试点评审</span>
          <span class="wb-score" :class="{ 'wb-score--low': testPointReview.score < 60 }">
            {{ testPointReview.score }}/100
          </span>
          <BaseTag :tone="gateTone(testPointReview.gate_status)" size="sm" dot>
            {{ testPointReview.gate_status }}
          </BaseTag>
          <span
            v-if="typeof tprCoverage.TestPoint === 'number'"
            class="wb-score-reason"
          >
            覆盖率 {{ tprCoverage.TestPoint }}%
          </span>
        </div>

        <div v-if="tpTree.length" class="tp-tree">
          <div v-for="node in tpTree" :key="node.item.id" class="tp-node">
            <div class="tp-node__row">
              <span class="tp-node__marker">{{ node.children.length ? '▾' : '·' }}</span>
              <BaseTag :tone="tpCategoryTone[node.item.category] || 'gray'" size="sm">
                {{ node.item.category }}
              </BaseTag>
              <span class="tp-node__title">{{ node.item.title }}</span>
            </div>
            <div v-if="node.children.length" class="tp-node__children">
              <div v-for="child in node.children" :key="child.item.id" class="tp-node tp-node--child">
                <div class="tp-node__row">
                  <span class="tp-node__marker">·</span>
                  <BaseTag :tone="tpCategoryTone[child.item.category] || 'gray'" size="sm">
                    {{ child.item.category }}
                  </BaseTag>
                  <span class="tp-node__title">{{ child.item.title }}</span>
                </div>
                <p v-if="child.item.description" class="tp-node__desc">{{ child.item.description }}</p>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-block">尚未生成测试点，点击「AI 生成」由 AI 按 Story 拆解</div>
      </section>

      <!-- ═══ ④ 测试场景 ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">④ 测试场景</span>
          <div class="wb-section__ops">
            <BaseButton
              variant="secondary"
              size="sm"
              :loading="scGenerating"
              @click="doScenariosGenerate"
            >
              {{ testScenarios.length ? '重新生成' : 'AI 生成' }}
            </BaseButton>
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="!testScenarios.length"
              :loading="scReviewing"
              @click="doScenariosReview"
            >
              AI 评审
            </BaseButton>
          </div>
        </div>

        <div v-if="scenarioReview" class="wb-score-row">
          <span class="wb-score-label">场景评审</span>
          <span class="wb-score" :class="{ 'wb-score--low': scenarioReview.score < 60 }">
            {{ scenarioReview.score }}/100
          </span>
          <BaseTag :tone="gateTone(scenarioReview.gate_status)" size="sm" dot>
            {{ scenarioReview.gate_status }}
          </BaseTag>
        </div>

        <div v-if="testScenarios.length" class="card-list">
          <div v-for="sc in testScenarios" :key="sc.id" class="wb-card">
            <div class="wb-card__head">
              <span class="wb-card__title">{{ sc.sort_order + 1 }}. {{ sc.title }}</span>
              <BaseTag v-if="sc.coverage_dim" tone="blue" size="sm">{{ sc.coverage_dim }}</BaseTag>
            </div>
            <p class="wb-card__desc">{{ sc.description }}</p>
          </div>
        </div>
        <div v-else class="empty-block">尚未生成测试场景，点击「AI 生成」由 AI 按测试点设计业务情况</div>
      </section>

      <!-- ═══ ⑤ 测试用例 ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">⑤ 测试用例</span>
          <div class="wb-section__ops">
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="!cases.length"
              :loading="caseReviewing"
              @click="doCasesReview"
            >
              AI 评审
            </BaseButton>
          </div>
        </div>

        <div v-if="caseReview" class="wb-score-row">
          <span class="wb-score-label">用例评审</span>
          <span class="wb-score" :class="{ 'wb-score--low': caseReview.score < 60 }">
            {{ caseReview.score }}/100
          </span>
          <BaseTag :tone="gateTone(caseReview.gate_status)" size="sm" dot>
            {{ caseReview.gate_status }}
          </BaseTag>
        </div>

        <div v-if="cases.length" class="card-list">
          <div v-for="c in cases" :key="c.id" class="wb-card">
            <div class="wb-card__head">
              <span class="wb-card__title">{{ c.title }}</span>
              <span v-if="c.bound_count" class="wb-card__bound">已绑定 {{ c.bound_count }}</span>
            </div>
            <p v-if="c.preconditions" class="wb-card__desc">前置：{{ c.preconditions }}</p>
            <p class="wb-card__desc"><b>步骤：</b>{{ c.steps }}</p>
            <p class="wb-card__sub"><b>预期：</b>{{ c.expected }}</p>
          </div>
        </div>
        <div v-else class="empty-block">尚未生成用例，请先在需求详情中生成，或通过下方测试缺口「AI 补测」</div>
      </section>

      <!-- ═══ ⑥ 策略 / 覆盖率 / 测试缺口 ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">⑥ 测试策略与覆盖率</span>
          <div class="wb-section__ops">
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="!cases.length"
              :loading="strategyLoading"
              @click="doStrategy"
            >
              策略推荐
            </BaseButton>
            <BaseButton
              variant="secondary"
              size="sm"
              :loading="coverageLoading"
              @click="doCoverage"
            >
              覆盖率分析
            </BaseButton>
          </div>
        </div>

        <div v-if="strategy" class="strategy-row">
          <span class="wb-score-label">自动化占比</span>
          <span class="strategy-ratio">{{ strategy.automation_ratio }}%</span>
          <span v-if="strategyResult.reasoning" class="wb-score-reason">
            {{ String(strategyResult.reasoning) }}
          </span>
        </div>

        <div v-if="coverage" class="cov-list">
          <div v-for="bar in [
            { key: 'requirement_coverage', label: '需求' },
            { key: 'story_coverage', label: 'Story' },
            { key: 'test_point_coverage', label: '测试点' },
            { key: 'scenario_coverage', label: '场景' },
            { key: 'case_coverage', label: '用例' },
            { key: 'automation_coverage', label: '自动化' },
            { key: 'risk_coverage', label: '风险' },
          ]" :key="bar.key" class="cov-bar">
            <span class="cov-bar__label">{{ bar.label }}</span>
            <div class="cov-bar__track">
              <div
                class="cov-bar__fill"
                :class="{ 'cov-bar__fill--low': (coverage[bar.key as keyof CoverageSnapshotInfo] as number) < 60 }"
                :style="{ width: `${(coverage[bar.key as keyof CoverageSnapshotInfo] as number) || 0}%` }"
              ></div>
            </div>
            <span class="cov-bar__value">
              {{ (coverage[bar.key as keyof CoverageSnapshotInfo] as number) || 0 }}%
            </span>
          </div>
        </div>

        <!-- 测试缺口 -->
        <div class="gap-block">
          <div class="gap-block__head">
            <span class="gap-block__title">测试缺口（{{ testGaps.length }}）</span>
            <span class="gap-block__hint">缺口可直接「AI 补测」生成补充用例</span>
          </div>
          <div v-if="testGaps.length" class="gap-list">
            <div v-for="g in testGaps" :key="g.id" class="gap-item">
              <BaseTag :tone="testGapSeverityTone(g.severity)" size="sm">{{ g.severity }}</BaseTag>
              <BaseTag :tone="g.status === 'open' ? 'yellow' : 'gray'" size="sm">
                {{ g.status === 'open' ? '未处理' : '已关闭' }}
              </BaseTag>
              <BaseTag v-if="g.layer" tone="blue" size="sm">{{ g.layer }}</BaseTag>
              <span class="gap-item__desc">{{ g.description }}</span>
              <div class="gap-item__ops">
                <BaseButton
                  v-if="g.status === 'open'"
                  variant="primary"
                  size="sm"
                  :loading="supplementingId === g.id"
                  @click="supplementingId = g.id; doSupplement(g)"
                >
                  AI 补测
                </BaseButton>
                <BaseButton
                  variant="ghost"
                  size="sm"
                  @click="doGapStatus(g, g.status === 'open' ? 'closed' : 'open')"
                >
                  {{ g.status === 'open' ? '关闭' : '重开' }}
                </BaseButton>
              </div>
            </div>
          </div>
          <div v-else class="empty-block">暂无测试缺口</div>
        </div>
      </section>

      <!-- ═══ ⑦ AI 任务记录 ═══ -->
      <section class="wb-section">
        <div class="wb-section__head">
          <span class="wb-section__title">AI 任务记录（{{ aiTasks.length }}）</span>
          <BaseButton variant="ghost" size="sm" @click="loadAll">刷新</BaseButton>
        </div>
        <div v-if="aiTasks.length" class="task-list">
          <div v-for="t in aiTasks" :key="t.id" class="task-item">
            <BaseTag :tone="taskStatusTone(t.status)" size="sm" dot>
              {{ TASK_META[t.status]?.label ?? t.status }}
            </BaseTag>
            <span class="task-item__stage">{{ STAGE_LABEL[t.stage] ?? t.stage }}</span>
            <span class="task-item__model">{{ t.model || '--' }}</span>
            <span v-if="t.error" class="task-item__error" :title="t.error">{{ t.error }}</span>
            <span class="task-item__time">{{ formatTime(t.created_at) }}</span>
          </div>
        </div>
        <div v-else class="empty-block">暂无 AI 任务</div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.wb-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 24px 20px;
}
.wb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 0;
}
.wb-header__title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.wb-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.wb-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.wb-section {
  padding: 12px;
  background-color: var(--bg-soft);
  border: 2px solid var(--outline);
  border-radius: var(--radius-md);
}
.wb-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.wb-section__title {
  font-family: var(--font-heading);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.wb-section__ops {
  display: flex;
  align-items: center;
  gap: 8px;
}
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

/* ── 评分行 ── */
.wb-score-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.wb-score-label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-muted);
}
.wb-score {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-success);
}
.wb-score--low {
  color: var(--color-danger);
}
.wb-score-reason {
  flex: 1;
  min-width: 0;
  font-size: 11.5px;
  color: var(--text-secondary);
}

/* ── 需求分析 elements ── */
.elem-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px;
}
.elem-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.elem-card__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
}
.elem-card__value {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-word;
}

/* ── 缺口 ── */
.gap-block {
  margin-top: 12px;
}
.gap-block__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.gap-block__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.gap-block__hint {
  font-size: 11px;
  color: var(--text-muted);
}
.gap-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.gap-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  flex-wrap: wrap;
}
.gap-item__desc {
  flex: 1;
  min-width: 120px;
  font-size: 12px;
  color: var(--text-primary);
}
.gap-item__q {
  font-size: 11.5px;
  color: var(--color-warning);
}
.gap-item__ops {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* ── 卡片列表 ── */
.card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wb-card {
  padding: 10px 12px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.wb-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.wb-card__title {
  font-family: var(--font-heading);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.wb-card__tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.wb-card__bound {
  padding: 2px 8px;
  border-radius: 999px;
  background-color: var(--color-primary-soft);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}
.wb-card__desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.wb-card__sub {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 测试点树 ── */
.tp-tree {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tp-node__row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tp-node__marker {
  width: 14px;
  flex-shrink: 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}
.tp-node__title {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-primary);
}
.tp-node__desc {
  margin: 4px 0 0 40px;
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.5;
}
.tp-node__children {
  margin: 6px 0 0 14px;
  padding-left: 10px;
  border-left: 2px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── 策略 / 覆盖率 ── */
.strategy-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.strategy-ratio {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary-dark);
}
.cov-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cov-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cov-bar__label {
  width: 56px;
  flex-shrink: 0;
  font-size: 11.5px;
  color: var(--text-secondary);
  text-align: right;
}
.cov-bar__track {
  flex: 1;
  height: 12px;
  background-color: var(--bg-input);
  border: 2px solid var(--outline);
  border-radius: 999px;
  overflow: hidden;
}
.cov-bar__fill {
  height: 100%;
  background-color: var(--color-success);
  border-radius: 999px;
  transition: width 0.3s ease;
}
.cov-bar__fill--low {
  background-color: var(--color-danger);
}
.cov-bar__value {
  width: 44px;
  flex-shrink: 0;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── AI 任务 ── */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background-color: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  flex-wrap: wrap;
}
.task-item__stage {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.task-item__model {
  font-size: 11px;
  color: var(--text-muted);
}
.task-item__error {
  flex: 1;
  min-width: 120px;
  font-size: 11.5px;
  color: var(--color-danger);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-item__time {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
}
</style>
