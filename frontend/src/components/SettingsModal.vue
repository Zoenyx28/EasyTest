<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import BaseDialog from './base/BaseDialog.vue';
import BaseButton from './base/BaseButton.vue';
import BaseInput from './base/BaseInput.vue';
import BaseTag from './base/BaseTag.vue';
import { useApi } from '../composables/useApi';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'showToast', msg: string): void;
}>();

const api = useApi();

/* ── Tab ── */
type TabKey = 'exec' | 'llm' | 'lark';
const activeTab = ref<TabKey>('exec');
const tabs: { key: TabKey; label: string }[] = [
  { key: 'exec', label: '执行设置' },
  { key: 'llm', label: 'LLM 配置' },
  { key: 'lark', label: '飞书授权' },
];

/* ════════════════ Tab 1：执行设置（本地存储） ════════════════ */
const STORAGE_KEY = 'pytest_pro_settings';

interface AppSettings {
  clusterName: string;
  timeoutSec: number;
  autoRetry: boolean;
  enableLiveLogs: boolean;
}

function loadSettings(): AppSettings {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return { clusterName: 'default', timeoutSec: 30, autoRetry: true, enableLiveLogs: true };
}

function persistSettings(settings: AppSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

const clusterName = ref('default');
const timeoutSec = ref(30);
const autoRetry = ref(true);
const enableLiveLogs = ref(true);

/* ════════════════ Tab 2：LLM 全局配置（/api/settings/llm） ════════════════ */
const llmLoading = ref(false);
const llmSaving = ref(false);
const provider = ref('');
const apiBase = ref('');
const textModel = ref('');
const visionModel = ref('');
const apiKey = ref('');
const hasKey = ref(false);
const apiKeyMasked = ref('');

async function loadLlm() {
  llmLoading.value = true;
  try {
    const s = await api.get<any>('/settings/llm');
    provider.value = s.provider || '';
    apiBase.value = s.api_base || '';
    textModel.value = s.text_model || '';
    visionModel.value = s.vision_model || '';
    hasKey.value = !!s.has_key;
    apiKeyMasked.value = s.api_key_masked || '';
  } catch (e: any) {
    emit('showToast', e.message || '加载 LLM 配置失败');
  } finally {
    llmLoading.value = false;
  }
}

async function saveLlm() {
  const body: Record<string, string> = {
    provider: provider.value,
    api_base: apiBase.value,
    text_model: textModel.value,
    vision_model: visionModel.value,
  };
  // 留空表示不修改已保存的 key，避免覆盖
  if (apiKey.value.trim()) {
    body.api_key = apiKey.value.trim();
  }
  llmSaving.value = true;
  try {
    await api.put('/settings/llm', body);
    apiKey.value = '';
    await loadLlm();
    emit('showToast', 'LLM 配置已保存');
  } catch (e: any) {
    emit('showToast', e.message || '保存 LLM 配置失败');
  } finally {
    llmSaving.value = false;
  }
}

/* ════════════════ Tab 3：飞书授权（/api/settings/lark/*） ════════════════ */
interface LarkStatus {
  bound: boolean;
  app_id: string;
  lark_open_id: string;
  token_status: string;
  auth_required: boolean;
  auth_pending: boolean;
  auth_error: string;
  cli_available: boolean;
}
interface PendingAuth {
  verification_url: string;
  device_code: string;
  expires_in: number;
  startedAt: number;
}

const larkLoading = ref(false);
const larkStatus = ref<LarkStatus>({
  bound: false, app_id: '', lark_open_id: '', token_status: '',
  auth_required: true, auth_pending: false, auth_error: '', cli_available: true,
});
const authPending = ref<PendingAuth | null>(null);
const authStarting = ref(false);
const authCompleting = ref(false);
const authDone = ref(false);
let pollTimer: number | undefined;

async function loadLark() {
  larkLoading.value = true;
  try {
    larkStatus.value = await api.get<LarkStatus>('/settings/lark/status');
  } catch (e: any) {
    emit('showToast', e.message || '查询飞书授权状态失败');
  } finally {
    larkLoading.value = false;
  }
}

async function startAuth() {
  authStarting.value = true;
  authDone.value = false;
  larkStatus.value.auth_error = '';
  try {
    const res = await api.post<{ verification_url: string; device_code: string; expires_in: number }>('/settings/lark/auth');
    authPending.value = {
      verification_url: res.verification_url,
      device_code: res.device_code,
      expires_in: res.expires_in,
      startedAt: Date.now(),
    };
    startPolling();
  } catch (e: any) {
    emit('showToast', e.message || '发起飞书授权失败');
  } finally {
    authStarting.value = false;
  }
}

/**
 * 单次查询授权状态。发起授权后后端由后台任务执行阻塞式 `auth login --device-code`，
 * 本函数仅轮询快速的 status 接口，确认绑定后自动结束。返回 true 表示仍在等待用户确认。
 */
async function checkAuthStatus(): Promise<boolean> {
  if (!authPending.value) return false;
  try {
    const s = await api.get<LarkStatus>('/settings/lark/status');
    larkStatus.value = s;
    // 后台任务进行中 → 继续等待
    if (s.auth_pending) return true;
    // 后台任务已完成但失败
    if (s.auth_error) {
      stopPolling();
      authPending.value = null;
      emit('showToast', s.auth_error || '飞书授权失败，请重新发起授权');
      return false;
    }
    // 后台任务完成并已自动绑定
    if (s.bound) {
      stopPolling();
      authPending.value = null;
      authDone.value = true;
      emit('showToast', '飞书授权成功');
      return false;
    }
    // 兜底：任务结束但未绑定
    stopPolling();
    authPending.value = null;
    emit('showToast', '飞书授权未完成，请重新发起授权');
    return false;
  } catch (e: any) {
    emit('showToast', e.message || '查询飞书授权状态失败');
    return false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (!authPending.value) return;
    // device_code 有效期已过 → 停止等待
    if (Date.now() - authPending.value.startedAt > authPending.value.expires_in * 1000) {
      stopPolling();
      authPending.value = null;
      emit('showToast', '授权链接已过期，请重新发起授权');
      return;
    }
    await checkAuthStatus();
  }, 3000);
}

async function completeAuth() {
  if (!authPending.value) return;
  authCompleting.value = true;
  try {
    const stillPending = await checkAuthStatus();
    if (stillPending) {
      emit('showToast', '授权进行中，请在浏览器完成确认');
    }
  } finally {
    authCompleting.value = false;
  }
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function cancelAuth() {
  stopPolling();
  authPending.value = null;
  authDone.value = false;
}

function copyText(text: string) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(
      () => emit('showToast', '已复制到剪贴板'),
      () => emit('showToast', '复制失败'),
    );
  } else {
    emit('showToast', '当前浏览器不支持复制');
  }
}

function tokenStatusTag(s: string): { tone: 'green' | 'yellow' | 'red' | 'gray'; label: string } {
  switch (s) {
    case 'valid': return { tone: 'green', label: '有效' };
    case 'needs_refresh': return { tone: 'yellow', label: '即将过期' };
    case 'invalid': return { tone: 'red', label: '已失效' };
    case 'expired': return { tone: 'red', label: '已过期' };
    default: return { tone: 'gray', label: s || '未知' };
  }
}

function formatExpires(sec: number): string {
  if (sec >= 60) return `${Math.round(sec / 60)} 分钟`;
  return `${sec} 秒`;
}

/* ── 打开时按 Tab 加载数据 ── */
watch(() => props.isOpen, (open) => {
  if (!open) {
    cancelAuth();
    return;
  }
  if (activeTab.value === 'llm') loadLlm();
  if (activeTab.value === 'lark') loadLark();
});

watch(activeTab, (tab) => {
  if (!props.isOpen) return;
  if (tab === 'llm') loadLlm();
  if (tab === 'lark') loadLark();
});

onMounted(() => {
  const s = loadSettings();
  clusterName.value = s.clusterName;
  timeoutSec.value = s.timeoutSec;
  autoRetry.value = s.autoRetry;
  enableLiveLogs.value = s.enableLiveLogs;
});

onUnmounted(() => {
  stopPolling();
});

const handleSave = () => {
  persistSettings({
    clusterName: clusterName.value,
    timeoutSec: timeoutSec.value,
    autoRetry: autoRetry.value,
    enableLiveLogs: enableLiveLogs.value,
  });
  emit('showToast', '设置已保存');
  emit('close');
};
</script>

<template>
  <BaseDialog :open="isOpen" title="系统设置" :width="560" @close="emit('close')">
    <!-- Tab 切换 -->
    <div class="settings-tabs px-5 pt-4">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="settings-tab"
        :class="{ 'settings-tab--active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ═══ Tab 1：执行设置 ═══ -->
    <div v-if="activeTab === 'exec'" class="px-5 py-4 text-[13px]" style="color: var(--text-secondary);">
      <div class="mb-[16px]">
        <div class="text-[12px] font-semibold mb-[8px]" style="color: var(--text-primary);">并发数</div>
        <div class="flex items-center gap-[10px]">
          <button
            @click="timeoutSec = Math.max(1, timeoutSec - 1)"
            class="step-btn w-[26px] h-[26px] text-[14px] cursor-pointer"
          >
            −
          </button>
          <span class="text-[14px] font-semibold min-w-[24px] text-center" style="color: var(--text-primary);">{{ timeoutSec }}</span>
          <button
            @click="timeoutSec = Math.min(10, timeoutSec + 1)"
            class="step-btn w-[26px] h-[26px] text-[14px] cursor-pointer"
          >
            +
          </button>
          <span class="text-[11.5px]" style="color: var(--text-tertiary);">最多 10 个并发</span>
        </div>
      </div>

      <div>
        <div class="text-[12px] font-semibold mb-[8px]" style="color: var(--text-primary);">执行模式</div>
        <div class="flex gap-[8px]">
          <div
            @click="autoRetry = true"
            class="option-card flex-1 text-center px-2 py-[8px] text-[12.5px] cursor-pointer"
            :class="autoRetry ? 'option-card--active' : ''"
          >
            并发执行
          </div>
          <div
            @click="autoRetry = false"
            class="option-card flex-1 text-center px-2 py-[8px] text-[12.5px] cursor-pointer"
            :class="!autoRetry ? 'option-card--active' : ''"
          >
            顺序执行
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Tab 2：LLM 配置 ═══ -->
    <div v-else-if="activeTab === 'llm'" class="px-5 py-4 space-y-3">
      <p class="text-[11.5px]" style="color: var(--text-tertiary);">
        需求智能体（需求分析 / 评审 / Story 拆解 / 用例生成）将读取此处配置调用大模型。API key 仅保存在后端。
      </p>

      <div v-if="llmLoading" class="py-8 text-center text-[12.5px]" style="color: var(--text-muted);">加载中…</div>

      <template v-else>
        <div class="form-field">
          <label class="form-label">Provider（服务商）</label>
          <BaseInput v-model="provider" type="text" placeholder="deepseek / openai / ollama" />
        </div>
        <div class="form-field">
          <label class="form-label">API Base URL</label>
          <BaseInput v-model="apiBase" type="text" placeholder="https://api.example.com/v1" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="form-field">
            <label class="form-label">文本模型</label>
            <BaseInput v-model="textModel" type="text" placeholder="deepseek-chat" />
          </div>
          <div class="form-field">
            <label class="form-label">视觉模型</label>
            <BaseInput v-model="visionModel" type="text" placeholder="可选" />
          </div>
        </div>
        <div class="form-field">
          <label class="form-label">
            API Key
            <BaseTag v-if="hasKey" tone="green" size="sm" class="ml-2">已配置 {{ apiKeyMasked }}</BaseTag>
            <BaseTag v-else tone="gray" size="sm" class="ml-2">未配置</BaseTag>
          </label>
          <BaseInput v-model="apiKey" type="password" :placeholder="hasKey ? '留空则不修改已保存的 key' : '输入 API Key'" />
        </div>
      </template>
    </div>

    <!-- ═══ Tab 3：飞书授权 ═══ -->
    <div v-else class="px-5 py-4 space-y-3">
      <p class="text-[11.5px]" style="color: var(--text-tertiary);">
        授权飞书后，可在需求来源中提取飞书云文档内容。Token 生命周期由 lark-cli 管理，过期后可一键重新授权。
      </p>

      <div v-if="larkLoading" class="py-8 text-center text-[12.5px]" style="color: var(--text-muted);">加载中…</div>

      <template v-else>
        <!-- 状态区 -->
        <div class="lark-status-card px-3 py-3">
          <div class="flex items-center gap-2">
            <span class="text-[12px] font-semibold" style="color: var(--text-primary);">授权状态</span>
            <BaseTag v-if="larkStatus.auth_required" tone="red" size="sm" dot>未授权</BaseTag>
            <BaseTag v-else :tone="tokenStatusTag(larkStatus.token_status).tone" size="sm" dot>{{ tokenStatusTag(larkStatus.token_status).label }}</BaseTag>
          </div>
          <div v-if="!larkStatus.auth_required && larkStatus.lark_open_id" class="mt-2 text-[12px] space-y-0.5" style="color: var(--text-secondary);">
            <div>飞书 Open ID：<span style="color: var(--text-primary);">{{ larkStatus.lark_open_id }}</span></div>
            <div>Token 状态：{{ tokenStatusTag(larkStatus.token_status).label }}（{{ larkStatus.token_status }}）</div>
          </div>
          <div v-if="!larkStatus.cli_available" class="mt-2">
            <BaseTag tone="orange" size="sm">飞书 CLI 不可用，无法发起授权</BaseTag>
          </div>
          <div v-if="larkStatus.auth_required && larkStatus.bound" class="mt-2 text-[12px]" style="color: var(--color-warning);">
            已绑定但 Token 已过期/失效，请重新授权。
          </div>
          <div v-if="larkStatus.auth_error" class="mt-2 px-2 py-1.5 rounded" style="color: var(--color-warning); background-color: var(--warning-soft);">
            {{ larkStatus.auth_error }}
          </div>
        </div>

        <!-- 授权中 -->
        <div v-if="authPending" class="lark-status-card px-3 py-3 space-y-2">
          <div class="text-[12px] font-semibold" style="color: var(--text-primary);">请在浏览器中完成授权</div>
          <div class="text-[12px]">
            <span style="color: var(--text-secondary);">验证链接：</span>
            <a
              :href="authPending.verification_url"
              target="_blank"
              rel="noopener"
              class="underline"
              style="color: var(--cta); word-break: break-all;"
            >{{ authPending.verification_url }}</a>
            <button class="copy-link-btn ml-2" @click="copyText(authPending.verification_url)">复制</button>
          </div>
          <div class="text-[12px]" style="color: var(--text-secondary);">
            Device Code：<span style="color: var(--text-primary); font-family: var(--font-mono);">{{ authPending.device_code }}</span>
            <button class="copy-link-btn ml-2" @click="copyText(authPending.device_code)">复制</button>
          </div>
          <div class="text-[11.5px]" style="color: var(--text-tertiary);">
            链接有效期 {{ formatExpires(authPending.expires_in) }}。在浏览器完成扫码/确认后，将自动完成绑定，也可点击下方按钮手动完成。
          </div>
          <div class="flex items-center gap-2 pt-1">
            <BaseButton variant="secondary" size="sm" :loading="authCompleting" @click="completeAuth">完成授权</BaseButton>
            <BaseButton variant="ghost" size="sm" @click="cancelAuth">取消</BaseButton>
          </div>
        </div>

        <!-- 授权成功提示 -->
        <div v-else-if="authDone" class="text-[12px]" style="color: var(--color-success);">
          授权已完成，可正常使用飞书文档提取。
        </div>

        <!-- 操作按钮 -->
        <div v-if="!authPending" class="flex items-center gap-2">
          <BaseButton
            variant="primary"
            :disabled="!larkStatus.cli_available"
            :loading="authStarting"
            @click="startAuth"
          >
            {{ larkStatus.auth_required ? (larkStatus.bound ? '重新授权' : '发起授权') : '重新授权' }}
          </BaseButton>
          <BaseButton v-if="!larkStatus.auth_required" variant="secondary" @click="loadLark">刷新状态</BaseButton>
        </div>
      </template>
    </div>

    <!-- Footer -->
    <template #footer>
      <template v-if="activeTab === 'exec'">
        <BaseButton variant="secondary" size="sm" @click="emit('close')">取消</BaseButton>
        <BaseButton variant="primary" size="sm" @click="handleSave">保存</BaseButton>
      </template>
      <template v-else-if="activeTab === 'llm'">
        <BaseButton variant="primary" size="sm" :loading="llmSaving" :disabled="llmLoading" @click="saveLlm">保存配置</BaseButton>
      </template>
    </template>
  </BaseDialog>
</template>

<style scoped>
/* ── Tab 胶囊 ── */
.settings-tabs {
  display: flex;
  gap: 4px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.settings-tab {
  padding: 6px 14px;
  border-radius: 10px;
  font-size: 12.5px;
  font-weight: 500;
  border: 2px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.settings-tab:hover {
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
}
.settings-tab--active {
  background-color: var(--color-primary);
  border-color: var(--outline);
  color: var(--text-primary);
  font-weight: 600;
  box-shadow: var(--shadow-hard-sm);
}
.settings-tab--active:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}

/* ── 表单字段 ── */
.form-field {
  margin-bottom: 12px;
}
.form-label {
  display: flex;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--text-secondary);
}

/* ── 飞书状态卡片 ── */
.lark-status-card {
  background-color: var(--card-bg-2);
  border: 2px solid var(--outline);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-hard-sm);
}
.copy-link-btn {
  padding: 2px 8px;
  border: 1.5px solid var(--outline);
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  background-color: var(--bg-soft);
  cursor: pointer;
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
}
.copy-link-btn:hover {
  transform: translate(1px, 1px);
  box-shadow: var(--shadow-hard-sm-pressed);
  color: var(--text-primary);
}

/* ── 步进按钮 / 选项卡片（沿用原执行设置样式） ── */
.step-btn {
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background-color: var(--card-bg-2);
  color: var(--text-primary);
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}
.step-btn:hover {
  background-color: var(--bg-card-hover);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.option-card {
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  background-color: var(--card-bg);
  box-shadow: var(--shadow-hard-sm);
  color: var(--text-secondary);
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.option-card:hover {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.option-card--active {
  border-color: var(--color-primary);
  background-color: var(--color-primary-soft);
  color: var(--text-primary);
  font-weight: 600;
}
</style>
