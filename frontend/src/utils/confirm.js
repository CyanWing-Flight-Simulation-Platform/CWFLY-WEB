/**
 * 自研二次确认弹层。
 * 用法：if (!(await confirmDialog('确定删除？'))) return
 * 或：  if (!(await confirmDialog({ title, message, confirmText }))) return
 */
const STYLE_ID = 'cw-confirm-dialog-style'

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
.cw-confirm-overlay{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(15,23,42,.34);backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);animation:cwConfirmIn .16s ease both}
.cw-confirm-box{width:100%;max-width:420px;padding:22px 22px 18px;border:1px solid var(--glass-border-strong,rgba(15,23,42,.08));border-radius:16px;background:var(--glass-bg-strong,#fff);box-shadow:0 22px 60px rgba(15,23,42,.22);color:var(--c-text,#111827);animation:cwConfirmPop .18s cubic-bezier(.22,1,.36,1) both}
.cw-confirm-head{display:flex;align-items:flex-start;gap:12px}
.cw-confirm-icon{display:flex;align-items:center;justify-content:center;width:34px;height:34px;flex:0 0 auto;border-radius:10px;background:rgba(220,38,38,.09);color:#dc2626}
.cw-confirm-box.is-info .cw-confirm-icon{background:rgba(37,99,235,.09);color:#2563eb}
.cw-confirm-icon svg{width:18px;height:18px}
.cw-confirm-title{flex:1;min-width:0;margin-top:2px;font-size:15px;font-weight:700;line-height:1.5}
.cw-confirm-message{margin:12px 0 0;color:var(--c-text-secondary,#6b7280);font-size:13px;line-height:1.75;white-space:pre-wrap;word-break:break-word}
.cw-confirm-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:22px}
.cw-confirm-btn{height:34px;padding:0 16px;border:1px solid transparent;border-radius:8px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s ease,border-color .15s ease}
.cw-confirm-btn--cancel{border-color:rgba(15,23,42,.10);background:rgba(15,23,42,.04);color:var(--c-text,#111827)}
.cw-confirm-btn--cancel:hover{background:rgba(15,23,42,.08)}
.cw-confirm-btn--ok{background:#dc2626;color:#fff}
.cw-confirm-btn--ok:hover{background:#b91c1c}
.cw-confirm-box.is-info .cw-confirm-btn--ok{background:#2563eb}
.cw-confirm-box.is-info .cw-confirm-btn--ok:hover{background:#1d4ed8}
html[data-theme='dark'] .cw-confirm-box{border-color:rgba(255,255,255,.10);background:rgba(15,23,42,.98);color:#f8fafc}
html[data-theme='dark'] .cw-confirm-message{color:#94a3b8}
html[data-theme='dark'] .cw-confirm-btn--cancel{border-color:rgba(255,255,255,.12);background:rgba(255,255,255,.06);color:#f8fafc}
html[data-theme='dark'] .cw-confirm-btn--cancel:hover{background:rgba(255,255,255,.10)}
@keyframes cwConfirmIn{from{opacity:0}to{opacity:1}}
@keyframes cwConfirmPop{from{opacity:0;transform:translateY(8px) scale(.97)}to{opacity:1;transform:none}}
@media (max-width:480px){.cw-confirm-box{padding:18px 16px 14px}.cw-confirm-actions{margin-top:18px}}
`
  document.head.appendChild(style)
}

export function confirmDialog(options = {}) {
  const opts = typeof options === 'string' ? { message: options } : (options || {})
  const {
    title = '请确认操作',
    message = '',
    confirmText = '确定',
    cancelText = '取消',
    tone = 'danger'
  } = opts
  ensureStyle()
  return new Promise((resolve) => {
    const overlay = document.createElement('div')
    overlay.className = 'cw-confirm-overlay'

    const box = document.createElement('div')
    box.className = 'cw-confirm-box' + (tone === 'info' ? ' is-info' : '')
    box.setAttribute('role', 'dialog')
    box.setAttribute('aria-modal', 'true')

    const head = document.createElement('div')
    head.className = 'cw-confirm-head'
    const icon = document.createElement('span')
    icon.className = 'cw-confirm-icon'
    icon.innerHTML = tone === 'info'
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3 2.8 19a1.6 1.6 0 0 0 1.4 2.4h15.6a1.6 1.6 0 0 0 1.4-2.4z"/><path d="M12 9v4.5M12 17h.01"/></svg>'
    const titleEl = document.createElement('div')
    titleEl.className = 'cw-confirm-title'
    titleEl.textContent = title
    head.append(icon, titleEl)

    const msgEl = document.createElement('div')
    msgEl.className = 'cw-confirm-message'
    msgEl.textContent = message

    const actions = document.createElement('div')
    actions.className = 'cw-confirm-actions'
    const cancelBtn = document.createElement('button')
    cancelBtn.type = 'button'
    cancelBtn.className = 'cw-confirm-btn cw-confirm-btn--cancel'
    cancelBtn.textContent = cancelText
    const okBtn = document.createElement('button')
    okBtn.type = 'button'
    okBtn.className = 'cw-confirm-btn cw-confirm-btn--ok'
    okBtn.textContent = confirmText
    actions.append(cancelBtn, okBtn)

    box.append(head, msgEl, actions)
    overlay.append(box)
    document.body.appendChild(overlay)

    const close = (value) => {
      document.removeEventListener('keydown', onKey)
      overlay.remove()
      resolve(value)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') close(false)
      if (e.key === 'Enter') close(true)
    }
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(false)
    })
    cancelBtn.addEventListener('click', () => close(false))
    okBtn.addEventListener('click', () => close(true))
    document.addEventListener('keydown', onKey)
    requestAnimationFrame(() => okBtn.focus())
  })
}
