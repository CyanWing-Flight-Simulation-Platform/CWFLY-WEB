<template>
  <div class="portal-home fade-in">
    <!-- Hero -->
    <section class="hero">
      <div class="hero__content">
        <span class="hero__eyebrow">CWFLY&nbsp;·&nbsp;青翼模拟飞行</span>
        <h1 class="hero__title">
          让每一次<span class="hero__accent">连飞</span><span class="hero__comma">，</span>都更接近<span class="hero__accent">真实</span>
        </h1>
        <p>加入 CWFLY，和飞行员、管制员一起，在真实的航路与空域中飞行。</p>
        <div class="hero__actions">
          <router-link to="/register" class="btn-primary">立即注册</router-link>
          <router-link to="/login" class="btn-outline">已有账号？登录</router-link>
          <a target="_blank" rel="noopener" :href="qqGroupUrl" class="btn-qq">加入 QQ 群</a>
        </div>
      </div>
    </section>

    <!-- 实时状态条 -->
    <section class="status-section" aria-label="平台实时状态">
      <div class="status-bar">
        <div class="status-bar__head">
          <span>平台实时状态</span>
          <span class="status-bar__hint">FSD NETWORK</span>
        </div>
        <div class="status-grid">
          <div v-for="item in statusItems" :key="item.label" class="status-item">
            <span class="status-icon" aria-hidden="true">
              <svg v-if="item.icon === 'pilot'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.5 13.5 3 10.5V8l7 2.2V4.8a1.5 1.5 0 0 1 3 0v5.4l7-2.2v2.5l-7.5 3v4.3l2.5 1.5V21l-4-1-4 1v-1.2l2.5-1.5z" />
              </svg>
              <svg v-else-if="item.icon === 'radar'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
                <circle cx="12" cy="12" r="8" />
                <circle cx="12" cy="12" r="3" />
                <path d="m12 12 5-5M12 4v2M4 12h2M12 20v-2M20 12h-2" />
              </svg>
              <svg v-else-if="item.icon === 'activity'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="5" width="18" height="16" rx="2" />
                <path d="M8 3v4M16 3v4M3 10h18" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            <div class="status-value">{{ item.value }}</div>
            <div class="status-label">
              {{ item.label }}
              <span v-if="item.value === 0" class="status-standby"><i></i>[SYSTEM STANDBY]</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 近期活动 -->
    <section class="section">
      <div class="section__inner">
        <div class="section-head">
          <div>
            <h2 class="section-title">近期活动</h2>
            <p class="section-subtitle">和社区一起起飞，参加下一场连飞活动。</p>
          </div>
          <router-link to="/events" class="section-link section-link--overlay">查看全部活动 <span aria-hidden="true">→</span></router-link>
        </div>

        <div v-if="events.length" class="event-grid">
          <router-link
            v-for="e in events"
            :key="e.id"
            :to="`/events`"
            class="event-card card card--hover"
          >
            <div class="event-card__date">
              <span class="event-card__day">{{ dayOf(e.date) }}</span>
              <span class="event-card__mon">{{ monthOf(e.date) }}</span>
            </div>
            <div class="event-card__body">
              <h3 class="event-card__title">{{ e.title }}</h3>
              <p class="event-card__meta">{{ e.date }} · {{ e.dep || 'TBA' }} → {{ e.arr || 'TBA' }}</p>
            </div>
            <span class="badge" :class="eventBadgeClass(e.status)">{{ e.status || '活动' }}</span>
          </router-link>
        </div>
        <div v-else class="empty-state">
          <p>近期活动正在筹备中</p>
          <router-link to="/events" class="btn btn-outline btn-sm">先去活动中心看看</router-link>
        </div>
      </div>
    </section>

    <!-- 排行榜 + 关于 -->
    <section class="section section--soft">
      <div class="section__inner">
        <div class="split-grid">
          <div class="leaderboard-panel card">
            <div class="panel-head">
              <div>
                <h2 class="section-title">积分排行榜</h2>
                <p class="section-subtitle">最近活跃的飞行与社区贡献者。</p>
              </div>
              <router-link to="/leaderboard" class="section-link">完整榜单 <span aria-hidden="true">→</span></router-link>
            </div>

            <ol v-if="leaderboard.length" class="rank-list">
              <li v-for="(u, i) in leaderboard" :key="u.userId" class="rank-item">
                <span class="rank-index" :class="{ 'rank-index--top': i < 3 }">{{ i + 1 }}</span>
                <span class="rank-user">{{ u.userId }}</span>
                <span class="rank-points">{{ u.points || 0 }} <small>积分</small></span>
              </li>
            </ol>
            <div v-else-if="leaderboardNeedsLogin" class="rank-empty">
              <p>登录后查看社区积分排行榜，看看谁在最近飞得最多。</p>
              <router-link to="/login" class="rank-login">登录查看 <span aria-hidden="true">→</span></router-link>
            </div>
            <div v-else class="rank-empty">排行榜正在统计，完成飞行或参与活动后即可上榜。</div>
          </div>

          <div class="about-panel card">
            <span class="eyebrow">ABOUT CWFLY</span>
            <h2 class="about-panel__title">把模拟飞行，飞成一场真实的协作</h2>
            <p class="about-panel__text">
              CWFLY 连接飞行员、管制员与飞行爱好者，用真实的航路、气象与连飞规则，
              一起完成每一次起飞和落地。
            </p>
            <div class="about-panel__links">
              <router-link to="/about">关于我们</router-link>
              <router-link to="/meetings">会议记录</router-link>
              <router-link to="/controller-public">职员公示</router-link>
            </div>
            <router-link to="/apply/controller" class="about-panel__cta">成为管制员 <span aria-hidden="true">→</span></router-link>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import api, { eventsApi, flightplanApi } from '@/api'
import { useUserStore } from '@/store/user'
import { QQ_GROUP_URL } from '@/utils/links'

const qqGroupUrl = QQ_GROUP_URL

const userStore = useUserStore()
const events = ref([])
const leaderboard = ref([])
const leaderboardNeedsLogin = ref(false)
const stats = ref({ onlineUsers: '--', eventCount: '--' })
const fsdPilots = ref([])
const fsdAtc = ref([])
const pilotsLoaded = ref(false)
const atcLoaded = ref(false)

const statusItems = computed(() => [
  { label: '在线飞行员', value: pilotsLoaded.value ? fsdPilots.value.length : '--', icon: 'pilot' },
  { label: '在线管制员', value: atcLoaded.value ? fsdAtc.value.length : '--', icon: 'radar' },
  { label: '平台活动', value: stats.value.eventCount ?? '--', icon: 'activity' },
  { label: '在线用户', value: stats.value.onlineUsers ?? '--', icon: 'users' },
])

let statusTimer = null

function dayOf(d) {
  return d ? String(new Date(d).getDate()).padStart(2, '0') : '--'
}

function monthOf(d) {
  if (!d) return ''
  return ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'][new Date(d).getMonth()]
}

function eventBadgeClass(status) {
  if (status === '报名中') return 'badge-success'
  if (status === '进行中') return 'badge-info'
  return 'badge-default'
}

async function fetchDashboardStats() {
  const res = await fetch('/api/dashboard/stats', {
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`dashboard stats ${res.status}`)
  return res.json()
}

async function loadStatus() {
  const [dashboard, pilots, controllers] = await Promise.allSettled([
    fetchDashboardStats(),
    flightplanApi.fsdOnline(),
    flightplanApi.fsdControllers(),
  ])

  if (dashboard.status === 'fulfilled') {
    const data = dashboard.value?.data || {}
    stats.value = {
      onlineUsers: data.onlineUsers ?? '--',
      eventCount: data.eventCount ?? '--',
    }
  }
  if (pilots.status === 'fulfilled') {
    fsdPilots.value = Array.isArray(pilots.value?.data) ? pilots.value.data : []
    pilotsLoaded.value = true
  }
  if (controllers.status === 'fulfilled') {
    fsdAtc.value = Array.isArray(controllers.value?.data) ? controllers.value.data : []
    atcLoaded.value = true
  }
}

async function loadEvents() {
  try {
    const res = await eventsApi.list({})
    events.value = (res.data || []).slice(0, 3)
  } catch {
    events.value = []
  }
}

async function loadLeaderboard() {
  if (!userStore.isLoggedIn) {
    leaderboard.value = []
    leaderboardNeedsLogin.value = true
    return
  }
  leaderboardNeedsLogin.value = false
  try {
    const res = await api.get('/points/leaderboard')
    leaderboard.value = (res.data || []).slice(0, 5)
  } catch {
    leaderboard.value = []
  }
}

onMounted(() => {
  document.title = 'CW - 青翼模拟飞行连飞平台'
  loadStatus()
  loadEvents()
  loadLeaderboard()
  statusTimer = setInterval(loadStatus, 30000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style scoped>
.portal-home {
  --ui-font: "Inter", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "PingFang SC", "Microsoft YaHei", sans-serif;
  --surface-bg: rgba(255, 255, 255, .80);
  --surface-border: rgba(15, 23, 42, .07);
  --hairline: rgba(15, 23, 42, .09);
  --surface-shadow: 0 14px 34px rgba(25, 42, 64, .08);
  --surface-inset: inset 0 1px 2px rgba(15, 23, 42, .07);
  --row-bg: rgba(15, 23, 42, .025);
  --event-bg: rgba(255, 255, 255, .15);
  --event-bg-hover: rgba(255, 255, 255, .21);
  --event-border: rgba(255, 255, 255, .30);
  --event-title: #ffffff;
  --event-meta: #ffffff;
  --event-badge-bg: rgba(255, 255, 255, .18);
  --event-badge-text: #ffffff;
  --event-shadow: 0 8px 24px rgba(25, 42, 64, .08);
  --event-tint: linear-gradient(180deg, rgba(8, 13, 20, .56), rgba(8, 13, 20, .48));
  --status-bg: rgba(255, 255, 255, .15);
  --status-border: rgba(255, 255, 255, .30);
  --status-tint: linear-gradient(180deg, rgba(8, 13, 20, .50), rgba(8, 13, 20, .42));
  position: relative;
  background: linear-gradient(180deg, rgba(6, 14, 26, .26) 0%, rgba(6, 14, 26, .04) 38%, rgba(6, 14, 26, .24) 100%);
  color: var(--c-text);
}

html[data-theme='dark'] .portal-home {
  --surface-bg: rgba(14, 22, 36, .76);
  --surface-border: rgba(255, 255, 255, .08);
  --hairline: rgba(255, 255, 255, .10);
  --surface-shadow: 0 16px 38px rgba(0, 0, 0, .18);
  --surface-inset: inset 0 1px 2px rgba(255, 255, 255, .05);
  --row-bg: rgba(255, 255, 255, .035);
  --event-bg: rgba(15, 20, 28, .35);
  --event-bg-hover: rgba(20, 26, 35, .44);
  --event-border: rgba(255, 255, 255, .14);
  --event-title: #ffffff;
  --event-meta: #ffffff;
  --event-badge-bg: rgba(255, 255, 255, .10);
  --event-badge-text: #ffffff;
  --event-shadow: 0 10px 24px rgba(0, 0, 0, .14);
  --event-tint: none;
  --status-bg: rgba(255, 255, 255, .12);
  --status-border: rgba(255, 255, 255, .14);
  --status-tint: linear-gradient(180deg, rgba(0, 0, 0, .42), rgba(0, 0, 0, .34));
  background: linear-gradient(180deg, rgba(2, 8, 18, .48) 0%, rgba(2, 8, 18, .08) 38%, rgba(2, 8, 18, .46) 100%);
}

/* Hero */
.hero {
  position: relative;
  padding: 78px 24px 56px;
  text-align: center;
  overflow: hidden;
}
.hero__content {
  position: relative;
  z-index: 1;
  max-width: 760px;
  margin: 0 auto;
}
.hero__eyebrow {
  display: inline-block;
  margin-bottom: 10px;
  color: #fff;
  font-family: "Inter", "PingFang SC", "OPPO Sans", "Source Han Sans SC", "Noto Sans SC", sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .12em;
  word-spacing: .12em;
  line-height: 1.4;
  text-transform: uppercase;
  text-shadow: none;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
.hero__title {
  margin: 0 0 20px;
  color: #1f2937;
  font-family: "Inter", "PingFang SC", "OPPO Sans", "Source Han Sans SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
  font-size: clamp(34px, 4.6vw, 54px);
  font-weight: 600;
  letter-spacing: .02em;
  line-height: 1.18;
  text-shadow: none;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-synthesis: none;
}
.hero__accent { color: #2563eb; }
.hero__comma {
  opacity: .4;
  font-size: .86em;
  font-weight: inherit;
}
.hero__content p {
  max-width: 560px;
  margin: 0 auto 30px;
  color: #4b5563;
  font-size: 15px;
  font-weight: 400;
  letter-spacing: .015em;
  line-height: 1.85;
  text-shadow: none;
}
.hero__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}
.hero__actions a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 23px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: transform .22s ease, box-shadow .25s ease, background-color .25s ease;
}
.hero__actions a:hover { transform: translateY(-2px); text-decoration: none; }
.hero__actions a:active { transform: scale(.97); }
.hero__actions .btn-primary {
  color: #fff;
  border: 1px solid rgba(255, 255, 255, .18);
  background: linear-gradient(180deg, #369bf1 0%, var(--c-primary) 100%);
  box-shadow: 0 8px 18px rgba(0, 113, 227, .16);
}
.hero__actions .btn-primary:hover {
  box-shadow: 0 0 0 3px rgba(0, 113, 227, .09), 0 10px 22px rgba(0, 113, 227, .22);
}
.hero__actions .btn-outline,
.hero__actions .btn-qq {
  color: var(--c-text);
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, .52);
  backdrop-filter: blur(16px) saturate(130%);
  -webkit-backdrop-filter: blur(16px) saturate(130%);
  box-shadow: 0 6px 18px rgba(25, 42, 64, .06);
}
html[data-theme='dark'] .hero__actions .btn-outline,
html[data-theme='dark'] .hero__actions .btn-qq {
  color: rgba(255, 255, 255, .92);
  border-color: rgba(255, 255, 255, .10);
  background: rgba(255, 255, 255, .07);
}
html[data-theme='dark'] .hero__content h1 { color: #fff; }
html[data-theme='dark'] .hero__accent { color: #60a5fa; }
html[data-theme='dark'] .hero__content p { color: rgba(255, 255, 255, .68); }

/* 实时状态：单一整块面板 */
.status-section {
  max-width: 1148px;
  margin: 0 auto;
  padding: 0 24px;
}
.status-bar {
  position: relative;
  padding: 22px 30px;
  border: 1px solid var(--event-border);
  border-radius: 20px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(28px) saturate(120%);
  -webkit-backdrop-filter: blur(28px) saturate(120%);
  box-shadow: var(--event-shadow), var(--surface-inset);
}
.status-bar__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: rgba(255, 255, 255, .62);
  font-family: var(--ui-font);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: .05em;
}
.status-bar__hint {
  margin-left: auto;
  color: rgba(255, 255, 255, .40);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: .05em;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: stretch;
}
.status-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  min-width: 0;
  padding: 4px 24px;
  border-left: 1px solid var(--hairline);
  text-align: left;
}
.status-item:first-child { border-left: 0; padding-left: 0; }
.status-icon,
.status-standby { display: none; }
.status-value {
  color: #fff;
  font-family: var(--ui-font);
  font-size: 42px;
  font-weight: 750;
  letter-spacing: -.05em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.status-label {
  margin-top: 8px;
  color: rgba(255, 255, 255, .60);
  font-family: var(--ui-font);
  font-size: 11px;
  font-weight: 450;
  letter-spacing: .02em;
}
html[data-theme='dark'] .hero__content p { color: rgba(255, 255, 255, .70); }
html[data-theme='dark'] .status-value { color: #fff; }
html[data-theme='dark'] .status-label { color: rgba(255, 255, 255, .60); }

/* Sections */
.section { padding: 56px 24px; }
.section--soft { background: transparent; }
.section__inner { max-width: 1100px; margin: 0 auto; }
.section-head,
.panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}
.section-title {
  margin: 0;
  color: var(--c-text);
  font-family: var(--ui-font);
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -.015em;
}
.section-subtitle {
  margin: 6px 0 0;
  color: var(--c-text-muted);
  font-size: 12px;
  letter-spacing: .01em;
}
.section-link {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  padding: 5px 10px;
  border: 1px solid rgba(255, 255, 255, .42);
  border-radius: 999px;
  background: rgba(255, 255, 255, .46);
  backdrop-filter: blur(12px) saturate(130%);
  -webkit-backdrop-filter: blur(12px) saturate(130%);
  color: #0b5cab;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}
.section-link:hover { background: rgba(255, 255, 255, .62); text-decoration: none; }
html[data-theme='dark'] .section-link {
  border-color: rgba(255, 255, 255, .12);
  background: rgba(15, 23, 42, .42);
  color: #9cc9ff;
}
html[data-theme='dark'] .section-link:hover { background: rgba(15, 23, 42, .58); }

/* 图片/天空上的文字链接：不使用胶囊，保持干净 */
.section-link.section-link--overlay {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  color: #fff;
  text-shadow: 0 2px 6px rgba(0, 0, 0, .35);
}
.section-link.section-link--overlay:hover {
  background: transparent;
  color: #fff;
  text-decoration: none;
}
.section-link--overlay span {
  display: inline-block;
  margin-left: 4px;
  transition: transform .2s ease;
}
.section-link--overlay:hover span { transform: translateX(3px); }
html[data-theme='dark'] .section-link.section-link--overlay {
  border: 0;
  background: transparent;
  color: #fff;
}
html[data-theme='dark'] .section-link.section-link--overlay:hover {
  background: transparent;
  color: #fff;
}
html[data-theme='dark'] .section-title { color: #fff; }
html[data-theme='dark'] .section-subtitle { color: rgba(255, 255, 255, .48); }

/* Event cards: solid, quiet, high contrast */
.event-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.event-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  padding: 18px;
  color: var(--event-title);
  text-decoration: none;
  border: 1px solid var(--event-border);
  border-radius: 16px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(16px) saturate(120%);
  -webkit-backdrop-filter: blur(16px) saturate(120%);
  box-shadow: var(--event-shadow);
  transition: transform .22s ease, background-color .22s ease, box-shadow .22s ease;
}
.event-card:hover {
  background-color: var(--event-bg-hover);
  transform: translateY(-1px);
  text-decoration: none;
  box-shadow: 0 12px 28px rgba(25, 42, 64, .12);
}
html[data-theme='dark'] .event-card {
  backdrop-filter: blur(16px) saturate(120%);
  -webkit-backdrop-filter: blur(16px) saturate(120%);
}
html[data-theme='dark'] .event-card:hover {
  box-shadow: 0 14px 30px rgba(2, 8, 18, .18);
}
.event-card__date {
  display: flex;
  flex: 0 0 50px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60px;
  border-radius: 12px;
  background: var(--c-primary);
  color: #fff;
}
.event-card__day { font-size: 22px; font-weight: 700; line-height: 1; }
.event-card__mon {
  margin-top: 4px;
  color: rgba(255, 255, 255, .66);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .12em;
}
.event-card__body { min-width: 0; flex: 1; }
.event-card__title {
  overflow: hidden;
  margin: 0 0 5px;
  color: var(--event-title);
  font-size: 13px;
  font-weight: 650;
  text-shadow: 0 1px 3px rgba(0, 0, 0, .32);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-card__meta {
  overflow: hidden;
  margin: 0;
  color: var(--event-meta);
  font-size: 11px;
  text-shadow: 0 1px 3px rgba(0, 0, 0, .28);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-card .badge {
  flex-shrink: 0;
  border: 0;
  background: var(--event-badge-bg);
  color: var(--event-badge-text);
  font-size: 10px;
  opacity: 1;
}

.empty-state {
  padding: 34px 24px;
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  background: var(--surface-bg);
  backdrop-filter: blur(20px) saturate(130%);
  -webkit-backdrop-filter: blur(20px) saturate(130%);
  color: var(--c-text-muted);
  text-align: center;
}
.empty-state__icon { margin-bottom: 8px; color: var(--c-primary); font-size: 18px; }
.empty-state p { margin: 0 0 14px; font-size: 13px; }
html[data-theme='dark'] .empty-state { color: rgba(255, 255, 255, .52); }

/* Leaderboard + about */
.split-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, .9fr);
  gap: 18px;
}
.leaderboard-panel,
.about-panel {
  padding: 24px;
  border: 1px solid var(--event-border);
  border-radius: 18px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(20px) saturate(130%);
  -webkit-backdrop-filter: blur(20px) saturate(130%);
  box-shadow: var(--event-shadow);
  color: var(--event-title);
}

.panel-head { align-items: flex-start; }
.rank-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.rank-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 10px;
  border-radius: 10px;
  font-size: 12px;
}
.leaderboard-panel .rank-item:nth-child(odd) { background: var(--row-bg); }
.rank-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 24px;
  height: 24px;
  border-radius: 7px;
  color: var(--c-text-muted);
  font-size: 10px;
  font-weight: 700;
}
.rank-index--top {
  color: #946018;
  background: rgba(245, 183, 65, .16);
}
.rank-user {
  overflow: hidden;
  flex: 1;
  color: var(--c-text);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-points { color: var(--c-text-secondary); font-variant-numeric: tabular-nums; }
.rank-points small { color: var(--c-text-muted); font-size: 10px; }
.rank-empty { padding: 20px 4px; color: var(--c-text-muted); font-size: 12px; line-height: 1.75; }
.rank-empty p { margin: 0 0 10px; }
.rank-login { color: var(--c-primary); font-size: 12px; font-weight: 600; text-decoration: none; }
.rank-login:hover { text-decoration: underline; }
html[data-theme='dark'] .leaderboard-panel .rank-user { color: #fff; }
html[data-theme='dark'] .leaderboard-panel .rank-points { color: rgba(255, 255, 255, .62); }
html[data-theme='dark'] .leaderboard-panel .rank-points small,
html[data-theme='dark'] .rank-empty { color: rgba(255, 255, 255, .46); }
html[data-theme='dark'] .rank-index { color: rgba(255, 255, 255, .48); }
html[data-theme='dark'] .rank-index--top { color: #d9b36b; }

.eyebrow {
  color: var(--c-primary);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .17em;
}
.about-panel__title {
  margin: 10px 0 10px;
  color: var(--c-text);
  font-size: 19px;
  font-weight: 650;
  line-height: 1.4;
  letter-spacing: -.015em;
}
.about-panel__text {
  margin: 0;
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.85;
}
.about-panel__links {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 18px;
}
.about-panel__links a,
.about-panel__cta {
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}
.about-panel__links a:hover,
.about-panel__cta:hover { text-decoration: underline; }
.about-panel__cta {
  display: inline-block;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--hairline);
}
html[data-theme='dark'] .about-panel__title { color: #fff; }
html[data-theme='dark'] .about-panel__text { color: rgba(255, 255, 255, .56); }

/* 深色玻璃面板最终配色（覆盖上面的亮色基础规则） */
.portal-home .status-item { border-left-color: rgba(255, 255, 255, .14); }
.portal-home .leaderboard-panel .section-title,
.portal-home .about-panel__title {
  color: #fff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, .28);
}
.portal-home .leaderboard-panel .section-subtitle,
.portal-home .leaderboard-panel .rank-empty,
.portal-home .about-panel__text {
  color: rgba(255, 255, 255, .62);
}
.portal-home .leaderboard-panel .section-link {
  border-color: rgba(255, 255, 255, .20);
  background: rgba(255, 255, 255, .12);
  color: #fff;
}
.portal-home .leaderboard-panel .section-link:hover {
  background: rgba(255, 255, 255, .20);
}
.portal-home .leaderboard-panel .rank-item:nth-child(odd) {
  background: rgba(255, 255, 255, .06);
}
.portal-home .leaderboard-panel .rank-user { color: #fff; }
.portal-home .leaderboard-panel .rank-points { color: rgba(255, 255, 255, .62); }
.portal-home .leaderboard-panel .rank-points small,
.portal-home .leaderboard-panel .rank-index,
.portal-home .leaderboard-panel .rank-empty { color: rgba(255, 255, 255, .48); }
.portal-home .leaderboard-panel .rank-index--top { color: #e8c47a; background: rgba(245, 183, 65, .16); }
.portal-home .leaderboard-panel .rank-login { color: #9cc9ff; }
.portal-home .about-panel .about-panel__links a,
.portal-home .about-panel .about-panel__cta { color: #9cc9ff; }
.portal-home .about-panel .about-panel__cta { border-top-color: rgba(255, 255, 255, .16); }

@media (max-width: 860px) {
  .status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 0; }
  .status-item { padding: 16px 16px; }
  .status-item:nth-child(odd) { border-left: 0; padding-left: 0; }
  .status-item:nth-child(n+3) { border-top: 1px solid var(--hairline); }
  .event-grid { grid-template-columns: 1fr; }
  .split-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .hero { padding: 62px 20px 42px; }
  .hero__content h1 { font-size: 34px; }
  .status-section { max-width: 100%; padding: 0 16px; }
  .status-bar { padding: 16px 12px; }
  .status-item { padding: 14px 10px; }
  .status-value { font-size: 32px; }
  .section { padding: 42px 16px; }
  .section-head { align-items: flex-start; flex-direction: column; gap: 10px; }
  .hero__actions { flex-direction: column; align-items: stretch; }
  .hero__actions a { width: 100%; }
}
</style>
