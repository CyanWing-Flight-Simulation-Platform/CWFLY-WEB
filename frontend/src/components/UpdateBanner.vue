<template>
  <Transition name="cw-update">
    <div v-if="visible" class="update-banner" role="status" aria-live="polite">
      <span class="update-banner__dot" aria-hidden="true"></span>
      <span class="update-banner__text">站点已更新，刷新页面以使用最新版本</span>
      <button type="button" class="update-banner__refresh" @click="refresh">立即刷新</button>
      <button type="button" class="update-banner__close" aria-label="稍后提醒" title="稍后提醒" @click="dismiss">×</button>
    </div>
  </Transition>
</template>

<script setup>
import { useUpdatePrompt } from '@/composables/useUpdatePrompt'

const { visible, refresh, dismiss } = useUpdatePrompt()
</script>

<style scoped>
.update-banner {
  position: fixed;
  top: calc(var(--header-h, 60px) + 14px);
  left: 50%;
  z-index: 3000;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: min(680px, calc(100vw - 32px));
  padding: 10px 12px 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 12px;
  background: rgba(22, 28, 40, 0.94);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.28);
  color: #fff;
  transform: translateX(-50%);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.update-banner__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.18);
}

.update-banner__text {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.5;
}

.update-banner__refresh {
  flex: 0 0 auto;
  padding: 6px 12px;
  border: 0;
  border-radius: 8px;
  background: #fff;
  color: #101828;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.update-banner__refresh:hover {
  opacity: 0.86;
}

.update-banner__close {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: rgba(255, 255, 255, 0.72);
  font-size: 18px;
  line-height: 22px;
  cursor: pointer;
}

.update-banner__close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.cw-update-enter-active,
.cw-update-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.cw-update-enter-from,
.cw-update-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

@media (max-width: 640px) {
  .update-banner {
    top: calc(var(--header-h, 56px) + 10px);
    gap: 8px;
    padding: 9px 10px 9px 12px;
  }

  .update-banner__text {
    font-size: 12px;
  }
}
</style>
