<script setup lang="ts">
defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 flex items-center justify-center z-50 p-4" style="background-color: var(--overlay-bg);">
    <div 
      class="help-panel w-[380px] max-w-[90vw] overflow-hidden"
    >
      <div 
        class="flex items-center justify-between px-[18px] py-[14px] border-b"
        style="border-color: var(--border);"
      >
        <h3 class="help-title">使用帮助</h3>
        <button 
          @click="emit('close')" 
          class="cursor-pointer text-[15px]"
          style="color: var(--text-tertiary);"
        >
          ✕
        </button>
      </div>

      <div class="px-[18px] py-[16px] text-[13px]" style="color: var(--text-secondary);">
        <div class="mb-[14px]">
          <div class="text-[12.5px] font-semibold mb-[3px]" style="color: var(--text-primary);">自动化</div>
          <div class="text-[12px] leading-[1.6]">左侧按模块/类/用例查看测试目录树，可按 API / UI 类型筛选，勾选后点击「执行选中」运行。</div>
        </div>

        <div class="mb-[14px]">
          <div class="text-[12.5px] font-semibold mb-[3px]" style="color: var(--text-primary);">测试执行</div>
          <div class="text-[12px] leading-[1.6]">实时查看任务执行进度、状态统计与每条用例的详细结果，可随时停止正在运行的任务。</div>
        </div>

        <div>
          <div class="text-[12.5px] font-semibold mb-[3px]" style="color: var(--text-primary);">测试报告</div>
          <div class="text-[12px] leading-[1.6]">查看历史执行报告，包含通过率、耗时和分层展开的用例结果详情。</div>
        </div>
      </div>

      <div 
        class="flex justify-end px-[18px] py-[12px] border-t"
        style="border-color: var(--border);"
      >
        <button 
          @click="emit('close')" 
          class="help-btn px-4 py-1.5 text-sm font-medium rounded cursor-pointer"
        >
          知道了
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Claymorphism：弹窗面板（3px 硬描边 + 硬阴影 + 柔和投影） ── */
.help-panel {
  background-color: var(--card-bg);
  border: 3px solid var(--outline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-hard-lg), var(--shadow-dialog);
}

/* ── Claymorphism：弹窗标题 ── */
.help-title {
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Claymorphism：主 CTA 按钮（绿） ── */
.help-btn {
  background-color: var(--cta);
  color: #fff;
  border: 2px solid var(--outline);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-hard-sm);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease, filter 0.15s ease;
}
.help-btn:hover {
  background-color: var(--cta-dark);
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-sm-pressed);
}
.help-btn:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--outline);
}
</style>