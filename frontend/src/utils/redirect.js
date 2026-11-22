/**
 * 登录回跳地址白名单。
 *
 * 只接受本站内部的绝对路径（以单个 / 开头），拒绝协议、域名、协议相对 URL、
 * 反斜杠和登录/注册页自身，避免开放重定向。
 */
const AUTH_PATHS = new Set(['/login', '/register', '/forgot-password'])

export function safeRedirectPath(raw) {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string') return ''
  const text = value.trim()
  if (!text || text.length > 2048) return ''
  if (text.includes('\\')) return ''
  if (!text.startsWith('/') || text.startsWith('//')) return ''

  try {
    const url = new URL(text, window.location.origin)
    if (url.origin !== window.location.origin) return ''
    const decodedPath = decodeURIComponent(url.pathname)
    if (!decodedPath.startsWith('/') || decodedPath.startsWith('//')) return ''
    if (decodedPath.includes('\\')) return ''
    if (AUTH_PATHS.has(decodedPath)) return ''
    return url.pathname + url.search + url.hash
  } catch {
    return ''
  }
}

export function loginLocation(fullPath = '') {
  const redirect = safeRedirectPath(fullPath)
  return redirect ? { path: '/login', query: { redirect } } : { path: '/login' }
}

export function resolvePostLoginPath(raw) {
  return safeRedirectPath(raw) || '/dashboard'
}

/**
 * 登录成功后的跳转。
 *
 * 普通站内路径走 Vue Router；`/api/...` 是后端直出页面（如 OAuth2 授权页
 * `/api/oauth/authorize`），必须整页跳转，否则会被前端路由当成 404。
 */
export function applyPostLoginPath(router, raw) {
  const path = resolvePostLoginPath(raw)
  if (path.startsWith('/api/')) {
    window.location.assign(path)
    return
  }
  router.replace(path)
}
