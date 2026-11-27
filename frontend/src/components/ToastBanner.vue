<template>
  <TransitionGroup name="toast" tag="div" class="toast-stack" aria-live="polite">
    <div
      v-for="item in toastState.items"
      :key="item.id"
      class="toast-card"
      :class="'toast-card--' + item.type"
      role="status"
      @click="removeToast(item.id)"
    >
      <span class="toast-card__icon" aria-hidden="true">
        <svg v-if="item.type === 'success'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="9" /><path d="m8 12 2.6 2.6L16.5 8.7" />
        </svg>
        <svg v-else-if="item.type === 'error'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5" /><path d="M12 16.5h.01" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 7.5h.01" />
        </svg>
      </span>
      <span class="toast-card__message">{{ item.message }}</span>
      <button class="toast-card__close" type="button" aria-label="关闭提示" @click.stop="removeToast(item.id)">×</button>
    </div>
  </TransitionGroup>
</template>

<script setup>
import { removeToast, toastState } from '@/utils/banner'
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: calc(var(--header-h, 60px) + 14px);
  left: 50%;
  z-index: 3000;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: max-content;
  max-width: min(620px, calc(100vw - 32px));
  transform: translateX(-50%);
  pointer-events: none;
}

.toast-card {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  width: max-content;
  max-width: min(620px, calc(100vw - 32px));
  padding: 11px 10px 11px 12px;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 10px;
  background: rgba(17, 24, 39, .94);
  box-shadow: 0 12px 32px rgba(0, 0, 0, .28);
  color: #f8fafc;
  pointer-events: auto;
  cursor: pointer;
  backdrop-filter: blur(16px) saturate(130%);
  -webkit-backdrop-filter: blur(16px) saturate(130%);
}
.toast-card--success { --toast-accent: #34d399; }
.toast-card--error { --toast-accent: #f87171; }
.toast-card--info { --toast-accent: #60a5fa; }

.toast-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--toast-accent);
}
.toast-card__icon svg { width: 18px; height: 18px; }
.toast-card__message {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}
.toast-card__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--c-text-muted, #6b7280);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}
.toast-card__close:hover { background: rgba(255, 255, 255, .1); color: #fff; }

.toast-enter-active,
.toast-leave-active { transition: opacity .2s ease, transform .2s ease; }
.toast-enter-from { opacity: 0; transform: translateY(-8px); }
.toast-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
