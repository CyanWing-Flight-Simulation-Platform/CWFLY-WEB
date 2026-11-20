// ===== 全局 Toast 通知 =====
// 原「右上角红色横幅」已统一改为轻量 Toast：
//   import { showToast, showBanner } from '@/utils/banner'
//   showToast('保存成功', { type: 'success' })
//   showBanner('登录已过期，请重新登录')  // 兼容旧调用，自动按文案推断类型
import { reactive } from 'vue'
import { safeRedirectPath } from '@/utils/redirect'

export const toastState = reactive({
  items: []
})

// 保留给登录过期跳转逻辑读取时长
export const bannerState = reactive({
  visible: false,
  message: '',
  duration: 3000,
  key: 0
})

let seq = 0
const timers = new Map()

function inferType(message) {
  const text = String(message || '')
  if (/失败|错误|异常|过期|不存在|不可|无法|请先|请输入|请选择|封禁|拒绝|未授权|超时/.test(text)) return 'error'
  if (/成功|已保存|已更新|已提交|已恢复|已删除|已添加|已完成/.test(text)) return 'success'
  return 'info'
}

export function removeToast(id) {
  const index = toastState.items.findIndex((item) => item.id === id)
  if (index >= 0) toastState.items.splice(index, 1)
  const timer = timers.get(id)
  if (timer) {
    clearTimeout(timer)
    timers.delete(id)
  }
}

export function showToast(message, opts = {}) {
  const text = String(message ?? '')
  if (!text) return 0
  // 同一文案已在展示时只保留一条，避免重复请求/双击导致两个完全相同的 Toast
  const active = toastState.items.find((item) => item.message === text)
  if (active) {
    const oldTimer = timers.get(active.id)
    if (oldTimer) clearTimeout(oldTimer)
    const duration = Math.max(1200, Number(opts.duration) || 3200)
    timers.set(active.id, setTimeout(() => removeToast(active.id), duration))
    return active.id
  }
  const duration = Math.max(1200, Number(opts.duration) || 3200)
  const item = {
    id: ++seq,
    message: text,
    type: opts.type || inferType(text),
    duration
  }
  toastState.items.push(item)
  // 最多同时保留 4 条，避免刷屏
  while (toastState.items.length > 4) {
    removeToast(toastState.items[0].id)
  }
  timers.set(item.id, setTimeout(() => removeToast(item.id), duration))
  return item.id
}

/** 兼容旧调用：showBanner 现在等价于 showToast。 */
export function showBanner(message, opts = {}) {
  bannerState.message = String(message ?? '')
  bannerState.duration = Math.max(1000, Number(opts.duration) || 3000)
  bannerState.key += 1
  bannerState.visible = true
  return showToast(message, { ...opts, duration: bannerState.duration })
}

export function hideBanner(id) {
  bannerState.visible = false
  if (id) {
    removeToast(id)
    return
  }
  toastState.items.forEach((item) => removeToast(item.id))
}

/**
 * 等提示完整展示后再跳转登录页。
 */
export function navigateToLoginAfterBanner(navigate, redirectPath = '') {
  const delay = Math.max(1000, bannerState.duration || 3000) + 300
  setTimeout(() => {
    if (window.location.pathname.startsWith('/login')) return
    const redirect = safeRedirectPath(redirectPath)
    const target = redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'
    if (typeof navigate === 'function') {
      navigate(target)
    } else {
      window.location.href = target
    }
  }, delay)
}

/** @deprecated 保留旧导出名 */
export const hideToast = hideBanner
