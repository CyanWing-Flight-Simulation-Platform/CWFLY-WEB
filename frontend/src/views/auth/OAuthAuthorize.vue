<template>
  <div class="auth-page">
    <div class="auth-card card p-lg" style="text-align:center;">
      <div class="auth-logo" style="font-size:24px;font-weight:800;color:var(--c-primary);margin-bottom:8px;">CWFLY</div>
      <p class="text-muted mb-lg">授权登录 ATC 管制员中心</p>

      <!-- 已有登录状态：需用户显式确认才授权(2026-10-25 审计 P0-2: 此前打开页面即自动携 token 跳转) -->
      <div v-if="checking" class="text-sm text-muted">验证登录状态...</div>
      <div v-else-if="token && !granted" class="mt-lg">
        <p class="mb-md text-sm">即将向 <b>{{ appOrigin }}</b> 授权您的 CWFLY 登录凭证。</p>
        <p class="mb-lg text-sm text-muted">请在弹出的授权确认窗口中核对信息后确认。</p>
        <button class="btn btn-block" @click="requestConsent">重新打开授权确认</button>
      </div>

      <!-- 未登录：显示登录表单 -->
      <form v-else-if="!token" @submit.prevent="handleLogin">
        <div class="mb-md">
          <label class="text-sm font-bold mb-sm" style="display:block;">CID</label>
          <input v-model="form.cid" class="input" placeholder="4位数字 CID" maxlength="4" required />
        </div>
        <div class="mb-md">
          <label class="text-sm font-bold mb-sm" style="display:block;">密码</label>
          <input v-model="form.password" class="input" type="password" placeholder="输入密码" required />
        </div>
        <div v-if="err" class="error-banner mb-md"><span>{{ err }}</span></div>
        <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
          {{ loading ? '登录中...' : '登录并授权' }}
        </button>
      </form>

      <!-- 跳转中 -->
      <div v-else class="text-sm text-success">授权成功，正在跳转...</div>
    </div>

    <!-- 第三方授权确认弹窗（自研 Modal，无图标无表情） -->
    <OAuthConsentModal
      v-model:open="consentOpen"
      app-name="ATC 管制员中心"
      :app-origin="appOrigin"
      :user-name="accountName"
      :cid="accountCid"
      :scopes="consentScopes"
      @approve="grant"
      @deny="cancel"
      @close="cancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authApi } from '@/api/index.js'
import OAuthConsentModal from '@/components/oauth/OAuthConsentModal.vue'

const route = useRoute()
const router = useRouter()
const token = ref('')
const checking = ref(true)
const loading = ref(false)
const err = ref('')
const granted = ref(false)

// 授权确认弹窗状态
const consentOpen = ref(false)
const accountName = ref('')
const accountCid = ref('')
// 本次授权将交给第三方读取的字段（左列字段名 / 右列数据）
const consentScopes = computed(() => [
  { label: '用户名', value: accountName.value || '可读取' },
  { label: 'CID', value: accountCid.value || '可读取' },
  { label: '权限等级', value: '可读取' },
  { label: '登录凭证', value: '可读取' },
])

function requestConsent() {
  consentOpen.value = true
}

function grant() {
  granted.value = true
  const redirect = getRedirectUri()
  window.location.href = `${redirect}?token=${encodeURIComponent(token.value)}`
}
function cancel() {
  consentOpen.value = false
  router.push('/')
}
const form = ref({ cid: '', password: '' })

// 受信任的重定向地址白名单
const ALLOWED_REDIRECTS = [
  'http://localhost:5176/oauth/callback',
  'http://localhost:5173/oauth/callback',
  'https://cwflysim.cn/oauth/callback',
  'https://atc.cwflysim.cn/oauth/callback',
  'https://www.cwflysim.cn/oauth/callback',
]

function getRedirectUri() {
  const uri = route.query.redirect_uri || route.query.redirect || ''
  // 仅允许白名单中的地址
  if (ALLOWED_REDIRECTS.includes(uri)) return uri
  return 'http://localhost:5176/oauth/callback'
}

/** 展示给用户核对的第三方域（不含完整回调地址，避免误导） */
const appOrigin = computed(() => {
  try {
    return new URL(getRedirectUri()).host || getRedirectUri()
  } catch {
    return getRedirectUri()
  }
})

/** 从本地缓存的登录用户里取展示名与 CID */
function readAccount() {
  try {
    const raw = localStorage.getItem('cw_user')
    const user = raw ? JSON.parse(raw) : null
    if (!user) return
    accountName.value = user.username || `CID ${user.cid ?? ''}`.trim()
    accountCid.value = user.cid ?? ''
  } catch {
    /* 本地缓存损坏时留空，弹窗会退化为只显示 CID */
  }
}

onMounted(async () => {
  readAccount()
  // Cookie 会话无法被 JS 读取；已登录时向服务端换取一枚仅用于本次 OAuth 跳转的 token
  if (localStorage.getItem('cw_auth') === '1') {
    try {
      const res = await authApi.refresh()
      token.value = res.data?.token || ''
    } catch { /* 未登录或过期，展示登录表单 */ }
  }
  checking.value = false
  // 已登录：直接弹出确认框，用户核对后再放行
  if (token.value) consentOpen.value = true
})

async function handleLogin() {
  if (!form.value.cid || !form.value.password) { err.value = '请填写 CID 和密码'; return }
  loading.value = true; err.value = ''
  try {
    const res = await authApi.login({ cid: form.value.cid, password: form.value.password })
    token.value = res.data.token
    localStorage.setItem('cw_user', JSON.stringify(res.data.user))
    localStorage.setItem('cw_auth', '1')
    // 登录成功后不再自动跳转，统一走授权确认弹窗
    readAccount()
    consentOpen.value = true
  } catch (e) { err.value = e.message || '登录失败' }
  finally { loading.value = false }
}
</script>
