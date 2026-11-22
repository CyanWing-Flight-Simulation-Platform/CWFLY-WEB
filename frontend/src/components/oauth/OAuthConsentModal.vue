<script setup>
/**
 * 第三方 OAuth 授权确认弹窗
 *
 * 视觉：单栏纵向流式排版，靠留白与字重分层；毛玻璃卡片 + 极细描边 + 弥散阴影。
 * 不使用图标 / Emoji / 装饰边框；全部颜色取自主题 token（--ui-* / --c-* / --glass-*）。
 *
 * 用法：
 *   <OAuthConsentModal
 *     v-model:open="visible"
 *     app-name="ATC 管制员中心"
 *     app-origin="atc.cwflysim.cn"
 *     user-name="CW-1234"
 *     cid="1234"
 *     :scopes="['用户名', 'CID', '权限等级']"
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
      // 焦点落在对话框本身：屏幕阅读器直接朗读标题，按钮也不会一出现就带高亮框
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
            <ul class="oc-fields">
              <li v-for="label in scopeLabels" :key="label" class="oc-field">{{ label }}</li>
              <li v-if="!scopeLabels.length" class="oc-field">基本账户信息</li>
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
                class="oc-btn oc-btn--primary"
                :disabled="loading"
                @click="approve"
              >{{ loading ? '处理中' : '同意授权' }}</button>
              <button
                type="button"
                class="oc-btn oc-btn--ghost"
                :disabled="loading"
                @click="deny"
              >拒绝</button>
            </div>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.oc-card {
  --oc-hairline: var(--ui-divider, rgba(15, 23, 42, .06));
}

.oc-overlay {
  position: fixed;
  inset: 0;
  z-index: 3200;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--ui-overlay, rgba(15, 23, 42, .35));
  backdrop-filter: blur(14px) saturate(130%);
  -webkit-backdrop-filter: blur(14px) saturate(130%);
}

.oc-card {
  width: min(508px, 100%);
  max-height: min(88vh, 760px);
  overflow: auto;
  padding: 34px 34px 26px;
  border: 1px solid var(--ui-dialog-border, rgba(15, 23, 42, .1));
  border-radius: 26px;
  background: var(--ui-dialog-bg, rgba(255, 255, 255, .88));
  box-shadow:
    var(--glass-shadow-lg, 0 18px 56px rgba(0, 0, 0, .16)),
    inset 0 1px 0 color-mix(in srgb, #fff 55%, transparent);
  backdrop-filter: blur(30px) saturate(180%);
  -webkit-backdrop-filter: blur(30px) saturate(180%);
  color: var(--ui-text, #111827);
  outline: none;
}

/* ---------- 头部 ---------- */
.oc-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.oc-app {
  margin: 0;
  font-size: 25px;
  font-weight: 700;
  line-height: 1.22;
  letter-spacing: -.022em;
  color: var(--ui-text, #111827);
  word-break: break-word;
}
.oc-sub {
  margin: 0;
  font-size: 12.5px;
  font-weight: 400;
  line-height: 1.6;
  color: var(--ui-text-muted, #9ca3af);
}

/* ---------- 权限字段：无边框网格 ---------- */
.oc-scopes {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 30px;
}
.oc-cap {
  margin: 0;
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: .16em;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 22px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.oc-field {
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.45;
  letter-spacing: .005em;
  color: var(--ui-text, #111827);
  word-break: break-word;
}

/* ---------- 风险提示：纯文本 + 极细柔和竖线 ---------- */
.oc-warn {
  margin: 28px 0 0;
  padding: 1px 0 1px 13px;
  border-left: 2px solid color-mix(in srgb, var(--c-warning) 62%, transparent);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.8;
  color: var(--ui-text-secondary, #6b7280);
}

/* ---------- 底部 ---------- */
.oc-foot {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 30px;
  padding-top: 18px;
  border-top: 1px solid var(--oc-hairline);
}
.oc-account {
  margin: 0;
  font-size: 10.5px;
  letter-spacing: .02em;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.oc-btn {
  height: 36px;
  padding: 0 18px;
  border-radius: 10px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .01em;
  cursor: pointer;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease, filter .18s ease;
}
.oc-btn:disabled {
  opacity: .55;
  cursor: default;
}

/* 主按钮：带细腻光影过渡的品牌渐变 */
.oc-btn--primary {
  border: 1px solid color-mix(in srgb, var(--c-primary-dark) 55%, transparent);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--c-primary) 86%, #fff 14%) 0%,
    var(--c-primary) 52%,
    var(--c-primary-dark) 100%
  );
  color: #fff;
  box-shadow:
    0 1px 2px color-mix(in srgb, var(--c-primary-dark) 32%, transparent),
    inset 0 1px 0 color-mix(in srgb, #fff 34%, transparent);
}
.oc-btn--primary:hover:not(:disabled) {
  filter: brightness(1.05);
  box-shadow:
    0 3px 12px color-mix(in srgb, var(--c-primary) 30%, transparent),
    inset 0 1px 0 color-mix(in srgb, #fff 34%, transparent);
}
.oc-btn--primary:active:not(:disabled) {
  filter: brightness(.97);
  box-shadow: inset 0 1px 3px color-mix(in srgb, var(--c-primary-dark) 45%, transparent);
}
.oc-btn--primary:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--c-primary) 55%, transparent);
  outline-offset: 3px;
}

/* 次按钮：纯文字幽灵按钮，层级明显更低 */
.oc-btn--ghost {
  border: 1px solid transparent;
  background: transparent;
  color: var(--ui-text-muted, #9ca3af);
  font-weight: 500;
}
.oc-btn--ghost:hover:not(:disabled) {
  background: var(--ui-ghost-bg, rgba(15, 23, 42, .05));
  color: var(--ui-text-secondary, #6b7280);
}
.oc-btn--ghost:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--ui-text-muted, #9ca3af) 55%, transparent);
  outline-offset: 3px;
}

/* ---------- 入场动效 ---------- */
.oc-enter-active,
.oc-leave-active { transition: opacity .2s ease; }
.oc-enter-active .oc-card,
.oc-leave-active .oc-card {
  transition: transform .26s cubic-bezier(.22, 1, .36, 1), opacity .26s ease;
}
.oc-enter-from,
.oc-leave-to { opacity: 0; }
.oc-enter-from .oc-card,
.oc-leave-to .oc-card { opacity: 0; transform: translateY(9px) scale(.99); }

/* ---------- 窄屏 ---------- */
@media (max-width: 560px) {
  .oc-overlay { padding: 14px; }
  .oc-card {
    padding: 26px 22px 20px;
    border-radius: 20px;
  }
  .oc-app { font-size: 21px; }
  .oc-fields { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .oc-scopes { margin-top: 24px; }
  .oc-warn { margin-top: 22px; }
  .oc-foot { margin-top: 24px; }
  .oc-actions { justify-content: stretch; }
  .oc-btn { flex: 1 1 auto; }
}

@media (prefers-reduced-motion: reduce) {
  .oc-enter-active .oc-card,
  .oc-leave-active .oc-card { transition: none; }
  .oc-enter-from .oc-card,
  .oc-leave-to .oc-card { transform: none; }
}
</style>
