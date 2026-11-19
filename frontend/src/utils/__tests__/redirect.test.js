// @vitest-environment jsdom
/**
 * 登录回跳地址安全测试。
 *
 * 只允许站内绝对路径；协议、域名、协议相对 URL、反斜杠、登录/注册页
 * 以及编码绕过都必须被拒绝。
 */
import { describe, expect, it } from 'vitest'
import {
  loginLocation,
  resolvePostLoginPath,
  safeRedirectPath,
} from '../redirect.js'

describe('safeRedirectPath', () => {
  it('允许站内路径，并保留 query/hash', () => {
    expect(safeRedirectPath('/admin/meetings?tab=1#top')).toBe('/admin/meetings?tab=1#top')
    expect(safeRedirectPath('/meetings')).toBe('/meetings')
  })

  it('拒绝站外和协议 URL', () => {
    expect(safeRedirectPath('//evil.com')).toBe('')
    expect(safeRedirectPath('https://evil.com')).toBe('')
    expect(safeRedirectPath('http://evil.com/x')).toBe('')
    expect(safeRedirectPath('javascript:alert(1)')).toBe('')
  })

  it('拒绝反斜杠和编码绕过', () => {
    expect(safeRedirectPath('/\\evil.com')).toBe('')
    expect(safeRedirectPath('/%2F%2Fevil.com')).toBe('')
    expect(safeRedirectPath('/%5Cevil.com')).toBe('')
  })

  it('拒绝登录/注册页，避免循环', () => {
    expect(safeRedirectPath('/login')).toBe('')
    expect(safeRedirectPath('/register')).toBe('')
    expect(safeRedirectPath('/forgot-password')).toBe('')
  })

  it('拒绝空值和非字符串', () => {
    expect(safeRedirectPath('')).toBe('')
    expect(safeRedirectPath(null)).toBe('')
    expect(safeRedirectPath(undefined)).toBe('')
  })
})

describe('loginLocation / resolvePostLoginPath', () => {
  it('生成登录页回跳参数', () => {
    expect(loginLocation('/admin/meetings')).toEqual({
      path: '/login',
      query: { redirect: '/admin/meetings' },
    })
  })

  it('非法回跳地址回落仪表盘', () => {
    expect(resolvePostLoginPath('https://evil.com')).toBe('/dashboard')
    expect(resolvePostLoginPath('/login')).toBe('/dashboard')
    expect(resolvePostLoginPath('/meetings')).toBe('/meetings')
  })
})
