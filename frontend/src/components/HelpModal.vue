<script setup lang="ts">
defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 flex items-center justify-center z-50 p-4" style="background: rgba(0,0,0,.32);">
    <div 
      class="w-[380px] max-w-[90vw] rounded-[14px] border overflow-hidden"
      style="background-color: var(--card-bg); border-color: var(--border); box-shadow: 0 20px 50px rgba(0,0,0,.3);"
    >
      <div 
        class="flex items-center justify-between px-[18px] py-[14px] border-b"
        style="border-color: var(--border);"
      >
        <h3 class="text-[15px] font-semibold" style="color: var(--text-primary);">使用帮助</h3>
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
          <div class="text-[12.5px] font-semibold mb-[3px]" style="color: var(--text-primary);">用例总览</div>
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
          class="px-4 py-1.5 text-sm font-medium rounded cursor-pointer transition-colors"
          style="background-color: var(--accent); border-color: var(--accent); color: #fff;"
        >
          知道了
        </button>
      </div>
    </div>
  </div>
</template>