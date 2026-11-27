<template>
  <div class="auth-page">
    <div class="auth-card card p-lg">
      <div class="text-center mb-lg">
        <router-link to="/portal" class="auth-logo">CWFLY</router-link>
        <p class="text-muted mt-sm">登录您的账号</p>
      </div>

      <form @submit.prevent="handleLogin" novalidate>
        <FormField
          label="CID" required for-id="login-cid"
          :error="fb.errors.cid" :shake="fb.shaking.cid"
          @animationend="fb.shaking.cid = false"
        >
          <input
            id="login-cid" v-model="form.cid" class="input"
            inputmode="numeric" maxlength="4" placeholder="4 位数字 CID"
            autocomplete="username webauthn" aria-required="true"
            :aria-invalid="!!fb.errors.cid" @input="fb.input('cid')"
          />
        </FormField>

        <FormField
          label="密码" required for-id="login-pwd"
          :error="fb.errors.password" :shake="fb.shaking.password"
          @animationend="fb.shaking.password = false"
        >
          <input
            id="login-pwd" v-model="form.password" class="input"
            type="password" placeholder="输入密码" autocomplete="current-password"
            aria-required="true" :aria-invalid="!!fb.errors.password" @input="fb.input('password')"
          />
        </FormField>

        <div class="forgot-row">
          <router-link to="/forgot-password" class="forgot-link">忘记密码？</router-link>
        </div>

        <div v-if="err" class="alert alert-err">{{ err }}</div>

        <SubmitButton :status="status" label="登 录" @settle="status = 'idle'" />

        <button
          type="button"
          class="btn btn-outline btn-block mt-sm"
          :disabled="passkeyLoading"
          @click="loginWithPasskey"
        >
          {{ passkeyLoading ? '正在唤起 Passkey…' : '使用 Passkey 登录' }}
        </button>
        <p v-if="passkeyErr" class="text-xs mt-sm" style="color:var(--c-danger);text-align:center;">{{ passkeyErr }}</p>

        <!-- 新设备/IP 登录二次验证：果冻弹出邮箱验证码框 -->
        <div v-if="showVerify" class="verify-wrap">
          <div class="verify-box">
            <p class="text-sm text-muted mb-sm">
              检测到新设备/IP 登录，为保障账号安全，请通过邮箱验证码确认身份
              <b>{{ maskedEmail }}</b>
            </p>
            <div class="flex gap-sm mb-sm">
              <input v-model="verifyCode" class="input" placeholder="输入6位邮箱验证码" maxlength="6" autocomplete="one-time-code" style="flex:1;" />
              <button type="button" class="btn btn-outline btn-sm" @click="sendLoginCode" :disabled="sendingCode || codeCooldown > 0">
                {{ codeCooldown > 0 ? codeCooldown + 's' : sendingCode ? '发送中...' : '发送验证码' }}
              </button>
            </div>
            <button type="button" class="btn btn-primary btn-block" @click="confirmLoginVerify" :disabled="verifying">
              {{ verifying ? '验证中...' : '验证并登录' }}
            </button>
            <p v-if="verifyErr" class="text-xs mt-sm" style="color:var(--c-danger);">{{ verifyErr }}</p>
          </div>
        </div>
      </form>

      <div class="text-center mt-md text-sm text-muted">
        还没有账号？ <router-link to="/register">立即注册</router-link>
      </div>
      <p class="text-xs mt-sm text-muted" style="line-height:1.7;text-align:center;">
        登录即表示你已阅读并同意
        <router-link to="/user-agreement">《用户协议》</router-link> 与
        <router-link to="/privacy-policy">《隐私政策》</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { authApi } from '@/api'
import { getDeviceFp } from '@/utils/deviceFp'
import { waitForPowToken } from '@/utils/pow'
import { useFieldFeedback } from '@/utils/fieldFeedback'
import { applyPostLoginPath } from '@/utils/redirect'
import { getPasskey } from '@/utils/passkey'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const postLoginPath = () => applyPostLoginPath(router, route.query.redirect)
const form = ref({ cid: '', password: '' })
const err = ref('')
const status = ref('idle')
const fb = useFieldFeedback(['cid', 'password'])
let successTimer = null

// ===== 新设备/IP 登录二次验证（邮箱验证码）=====
const showVerify = ref(false)   // 验证码框是否显示（果冻弹出）
const verifyEmail = ref('')     // 账号完整邮箱（用于发送验证码）
const verifyCode = ref('')      // 用户输入的邮箱验证码
const loginChallenge = ref('')  // 后端签发的一次性登录挑战（绑定 CID/IP）
const sendingCode = ref(false)
const codeCooldown = ref(0)
const verifying = ref(false)
const verifyErr = ref('')
let cooldownTimer = null

const passkeyLoading = ref(false)
const passkeyErr = ref('')

/** 脱敏邮箱用于展示，如 ab***@x.com */
const maskedEmail = computed(() => {
  const e = verifyEmail.value
  if (!e || !e.includes('@')) return ''
  const [name, domain] = e.split('@')
  return (name.slice(0, 2) + '***@' + domain)
})

async function handleLogin() {
  if (status.value !== 'idle') return
  err.value = ''
  fb.clearAll()
  if (!/^\d{4}$/.test(String(form.value.cid || '').trim())) {
    fb.fail('cid', '请输入 4 位数字 CID')
    return
  }
  if (!form.value.password) {
    fb.fail('password', '请输入密码')
    return
  }
  status.value = 'loading'
  try {
    const res = await userStore.login(form.value.cid, form.value.password)
    // 新 IP 登录：后端要求邮箱验证码二次验证（不返回 token）
    if (res && res.needVerify) {
      status.value = 'idle'
      verifyEmail.value = res.email || ''
      loginChallenge.value = res.loginChallenge || ''
      showVerify.value = true
      verifyErr.value = ''
      sendLoginCode()
      return
    }
    status.value = 'success'
    successTimer = setTimeout(() => postLoginPath(), 1300)
  } catch (e) {
    status.value = 'error'
    err.value = e.message || '登录失败，请检查 CID 和密码'
  }
}

/** 发送登录验证码到账号邮箱（purpose=login；H-1 加固后该用途同样强制人机验证，token 一次性） */
async function sendLoginCode() {
  verifyErr.value = ''
  if (!verifyEmail.value) { verifyErr.value = '无法获取账号邮箱'; return }
  sendingCode.value = true
  try {
    // PoW：静默等待令牌（拿不到也照常发，由后端判定）
    const powToken = await waitForPowToken(1200)
    const res = await fetch('/api/verify/send', {
      method: 'POST',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        'X-Device-Fp': getDeviceFp(),
        ...(powToken ? { 'X-PoW-Token': powToken } : {})
      },
      body: JSON.stringify({ email: verifyEmail.value, purpose: 'login' })
    })
    const data = await res.json()
    // token 已被服务端 siteverify 消耗：无论成功失败都重置，下次点击重新取新 token
    if (!data.success) {
      // 服务器冷却中(429)：用返回的剩余秒数恢复倒计时（与注册页一致）
      if (data.cooldown) startCooldown(data.cooldown)
      verifyErr.value = data.message || '发送失败'
      return
    }
    startCooldown(data.cooldown || 60)
  } catch (e) { verifyErr.value = e.message || '发送失败' }
  finally { sendingCode.value = false }
}

/** 验证码按钮倒计时 */
function startCooldown(secs) {
  if (cooldownTimer) clearInterval(cooldownTimer)
  codeCooldown.value = secs
  cooldownTimer = setInterval(() => {
    codeCooldown.value--
    if (codeCooldown.value <= 0) { clearInterval(cooldownTimer); cooldownTimer = null }
  }, 1000)
}

/** 提交邮箱验证码：通过后签发 JWT 并跳转 */
async function confirmLoginVerify() {
  verifyErr.value = ''
  if (!verifyCode.value) { verifyErr.value = '请输入邮箱验证码'; return }
  if (!loginChallenge.value) { verifyErr.value = '登录验证已失效，请重新登录'; return }
  verifying.value = true
  try {
    const res = await authApi.loginVerify({
      cid: form.value.cid,
      emailCode: verifyCode.value,
      loginChallenge: loginChallenge.value,
    })
    userStore.applyLogin(res.data)
    postLoginPath()
  } catch (e) {
    verifyErr.value = e.message || '验证失败'
  } finally {
    verifying.value = false
  }
}

/**
 * WebAuthn 错误翻译：浏览器/系统侧的原文对用户没有意义，这里按成因给出可操作提示。
 */
function describePasskeyError(e) {
  const serverMsg = e?.response?.data?.message
  if (serverMsg) return serverMsg
  const name = String(e?.name || '')
  const msg = String(e?.message || '')
  if (/credential manager/i.test(msg) || /talking to the credential/i.test(msg)) {
    return '系统凭据管理器不可用：请先在本机启用 Windows Hello（设置 → 账户 → 登录选项 → PIN/指纹），或改用手机扫码、密码登录'
  }
  if (name === 'NotAllowedError' || name === 'AbortError') {
    return 'Passkey 登录已取消或验证超时，可重试或用密码登录'
  }
  if (name === 'SecurityError') {
    return '当前页面来源与 Passkey 绑定时不一致（域名变了），请用密码登录后在个人中心重新绑定'
  }
  if (name === 'InvalidStateError') {
    return '该设备已存在同一账号的 Passkey，请直接登录'
  }
  if (name === 'NotSupportedError') {
    return '当前浏览器或系统不支持 Passkey，请改用密码登录'
  }
  return msg || 'Passkey 登录失败，请使用密码登录'
}

async function loginWithPasskey() {
  passkeyErr.value = ''
  const cid = String(form.value.cid || '').trim()
  // 没有 CID 时服务端无法限定凭据列表，浏览器会退化成「创建通行密钥」对话框，
  // 所以必须先填 CID（WebAuthn 会按 allowCredentials 精确匹配已绑定的凭据）。
  if (!cid) {
    passkeyErr.value = '请先输入 CID，再使用 Passkey 登录'
    return
  }
  passkeyLoading.value = true
  try {
    const optionsRes = await authApi.passkeyLoginOptions({ cid })
    const options = optionsRes.data?.options || {}
    const credential = await getPasskey(options)
    const verifyRes = await authApi.passkeyLoginVerify({
      ...(cid ? { cid } : {}),
      challenge: optionsRes.data?.challenge || options.challenge,
      credential,
    })
    userStore.applyLogin(verifyRes.data)
    postLoginPath()
  } catch (e) {
    passkeyErr.value = describePasskeyError(e)
  } finally {
    passkeyLoading.value = false
  }
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
  if (successTimer) clearTimeout(successTimer)
})
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-bg);
  padding: 24px;
}
.auth-card {
  width: 100%;
  max-width: 400px;
}
.auth-logo {
  font-size: 22px;
  font-weight: 800;
  color: var(--c-primary);
  text-decoration: none;
}
.auth-logo:hover { text-decoration: none; }
.forgot-row { display: flex; justify-content: flex-end; margin: -6px 0 14px; }
.forgot-link { font-size: 13px; color: var(--c-primary); }
.forgot-link:hover { text-decoration: underline; }

.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
  border-radius: 8px;
  border-left: 4px solid var(--c-danger, #ff453a);
  background: rgba(255, 69, 58, 0.08);
  font-size: 14px;
  color: var(--c-text);
  line-height: 1.5;
}
.error-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--c-danger, #ff453a);
  color: #fff;
  font-size: 12px;
  font-weight: bold;
  flex-shrink: 0;
}

/* ===== 新设备/IP 二次验证框：果冻弹出 ===== */
.verify-wrap {
  margin-top: 16px;
  animation: loginJellyIn .5s cubic-bezier(.34, 1.56, .64, 1) both;
}
.verify-box {
  padding: 16px;
  border: 1px solid var(--c-border-light, rgba(128,128,128,.2));
  border-radius: 10px;
  background: var(--c-bg-soft, rgba(128,128,128,.06));
}
@keyframes loginJellyIn {
  0%   { opacity: 0; transform: translateY(-16px) scaleY(.2); }
  55%  { opacity: 1; transform: translateY(3px) scaleY(1.06); }
  75%  { opacity: 1; transform: translateY(-1px) scaleY(.97); }
  100% { opacity: 1; transform: translateY(0) scaleY(1); }
}
</style>


