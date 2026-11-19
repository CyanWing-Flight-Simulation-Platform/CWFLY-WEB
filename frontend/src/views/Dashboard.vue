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
      <button class="btn btn-outline btn-sm dash-refresh" :disabled="refreshing" @click="refreshAll">
        {{ refreshing ? '刷新中...' : '刷新数据' }}
      </button>
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
        <section class="dash-card">
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
          <div v-else class="dash-empty">暂无在线用户或 FSD 暂时不可用</div>
        </section>
      </div>

      <div class="dash-col dash-col--side">
        <!-- 个人信息 -->
        <section class="dash-card">
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
        <section class="dash-card">
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
const refreshing = ref(false)
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
      onlineUsers: data.onlineUsers ?? onlineStore.count ?? '--'
    }
  }
  if (eventsRes.status === 'fulfilled') {
    events.value = Array.isArray(eventsRes.value?.data) ? eventsRes.value.data : []
  }
  await Promise.allSettled([loadStaff(), loadFsd()])
}

async function refreshAll() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadDashboard()
  } finally {
    refreshing.value = false
  }
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
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dash-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
  border: 1px solid var(--glass-border-strong);
  border-radius: 18px;
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  box-shadow: 0 8px 26px rgba(15, 23, 42, .05);
}
.dash-hero__identity { display: flex; min-width: 0; align-items: center; gap: 16px; }
.dash-avatar {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  overflow: hidden;
  border: 1px solid var(--glass-border-strong);
  border-radius: 18px;
  background: var(--c-bg-soft, rgba(128, 128, 128, .08));
}
.dash-avatar img { width: 100%; height: 100%; object-fit: cover; }
.dash-hero__text { min-width: 0; }
.dash-hero__text h1 { margin: 0; color: var(--c-text); font-size: 21px; font-weight: 700; letter-spacing: .01em; }
.dash-hero__text p {
  margin: 5px 0 0;
  color: var(--c-text-muted);
  font-size: 13px;
  line-height: 1.5;
}
.dash-hero__text .dot { margin: 0 6px; opacity: .5; }
.dash-refresh { flex-shrink: 0; }

.dash-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.kpi-card {
  position: relative;
  overflow: hidden;
  padding: 18px 20px;
  border: 1px solid var(--glass-border-strong);
  border-radius: 16px;
  background: var(--glass-bg-strong);
  box-shadow: 0 8px 22px rgba(15, 23, 42, .04);
}
.kpi-label { color: var(--c-text-muted); font-size: 12px; font-weight: 500; }
.kpi-value {
  margin-top: 9px;
  color: var(--c-text);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}
.kpi-value small { margin-left: 3px; color: var(--c-text-muted); font-size: 13px; font-weight: 600; }
.kpi-note { margin-top: 7px; color: var(--c-text-muted); font-size: 11px; opacity: .75; }

.dash-quick {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.quick-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--glass-border-strong);
  border-radius: 14px;
  background: var(--glass-bg-strong);
  color: var(--c-text);
  text-decoration: none;
  transition: transform .16s ease, border-color .16s ease, background-color .16s ease;
}
.quick-card:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, .28);
  text-decoration: none;
}
.quick-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 10px;
  background: rgba(37, 99, 235, .09);
  color: var(--c-primary);
}
.quick-card__body { display: flex; flex: 1; min-width: 0; flex-direction: column; gap: 2px; }
.quick-card__body strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.quick-card__body small { overflow: hidden; color: var(--c-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.quick-card__arrow { color: var(--c-text-muted); font-size: 14px; opacity: .6; }

.dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr);
  gap: 16px;
  align-items: start;
}
.dash-col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.dash-card {
  padding: 20px 22px;
  border: 1px solid var(--glass-border-strong);
  border-radius: 18px;
  background: var(--glass-bg-strong);
  box-shadow: 0 8px 26px rgba(15, 23, 42, .04);
}
.dash-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.dash-card__head h2 { margin: 0; color: var(--c-text); font-size: 15px; font-weight: 700; }
.dash-card__head p { margin: 4px 0 0; color: var(--c-text-muted); font-size: 11px; }
.dash-link { flex-shrink: 0; color: var(--c-primary); font-size: 12px; text-decoration: none; }
.dash-link:hover { text-decoration: none; }

.online-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.online-metric {
  padding: 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, .025);
  text-align: center;
}
.online-metric strong { display: block; color: var(--c-text); font-size: 22px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.online-metric span { display: block; margin-top: 4px; color: var(--c-text-muted); font-size: 11px; }
.online-list { margin-top: 14px; }
.online-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-top: 1px solid var(--c-border-light);
  font-size: 12px;
}
.online-row:first-child { border-top: 0; }
.online-row__callsign { min-width: 76px; color: var(--c-text); font-weight: 700; }
.online-row__meta { color: var(--c-text-muted); }
.online-row__route { margin-left: auto; color: var(--c-text-muted); text-align: right; }
.online-more { padding-top: 10px; border-top: 1px solid var(--c-border-light); color: var(--c-text-muted); font-size: 11px; }
.online-more a { color: var(--c-primary); text-decoration: none; }
.dash-empty { padding: 24px 8px; color: var(--c-text-muted); font-size: 12px; text-align: center; }

.info-list { display: flex; flex-direction: column; }
.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 17px;
  padding: 10px 0;
  border-top: 1px solid var(--c-border-light);
  font-size: 12px;
}
.info-row:first-child { border-top: 0; padding-top: 0; }
.info-row span { color: var(--c-text-muted); }
.info-row strong { color: var(--c-text); font-weight: 600; text-align: right; }

.event-list { display: flex; flex-direction: column; }
.event-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid var(--c-border-light);
  color: var(--c-text);
  text-decoration: none;
}
.event-row:first-child { border-top: 0; padding-top: 0; }
.event-date { flex-shrink: 0; color: var(--c-primary); font-size: 11px; font-variant-numeric: tabular-nums; }
.event-main { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.event-main strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.event-main small { overflow: hidden; color: var(--c-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.calendar-card { min-width: 0; }
.calendar-nav { display: flex; align-items: center; gap: 8px; }
.calendar-nav strong { min-width: 94px; color: var(--c-text); font-size: 12px; font-weight: 600; text-align: center; }
.calendar-nav__btn,
.calendar-today-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  padding: 0 9px;
  border: 1px solid var(--c-border-light);
  border-radius: 7px;
  background: transparent;
  color: var(--c-text-muted);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
}
.calendar-nav__btn { width: 26px; padding: 0; font-size: 16px; }
.calendar-nav__btn:hover,
.calendar-today-btn:hover { border-color: var(--c-primary); color: var(--c-primary); }
.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  border-bottom: 1px solid var(--c-border-light);
  color: var(--c-text-muted);
  font-size: 11px;
  text-align: center;
}
.calendar-weekdays span { padding: 8px 0; }
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  border-left: 1px solid var(--c-border-light);
  border-top: 1px solid var(--c-border-light);
}
.calendar-day {
  min-height: 86px;
  padding: 7px 8px;
  border-right: 1px solid var(--c-border-light);
  border-bottom: 1px solid var(--c-border-light);
  background: rgba(255, 255, 255, .02);
}
.calendar-day.is-empty { background: rgba(15, 23, 42, .018); }
.calendar-day.is-today { background: rgba(37, 99, 235, .055); box-shadow: inset 0 0 0 1px rgba(37, 99, 235, .22); }
.calendar-day__num { color: var(--c-text-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.calendar-day.is-today .calendar-day__num { color: var(--c-primary); font-weight: 700; }
.calendar-day__events { display: flex; flex-direction: column; gap: 3px; margin-top: 5px; }
.calendar-event {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px 4px;
  overflow: hidden;
  border-radius: 4px;
  background: rgba(37, 99, 235, .08);
  color: var(--c-primary);
  font-size: 10px;
  text-decoration: none;
}
.calendar-event:hover { background: rgba(37, 99, 235, .14); text-decoration: none; }
.calendar-event__time { flex-shrink: 0; opacity: .8; }
.calendar-event__title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.calendar-event__more { color: var(--c-text-muted); font-size: 10px; }

@media (max-width: 1100px) {
  .dash-grid { grid-template-columns: 1fr; }
  .dash-col--side { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 800px) {
  .dash-kpis,
  .dash-quick { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .online-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 620px) {
  .dash-hero { align-items: flex-start; padding: 18px; }
  .dash-hero__text h1 { font-size: 18px; }
  .dash-kpis,
  .dash-quick,
  .dash-col--side { grid-template-columns: 1fr; }
  .dash-card { padding: 16px; }
  .calendar-day { min-height: 64px; padding: 5px; }
  .calendar-day__events { display: none; }
}
</style>
