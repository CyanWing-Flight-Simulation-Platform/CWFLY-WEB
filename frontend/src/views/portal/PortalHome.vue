<template>
  <div class="portal-home fade-in">
    <!-- Hero -->
    <section class="hero">
      <div class="hero__content">
        <h1 class="hero__title">CWFLY·青翼模拟飞行连飞平台</h1>
        <div class="hero__actions">
          <router-link to="/register" class="btn-primary">立即注册</router-link>
          <router-link to="/login" class="btn-outline">已有账号？登录</router-link>
          <a target="_blank" rel="noopener" :href="qqGroupUrl" class="btn-qq">加入 QQ 群</a>
        </div>
      </div>
    </section>

    <!-- 实时状态条 -->
    <section v-reveal class="status-section" aria-label="平台实时状态">
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

    <!-- 核心功能 -->
    <section v-reveal class="section section--features">
      <div class="section__inner">
        <div class="section-head">
          <div>
            <h2 class="section-title">为每一次连飞而设计</h2>
            <p class="section-subtitle">真实的数据、专业的人和一群认真飞行的伙伴。</p>
          </div>
        </div>
        <div class="feature-grid">
          <article
            v-for="(feature, index) in features"
            :key="feature.title"
            v-reveal
            class="feature-card"
            :style="{ '--reveal-index': index }"
          >
            <span class="feature-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <path v-for="path in feature.paths" :key="path" :d="path" />
              </svg>
            </span>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- 实时数据 -->
    <section ref="liveStatsEl" v-reveal class="section section--stats">
      <div class="section__inner">
        <div class="section-head">
          <div>
            <h2 class="section-title">实时数据战报</h2>
            <p class="section-subtitle">平台运行与社区活跃度的真实切片。</p>
          </div>
        </div>
        <div class="live-stats">
          <div
            v-for="(stat, index) in liveStats"
            :key="stat.key"
            v-reveal
            class="live-stat"
            :style="{ '--reveal-index': index }"
          >
            <strong>{{ formatCount(stat.key) }}</strong>
            <span>{{ stat.label }}</span>
            <small>{{ stat.note }}</small>
          </div>
        </div>
      </div>
    </section>

    <!-- 热门航线 / 活动 Bento -->
    <section v-reveal class="section section--bento">
      <div class="section__inner">
        <div class="section-head">
          <div>
            <h2 class="section-title">热门航线与活动</h2>
            <p class="section-subtitle">从一场活动开始，加入下一次真实的协作飞行。</p>
          </div>
          <router-link to="/events" class="section-link section-link--overlay">查看全部活动 <span aria-hidden="true">→</span></router-link>
        </div>

        <div class="bento-grid">
          <router-link v-reveal to="/events" class="bento-card bento-card--hero">
            <div class="bento-card__top">
              <span class="bento-card__label">{{ bentoHero.label }}</span>
              <span class="badge badge-info">{{ bentoHero.status }}</span>
            </div>
            <div class="bento-card__body">
              <h3>{{ bentoHero.title }}</h3>
              <p>{{ bentoHero.meta }}</p>
            </div>
            <div class="route-diagram" aria-hidden="true">
              <span class="route-diagram__point">{{ bentoHero.dep || 'DEP' }}</span>
              <span class="route-diagram__line"><i></i><svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg></span>
              <span class="route-diagram__point">{{ bentoHero.arr || 'ARR' }}</span>
            </div>
          </router-link>

          <router-link
            v-for="(card, index) in bentoSmall"
            :key="card.title"
            v-reveal
            to="/events"
            class="bento-card"
            :style="{ '--reveal-index': index + 1 }"
          >
            <div class="bento-card__top">
              <span class="bento-card__label">{{ card.label }}</span>
              <span class="bento-card__arrow" aria-hidden="true">↗</span>
            </div>
            <div class="bento-card__body">
              <h3>{{ card.title }}</h3>
              <p>{{ card.meta }}</p>
            </div>
            <span class="bento-card__note">{{ card.note || '点击查看活动详情' }}</span>
          </router-link>
        </div>
      </div>
    </section>
    <!-- 排行榜 + 关于 -->
    <section v-reveal class="section section--soft">
      <div class="section__inner">
        <div class="split-grid">
          <div v-reveal class="leaderboard-panel">
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

          <div v-reveal class="about-panel" :style="{ '--reveal-index': 1 }">
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
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import api, { eventsApi, flightplanApi } from '@/api'
import { useUserStore } from '@/store/user'
import { QQ_GROUP_URL } from '@/utils/links'

const qqGroupUrl = QQ_GROUP_URL

const userStore = useUserStore()
const events = ref([])
const leaderboard = ref([])
const leaderboardNeedsLogin = ref(false)
const stats = ref({
  totalUsers: '--',
  controllerCount: '--',
  eventCount: '--',
  onlineUsers: '--',
})
const fsdPilots = ref([])
const fsdAtc = ref([])
const pilotsLoaded = ref(false)
const atcLoaded = ref(false)

// 在线用户必须与在线飞行员/管制员同源：直接由 FSD 快照去重计算，
// 不再依赖可能混入网页游客/后台账号的统计口径。
const fsdOnlineUserCount = computed(() => {
  const keys = new Set()
  for (const pilot of fsdPilots.value) {
    keys.add(String(pilot.cid || pilot.callsign || ''))
  }
  for (const atc of fsdAtc.value) {
    keys.add(String(atc.cid || atc.callsign || ''))
  }
  keys.delete('')
  return keys.size
})

const statusItems = computed(() => [
  { label: '在线飞行员', value: pilotsLoaded.value ? fsdPilots.value.length : '--', icon: 'pilot' },
  { label: '在线管制员', value: atcLoaded.value ? fsdAtc.value.length : '--', icon: 'radar' },
  { label: '平台活动', value: stats.value.eventCount ?? '--', icon: 'activity' },
  {
    label: '在线用户',
    value: pilotsLoaded.value && atcLoaded.value ? fsdOnlineUserCount.value : (stats.value.onlineUsers ?? '--'),
    icon: 'users'
  },
])

let statusTimer = null

/* ---------- 首页展示内容 ---------- */
const features = [
  {
    title: '真实航路规划',
    desc: '基于真实航路、机场与航图数据规划飞行，让每一次飞行都有据可循。',
    paths: ['M4 18c4-1 7-5 9-11M7 20l2-3M17 6l2-2', 'M4 5h5M4 9h3'],
  },
  {
    title: '专业管制服务',
    desc: '由认证管制员提供席位服务，从放行、地面到进近与区域管制。',
    paths: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18', 'M12 7v5l3 2', 'M12 3v2M21 12h-2M12 21v-2M3 12h2'],
  },
  {
    title: '实时气象与航图',
    desc: '集成气象、航图与航班数据，在飞行前掌握完整运行环境。',
    paths: ['M6 17a4 4 0 0 1 1-7.9A5 5 0 0 1 17 8a3.5 3.5 0 0 1 .5 7H6', 'M8 20h8'],
  },
  {
    title: '社区连飞活动',
    desc: '参与主题连飞、节假日活动与跨区域协作，与社区一起起飞。',
    paths: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8', 'M22 21v-2a4 4 0 0 0-3-3.9'],
  },
]

const featuredRoutes = [
  { title: '京沪空中走廊', meta: 'ZBAA → ZSSS', note: '热门干线 · 京沪运行', dep: 'ZBAA', arr: 'ZSSS', label: '热门航线' },
  { title: '成渝连线', meta: 'ZUUU → ZUCK', note: '西南区域 · 山地进近', dep: 'ZUUU', arr: 'ZUCK', label: '热门航线' },
]

const liveStats = [
  { key: 'totalUsers', label: '注册机组', note: '加入 CWFLY 的飞行与管制成员' },
  { key: 'controllerCount', label: '认证管制员', note: '提供专业席位服务的管制成员' },
  { key: 'eventCount', label: '历史活动场次', note: '社区连飞与专题活动累计' },
  { key: 'onlineUsers', label: '当前在线', note: '当前连接 FSD 的机组' },
]

const liveStatsEl = ref(null)
const countValues = reactive({ totalUsers: 0, controllerCount: 0, eventCount: 0, onlineUsers: 0 })
const countVisible = ref(false)
const statsLoaded = ref(false)
let countStarted = false
let countObserver = null
let countRaf = 0

const liveCountTargets = computed(() => ({
  totalUsers: Number(stats.value.totalUsers) || 0,
  controllerCount: Number(stats.value.controllerCount) || 0,
  eventCount: Number(stats.value.eventCount) || 0,
  onlineUsers: Number(stats.value.onlineUsers) || 0,
}))

function formatCount(key) {
  return Number(countValues[key] || 0).toLocaleString('zh-CN')
}

function startCountUp() {
  if (countStarted || !countVisible.value || !statsLoaded.value) return
  countStarted = true
  const targets = liveCountTargets.value
  const start = performance.now()
  const duration = 1300
  const tick = (now) => {
    const p = Math.min(1, (now - start) / duration)
    const eased = 1 - Math.pow(1 - p, 3)
    for (const key of Object.keys(targets)) {
      countValues[key] = Math.round(targets[key] * eased)
    }
    if (p < 1) countRaf = requestAnimationFrame(tick)
    else for (const key of Object.keys(targets)) countValues[key] = targets[key]
  }
  countRaf = requestAnimationFrame(tick)
}

/* ---------- Scroll Reveal（IntersectionObserver，无 scroll 监听） ---------- */
let revealObserver = null
if (typeof IntersectionObserver !== 'undefined') {
  revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        // 双向触发：进入视口淡入上浮，离开视口淡出下坠；不取消观察，可无限次触发
        entry.target.classList.toggle('is-visible', entry.isIntersecting)
      })
    },
    { threshold: 0.15, rootMargin: '0px 0px -10% 0px' },
  )
}

const vReveal = {
  mounted(el) {
    // 自定义指令不会自动产生 HTML 属性；补上 data-reveal 让 CSS 初始态生效
    el.setAttribute('data-reveal', '')
    if (!revealObserver) {
      el.classList.add('is-visible')
      return
    }
    revealObserver.observe(el)
  },
  unmounted() {
    // 元素卸载时无需 unobserve；页面卸载时统一 disconnect 观察器
  },
}

const bentoEvents = computed(() => {
  const seenIds = new Set()
  const seenContent = new Set()
  const unique = []
  for (const event of events.value) {
    const id = String(event.id ?? '')
    const contentKey = `${event.title || ''}|${event.date || ''}|${event.dep || ''}|${event.arr || ''}`
    if ((id && seenIds.has(id)) || seenContent.has(contentKey)) continue
    if (id) seenIds.add(id)
    seenContent.add(contentKey)
    unique.push(event)
  }
  return unique.slice(0, 3)
})
const bentoHero = computed(() => {
  const event = bentoEvents.value[0]
  if (event) {
    return {
      title: event.title,
      meta: `${event.date} · ${event.dep || 'TBA'} → ${event.arr || 'TBA'}`,
      dep: event.dep || '',
      arr: event.arr || '',
      label: '近期活动',
      status: event.status || '活动',
    }
  }
  const route = featuredRoutes[0]
  return { ...route, status: route.label }
})
const bentoSmall = computed(() => {
  const items = bentoEvents.value.slice(1, 3).map((event) => ({
    title: event.title,
    meta: `${event.date} · ${event.dep || 'TBA'} → ${event.arr || 'TBA'}`,
    dep: event.dep || '',
    arr: event.arr || '',
    label: '近期活动',
    status: event.status || '活动',
  }))
  for (const route of featuredRoutes) {
    if (items.length >= 2) break
    items.push({ ...route, status: route.label })
  }
  return items.slice(0, 2)
})

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
      totalUsers: data.totalUsers ?? '--',
      controllerCount: data.controllerCount ?? '--',
      eventCount: data.eventCount ?? '--',
      onlineUsers: data.onlineUsers ?? '--',
    }
    statsLoaded.value = true
    startCountUp()
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

onMounted(async () => {
  document.title = 'CW - 青翼模拟飞行连飞平台'
  loadStatus()
  loadEvents()
  loadLeaderboard()
  statusTimer = setInterval(loadStatus, 30000)

  await nextTick()
  if (liveStatsEl.value && typeof IntersectionObserver !== 'undefined') {
    countObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          countVisible.value = true
          startCountUp()
          countObserver?.unobserve(entry.target)
        })
      },
      { threshold: 0.2 },
    )
    countObserver.observe(liveStatsEl.value)
  } else {
    countVisible.value = true
  }
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
  if (revealObserver) revealObserver.disconnect()
  if (countObserver) countObserver.disconnect()
  if (countRaf) cancelAnimationFrame(countRaf)
})
</script>

<style scoped>
.portal-home {
  --ui-font: "Inter", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "PingFang SC", "Microsoft YaHei", sans-serif;
  --surface-bg: rgba(255, 255, 255, .65);
  --surface-border: rgba(255, 255, 255, .50);
  --hairline: rgba(15, 23, 42, .07);
  --surface-shadow: 0 8px 32px rgba(0, 0, 0, .06);
  --surface-inset: inset 0 1px 1px rgba(255, 255, 255, .55);
  --row-bg: rgba(15, 23, 42, .025);
  --event-bg: rgba(255, 255, 255, .65);
  --event-bg-hover: rgba(255, 255, 255, .78);
  --event-border: rgba(255, 255, 255, .50);
  --event-title: #111827;
  --event-meta: #4B5563;
  --event-badge-bg: rgba(37, 99, 235, .08);
  --event-badge-text: #1D4ED8;
  --event-shadow: 0 8px 32px rgba(0, 0, 0, .06);
  --event-tint: none;
  --status-bg: rgba(255, 255, 255, .65);
  --status-border: rgba(255, 255, 255, .70);
  --status-tint: none;
  position: relative;
  /* 背景由 App.vue 的全屏固定层统一提供；此处不再叠加局部渐变，避免页面底部出现横向断层 */
  background: transparent;
  color: var(--c-text);
}

html[data-theme='dark'] .portal-home {
  --surface-bg: rgba(14, 22, 36, .76);
  --surface-border: rgba(255, 255, 255, .08);
  --hairline: rgba(255, 255, 255, .10);
  --surface-shadow: 0 16px 38px rgba(0, 0, 0, .18);
  --surface-inset: inset 0 1px 2px rgba(255, 255, 255, .05);
  --row-bg: rgba(255, 255, 255, .035);
  --event-bg: rgba(15, 20, 28, .58);
  --event-bg-hover: rgba(20, 26, 35, .68);
  --event-border: rgba(255, 255, 255, .14);
  --event-title: #ffffff;
  --event-meta: #ffffff;
  --event-badge-bg: rgba(255, 255, 255, .10);
  --event-badge-text: #ffffff;
  --event-shadow: 0 8px 32px rgba(0, 0, 0, .18);
  --event-tint: none;
  --status-bg: rgba(15, 20, 28, .58);
  --status-border: rgba(255, 255, 255, .14);
  --status-tint: none;
  background: transparent;
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
.hero__title {
  margin: 0 0 24px;
  color: #111827;
  font-family: "Inter", "PingFang SC", "OPPO Sans", "Source Han Sans SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
  font-size: clamp(36px, 4.8vw, 58px);
  font-weight: 600;
  letter-spacing: -.025em;
  line-height: 1.12;
  text-shadow: none;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-synthesis: none;
}
.hero__content p {
  max-width: 540px;
  margin: 0 auto 32px;
  color: #4B5563;
  font-size: 15px;
  font-weight: 400;
  letter-spacing: .01em;
  line-height: 1.8;
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
html[data-theme='dark'] .hero__title {
  color: rgba(255, 255, 255, .98);
  text-shadow: 0 2px 18px rgba(0, 0, 0, .38);
}
html[data-theme='dark'] .hero__content p { color: rgba(255, 255, 255, .82); }

/* 实时状态：单一整块面板 */
.status-section {
  max-width: 1148px;
  margin: 0 auto;
  padding: 0 24px;
}
.status-bar {
  position: relative;
  padding: 16px 28px;
  border: 1px solid var(--event-border);
  border-radius: 20px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(24px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(120%);
  box-shadow: var(--event-shadow);
  transition: all .3s cubic-bezier(.25, .8, .25, 1);
  will-change: transform, box-shadow, border-color;
}
.status-bar:hover {
  transform: translateY(-4px) scale(1.01);
  border-color: rgba(255, 255, 255, .9);
  box-shadow: 0 20px 48px rgba(15, 23, 42, .10);
}
.status-bar__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: var(--event-meta);
  font-family: var(--ui-font);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: .04em;
}
.status-bar__hint {
  margin-left: auto;
  color: var(--event-meta);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: .08em;
}
.status-grid {
  display: flex;
  align-items: stretch;
  justify-content: space-around;
}
.status-item {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 2px 16px;
  text-align: center;
}
.status-icon,
.status-standby { display: none; }
.status-value {
  color: var(--event-title);
  font-family: var(--ui-font);
  font-size: 38px;
  font-weight: 750;
  letter-spacing: -.05em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.status-label {
  margin-top: 7px;
  color: var(--event-meta);
  font-family: var(--ui-font);
  font-size: 11px;
  font-weight: 450;
  letter-spacing: .02em;
}
html[data-theme='dark'] .hero__content p { color: rgba(255, 255, 255, .82); }
html[data-theme='dark'] .status-value { color: #fff; }
html[data-theme='dark'] .status-label { color: rgba(255, 255, 255, .76); }
html[data-theme='dark'] .status-bar__head,
html[data-theme='dark'] .status-bar__hint { color: rgba(255, 255, 255, .68); }

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
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  color: #1D4ED8;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  transition: color .2s ease;
}
.section-link:hover { color: #1e40af; text-decoration: none; }
html[data-theme='dark'] .section-link {
  border-color: transparent;
  background: transparent;
  color: #93C5FD;
}
html[data-theme='dark'] .section-link:hover { background: transparent; color: #BFDBFE; }

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
html[data-theme='dark'] .section-title { color: #fff; text-shadow: 0 1px 10px rgba(0, 0, 0, .28); }
html[data-theme='dark'] .section-subtitle { color: rgba(255, 255, 255, .68); }

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
  backdrop-filter: blur(24px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(120%);
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
  backdrop-filter: blur(24px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(120%);
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
  box-shadow: var(--surface-shadow);
  backdrop-filter: blur(24px) saturate(125%);
  -webkit-backdrop-filter: blur(24px) saturate(125%);
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
  backdrop-filter: blur(24px) saturate(125%);
  -webkit-backdrop-filter: blur(24px) saturate(125%);
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

.about-panel__title {
  margin: 0 0 12px;
  color: var(--c-text);
  font-size: 20px;
  font-weight: 680;
  line-height: 1.4;
  letter-spacing: -.02em;
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


/* ---------- Scroll Reveal ---------- */
.portal-home [data-reveal] {
  opacity: 0;
  transform: translateY(40px);
  transition:
    opacity .8s ease-out,
    transform .8s cubic-bezier(.25, 1, .5, 1);
  transition-delay: calc(var(--reveal-index, 0) * 100ms);
  will-change: opacity, transform;
}
.portal-home [data-reveal].is-visible {
  opacity: 1;
  transform: translateY(0);
}
@media (prefers-reduced-motion: reduce) {
  .portal-home [data-reveal] {
    opacity: 1;
    transform: none;
    transition: none;
  }
}

/* ---------- 核心功能 ---------- */
.section--features { padding-top: 112px; }
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: 1fr;
  align-items: stretch;
  gap: 16px;
}
.feature-card {
  display: flex;
  flex-direction: column;
  align-self: stretch;
  height: 100%;
  min-height: 196px;
  padding: 28px 24px;
  border: 1px solid rgba(255, 255, 255, .50);
  border-radius: 18px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(24px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(120%);
  box-shadow: var(--event-shadow);
  color: var(--event-title);
  cursor: pointer;
  transition: all .3s cubic-bezier(.25, .8, .25, 1);
  will-change: transform, box-shadow, border-color;
}
.portal-home .feature-card:hover {
  transform: translateY(-4px) scale(1.01);
}
.feature-card:hover {
  border-color: rgba(255, 255, 255, .9);
  box-shadow: 0 20px 48px rgba(15, 23, 42, .10);
}
.feature-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  width: auto;
  height: auto;
  margin-bottom: 22px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: #1E3A8A;
  transform-origin: center;
  transition: transform .3s cubic-bezier(.25, .8, .25, 1);
}
.feature-card:hover .feature-card__icon {
  transform: translateY(-1px) scale(1.1);
}
/* v-reveal 会给卡片设置自己的 transform transition；这里保持 hover 的弹性曲线 */
.portal-home .feature-card {
  transition: all .3s cubic-bezier(.25, .8, .25, 1);
}
.feature-card__icon svg { width: 34px; height: 34px; flex: 0 0 34px; }
.feature-card h3 {
  margin: 0 0 9px;
  color: var(--event-title);
  font-family: var(--ui-font);
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -.01em;
}
.feature-card p {
  margin: 0;
  color: var(--event-meta);
  font-size: 12px;
  line-height: 1.75;
}
html[data-theme='dark'] .feature-card__icon {
  border-color: transparent;
  background: transparent;
  color: #93C5FD;
}

/* ---------- 实时数据战报 ---------- */
.section--stats { padding-top: 96px; }
.live-stats {
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  overflow: hidden;
  padding: 8px 12px;
  border: 1px solid var(--event-border);
  border-radius: 20px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(24px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(120%);
  box-shadow: var(--event-shadow);
}
.live-stat {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  align-items: center;
  min-width: 0;
  padding: 28px 20px 26px;
  text-align: center;
}
.live-stat strong {
  color: var(--event-title);
  font-family: var(--ui-font);
  font-size: clamp(34px, 4vw, 52px);
  font-weight: 750;
  letter-spacing: -.045em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.live-stat span { margin-top: 12px; color: var(--event-title); font-size: 13px; font-weight: 600; }
.live-stat small { margin-top: 6px; color: var(--event-meta); font-size: 11px; line-height: 1.6; }

/* ---------- 热门航线 / 活动 Bento ---------- */
.section--bento { padding-top: 64px; }
.bento-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(168px, 1fr));
  gap: 16px;
}
.bento-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  padding: 22px;
  border: 1px solid var(--event-border);
  border-radius: 18px;
  background-color: var(--event-bg);
  background-image: var(--event-tint);
  backdrop-filter: blur(24px) saturate(120%);
  -webkit-backdrop-filter: blur(24px) saturate(120%);
  box-shadow: var(--event-shadow);
  color: var(--event-title);
  text-decoration: none;
  transition: transform .22s ease, background-color .22s ease, box-shadow .22s ease;
}
.bento-card:hover {
  background-color: var(--event-bg-hover);
  transform: translateY(-2px);
  text-decoration: none;
  box-shadow: 0 14px 32px rgba(25, 42, 64, .14);
}
.bento-card--hero { grid-column: span 2; grid-row: span 2; padding: 28px; }
.bento-card__top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.bento-card__label {
  color: var(--event-meta);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: .02em;
}
.bento-card__arrow { color: var(--event-meta); font-size: 15px; }
.bento-card__body { margin-top: auto; padding-top: 28px; }
.bento-card__body h3 {
  overflow: hidden;
  margin: 0 0 8px;
  color: var(--event-title);
  font-family: var(--ui-font);
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -.015em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bento-card--hero .bento-card__body h3 { font-size: clamp(23px, 3vw, 32px); white-space: normal; }
.bento-card__body p { margin: 0; color: var(--event-meta); font-size: 12px; line-height: 1.7; }
.bento-card__note { display: block; margin-top: 14px; color: var(--event-meta); font-size: 11px; }
.bento-card :deep(.badge) {
  border: 1px solid rgba(37, 99, 235, .14);
  background: rgba(37, 99, 235, .08);
  color: #1D4ED8;
}
html[data-theme='dark'] .bento-card :deep(.badge) {
  border-color: rgba(255, 255, 255, .15);
  background: rgba(255, 255, 255, .10);
  color: #fff;
}
.route-diagram {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 30px;
  color: var(--event-meta);
  font-family: var(--ui-font);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .06em;
}
.route-diagram__point { flex-shrink: 0; }
.route-diagram__line { position: relative; display: flex; flex: 1; align-items: center; min-width: 40px; height: 18px; }
.route-diagram__line::before {
  position: absolute;
  top: 50%;
  right: 0;
  left: 0;
  border-top: 1px dashed rgba(15, 23, 42, .22);
  content: "";
}
.route-diagram__line i {
  position: absolute;
  left: 0;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--event-title);
  transform: translateY(-50%);
}
.route-diagram__line svg {
  position: absolute;
  left: 50%;
  width: 15px;
  height: 15px;
  color: var(--event-title);
  transform: translate(-50%, -50%);
}
html[data-theme='dark'] .route-diagram__line::before { border-top-color: rgba(255, 255, 255, .28); }
html[data-theme='dark'] .route-diagram__line i { background: #fff; }
html[data-theme='dark'] .route-diagram__line svg { color: #fff; }


/* ---------- 浅色模式：高透白玻璃 + 绝对深色文字 ---------- */
html[data-theme='light'] .portal-home .status-bar,
html[data-theme='light'] .portal-home .feature-card,
html[data-theme='light'] .portal-home .live-stats,
html[data-theme='light'] .portal-home .bento-card,
html[data-theme='light'] .portal-home .leaderboard-panel,
html[data-theme='light'] .portal-home .about-panel {
  color: #111827 !important;
  border: 1px solid rgba(255, 255, 255, .50) !important;
  background-color: rgba(255, 255, 255, .65) !important;
  background-image: none !important;
  backdrop-filter: blur(24px) saturate(120%) !important;
  -webkit-backdrop-filter: blur(24px) saturate(120%) !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, .06) !important;
}

html[data-theme='light'] .portal-home .status-bar:hover,
html[data-theme='light'] .portal-home .feature-card:hover {
  border-color: rgba(255, 255, 255, .9) !important;
  box-shadow: 0 20px 48px rgba(0, 0, 0, .10) !important;
}

html[data-theme='light'] .portal-home .status-value,
html[data-theme='light'] .portal-home .status-bar__head,
html[data-theme='light'] .portal-home .status-bar__hint,
html[data-theme='light'] .portal-home .status-label,
html[data-theme='light'] .portal-home .feature-card h3,
html[data-theme='light'] .portal-home .live-stat strong,
html[data-theme='light'] .portal-home .live-stat span,
html[data-theme='light'] .portal-home .bento-card h3,
html[data-theme='light'] .portal-home .bento-card__label,
html[data-theme='light'] .portal-home .bento-card__arrow,
html[data-theme='light'] .portal-home .bento-card__note,
html[data-theme='light'] .portal-home .section-title,
html[data-theme='light'] .portal-home .about-panel__title,
html[data-theme='light'] .portal-home .leaderboard-panel .section-title,
html[data-theme='light'] .portal-home .rank-user {
  color: #111827 !important;
}

html[data-theme='light'] .portal-home .feature-card p,
html[data-theme='light'] .portal-home .live-stat small,
html[data-theme='light'] .portal-home .bento-card__body p,
html[data-theme='light'] .portal-home .section-subtitle,
html[data-theme='light'] .portal-home .about-panel__text,
html[data-theme='light'] .portal-home .leaderboard-panel .section-subtitle,
html[data-theme='light'] .portal-home .rank-points,
html[data-theme='light'] .portal-home .rank-points small,
html[data-theme='light'] .portal-home .rank-empty,
html[data-theme='light'] .portal-home .rank-index {
  color: #4B5563 !important;
}

html[data-theme='light'] .portal-home .feature-card__icon {
  border-color: transparent !important;
  background: transparent !important;
  color: #1E3A8A !important;
}
html[data-theme='light'] .portal-home .live-stat,
html[data-theme='light'] .portal-home .status-item {
  border-color: rgba(15, 23, 42, .09) !important;
}
html[data-theme='light'] .portal-home .bento-card:hover {
  background-color: rgba(255, 255, 255, .78) !important;
}
html[data-theme='light'] .portal-home .bento-card :deep(.badge) {
  border-color: rgba(37, 99, 235, .14) !important;
  background: rgba(37, 99, 235, .08) !important;
  color: #1D4ED8 !important;
}
html[data-theme='light'] .portal-home .route-diagram__line::before {
  border-top-color: rgba(15, 23, 42, .22) !important;
}
html[data-theme='light'] .portal-home .route-diagram__line i {
  background: #111827 !important;
}
html[data-theme='light'] .portal-home .route-diagram__line svg {
  color: #111827 !important;
}

@media (max-width: 860px) {
  .feature-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .live-stats { flex-wrap: wrap; }
  .live-stat { flex: 1 1 50%; }
  .bento-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: auto; }
  .bento-card--hero { grid-column: span 2; grid-row: auto; min-height: 300px; }
  .status-grid { flex-wrap: wrap; }
  .status-item { flex: 1 1 50%; padding: 16px; }
  .event-grid { grid-template-columns: 1fr; }
  .split-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .feature-grid { grid-template-columns: 1fr; }
  .live-stats { flex-direction: column; }
  .live-stat { flex: 1 1 100%; }
  .bento-grid { grid-template-columns: 1fr; }
  .bento-card--hero { grid-column: auto; min-height: 280px; }
  .hero { padding: 62px 20px 42px; }
  .hero__content h1 { font-size: 34px; }
  .status-section { max-width: 100%; padding: 0 16px; }
  .status-bar { padding: 18px 16px; }
  .status-grid { flex-direction: column; }
  .status-item { flex: 1 1 100%; padding: 10px 0; }
  .status-value { font-size: 32px; }
  .section { padding: 42px 16px; }
  .section--features { padding-top: 64px; }
  .section-head { align-items: flex-start; flex-direction: column; gap: 10px; }
  .hero__actions { flex-direction: column; align-items: stretch; }
  .hero__actions a { width: 100%; }
}
</style>
