<template>
  <div class="dashboard fade-in">
    <!-- 顶部身份区 -->
    <section class="dash-hero">
      <div class="dash-hero__identity">
        <div class="dash-avatar">
          <img :src="avatarUrl" :alt="user.username" @error="onAvatarError" />
        </div>
        <div class="dash-hero__text">
          <h1>{{ greeting.time }}，{{ user.username }}</h1>
          <p>
            CID {{ user.cid }}
            <span class="dot">·</span>
            {{ roleLabel }}
            <span class="dot">·</span>
            注册于 {{ formatDate(user.profile?.createdAt) }}
          </p>
        </div>
      </div>
    </section>

    <!-- 核心 KPI -->
    <section class="dash-kpis">
      <div v-for="kpi in kpis" :key="kpi.label" class="kpi-card">
        <div class="kpi-label">{{ kpi.label }}</div>
        <div class="kpi-value">{{ kpi.value }}<small v-if="kpi.unit">{{ kpi.unit }}</small></div>
        <div class="kpi-note">{{ kpi.note }}</div>
      </div>
    </section>

    <!-- 快捷入口 -->
    <section class="dash-quick">
      <router-link v-for="action in quickActions" :key="action.to" :to="action.to" class="quick-card">
        <span class="quick-card__icon" v-html="action.icon"></span>
        <span class="quick-card__body">
          <strong>{{ action.title }}</strong>
          <small>{{ action.desc }}</small>
        </span>
        <span class="quick-card__arrow">→</span>
      </router-link>
    </section>

    <div class="dash-grid">
      <div class="dash-col dash-col--main">
        <!-- 在线网络 -->
        <section class="dash-card online-card">
          <div class="dash-card__head">
            <div>
              <h2>在线网络</h2>
              <p>FSD 连飞网络实时状态</p>
            </div>
            <router-link to="/map" class="dash-link">查看地图 →</router-link>
          </div>
          <div class="online-metrics">
            <div v-for="metric in onlineMetrics" :key="metric.label" class="online-metric">
              <strong>{{ metric.value }}</strong>
              <span>{{ metric.label }}</span>
            </div>
          </div>
        </section>

        <!-- 网络动态 -->
        <section class="dash-card network-card">
          <div class="dash-card__head">
            <div>
              <h2>网络动态</h2>
              <p>在线机组与管制席位</p>
            </div>
            <router-link to="/map" class="dash-link">在线地图 →</router-link>
          </div>
          <div v-if="fsdRows.length" class="online-list">
            <div v-for="row in fsdRows.slice(0, 6)" :key="row.kind + row.callsign" class="online-row">
              <span class="online-row__callsign">{{ row.callsign }}</span>
              <span class="badge" :class="row.kind === 'atc' ? 'badge-warning' : 'badge-info'">
                {{ row.kind === 'atc' ? '管制' : '机组' }}
              </span>
              <span class="online-row__meta">
                {{ row.kind === 'atc' ? atcFacilityName(row.facilityType) : (row.aircraft || '-') }}
              </span>
              <span class="online-row__route">
                {{ row.kind === 'atc' ? (row.frequency || '-') : ((row.dep || '---') + ' → ' + (row.dest || '---')) }}
              </span>
            </div>
            <div v-if="fsdRows.length > 6" class="online-more">
              还有 {{ fsdRows.length - 6 }} 个在线用户，前往
              <router-link to="/map">在线地图</router-link>
              查看
            </div>
          </div>
          <div v-else class="dash-empty network-empty">暂无在线用户或 FSD 暂时不可用</div>
        </section>
      </div>

      <div class="dash-col dash-col--side">
        <!-- 个人信息 -->
        <section class="dash-card personal-card">
          <div class="dash-card__head">
            <div>
              <h2>个人信息</h2>
              <p>当前账号概览</p>
            </div>
            <router-link to="/profile" class="dash-link">编辑 →</router-link>
          </div>
          <div class="info-list">
            <div class="info-row"><span>用户名</span><strong>{{ user.username }}</strong></div>
            <div class="info-row"><span>权限等级</span><strong>{{ roleLabel }}</strong></div>
            <div class="info-row"><span>FSD 权限</span><strong>{{ fsdLevelName(user.profile?.fsdLevel ?? 1) }}</strong></div>
            <div class="info-row"><span>注册时间</span><strong>{{ formatDate(user.profile?.createdAt) }}</strong></div>
          </div>
        </section>

        <!-- 近期活动 -->
        <section class="dash-card upcoming-card">
          <div class="dash-card__head">
            <div>
              <h2>即将举行</h2>
              <p>近期连飞活动</p>
            </div>
            <router-link to="/network" class="dash-link">全部 →</router-link>
          </div>
          <div v-if="upcomingEvents.length" class="event-list">
            <router-link v-for="event in upcomingEvents" :key="event.id" to="/network" class="event-row">
              <span class="event-date">{{ event.date }}</span>
              <span class="event-main">
                <strong>{{ event.title }}</strong>
                <small>{{ event.time }} · {{ event.dep || '---' }} → {{ event.arr || '---' }}</small>
              </span>
            </router-link>
          </div>
          <div v-else class="dash-empty">暂无近期活动</div>
        </section>
      </div>
    </div>

    <!-- 活动日历 -->
    <section class="dash-card calendar-card">
      <div class="dash-card__head">
        <div>
          <h2>活动日历</h2>
          <p>本月连飞活动安排</p>
        </div>
        <div class="calendar-nav">
          <button class="calendar-nav__btn" type="button" aria-label="上个月" @click="changeMonth(-1)">‹</button>
          <strong>{{ calendarTitle }}</strong>
          <button class="calendar-nav__btn" type="button" aria-label="下个月" @click="changeMonth(1)">›</button>
          <button class="calendar-today-btn" type="button" @click="resetCalendar">今天</button>
        </div>
      </div>
      <div class="calendar-weekdays">
        <span v-for="day in weekdays" :key="day">{{ day }}</span>
      </div>
      <div class="calendar-grid">
        <div
          v-for="(cell, index) in calendarCells"
          :key="index"
          class="calendar-day"
          :class="{ 'is-empty': !cell.day, 'is-today': cell.isToday }"
        >
          <template v-if="cell.day">
            <span class="calendar-day__num">{{ cell.day }}</span>
            <div class="calendar-day__events">
              <router-link
                v-for="event in cell.events.slice(0, 2)"
                :key="event.id"
                to="/network"
                class="calendar-event"
                :title="event.title"
              >
                <span class="calendar-event__time">{{ event.time }}</span>
                <span class="calendar-event__title">{{ event.title }}</span>
              </router-link>
              <span v-if="cell.events.length > 2" class="calendar-event__more">+{{ cell.events.length - 2 }}</span>
            </div>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useUserStore } from '@/store/user'
import { useOnlineUsersStore } from '@/store/onlineUsers'
import { dashboardApi, adminApi, eventsApi, flightplanApi } from '@/api'
import { getBeijingHour } from '@/utils/timeBg'

const user = useUserStore()
const onlineStore = useOnlineUsersStore()

const nowTick = ref(0)
const nowTimer = setInterval(() => { nowTick.value = Date.now() }, 30000)

const greeting = computed(() => {
  void nowTick.value
  const h = getBeijingHour()
  if (h >= 5 && h < 11) return { time: '早上好', wish: '祝您今日飞行顺利' }
  if (h >= 11 && h < 13) return { time: '中午好', wish: '午餐时间，休息好再继续巡航' }
  if (h >= 13 && h < 18) return { time: '下午好', wish: '祝您航程一路顺风' }
  if (h >= 18 && h < 23) return { time: '晚上好', wish: '夜航模式已开启，祝您平安落地' }
  return { time: '夜深了', wish: '红眼航班辛苦了，早点休息' }
})

const platformStats = ref({
  totalUsers: '--',
  controllerCount: '--',
  eventCount: '--',
  onlineUsers: '--'
})
const events = ref([])
const fsdPilots = ref([])
const fsdAtc = ref([])
const fsdError = ref('')
const allStaff = ref([])
const onlineStaff = computed(() => allStaff.value.filter((s) => s.online))

const avatarUrl = ref(user.profile?.avatar || '/logo/logo_light.jpg')
const roleLabel = computed(() => {
  const rating = Number(user.profile?.rating ?? user.rating ?? 0)
  const fsdLevel = Number(user.profile?.fsdLevel ?? 1)
  if (rating >= 12) return '超级管理员'
  if (rating >= 11) return '管理员'
  if (rating >= 8) return '协管员'
  if (fsdLevel >= 2) return '管制员'
  return '飞行学员'
})

const flightHours = computed(() => Number(user.profile?.totalFlightHours || 0).toFixed(1))
const controllerHours = computed(() => Number(user.profile?.totalControllerHours || 0).toFixed(1))

const kpis = computed(() => [
  { label: '连飞总时长', value: flightHours.value, unit: 'h', note: '累计连飞在线时长', tone: 'blue' },
  { label: '管制总时长', value: controllerHours.value, unit: 'h', note: '累计管制在线时长', tone: 'green' },
  { label: '平台在线', value: platformStats.value.onlineUsers, note: '当前在线用户', tone: 'orange' },
  { label: '注册用户', value: platformStats.value.totalUsers, note: 'CWFLY 成员总数', tone: 'purple' }
])

const quickActions = [
  {
    to: '/flight-plan',
    title: '飞行计划',
    desc: '提交 / 查看连飞计划',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 19V5M5 12l7-7 7 7"/></svg>'
  },
  {
    to: '/network',
    title: '连飞活动',
    desc: '近期活动与报名',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>'
  },
  {
    to: '/charts',
    title: '航情查询',
    desc: '机场、航路与航图',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>'
  },
  {
    to: '/profile',
    title: '个人中心',
    desc: '账号与绑定设置',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
  }
]

const onlineMetrics = computed(() => [
  { label: '在线机组', value: fsdPilots.value.length },
  { label: '在线管制', value: fsdAtc.value.length },
  { label: '职员在线', value: onlineStaff.value.length },
  { label: '活动数量', value: platformStats.value.eventCount }
])

const ATC_FACILITY_NAMES = { 0: 'OBS', 1: 'FSS', 2: 'DEL', 3: 'GND', 4: 'TWR', 5: 'APP', 6: 'CTR' }
function atcFacilityName(t) {
  return ATC_FACILITY_NAMES[Number(t)] || ('FAC' + (t ?? ''))
}

const FSD_LEVEL_NAMES = {
  0: '飞行员', 1: '观察员', 2: '地面/放行 S1', 3: '塔台 S2',
  4: '终端 S3', 5: '区域 C1', 6: '区域 C2', 7: '区域 C3',
  8: '塔台教员 I1', 9: '进近教员 I2', 10: '区域教员 I3',
  11: 'SUP', 12: 'ADM'
}
function fsdLevelName(level) {
  return FSD_LEVEL_NAMES[level] || `未知(${level})`
}

const fsdRows = computed(() => {
  const byCallsign = (a, b) => String(a.callsign || '').localeCompare(String(b.callsign || ''), 'zh-CN')
  const atc = [...fsdAtc.value].sort(byCallsign).map((a) => ({ kind: 'atc', ...a }))
  const pilots = [...fsdPilots.value].sort(byCallsign).map((p) => ({ kind: 'pilot', ...p }))
  return [...atc, ...pilots]
})

const upcomingEvents = computed(() => {
  const now = Date.now()
  return [...events.value]
    .filter((event) => {
      const start = Number(event._start)
      return Number.isFinite(start) && start >= now - 60 * 60 * 1000
    })
    .sort((a, b) => Number(a._start) - Number(b._start))
    .slice(0, 3)
})

const weekdays = ['日', '一', '二', '三', '四', '五', '六']
const calendarCursor = ref(new Date())
const calendarTitle = computed(() => {
  const d = calendarCursor.value
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月`
})

function dateKey(value) {
  if (!value) return ''
  if (typeof value === 'string') return value.slice(0, 10)
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const eventsByDate = computed(() => {
  const map = {}
  for (const event of events.value) {
    const key = event.date || dateKey(event._start)
    if (!key) continue
    ;(map[key] ||= []).push(event)
  }
  return map
})

const calendarCells = computed(() => {
  const cursor = calendarCursor.value
  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  const firstDay = new Date(year, month, 1).getDay()
  const days = new Date(year, month + 1, 0).getDate()
  const todayKey = dateKey(new Date())
  const cells = []
  for (let i = 0; i < 42; i += 1) {
    const day = i - firstDay + 1
    if (day < 1 || day > days) {
      cells.push({ day: 0, events: [] })
      continue
    }
    const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    cells.push({ day, key, isToday: key === todayKey, events: eventsByDate.value[key] || [] })
  }
  return cells
})

function changeMonth(delta) {
  const d = new Date(calendarCursor.value)
  d.setDate(1)
  d.setMonth(d.getMonth() + delta)
  calendarCursor.value = d
}
function resetCalendar() {
  calendarCursor.value = new Date()
}

async function loadDashboard() {
  const [statsRes, eventsRes] = await Promise.allSettled([
    dashboardApi.stats(),
    eventsApi.list()
  ])
  if (statsRes.status === 'fulfilled' && statsRes.value?.data) {
    const data = statsRes.value.data
    platformStats.value = {
      totalUsers: data.totalUsers ?? '--',
      controllerCount: data.controllerCount ?? '--',
      eventCount: data.eventCount ?? '--',
      onlineUsers: data.webOnlineUsers ?? data.onlineUsers ?? onlineStore.count ?? '--'
    }
  }
  if (eventsRes.status === 'fulfilled') {
    events.value = Array.isArray(eventsRes.value?.data) ? eventsRes.value.data : []
  }
  await Promise.allSettled([loadStaff(), loadFsd()])
}

async function loadStaff() {
  if (!user.hasPermission('online')) return
  try {
    const res = await adminApi.online()
    allStaff.value = res.data.staff || []
  } catch { /* ignore */ }
}

async function loadFsd() {
  fsdError.value = ''
  try {
    const [pilotRes, atcRes] = await Promise.allSettled([
      flightplanApi.fsdOnline(),
      flightplanApi.fsdControllers()
    ])
    if (pilotRes.status === 'fulfilled' && pilotRes.value?.data) {
      fsdPilots.value = Array.isArray(pilotRes.value.data) ? pilotRes.value.data : []
    }
    if (atcRes.status === 'fulfilled' && atcRes.value?.data) {
      fsdAtc.value = Array.isArray(atcRes.value.data) ? atcRes.value.data : []
    }
  } catch {
    fsdError.value = 'FSD 连接失败'
  }
}

function formatDate(value) {
  if (!value) return '未知'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 10)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function onAvatarError(e) {
  e.target.src = '/logo/logo_light.jpg'
}

let dashboardTimer = null
onMounted(() => {
  avatarUrl.value = user.profile?.avatar || '/logo/logo_light.jpg'
  loadDashboard()
  dashboardTimer = setInterval(loadDashboard, 30000)
})

onUnmounted(() => {
  clearInterval(nowTimer)
  if (dashboardTimer) clearInterval(dashboardTimer)
})

watch(() => onlineStore.count, (count) => {
  if (count != null) platformStats.value.onlineUsers = count
})
watch(() => user.profile?.avatar, (value) => {
  if (value) avatarUrl.value = value
})
</script>

<style scoped>
/* 仪表盘：无边框、无高光、深色磨砂玻璃；全部文字不添加阴影 */
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
  --dash-bg: var(--ui-card-bg);
  --dash-bg-hover: var(--ui-card-bg-hover);
  --dash-text: var(--ui-text);
  --dash-soft: var(--ui-text-secondary);
  --dash-faint: var(--ui-text-muted);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

/* 所有卡片：只保留深色磨砂底，无边框、无阴影、无内高光 */
.dash-hero,
.kpi-card,
.quick-card,
.dash-card {
  border: none;
  box-shadow: none;
  background: var(--dash-bg);
  backdrop-filter: var(--ui-card-filter);
  -webkit-backdrop-filter: var(--ui-card-filter);
}

.dash-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
  border-radius: 18px;
}
.dash-hero__identity { display: flex; min-width: 0; align-items: center; gap: 16px; }
.dash-avatar {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  overflow: hidden;
  border: none;
  border-radius: 16px;
  background: var(--ui-ghost-bg);
}
.dash-avatar img { width: 100%; height: 100%; object-fit: cover; }
.dash-hero__text { min-width: 0; }
.dash-hero__text h1 {
  margin: 0;
  color: var(--dash-text);
  font-size: 21px;
  font-weight: 700;
  letter-spacing: .01em;
}
.dash-hero__text p {
  margin: 5px 0 0;
  color: var(--dash-soft);
  font-size: 13px;
  line-height: 1.5;
}
.dash-hero__text .dot { margin: 0 6px; opacity: .4; }

.dashboard .badge {
  border: none;
  background: var(--ui-ghost-bg);
  color: var(--dash-text);
}

.dash-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.kpi-card {
  position: relative;
  overflow: hidden;
  padding: 20px 22px;
  border-radius: 16px;
}
.kpi-label {
  color: var(--dash-soft);
  font-size: 11px;
  font-weight: 400;
}
.kpi-value {
  margin-top: 10px;
  color: var(--dash-text);
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -.02em;
  font-variant-numeric: tabular-nums;
}
.kpi-value small {
  margin-left: 4px;
  color: var(--dash-soft);
  font-size: 14px;
  font-weight: 500;
}
.kpi-note { margin-top: 8px; color: var(--dash-faint); font-size: 11px; }

.dash-quick {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.quick-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 17px;
  border-radius: 14px;
  color: var(--dash-text);
  text-decoration: none;
  transition: background-color .18s ease, transform .18s ease;
}
.quick-card:hover {
  background: var(--dash-bg-hover);
  text-decoration: none;
}
.quick-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background: var(--ui-ghost-bg);
  color: var(--dash-text);
}
.quick-card__body { display: flex; flex: 1; min-width: 0; flex-direction: column; gap: 2px; }
.quick-card__body strong { overflow: hidden; color: var(--dash-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.quick-card__body small { overflow: hidden; color: var(--dash-soft); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.quick-card__arrow { color: var(--dash-soft); font-size: 14px; }

.dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr);
  grid-template-areas:
    "online personal"
    "network upcoming";
  gap: 16px;
  align-items: stretch;
}
/* 两列拆成网格：在线网络只占第一行，底边与“即将举行”顶部对齐 */
.dash-col--main,
.dash-col--side { display: contents; }
.dash-col {
  min-width: 0;
}
.online-card { grid-area: online; }
.network-card { grid-area: network; }
.personal-card { grid-area: personal; }
.upcoming-card { grid-area: upcoming; }
.dash-card {
  height: auto;
  min-height: 0;
  padding: 22px 24px;
  border-radius: 18px;
}
/* 侧栏只按内容高度排列，避免“即将举行”被拉伸成空盒 */
.dash-col--main > .dash-card,
.dash-col--side > .dash-card { width: 100%; }
.upcoming-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  min-height: 0;
  align-self: stretch;
}
.upcoming-card .dash-empty { padding: 8px; margin: auto 0; }
.dash-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.dash-card__head h2 { margin: 0; color: var(--dash-text); font-size: 15px; font-weight: 700; }
.dash-card__head p { margin: 4px 0 0; color: var(--dash-soft); font-size: 11px; }
.dash-link { flex-shrink: 0; color: var(--dash-soft); font-size: 12px; text-decoration: none; }
.dash-link:hover { color: var(--dash-text); text-decoration: none; }

/* 在线网络：一整块透明容器，四项横向均分、垂直居中，无内部方块和边框 */
.online-card { display: flex; flex-direction: column; align-self: stretch; padding-bottom: 18px; }
.online-card .dash-card__head { margin-bottom: 0; }
.online-metrics {
  display: flex;
  flex: 1;
  justify-content: space-around;
  align-items: center;
  gap: 16px;
  padding: 6px 0;
}
.online-metric {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  border: none;
  background: none;
  text-align: center;
}
.online-metric strong {
  display: block;
  color: var(--dash-text);
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -.02em;
  font-variant-numeric: tabular-nums;
}
.online-metric span {
  display: block;
  margin-top: 10px;
  color: var(--dash-soft);
  font-size: 11px;
  font-weight: 400;
}
.online-list { display: flex; flex-direction: column; gap: 2px; margin-top: 10px; }
.online-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  transition: background-color .16s ease;
}
.online-row:hover { background: var(--ui-table-row-hover); }
.online-row__callsign { min-width: 76px; color: var(--dash-text); font-weight: 600; }
.online-row__meta { color: var(--dash-soft); }
.online-row__route { margin-left: auto; color: var(--dash-soft); text-align: right; }
.online-more { padding: 10px 10px 0; color: var(--dash-faint); font-size: 11px; }
.online-more a { color: var(--dash-soft); text-decoration: none; }
.online-more a:hover { color: var(--dash-text); }
.dash-empty { padding: 14px 8px 6px; color: var(--dash-faint); font-size: 12px; text-align: center; }
.network-card { display: flex; flex-direction: column; align-self: stretch; }
.network-card .dash-empty { margin: auto 0; padding: 8px; }

/* 个人信息：无分割线，只用间距与左浅右白的字色对比 */
.info-list { display: flex; flex-direction: column; gap: 0; }
.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 17px;
  padding: 14px 0;
  border: none;
  font-size: 13px;
}
.info-row span { color: var(--dash-soft); font-size: 12px; font-weight: 400; }
.info-row strong { color: var(--dash-text); font-size: 13px; font-weight: 700; text-align: right; }

.event-list { display: flex; flex-direction: column; gap: 4px; }
.event-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 0;
  border: none;
  color: var(--dash-text);
  text-decoration: none;
}
.event-date { flex-shrink: 0; color: var(--dash-soft); font-size: 11px; font-variant-numeric: tabular-nums; }
.event-main { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.event-main strong { overflow: hidden; color: var(--dash-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.event-main small { overflow: hidden; color: var(--dash-soft); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

/* 日历：去掉表格线，用留白和轻微底色分组 */
.calendar-card { min-width: 0; }
.calendar-nav { display: flex; align-items: center; gap: 8px; }
.calendar-nav strong { min-width: 94px; color: var(--dash-text); font-size: 12px; font-weight: 600; text-align: center; }
.calendar-nav__btn,
.calendar-today-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  padding: 0 9px;
  border: none;
  border-radius: 7px;
  background: var(--ui-ghost-bg);
  color: var(--dash-soft);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
}
.calendar-nav__btn { width: 26px; padding: 0; font-size: 16px; }
.calendar-nav__btn:hover,
.calendar-today-btn:hover { background: var(--ui-ghost-hover); color: var(--dash-text); }
.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  border: none;
  color: var(--dash-soft);
  font-size: 11px;
  text-align: center;
}
.calendar-weekdays span { padding: 8px 0; }
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  border: none;
}
.calendar-day {
  min-height: 82px;
  padding: 7px 8px;
  border: none;
  border-radius: 8px;
  background: var(--ui-ghost-bg);
}
.calendar-day.is-empty { background: transparent; }
.calendar-day.is-today { background: var(--ui-ghost-hover); }
.calendar-day__num { color: var(--dash-soft); font-size: 11px; font-variant-numeric: tabular-nums; }
.calendar-day.is-today .calendar-day__num { color: var(--dash-text); font-weight: 700; }
.calendar-day__events { display: flex; flex-direction: column; gap: 3px; margin-top: 5px; }
.calendar-event {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 3px 5px;
  overflow: hidden;
  border: none;
  border-radius: 4px;
  background: var(--ui-ghost-bg);
  color: var(--dash-text);
  font-size: 10px;
  text-decoration: none;
}
.calendar-event:hover { background: var(--ui-ghost-hover); text-decoration: none; }
.calendar-event__time { flex-shrink: 0; opacity: .75; }
.calendar-event__title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.calendar-event__more { color: var(--dash-faint); font-size: 10px; }

@media (max-width: 1100px) {
  .dash-grid {
    grid-template-columns: 1fr;
    grid-template-areas: none;
  }
  .dash-col { display: flex; flex-direction: column; gap: 16px; }
  .dash-col--side { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .online-card,
  .network-card,
  .personal-card,
  .upcoming-card { grid-area: auto; }
}
@media (max-width: 800px) {
  .dash-kpis,
  .dash-quick { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .online-metrics { flex-wrap: wrap; }
  .online-metric { flex: 1 1 40%; }
}
@media (max-width: 620px) {
  .dash-hero { align-items: flex-start; padding: 18px; }
  .dash-hero__text h1 { font-size: 18px; }
  .dash-kpis,
  .dash-quick,
  .dash-col--side { grid-template-columns: 1fr; }
  .dash-card { padding: 18px; }
  .calendar-day { min-height: 64px; padding: 5px; }
  .calendar-day__events { display: none; }
}
</style>
