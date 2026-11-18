<template>
  <Transition name="cw-update">
    <div v-if="visible" class="update-banner" role="status" aria-live="polite">
      <span class="update-banner__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 12a8 8 0 1 1-2.34-5.66" />
          <path d="M20 4v4h-4" />
        </svg>
      </span>
      <span class="update-banner__text">站点已更新，刷新页面以使用最新版本</span>
      <button type="button" class="update-banner__refresh" @click="refresh">立即刷新</button>
      <button type="button" class="update-banner__close" aria-label="稍后提醒" title="稍后提醒" @click="dismiss">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
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
  gap: 12px;
  width: max-content;
  max-width: min(620px, calc(100vw - 32px));
  padding: 12px 20px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  color: #333;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  transform: translateX(-50%);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
}

.update-banner__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.08);
  box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.2);
  animation: update-banner-breathe 2.4s ease-in-out infinite;
}

.update-banner__icon svg {
  width: 16px;
  height: 16px;
}

.update-banner__text {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #333;
}

.update-banner__refresh {
  flex: 0 0 auto;
  padding: 6px 12px;
  border: 1px solid rgba(37, 99, 235, 0.32);
  border-radius: 6px;
  background: transparent;
  color: #2563eb;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;
}

.update-banner__refresh:hover {
  border-color: rgba(37, 99, 235, 0.55);
  background: rgba(37, 99, 235, 0.08);
}

.update-banner__refresh:active {
  background: rgba(37, 99, 235, 0.14);
}

.update-banner__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  margin: 0 -6px 0 0;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #9aa0a6;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.update-banner__close svg {
  width: 15px;
  height: 15px;
}

.update-banner__close:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #4b5563;
}

/* 顶部下滑 + 轻微回弹，避免生硬闪现 */
.cw-update-enter-active {
  transition: opacity 0.28s ease, transform 0.38s cubic-bezier(0.22, 1.2, 0.36, 1);
}

.cw-update-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.cw-update-enter-from {
  opacity: 0;
  transform: translate(-50%, -14px) scale(0.97);
}

.cw-update-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px) scale(0.98);
}

@keyframes update-banner-breathe {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.18);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.06);
  }
}

html[data-theme='dark'] .update-banner {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(28, 28, 30, 0.85);
  color: #f5f5f7;
}

html[data-theme='dark'] .update-banner__text {
  color: #f5f5f7;
}

html[data-theme='dark'] .update-banner__icon {
  color: #64a8ff;
  background: rgba(100, 168, 255, 0.14);
}

html[data-theme='dark'] .update-banner__refresh {
  border-color: rgba(100, 168, 255, 0.4);
  color: #64a8ff;
}

html[data-theme='dark'] .update-banner__refresh:hover {
  border-color: rgba(100, 168, 255, 0.65);
  background: rgba(100, 168, 255, 0.12);
}

html[data-theme='dark'] .update-banner__close {
  color: #8e8e93;
}

html[data-theme='dark'] .update-banner__close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #f5f5f7;
}

@media (max-width: 640px) {
  .update-banner {
    top: calc(var(--header-h, 56px) + 10px);
    width: calc(100vw - 24px);
    gap: 10px;
    padding: 10px 14px;
  }

  .update-banner__text {
    font-size: 13px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .update-banner__icon {
    animation: none;
  }

  .cw-update-enter-active,
  .cw-update-leave-active {
    transition: opacity 0.2s ease;
  }
}
</style>
