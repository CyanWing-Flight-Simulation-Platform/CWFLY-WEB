/** 站内消息中心：未读红点 + 会话列表 + 对话（飞行员 ↔ 管制/用户） */
<template>
  <div v-if="enabled" class="msgc">
    <button class="header-icon-btn" :class="{ 'msgc-active': open }" title="站内消息" @click.stop="toggle">
      <span class="header-icon-btn__icon" v-html="icons.mail"></span>
      <span v-if="unread > 0" class="msgc-badge">{{ unread > 99 ? '99+' : unread }}</span>
    </button>

    <div v-if="open" class="msgc-panel" @click.stop>
      <div class="msgc-head">
        <template v-if="activePeer">
          <button class="msgc-back" type="button" @click="activePeer = null">‹</button>
          <b>{{ activePeer.peerName }}</b>
          <span class="msgc-cid">CID {{ activePeer.peerCid }}</span>
        </template>
        <template v-else>
          <b>站内消息</b>
          <span v-if="unread" class="msgc-cid">{{ unread }} 条未读</span>
        </template>
        <button class="msgc-close" type="button" @click="open = false">×</button>
      </div>

      <!-- 会话列表 -->
      <div v-if="!activePeer" class="msgc-list">
        <p v-if="!conversations.length" class="msgc-empty">还没有会话。在「在线客户端」页可以给机组/管制发私信。</p>
        <button
          v-for="c in conversations"
          :key="c.peerCid"
          class="msgc-item"
          type="button"
          @click="openThread(c)"
        >
          <span class="msgc-item__name">
            {{ c.peerName }}
            <em class="msgc-item__cid">{{ c.peerCid }}</em>
          </span>
          <span class="msgc-item__body">{{ c.lastFromMe ? '我：' : '' }}{{ c.lastBody }}</span>
          <span v-if="c.unread" class="msgc-item__dot">{{ c.unread }}</span>
        </button>
      </div>

      <!-- 对话 -->
      <div v-else class="msgc-thread">
        <div ref="scrollBox" class="msgc-messages">
          <p v-if="!messages.length" class="msgc-empty">还没有消息，说点什么吧。</p>
          <div
            v-for="m in messages"
            :key="m.id"
            class="msgc-bubble"
            :class="String(m.fromCid) === String(me) ? 'msgc-bubble--mine' : ''"
          >
            <span>{{ m.body }}</span>
            <time>{{ shortTime(m.createdAt) }}</time>
          </div>
        </div>
        <div class="msgc-send">
          <input v-model="draft" class="input" maxlength="500" placeholder="输入消息，回车发送" @keyup.enter="send" />
          <button class="btn btn-primary btn-sm" :disabled="sending || !draft.trim()" @click="send">发送</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { messageApi } from '@/api'
import { icons } from '@/utils/nav'
import { showToast } from '@/utils/banner'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()
const me = computed(() => String(userStore.profile?.cid || ''))
const enabled = computed(() => userStore.isLoggedIn && !!me.value)

const open = ref(false)
const unread = ref(0)
const conversations = ref([])
const activePeer = ref(null)
const messages = ref([])
const draft = ref('')
const sending = ref(false)
const scrollBox = ref(null)
let timer = null

async function refreshUnread() {
  if (!enabled.value) return
  try {
    const res = await messageApi.unread()
    unread.value = Number(res.data?.unread || 0)
  } catch { /* 静默：红点失败不打扰用户 */ }
}

async function loadConversations() {
  try {
    const res = await messageApi.conversations()
    conversations.value = res.data?.items || []
  } catch (e) {
    showToast('加载会话失败', { type: 'error' })
  }
}

async function openThread(conv) {
  activePeer.value = { peerCid: conv.peerCid, peerName: conv.peerName }
  try {
    const res = await messageApi.thread(conv.peerCid)
    messages.value = res.data?.items || []
    await nextTick()
    scrollBottom()
    refreshUnread()
    loadConversations()
  } catch (e) {
    showToast('加载消息失败', { type: 'error' })
  }
}

function scrollBottom() {
  const el = scrollBox.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send() {
  const text = draft.value.trim()
  if (!text || !activePeer.value) return
  sending.value = true
  try {
    const res = await messageApi.send(activePeer.value.peerCid, text)
    messages.value.push({
      id: `local-${Date.now()}`,
      fromCid: me.value,
      body: text,
      createdAt: new Date().toISOString(),
    })
    draft.value = ''
    await nextTick()
    scrollBottom()
    if (res.data?.deliveredInGame) showToast('已同时送达对方游戏客户端')
  } catch (e) {
    showToast(e?.response?.data?.message || '发送失败', { type: 'error' })
  } finally {
    sending.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    refreshUnread()
    loadConversations()
  } else {
    activePeer.value = null
  }
}

function shortTime(value) {
  const t = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(t.getTime())) return ''
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`
}

function onDocClick() {
  if (open.value) {
    open.value = false
    activePeer.value = null
  }
}

watch(open, (v) => {
  if (v) document.addEventListener('click', onDocClick)
  else document.removeEventListener('click', onDocClick)
})

onMounted(() => {
  refreshUnread()
  timer = setInterval(refreshUnread, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.msgc { position: relative; }
.msgc-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
}
.msgc-panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 340px;
  max-height: 460px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--c-border, rgba(15, 23, 42, .1));
  border-radius: 12px;
  background: var(--c-surface, #fff);
  box-shadow: 0 16px 40px rgba(15, 23, 42, .18);
  overflow: hidden;
  z-index: 2600;
}
.msgc-head { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--c-border, rgba(15, 23, 42, .08)); font-size: 13px; }
.msgc-cid { color: var(--c-text-muted, #6b7280); font-size: 12px; }
.msgc-close, .msgc-back { border: 0; background: transparent; cursor: pointer; font-size: 16px; line-height: 1; color: var(--c-text-muted, #6b7280); padding: 2px 6px; }
.msgc-close { margin-left: auto; }
.msgc-list { overflow-y: auto; }
.msgc-item { display: flex; flex-direction: column; gap: 3px; width: 100%; padding: 10px 12px; border: 0; border-bottom: 1px solid var(--c-border, rgba(15, 23, 42, .06)); background: transparent; text-align: left; cursor: pointer; }
.msgc-item:hover { background: var(--c-bg-soft, rgba(15, 23, 42, .03)); }
.msgc-item__name { font-size: 13px; font-weight: 600; }
.msgc-item__cid { margin-left: 6px; font-size: 11px; font-weight: 400; color: var(--c-text-muted, #6b7280); }
.msgc-item__body { font-size: 12px; color: var(--c-text-muted, #6b7280); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msgc-item__dot { align-self: flex-end; min-width: 16px; padding: 0 4px; border-radius: 8px; background: #ef4444; color: #fff; font-size: 10px; text-align: center; }
.msgc-thread { display: flex; flex-direction: column; min-height: 240px; }
.msgc-messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.msgc-bubble { display: flex; flex-direction: column; gap: 2px; max-width: 78%; align-self: flex-start; padding: 7px 10px; border-radius: 10px; background: var(--c-bg-soft, rgba(15, 23, 42, .05)); font-size: 13px; word-break: break-word; }
.msgc-bubble--mine { align-self: flex-end; background: var(--c-primary, #2563eb); color: #fff; }
.msgc-bubble time { font-size: 10px; opacity: .65; align-self: flex-end; }
.msgc-send { display: flex; gap: 6px; padding: 10px; border-top: 1px solid var(--c-border, rgba(15, 23, 42, .08)); }
.msgc-send .input { flex: 1; }
.msgc-empty { padding: 22px 14px; font-size: 12px; color: var(--c-text-muted, #6b7280); text-align: center; }
</style>
