<script setup>
/**
 * 第三方 OAuth 授权确认弹窗
 *
 * 视觉：单栏纵向流式，留白与字重分层；毛玻璃 + 极细描边 + 弥散阴影。
 * 无图标 / Emoji / 装饰线框；颜色全部来自主题 token（--ui-* / --c-* / --glass-*）。
 *
 * 用法：
 *   <OAuthConsentModal
 *     v-model:open="visible"
 *     app-name="Dubhe Nexus"
 *     app-origin="merak.dubhenexus.io"
 *     user-name="CW-2048"
 *     cid="2048"
 *     :scopes="['用户名', 'CID', '邮箱', '飞行时长']"
 *     @approve="onApprove"
 *     @deny="onDeny"
 *     @close="onClose"
 *   />
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  /** 是否打开（配合 v-model:open） */
  open: { type: Boolean, default: false },
  /** 请求方应用名（头部大字） */
  appName: { type: String, required: true },
  /** 请求方域（头部小字副标题，可空） */
  appOrigin: { type: String, default: '' },
  /** 当前登录用户名 */
  userName: { type: String, default: '' },
  /** 当前登录 CID */
  cid: { type: [String, Number], default: '' },
  /** 请求读取的字段（纯文本标签数组，也接受 { label } 对象） */
  scopes: { type: Array, default: () => [] },
  /** 被访问的产品名 */
  productName: { type: String, default: 'CWFLY' },
  /** 提交中：禁用两个按钮 */
  loading: { type: Boolean, default: false },
  /** 点遮罩 / 按 Esc 是否关闭 */
  dismissible: { type: Boolean, default: true },
})

const emit = defineEmits(['update:open', 'approve', 'deny', 'close'])

const cardRef = ref(null)
let lastActive = null
let lockedScroll = false

const scopeLabels = computed(() =>
  (props.scopes || [])
    .map((item) => (typeof item === 'string' ? item : item?.label || ''))
    .filter(Boolean),
)

const accountLine = computed(() => {
  const name = props.userName || (props.cid ? `CID ${props.cid}` : '')
  return props.cid ? `${name} (${props.cid})` : name
})

function lockScroll() {
  if (lockedScroll) return
  lockedScroll = true
  lastActive = document.activeElement
  document.body.style.overflow = 'hidden'
  document.addEventListener('keydown', onKeydown, true)
}

function unlockScroll() {
  if (!lockedScroll) return
  lockedScroll = false
  document.body.style.overflow = ''
  document.removeEventListener('keydown', onKeydown, true)
  const previous = lastActive
  lastActive = null
  if (previous && previous !== document.body && document.contains(previous)) {
    previous.focus?.({ preventScroll: true })
  }
}

function close() {
  emit('update:open', false)
  emit('close')
}

function approve() {
  if (props.loading) return
  emit('approve')
  close()
}

function deny() {
  if (props.loading) return
  emit('deny')
  close()
}

/** 焦点限制在卡片内，避免 Tab 逃逸到背后的页面 */
function onKeydown(event) {
  if (event.key === 'Escape') {
    if (!props.dismissible) return
    event.preventDefault()
    event.stopPropagation()
    deny()
    return
  }
  if (event.key !== 'Tab') return
  const root = cardRef.value
  if (!root) return
  const items = Array.from(
    root.querySelectorAll('button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'),
  ).filter((node) => node.getClientRects().length > 0)
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      lockScroll()
      nextTick(() => cardRef.value?.focus({ preventScroll: true }))
    } else {
      unlockScroll()
    }
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(unlockScroll)
</script>

<template>
  <Teleport to="body">
    <Transition name="oc">
      <div v-if="open" class="oc-overlay" @click.self="dismissible && deny()">
        <section
          ref="cardRef"
          class="oc-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="oc-title"
          aria-describedby="oc-desc"
          tabindex="-1"
        >
          <header class="oc-head">
            <h2 id="oc-title" class="oc-app">{{ appName }}</h2>
            <p id="oc-desc" class="oc-sub">
              正在请求访问您的 {{ productName }} 账户<template v-if="appOrigin"> · {{ appOrigin }}</template>
            </p>
          </header>

          <section class="oc-scopes" aria-labelledby="oc-scopes-cap">
            <p id="oc-scopes-cap" class="oc-cap">将读取以下字段</p>
            <ul class="oc-tags">
              <li v-for="label in scopeLabels" :key="label" class="oc-tag">{{ label }}</li>
              <li v-if="!scopeLabels.length" class="oc-tag">基本账户信息</li>
            </ul>
          </section>

          <p class="oc-warn">
            授权后，该应用可在有效期内持续读取上述字段。请仅对您信任的应用授权；若非本人操作，请选择拒绝。
          </p>

          <footer class="oc-foot">
            <p class="oc-account">当前授权账户：{{ accountLine }}</p>
            <div class="oc-actions">
              <button
                type="button"
                class="oc-btn oc-btn--ghost"
                :disabled="loading"
                @click="deny"
              >拒绝</button>
              <button
                type="button"
                class="oc-btn oc-btn--primary"
                :disabled="loading"
                @click="approve"
              >{{ loading ? '处理中' : '同意授权' }}</button>
            </div>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.oc-overlay {
  position: fixed;
  inset: 0;
  z-index: 3200;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--ui-overlay, rgba(15, 23, 42, .35));
  backdrop-filter: blur(16px) saturate(120%);
  -webkit-backdrop-filter: blur(16px) saturate(120%);
}

/* ---------- 卡片：毛玻璃 + 极细描边 + 弥散阴影 ---------- */
.oc-card {
  width: min(452px, 100%);
  max-height: min(88vh, 760px);
  overflow: auto;
  padding: 30px 28px 22px;
  border: 1px solid var(--ui-dialog-border, rgba(15, 23, 42, .1));
  border-radius: 18px;
  background: var(--ui-dialog-bg, rgba(255, 255, 255, .88));
  box-shadow: var(--glass-shadow-lg, 0 18px 56px rgba(0, 0, 0, .16));
  backdrop-filter: blur(28px) saturate(170%);
  -webkit-backdrop-filter: blur(28px) saturate(170%);
  color: var(--ui-text, #111827);
  outline: none;
}

/* ---------- 头部 ---------- */
.oc-head {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.oc-app {
  margin: 0;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -.02em;
  color: var(--ui-text, #111827);
  word-break: break-word;
}
.oc-sub {
  margin: 0;
  font-size: 12.5px;
  font-weight: 400;
  line-height: 1.55;
  color: var(--ui-text-muted, #9ca3af);
}

/* ---------- 权限：无边框胶囊 ---------- */
.oc-scopes {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 26px;
}
.oc-cap {
  margin: 0;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.oc-tag {
  padding: 4px 9px;
  border-radius: 7px;
  background: color-mix(in srgb, var(--ui-text, #111827) 5%, transparent);
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: .005em;
  color: var(--ui-text-secondary, #6b7280);
  word-break: break-word;
}

/* ---------- 风险提示：一根柔和竖线 + 极浅底 ---------- */
.oc-warn {
  margin: 24px 0 0;
  padding: 9px 12px;
  border-left: 2px solid color-mix(in srgb, var(--c-warning) 58%, transparent);
  border-radius: 0 6px 6px 0;
  background: color-mix(in srgb, var(--ui-text, #111827) 4%, transparent);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.7;
  color: var(--ui-text-secondary, #6b7280);
}

/* ---------- 底部 ---------- */
.oc-foot {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 26px;
}
.oc-account {
  margin: 0;
  font-size: 11px;
  font-weight: 400;
  letter-spacing: .01em;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.oc-btn {
  height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: .01em;
  cursor: pointer;
  transition: background .16s ease, color .16s ease, opacity .16s ease, transform .16s ease;
}
.oc-btn:disabled {
  opacity: .5;
  cursor: default;
}

/* 主按钮：主题反色纯色（浅色→近黑底白字；暗黑→白底近黑字） */
.oc-btn--primary {
  background: var(--ui-text, #111827);
  color: var(--ui-dialog-bg, #ffffff);
  font-weight: 600;
  box-shadow: 0 1px 2px color-mix(in srgb, var(--ui-text, #111827) 14%, transparent);
}
.oc-btn--primary:hover:not(:disabled) {
  opacity: .88;
}
.oc-btn--primary:active:not(:disabled) {
  transform: translateY(.5px);
  opacity: .82;
}
.oc-btn--primary:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--ui-text, #111827) 40%, transparent);
  outline-offset: 2px;
}

/* 次按钮：纯灰字幽灵 */
.oc-btn--ghost {
  background: transparent;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-btn--ghost:hover:not(:disabled) {
  background: color-mix(in srgb, var(--ui-text, #111827) 5%, transparent);
  color: var(--ui-text-secondary, #6b7280);
}
.oc-btn--ghost:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--ui-text-muted, #9ca3af) 45%, transparent);
  outline-offset: 2px;
}

/* ---------- 动效 ---------- */
.oc-enter-active,
.oc-leave-active { transition: opacity .18s ease; }
.oc-enter-active .oc-card,
.oc-leave-active .oc-card {
  transition: transform .24s cubic-bezier(.22, 1, .36, 1), opacity .24s ease;
}
.oc-enter-from,
.oc-leave-to { opacity: 0; }
.oc-enter-from .oc-card,
.oc-leave-to .oc-card { opacity: 0; transform: translateY(8px) scale(.99); }

/* ---------- 窄屏 ---------- */
@media (max-width: 560px) {
  .oc-overlay { padding: 14px; }
  .oc-card {
    padding: 24px 20px 18px;
    border-radius: 16px;
  }
  .oc-app { font-size: 22px; }
  .oc-scopes { margin-top: 22px; }
  .oc-warn { margin-top: 20px; }
  .oc-foot { margin-top: 22px; }
}

@media (prefers-reduced-motion: reduce) {
  .oc-enter-active .oc-card,
  .oc-leave-active .oc-card { transition: none; }
  .oc-enter-from .oc-card,
  .oc-leave-to .oc-card { transform: none; }
}
</style>
