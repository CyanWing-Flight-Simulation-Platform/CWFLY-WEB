<script setup>
/**
 * 第三方 OAuth 授权确认弹窗（按产品给定的最终视觉规范实现，参数不做改动）
 *
 * scopes 支持两种写法：
 *   ['用户名', 'CID']                    → 右侧数据列显示「可读取」
 *   [{ label: '用户名', value: 'CW-1' }] → 右侧数据列显示具体值
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  /** 是否打开（配合 v-model:open） */
  open: { type: Boolean, default: false },
  /** 请求方应用名（头部大字） */
  appName: { type: String, required: true },
  /** 请求方域（副标题里附带展示，可空） */
  appOrigin: { type: String, default: '' },
  /** 当前登录用户名 */
  userName: { type: String, default: '' },
  /** 当前登录 CID */
  cid: { type: [String, Number], default: '' },
  /** 请求读取的字段 */
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

const permRows = computed(() =>
  (props.scopes || [])
    .map((item) => {
      if (typeof item === 'string') return { label: item, value: '可读取' }
      if (!item || !item.label) return null
      return { label: item.label, value: item.value || '可读取' }
    })
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
          <h2 id="oc-title" class="oc-title">{{ appName }}</h2>
          <p id="oc-desc" class="oc-subtitle">
            正在请求访问您的 {{ productName }} 账户<template v-if="appOrigin"> · {{ appOrigin }}</template>
          </p>

          <ul class="oc-perms">
            <li v-for="row in permRows" :key="row.label" class="oc-perm">
              <span class="oc-perm__label">{{ row.label }}</span>
              <span class="oc-perm__value">{{ row.value }}</span>
            </li>
            <li v-if="!permRows.length" class="oc-perm">
              <span class="oc-perm__label">账户信息</span>
              <span class="oc-perm__value">可读取</span>
            </li>
          </ul>

          <p class="oc-warn">
            授权后，该应用可在有效期内持续读取上述字段。请仅对您信任的应用授权；若非本人操作，请选择拒绝。
          </p>

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
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ============================================================
   双主题：浅色为默认（白玻璃），html[data-theme='dark'] 覆盖为深色。
   所有颜色集中在本文件顶部变量里，规则只引用变量。
   ============================================================ */
.oc-overlay,
.oc-card {
  /* ---- 浅色（默认）---- */
  --oc-overlay: rgba(15, 23, 42, 0.28);
  --oc-card-bg: rgba(255, 255, 255, 0.72);
  --oc-card-border: rgba(15, 23, 42, 0.08);
  --oc-card-shadow: 0 24px 48px rgba(15, 23, 42, 0.16);
  --oc-card-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  --oc-title: #111113;
  --oc-subtitle: #52525b;
  --oc-label: #71717a;
  --oc-value: #18181b;
  --oc-warn-text: #3f3f46;
  --oc-account: #71717a;
  --oc-rule: rgba(245, 158, 11, 0.55);
  --oc-primary-bg: #18181b;
  --oc-primary-text: #ffffff;
  --oc-primary-shadow: 0 1px 2px rgba(15, 23, 42, 0.18);
  --oc-ghost: #71717a;
  --oc-ghost-hover: #27272a;
  --oc-focus: rgba(24, 24, 27, 0.35);
  --oc-focus-ghost: rgba(113, 113, 122, 0.4);
}

html[data-theme='dark'] .oc-overlay,
html[data-theme='dark'] .oc-card {
  /* ---- 暗黑 ---- */
  --oc-overlay: rgba(0, 0, 0, 0.35);
  --oc-card-bg: rgba(20, 20, 25, 0.85);
  --oc-card-border: rgba(255, 255, 255, 0.08);
  --oc-card-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
  --oc-card-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.06);
  --oc-title: #ffffff;
  --oc-subtitle: #a1a1aa;
  --oc-label: #71717a;
  --oc-value: #ffffff;
  --oc-warn-text: #a1a1aa;
  --oc-account: #71717a;
  --oc-rule: rgba(245, 158, 11, 0.5);
  --oc-primary-bg: #ffffff;
  --oc-primary-text: #000000;
  --oc-primary-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
  --oc-ghost: #a1a1aa;
  --oc-ghost-hover: #d4d4d8;
  --oc-focus: rgba(255, 255, 255, 0.45);
  --oc-focus-ghost: rgba(161, 161, 170, 0.45);
}

.oc-overlay {
  position: fixed;
  inset: 0;
  z-index: 3200;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--oc-overlay);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.oc-card {
  width: min(512px, 100%);
  max-height: min(88vh, 760px);
  overflow: auto;
  background: var(--oc-card-bg);
  backdrop-filter: blur(32px) saturate(180%);
  -webkit-backdrop-filter: blur(32px) saturate(180%);
  border: 1px solid var(--oc-card-border);
  border-radius: 20px;
  padding: 40px;
  box-shadow: var(--oc-card-shadow), var(--oc-card-highlight);
  outline: none;
}

/* 大标题 */
.oc-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -.01em;
  color: var(--oc-title);
  word-break: break-word;
}

/* 副标题 */
.oc-subtitle {
  margin: 0 0 32px;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.6;
  color: var(--oc-subtitle);
  word-break: break-word;
}

/* 权限列表：两列纯文字 */
.oc-perms {
  margin: 0;
  padding: 0;
  list-style: none;
}
.oc-perm {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  column-gap: 24px;
  align-items: baseline;
  line-height: 2;
}
.oc-perm__label {
  font-size: 12px;
  color: var(--oc-label);
}
.oc-perm__value {
  font-size: 14px;
  color: var(--oc-value);
  word-break: break-word;
}

/* 风险提示：仅一根柔和竖线 */
.oc-warn {
  margin: 24px 0 0;
  padding-left: 12px;
  border-left: 2px solid var(--oc-rule);
  font-size: 12px;
  line-height: 1.8;
  color: var(--oc-warn-text);
}

/* 当前账户 */
.oc-account {
  margin: 20px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--oc-account);
}

/* 按钮区 */
.oc-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 24px;
}

.oc-btn {
  font-family: inherit;
  font-size: 14px;
  line-height: 1.2;
  padding: 10px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: opacity .15s ease, background .15s ease, color .15s ease;
}
.oc-btn:disabled {
  opacity: .5;
  cursor: default;
}

/* 主按钮：主题反色（浅色黑底白字 / 暗黑白底黑字） */
.oc-btn--primary {
  background: var(--oc-primary-bg);
  color: var(--oc-primary-text);
  font-weight: 600;
  box-shadow: var(--oc-primary-shadow);
}
.oc-btn--primary:hover:not(:disabled) {
  opacity: .9;
}
.oc-btn--primary:focus-visible {
  outline: 2px solid var(--oc-focus);
  outline-offset: 2px;
}

/* 次按钮：纯文字幽灵按钮 */
.oc-btn--ghost {
  background: transparent;
  color: var(--oc-ghost);
  font-weight: 500;
}
.oc-btn--ghost:hover:not(:disabled) {
  color: var(--oc-ghost-hover);
}
.oc-btn--ghost:focus-visible {
  outline: 2px solid var(--oc-focus-ghost);
  outline-offset: 2px;
}

/* 动效 */
.oc-enter-active,
.oc-leave-active { transition: opacity .18s ease; }
.oc-enter-active .oc-card,
.oc-leave-active .oc-card {
  transition: transform .22s cubic-bezier(.22, 1, .36, 1), opacity .22s ease;
}
.oc-enter-from,
.oc-leave-to { opacity: 0; }
.oc-enter-from .oc-card,
.oc-leave-to .oc-card { opacity: 0; transform: translateY(8px) scale(.99); }

@media (max-width: 560px) {
  .oc-overlay { padding: 14px; }
  .oc-card { padding: 28px 22px; }
  .oc-title { font-size: 21px; }
  .oc-subtitle { margin-bottom: 24px; }
  .oc-perm { column-gap: 16px; }
}

@media (prefers-reduced-motion: reduce) {
  .oc-enter-active .oc-card,
  .oc-leave-active .oc-card { transition: none; }
  .oc-enter-from .oc-card,
  .oc-leave-to .oc-card { transform: none; }
}
</style>