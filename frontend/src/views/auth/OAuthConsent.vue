<template>
  <div class="consent-page">
    <!-- 打开失败：展示原因并提供返回入口 -->
    <div v-if="error" class="consent-fallback">
      <p class="consent-fallback__text">{{ error }}</p>
      <button type="button" class="consent-fallback__btn" @click="goHome">返回首页</button>
    </div>

    <OAuthConsentModal
      v-model:open="open"
      :app-name="context.appName"
      :app-origin="context.appOrigin"
      :user-name="context.userName"
      :cid="context.cid"
      :scopes="context.scopes"
      :loading="submitting"
      @approve="decide('approve')"
      @deny="decide('deny')"
      @close="onClose"
    />
  </div>
</template>

<script setup>
/**
 * 第三方 OAuth 授权确认页
 *
 * 流程：第三方 → /api/oauth/authorize（服务端校验 + 签发 approval）
 *      → 302 到本页 → 取上下文 → 弹窗确认 → POST /api/oauth/consent
 *      → 服务端返回带 code 的回调地址 → 整页跳回第三方。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import OAuthConsentModal from '@/components/oauth/OAuthConsentModal.vue'
import { oauthConsentApi } from '@/api'

const route = useRoute()
const router = useRouter()

const approval = String(route.query.approval || '')
const open = ref(false)
const submitting = ref(false)
const error = ref('')
const decided = ref(false)

const context = reactive({
  appName: '第三方应用',
  appOrigin: '',
  userName: '',
  cid: '',
  scopes: [],
})

function goHome() {
  router.replace('/')
}

function onClose() {
  // 用户按 Esc / 点遮罩关闭 = 拒绝；approve/deny 已经处理过则不重复提交
  if (decided.value) return
  decide('deny')
}

async function decide(decision) {
  if (decided.value) return
  decided.value = true
  submitting.value = true
  try {
    const res = await oauthConsentApi.decide(approval, decision)
    const target = res?.data?.data?.redirect
    if (!target) throw new Error('授权结果异常')
    window.location.replace(target)
  } catch (e) {
    decided.value = false
    submitting.value = false
    error.value = e?.response?.data?.error_description || e?.message || '授权失败，请稍后重试'
    open.value = false
  }
}

onMounted(async () => {
  if (!approval) {
    error.value = '授权请求缺失，请回到第三方应用重新发起。'
    return
  }
  try {
    const res = await oauthConsentApi.info(approval)
    const data = res?.data?.data || {}
    context.appName = data.appName || context.appName
    context.appOrigin = data.appOrigin || ''
    context.userName = data.userName || ''
    context.cid = data.cid || ''
    context.scopes = Array.isArray(data.scopes) ? data.scopes : []
    open.value = true
  } catch (e) {
    error.value = e?.response?.data?.error_description || '授权请求已过期，请回到第三方应用重新发起。'
  }
})
</script>

<style scoped>
.consent-page {
  min-height: 100vh;
}

.consent-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  min-height: 100vh;
  padding: 32px;
  text-align: center;
}
.consent-fallback__text {
  margin: 0;
  max-width: 420px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--c-text-secondary, #424245);
}
.consent-fallback__btn {
  height: 36px;
  padding: 0 20px;
  border: 1px solid var(--ui-ghost-border, rgba(15, 23, 42, .12));
  border-radius: 8px;
  background: var(--ui-ghost-bg, rgba(15, 23, 42, .05));
  color: var(--ui-text, #111827);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
</style>