/* global __CWFLY_BUILD_ID__ */
import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 站点更新提示
 *
 * 构建时 Vite 会写入 /version.json（buildId），并把同一个值注入
 * __CWFLY_BUILD_ID__。已打开的页面定时拉取 version.json：
 * buildId 与当前页面不一致时显示刷新提示。
 */
const CURRENT_BUILD_ID = typeof __CWFLY_BUILD_ID__ === 'string' ? __CWFLY_BUILD_ID__ : ''
const CHECK_INTERVAL_MS = 120000
const DISMISS_KEY = 'cw_update_dismissed_build'

export function useUpdatePrompt() {
  const visible = ref(false)
  const latestBuild = ref('')
  let timer = null
  let checking = false

  async function checkForUpdate() {
    if (checking || !import.meta.env.PROD || !CURRENT_BUILD_ID) return
    checking = true
    try {
      const res = await fetch(`/version.json?ts=${Date.now()}`, { cache: 'no-store' })
      if (!res.ok) return
      const data = await res.json()
      const buildId = String(data?.buildId || '')
      if (!buildId || buildId === CURRENT_BUILD_ID) return
      if (sessionStorage.getItem(DISMISS_KEY) === buildId) return
      latestBuild.value = buildId
      visible.value = true
    } catch {
      // 网络异常时静默，下一轮再试
    } finally {
      checking = false
    }
  }

  function refresh() {
    window.location.reload()
  }

  function dismiss() {
    if (latestBuild.value) {
      sessionStorage.setItem(DISMISS_KEY, latestBuild.value)
    }
    visible.value = false
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'visible') checkForUpdate()
  }

  onMounted(() => {
    checkForUpdate()
    timer = window.setInterval(checkForUpdate, CHECK_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', onVisibilityChange)
  })

  onUnmounted(() => {
    if (timer) window.clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('focus', onVisibilityChange)
  })

  return { visible, latestBuild, refresh, dismiss }
}
