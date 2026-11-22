<script setup>
/**
 * 第三方 OAuth 授权确认弹窗
 *
 * 设计要点（不复用任何现成模板）：
 *  - 左右分栏：左侧竖向品牌栏（纯排版，无图标），右侧为授权正文
 *  - 权限字段用「虚线边框网格 + 极细竖线 + 小圆点」纯文本呈现
 *  - 风险提示用极细警示色描边 + 左侧 2px 纯 CSS 竖线标记，无感叹号无底色块
 *  - 全部颜色来自主题 token（--ui-* / --c-* / --glass-*），浅色/暗黑自动切换
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
      // 焦点落在对话框本身：屏幕阅读器直接朗读标题与说明，
      // 同时避免按钮一出现就带一圈高亮描边（视觉噪音）
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
          <div class="oc-split">
            <!-- 左：竖向品牌栏 -->
            <aside class="oc-rail" aria-hidden="true">
              <span class="oc-rail__brand">{{ productName }}</span>
              <span class="oc-rail__rule" />
              <span class="oc-rail__label">授权确认</span>
            </aside>

            <!-- 右：正文 -->
            <div class="oc-main">
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

              <aside class="oc-warn">
                <p class="oc-warn__text">
                  授权后，该应用可在有效期内持续读取上述字段。请仅对您信任的应用授权；若非本人操作，请选择拒绝。
                </p>
              </aside>

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
            </div>
          </div>
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
  padding: 28px;
  background: var(--ui-overlay, rgba(15, 23, 42, .35));
  backdrop-filter: blur(10px) saturate(120%);
  -webkit-backdrop-filter: blur(10px) saturate(120%);
}

.oc-card {
  width: min(760px, 100%);
  max-height: min(88vh, 720px);
  overflow: auto;
  border: 1px solid var(--ui-dialog-border, rgba(15, 23, 42, .1));
  border-radius: 26px;
  background: var(--ui-dialog-bg, rgba(255, 255, 255, .88));
  box-shadow: var(--glass-shadow-lg, 0 18px 56px rgba(0, 0, 0, .16)), var(--glass-highlight, none);
  backdrop-filter: blur(26px) saturate(160%);
  -webkit-backdrop-filter: blur(26px) saturate(160%);
  color: var(--ui-text, #111827);
  outline: none;
}

/* ---------- 左右分栏 ---------- */
.oc-split {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
}

.oc-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 34px 0 30px;
  border-right: 1px solid var(--ui-divider, rgba(15, 23, 42, .06));
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--c-primary) 10%, transparent) 0%,
    transparent 62%
  );
}
.oc-rail__brand {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: .34em;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--c-primary) 78%, var(--ui-text, #111827));
}
.oc-rail__rule {
  width: 1px;
  flex: 1;
  min-height: 34px;
  background: var(--ui-divider, rgba(15, 23, 42, .06));
}
.oc-rail__label {
  writing-mode: vertical-rl;
  letter-spacing: .28em;
  font-size: 10.5px;
  color: var(--ui-text-muted, #9ca3af);
}

.oc-main {
  min-width: 0;
  padding: 34px 38px 30px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* ---------- 头部声明 ---------- */
.oc-head { display: flex; flex-direction: column; gap: 7px; }
.oc-app {
  margin: 0;
  font-size: 27px;
  font-weight: 800;
  line-height: 1.18;
  letter-spacing: -.018em;
  color: var(--ui-text, #111827);
  word-break: break-word;
}
.oc-sub {
  margin: 0;
  font-size: 12px;
  font-weight: 400;
  letter-spacing: .01em;
  color: var(--ui-text-muted, #9ca3af);
}

/* ---------- 权限字段：虚线网格 + 极细竖线 + 圆点 ---------- */
.oc-scopes { display: flex; flex-direction: column; gap: 10px; }
.oc-cap {
  margin: 0;
  font-size: 10.5px;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px dashed var(--ui-dialog-border, rgba(15, 23, 42, .14));
  border-radius: 14px;
  overflow: hidden;
}
.oc-field {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 13px 16px;
  font-size: 13px;
  line-height: 1.3;
  color: var(--ui-text-secondary, #6b7280);
  word-break: break-word;
}
.oc-field::before {
  content: '';
  flex: 0 0 auto;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--c-primary) 62%, var(--ui-text-muted, #9ca3af));
}
/* 极细竖线：偶数列左侧 */
.oc-field:nth-child(even) {
  border-left: 1px solid var(--ui-divider, rgba(15, 23, 42, .06));
}
/* 第二行起加横线 */
.oc-field:nth-child(n + 3) {
  border-top: 1px solid var(--ui-divider, rgba(15, 23, 42, .06));
}

/* ---------- 风险提示：极细描边 + 纯 CSS 竖线 ---------- */
.oc-warn {
  position: relative;
  padding: 12px 16px 12px 20px;
  border: 1px solid color-mix(in srgb, var(--c-warning) 32%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--c-warning) 4%, transparent);
}
.oc-warn::before {
  content: '';
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: 8px;
  width: 2px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--c-warning) 72%, transparent);
}
.oc-warn__text {
  margin: 0;
  font-size: 12px;
  line-height: 1.75;
  color: color-mix(in srgb, var(--c-warning) 58%, var(--ui-text, #111827));
}

/* ---------- 底部 ---------- */
.oc-foot {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 2px;
}
.oc-account {
  margin: 0;
  font-size: 10.5px;
  letter-spacing: .02em;
  color: var(--ui-text-muted, #9ca3af);
}
.oc-actions {
  display: flex;
  align-items: stretch;
  gap: 10px;
}
.oc-btn {
  height: 44px;
  padding: 0 22px;
  border-radius: 12px;
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: .01em;
  cursor: pointer;
  transition: filter .18s ease, background .18s ease, border-color .18s ease, color .18s ease;
}
.oc-btn:disabled { opacity: .55; cursor: default; }

.oc-btn--primary {
  flex: 1 1 58%;
  border: 1px solid transparent;
  background: linear-gradient(
    135deg,
    var(--c-primary) 0%,
    color-mix(in srgb, var(--c-primary-dark) 88%, var(--ui-text, #111827)) 100%
  );
  color: #fff;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--c-primary) 22%, transparent);
}
.oc-btn--primary:hover:not(:disabled) { filter: brightness(1.06); }
.oc-btn--primary:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

.oc-btn--ghost {
  flex: 0 0 auto;
  min-width: 104px;
  border: 1px solid var(--ui-ghost-border, rgba(15, 23, 42, .12));
  background: var(--ui-ghost-bg, rgba(15, 23, 42, .05));
  color: var(--ui-text-secondary, #6b7280);
}
.oc-btn--ghost:hover:not(:disabled) {
  background: var(--ui-ghost-hover, rgba(15, 23, 42, .09));
  color: var(--ui-text, #111827);
}
.oc-btn--ghost:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

/* ---------- 入场动效 ---------- */
.oc-enter-active,
.oc-leave-active { transition: opacity .2s ease; }
.oc-enter-active .oc-card,
.oc-leave-active .oc-card { transition: transform .24s cubic-bezier(.22, 1, .36, 1), opacity .24s ease; }
.oc-enter-from,
.oc-leave-to { opacity: 0; }
.oc-enter-from .oc-card,
.oc-leave-to .oc-card { opacity: 0; transform: translateY(10px) scale(.985); }

/* ---------- 窄屏：分栏折叠为竖向条 ---------- */
@media (max-width: 640px) {
  .oc-overlay { padding: 14px; }
  .oc-card { border-radius: 20px; }
  .oc-split { grid-template-columns: minmax(0, 1fr); }
  .oc-rail {
    flex-direction: row;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-right: 0;
    border-bottom: 1px solid var(--ui-divider, rgba(15, 23, 42, .06));
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--c-primary) 10%, transparent) 0%,
      transparent 70%
    );
  }
  .oc-rail__brand,
  .oc-rail__label { writing-mode: horizontal-tb; }
  .oc-rail__rule { width: auto; height: 1px; flex: 1; min-height: 0; }
  .oc-main { padding: 22px 20px 22px; gap: 18px; }
  .oc-app { font-size: 22px; }
  .oc-fields { grid-template-columns: minmax(0, 1fr); }
  .oc-field:nth-child(even) { border-left: 0; }
  .oc-field:nth-child(n + 2) { border-top: 1px solid var(--ui-divider, rgba(15, 23, 42, .06)); }
  .oc-field:nth-child(2) { border-top: 0; }
  .oc-btn--ghost { min-width: 88px; padding: 0 16px; }
}

@media (prefers-reduced-motion: reduce) {
  .oc-enter-active .oc-card,
  .oc-leave-active .oc-card { transition: none; }
  .oc-enter-from .oc-card,
  .oc-leave-to .oc-card { transform: none; }
}
</style>
