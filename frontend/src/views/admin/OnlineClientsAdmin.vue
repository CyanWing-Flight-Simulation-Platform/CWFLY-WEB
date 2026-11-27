/** 在线客户端（管理）：查看全部在线连接，可私信、踢出、全服广播 */
<template>
  <div class="ol-page">
    <div class="ol-head">
      <div>
        <h1 class="ol-title">在线客户端管理</h1>
        <p class="ol-desc">查看当前 FSD 连接，支持全服广播与强制踢出（操作会记录日志）。</p>
      </div>
      <div class="ol-actions">
        <button class="btn btn-outline btn-sm" :disabled="loading" @click="load">刷新</button>
        <button class="btn btn-primary btn-sm" @click="openBroadcast">全服广播</button>
      </div>
    </div>

    <div class="ol-stats">
      <span>在线 <b>{{ items.length }}</b></span>
      <span>机组 <b>{{ pilotCount }}</b></span>
      <span>管制 <b>{{ atcCount }}</b></span>
      <span v-if="stats" class="ol-stats__muted">
        连接 {{ stats.connections ?? '-' }} · 证书 {{ stats.certs ?? '-' }} · 认证失败 {{ stats.authFail ?? 0 }} · 事件循环 {{ stats.loopLagMaxMs ?? '-' }}ms
      </span>
    </div>

    <div v-if="err" class="alert alert-err">{{ err }}</div>

    <div class="ol-table">
      <div class="ol-row ol-row--head">
        <span>呼号</span><span>CID</span><span>类型</span><span>昵称</span><span>等级</span><span>静默</span><span>操作</span>
      </div>
      <div v-if="!items.length && !loading" class="ol-empty">当前没有客户端在线</div>
      <div v-for="c in items" :key="c.callsign" class="ol-row">
        <span class="ol-callsign">{{ c.callsign }}</span>
        <span>{{ c.cid }}</span>
        <span>{{ c.type === 'ATC' ? '管制' : '机组' }}</span>
        <span class="ol-name">{{ c.username || '-' }}</span>
        <span>{{ c.rating }}</span>
        <span>{{ c.idle }}s</span>
        <span class="ol-ops">
          <button class="btn btn-outline btn-xs" @click="openMessage(c)">私信</button>
          <button class="btn btn-danger btn-xs" @click="kick(c)">踢出</button>
        </span>
      </div>
    </div>

    <!-- 私信 -->
    <div v-if="dialogs.message" class="modal-overlay" @click.self="dialogs.message = false">
      <div class="modal card p-lg" style="max-width:480px;">
        <h3 class="mb-sm">发送到 {{ messageTarget?.callsign }}</h3>
        <p class="text-xs text-muted mb-sm">将通过 FSD 送达对方客户端（显示为服务器消息）。</p>
        <textarea v-model="messageText" class="input" rows="3" maxlength="300" placeholder="输入消息…"></textarea>
        <div class="flex gap-sm justify-end mt-md">
          <button class="btn btn-outline" @click="dialogs.message = false">取消</button>
          <button class="btn btn-primary" :disabled="sending || !messageText.trim()" @click="sendMessage">发送</button>
        </div>
      </div>
    </div>

    <!-- 全服广播 -->
    <div v-if="dialogs.broadcast" class="modal-overlay" @click.self="dialogs.broadcast = false">
      <div class="modal card p-lg" style="max-width:480px;">
        <h3 class="mb-sm">全服广播</h3>
        <p class="text-xs text-muted mb-sm">所有在线客户端都会收到这条服务器消息，请勿用于日常通知。</p>
        <textarea v-model="broadcastText" class="input" rows="3" maxlength="300" placeholder="输入广播内容…"></textarea>
        <div class="flex gap-sm justify-end mt-md">
          <button class="btn btn-outline" @click="dialogs.broadcast = false">取消</button>
          <button class="btn btn-danger" :disabled="sending || !broadcastText.trim()" @click="sendBroadcast">广播</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onlineApi } from '@/api'
import { showToast } from '@/utils/banner'

const loading = ref(false)
const err = ref('')
const items = ref([])
const stats = ref(null)
const pilotCount = computed(() => items.value.filter((c) => c.type === 'PILOT').length)
const atcCount = computed(() => items.value.length - pilotCount.value)

const dialogs = ref({ message: false, broadcast: false })
const messageTarget = ref(null)
const messageText = ref('')
const broadcastText = ref('')
const sending = ref(false)
let timer = null

async function load() {
  loading.value = true
  err.value = ''
  try {
    const res = await onlineApi.clients()
    items.value = res.data?.items || []
    const s = await onlineApi.stats().catch(() => null)
    stats.value = s?.data || null
  } catch (e) {
    err.value = e?.response?.data?.message || '获取在线列表失败'
  } finally {
    loading.value = false
  }
}

function openMessage(client) {
  messageTarget.value = client
  messageText.value = ''
  dialogs.value.message = true
}

async function sendMessage() {
  if (!messageTarget.value) return
  sending.value = true
  try {
    await onlineApi.message(messageTarget.value.callsign, messageText.value.trim())
    showToast('消息已发送')
    dialogs.value.message = false
  } catch (e) {
    showToast(e?.response?.data?.message || '发送失败', { type: 'error' })
  } finally {
    sending.value = false
  }
}

function openBroadcast() {
  broadcastText.value = ''
  dialogs.value.broadcast = true
}

async function sendBroadcast() {
  sending.value = true
  try {
    const res = await onlineApi.broadcast(broadcastText.value.trim())
    showToast(`已广播给 ${res.data?.delivered ?? 0} 个客户端`)
    dialogs.value.broadcast = false
  } catch (e) {
    showToast(e?.response?.data?.message || '广播失败', { type: 'error' })
  } finally {
    sending.value = false
  }
}

async function kick(client) {
  if (!window.confirm(`确定踢出 ${client.callsign}？该操作会记录到日志。`)) return
  try {
    await onlineApi.kick(client.callsign)
    showToast(`已踢出 ${client.callsign}`)
    load()
  } catch (e) {
    showToast(e?.response?.data?.message || '踢出失败', { type: 'error' })
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 20000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.ol-page { padding: 4px 0 32px; }
.ol-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.ol-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.ol-desc { font-size: 13px; color: var(--c-text-muted, #6b7280); margin: 0; }
.ol-actions { display: flex; gap: 8px; }
.ol-stats { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; font-size: 13px; color: var(--c-text-muted, #6b7280); margin-bottom: 14px; }
.ol-stats b { color: var(--c-text, #111827); font-size: 15px; }
.ol-stats__muted { margin-left: auto; }
.ol-table { border: 1px solid var(--c-border, rgba(15, 23, 42, .08)); border-radius: 12px; overflow: hidden; }
.ol-row { display: grid; grid-template-columns: 1.4fr .8fr .8fr 1.4fr .8fr .8fr 1.6fr; gap: 8px; align-items: center; padding: 10px 14px; font-size: 13px; border-top: 1px solid var(--c-border, rgba(15, 23, 42, .06)); }
.ol-row:first-child { border-top: 0; }
.ol-row--head { background: var(--c-bg-soft, rgba(15, 23, 42, .03)); font-weight: 700; font-size: 12px; }
.ol-callsign { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 700; }
.ol-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ol-ops { display: flex; gap: 6px; }
.ol-empty { padding: 28px; text-align: center; font-size: 13px; color: var(--c-text-muted, #6b7280); }
.btn-xs { padding: 3px 9px; font-size: 12px; border-radius: 7px; }
</style>
