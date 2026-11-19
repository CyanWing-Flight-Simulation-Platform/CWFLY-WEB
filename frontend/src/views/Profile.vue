<template>
  <div class="profile fade-in">
    <div class="page-header">
      <h1>个人中心</h1>
      <p>管理您的账号信息</p>
    </div>

    <!-- 头像（只能使用绑定 QQ 的 QQ 头像） -->
    <div class="card p-lg mb-lg">
      <h3 class="mb-md">头像</h3>
      <div class="flex items-center gap-md">
        <UserAvatar
          class="profile-avatar"
          :src="avatarUrl"
          :name="user.username"
          :size="80"
        />
        <div>
          <p class="text-sm text-muted">头像跟随绑定的 QQ 号自动生成，不支持上传自定义头像。</p>
          <p class="text-xs text-muted mt-sm">在下方「QQ 绑定」中填写/修改 QQ 号即可自动更新头像；解绑 QQ 后显示默认头像。</p>
        </div>
      </div>
    </div>

    <!-- 基本信息 -->
    <div class="card p-lg mb-lg profile-card" :aria-busy="loading">
      <h3 class="mb-md">基本信息</h3>
      <div class="profile-hours">
        <div class="profile-hours__item">
          <span class="profile-hours__label">连飞总时长</span>
          <strong class="profile-hours__value">{{ totalFlightHours }}<small>h</small></strong>
        </div>
        <div class="profile-hours__item">
          <span class="profile-hours__label">管制总时长</span>
          <strong class="profile-hours__value">{{ totalControllerHours }}<small>h</small></strong>
        </div>
      </div>
      <div v-if="loading" aria-busy="true" aria-label="正在加载个人信息">
        <Skeleton :lines="4" :height="16" />
      </div>
      <div v-else class="profile-info-grid">
        <div class="profile-cell"><span class="profile-label">CID</span><span class="profile-value profile-value--strong">{{ user.cid }}</span></div>
        <div class="profile-cell"><span class="profile-label">用户名</span><span class="profile-value">{{ user.username }}</span></div>
        <div class="profile-cell"><span class="profile-label">注册时间</span><span class="profile-value">{{ formatDate(profileData?.createdAt || user.profile?.createdAt) }}</span></div>
        <div class="profile-cell"><span class="profile-label">权限等级</span><span class="profile-value"><UserTag :rating="profileData?.rating ?? 0" /></span></div>
        <div class="profile-cell"><span class="profile-label">FSD 权限</span><span class="profile-value fsd-level-badge">{{ fsdLevelName(profileData?.fsdLevel ?? 1) }}</span></div>
        <div class="profile-cell"><span class="profile-label">邮箱</span><span class="profile-value">{{ profileData?.email || '未绑定' }}</span></div>
      </div>
    </div>

    <!-- 绑定信息 -->
    <div class="card p-lg mb-lg profile-card">
      <h3 class="mb-md">绑定设置</h3>
      <div class="profile-bind">
        <div class="bind-field">
          <label class="profile-label">邮箱</label>
          <div class="bind-row">
            <input v-model="bind.email" class="input bind-input" placeholder="绑定邮箱" />
            <button class="btn btn-primary btn-sm bind-btn" @click="sendVerifyCode" :disabled="codeSending">{{ codeSending ? '发送中' : '发送验证码' }}</button>
          </div>
          <div v-if="showVerifyInput" class="bind-row mt-sm">
            <input v-model="bind.verifyCode" class="input bind-input" placeholder="输入验证码" />
            <button class="btn btn-primary btn-sm bind-btn" @click="verifyEmail" :disabled="verifyLoading">{{ verifyLoading ? '验证中' : '验证' }}</button>
          </div>
        </div>
        <div class="bind-field">
          <label class="profile-label">QQ</label>
          <input v-model="bind.qq" class="input bind-input" placeholder="绑定 QQ 号（自动获取QQ头像）" />
        </div>
        <button class="btn btn-primary btn-sm bind-btn bind-btn--save" @click="saveBind" :disabled="bindLoading">{{ bindLoading ? '保存中...' : '保存绑定' }}</button>
        <p v-if="bindMsg" class="text-sm mt-sm bind-message" :style="{ color: bindMsgType === 'ok' ? 'var(--c-success)' : 'var(--c-danger)' }">{{ bindMsg }}</p>
      </div>
    </div>

    <!-- 自定义背景图 -->
    <div class="card p-lg mb-lg">
      <h3 class="mb-md">自定义背景图</h3>
      <p class="text-sm text-muted mb-md">上传一张图片作为平台的全局背景（支持 JPG/PNG，最大 10MB）</p>
      <div class="flex items-center gap-md flex-wrap">
        <div class="bg-preview" v-if="currentBg">
          <img :src="currentBg" style="width:100%;max-height:150px;object-fit:cover;border-radius:8px;" />
        </div>
        <div>
          <input type="file" accept="image/*" ref="bgFileInput" style="display:none;" @change="uploadBgImage" />
          <button class="btn btn-primary btn-sm" @click="$refs.bgFileInput.click()" :disabled="bgUploading">{{ bgUploading ? '上传中...' : '上传背景图' }}</button>
          <button v-if="profileData?.bgImage" class="btn btn-outline btn-sm ml-sm" @click="resetBgImage" :disabled="bgUploading">恢复默认</button>
          <p v-if="bgMsg" class="text-sm mt-sm" :style="{ color: bgMsgType === 'ok' ? 'var(--c-success)' : 'var(--c-danger)' }">{{ bgMsg }}</p>
        </div>
      </div>
    </div>

    <!-- 界面布局 -->
    <div class="card p-lg mb-lg">
      <h3 class="mb-md">界面布局</h3>
      <p class="text-sm text-muted mb-md">
        选择导航菜单位置，偏好会保存在本机；窗口宽度小于 860px 时自动回退为侧边栏抽屉。
      </p>
      <div class="layout-options">
        <button
          type="button"
          class="layout-option"
          data-layout="sidebar"
          :class="{ active: navLayout === 'sidebar' }"
          @click="setNavLayout('sidebar')"
        >
          <span class="layout-option__preview layout-option__preview--sidebar" aria-hidden="true"><i></i><i></i></span>
          <span class="layout-option__label">侧边栏布局</span>
          <span class="layout-option__hint">菜单固定在左侧，适合宽屏浏览</span>
        </button>
        <button
          type="button"
          class="layout-option"
          data-layout="topbar"
          :class="{ active: navLayout === 'topbar' }"
          @click="setNavLayout('topbar')"
        >
          <span class="layout-option__preview layout-option__preview--topbar" aria-hidden="true"><i></i><i></i></span>
          <span class="layout-option__label">顶部栏布局</span>
          <span class="layout-option__hint">菜单横向排列，内容区域更宽</span>
        </button>
      </div>
      <p v-if="narrowScreen" class="text-xs mt-sm text-muted">当前窗口较窄，已自动使用侧边栏抽屉模式。</p>
    </div>

    <!-- 修改密码 -->
    <div class="card p-lg">
      <h3 class="mb-md">修改密码</h3>
      <div style="max-width:360px;">
        <div class="mb-md"><input v-model="pwd.old" class="input" type="password" placeholder="当前密码" /></div>
        <div class="mb-md"><input v-model="pwd.newP" class="input" type="password" placeholder="新密码" /></div>
        <div class="mb-md"><input v-model="pwd.confirm" class="input" type="password" placeholder="确认新密码" /></div>
        <button class="btn btn-primary" @click="changePwd" :disabled="pwdLoading">{{ pwdLoading ? '修改中...' : '修改密码' }}</button>
        <p v-if="pwdMsg" class="text-sm mt-sm" :style="{ color: pwdMsgType === 'ok' ? 'var(--c-success)' : 'var(--c-danger)' }">{{ pwdMsg }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { navLayout, narrowScreen, setNavLayout } from '@/utils/navLayout'
import api, { profileApi } from '@/api'
import Skeleton from '@/components/base/Skeleton.vue'
import UserAvatar from '@/components/base/UserAvatar.vue'
import UserTag from '@/components/base/UserTag.vue'

const user = useUserStore()
const loading = ref(false)
const profileData = ref(null)
const totalFlightMinutes = ref(0)
const totalControllerMinutes = ref(0)

const avatarUrl = computed(() => profileData.value?.avatar || '')
const totalFlightHours = computed(() => (totalFlightMinutes.value / 60).toFixed(1))
const totalControllerHours = computed(() => (totalControllerMinutes.value / 60).toFixed(1))

const bind = reactive({ email: '', qq: '', verifyCode: '' })
const bindLoading = ref(false)
const bindMsg = ref('')
const bindMsgType = ref('ok')
const showVerifyInput = ref(false)
const codeSending = ref(false)
const verifyLoading = ref(false)

const pwd = ref({ old: '', newP: '', confirm: '' })
const pwdLoading = ref(false)
const pwdMsg = ref('')
const pwdMsgType = ref('ok')

// 自定义背景图
const bgFileInput = ref(null)
const bgUploading = ref(false)
const bgMsg = ref('')
const bgMsgType = ref('ok')
const currentBg = computed(() => profileData.value?.bgImage ? getBgUrl(profileData.value.bgImage) : null)

// FSD 等级映射与用户管理页一致（以用户管理页为准）：
// 0=飞行员 1=观察员 2=地面/放行S1 3=塔台S2 4=终端S3 5=区域C1 6=区域C2 7=区域C3
// 8=塔台教员I1 9=进近教员I2 10=区域教员I3 11=SUP 12=ADM
const FSD_LEVEL_NAMES = {
  0: '飞行员', 1: '观察员', 2: '地面/放行 S1', 3: '塔台 S2',
  4: '终端 S3', 5: '区域 C1', 6: '区域 C2', 7: '区域 C3',
  8: '塔台教员 I1', 9: '进近教员 I2', 10: '区域教员 I3',
  11: 'SUP', 12: 'ADM'
}
function fsdLevelName(level) { return FSD_LEVEL_NAMES[level] || `未知(${level})` }

// 权限等级标签统一由 UserTag 渲染（语义色映射在组件内维护，避免页面重复实现）

// 日期格式化：只显示 YYYY-MM-DD（本地时区）
function formatDate(v) {
  if (!v) return '未知'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 解析 FlightPlan.flightTime（HHMM 或 H:MM）为分钟。 */
function parseFlightMinutes(value) {
  const text = String(value || '').trim()
  if (!text) return 0
  const colon = text.match(/^(\d{1,3}):([0-5]\d)$/)
  if (colon) return Number(colon[1]) * 60 + Number(colon[2])
  if (/^\d{4}$/.test(text)) return Number(text.slice(0, 2)) * 60 + Number(text.slice(2))
  return 0
}

async function loadFlightTotal() {
  try {
    const res = await api.get('/flightplans')
    const plans = Array.isArray(res.data) ? res.data : []
    totalFlightMinutes.value = plans.reduce(
      (sum, plan) => sum + parseFlightMinutes(plan.flightTime),
      0
    )
  } catch { /* 无飞行计划时保持 0 */ }
}

onMounted(async () => {
  loading.value = true
  loadFlightTotal()
  try {
    const res = await profileApi.get()
    profileData.value = res.data
    bind.email = res.data.email || ''
    bind.qq = res.data.qq || ''
    const controllerHours = res.data.controllerHours ?? res.data.totalHours
    if (typeof controllerHours === 'number') {
      totalControllerMinutes.value = controllerHours * 60
    }
    applyBg(res.data.bgImage)
  } catch { /* ignore */ } finally {
    loading.value = false
  }
})

// 背景图相关
function getBgUrl(url) {
  return url ? url + '?t=' + Date.now() : ''
}
function applyBg(url) {
  const bg = getBgUrl(url)
  if (bg) {
    document.documentElement.style.setProperty('--custom-bg', `url(${JSON.stringify(bg)})`)
  } else {
    document.documentElement.style.removeProperty('--custom-bg')
  }
  // 通知 App.vue 的背景层做 3 秒渐变显示
  window.dispatchEvent(new CustomEvent('cw:custom-bg', { detail: bg }))
}

async function uploadBgImage(e) {
  const file = e.target.files[0]
  if (!file) return
  bgUploading.value = true
  bgMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('bgImage', file)
    const res = await api.post('/profile/bg-image', fd, { headers: { 'Content-Type': undefined } })
    profileData.value.bgImage = res.data.bgImage
    applyBg(res.data.bgImage)
    bgMsg.value = '背景图已更新'
    bgMsgType.value = 'ok'
  } catch (e) {
    bgMsg.value = '上传失败: ' + (e.response?.data?.message || e.message)
    bgMsgType.value = 'err'
  } finally { bgUploading.value = false }
}

async function resetBgImage() {
  bgUploading.value = true
  try {
    await api.delete('/profile/bg-image')
    profileData.value.bgImage = ''
    applyBg('')
    bgMsg.value = '已恢复默认背景'
    bgMsgType.value = 'ok'
  } catch (e) {
    bgMsg.value = '操作失败: ' + e.message
    bgMsgType.value = 'err'
  } finally { bgUploading.value = false }
}

async function sendVerifyCode() {
  if (!bind.email) return alert('请先输入邮箱')
  codeSending.value = true
  bindMsg.value = ''
  try {
    await api.post('/profile/send-verify', { email: bind.email })
    bindMsg.value = '验证码已发送'
    bindMsgType.value = 'ok'
    showVerifyInput.value = true
  } catch (e) {
    bindMsg.value = '发送失败: ' + e.message
    bindMsgType.value = 'err'
  } finally { codeSending.value = false }
}

async function verifyEmail() {
  if (!bind.verifyCode) return alert('请输入验证码')
  verifyLoading.value = true
  try {
    await api.post('/profile/verify-email', { email: bind.email, code: bind.verifyCode })
    bindMsg.value = '邮箱验证成功'
    bindMsgType.value = 'ok'
    showVerifyInput.value = false
    bind.verifyCode = ''
    profileData.value.email = bind.email
  } catch (e) {
    bindMsg.value = '验证失败: ' + e.message
    bindMsgType.value = 'err'
  } finally { verifyLoading.value = false }
}

async function saveBind() {
  bindLoading.value = true
  bindMsg.value = ''
  try {
    // 邮箱已通过「发送验证码+验证」(verify-email) 流程单独保存,
    // 后端已禁止 PUT /info 改邮箱(安全加固), 此处仅提交 QQ 等其他字段
    const res = await profileApi.updateInfo({ qq: bind.qq })
    bindMsg.value = '绑定信息已保存，头像已同步为 QQ 头像'
    bindMsgType.value = 'ok'
    profileData.value = res.data
    // 同步本地用户缓存，刷新/跳转后顶栏使用新的 QQ 头像
    if (user.profile) {
      user.setProfile({ ...user.profile, qq: res.data.qq, avatar: res.data.avatar })
    }
  } catch (e) { alert('保存失败: ' + e.message) }
  finally { bindLoading.value = false }
}

async function changePwd() {
  if (pwd.value.newP !== pwd.value.confirm) { pwdMsg.value = '两次密码不一致'; pwdMsgType.value = 'err'; return }
  pwdLoading.value = true
  try {
    await profileApi.update({ oldPassword: pwd.value.old, newPassword: pwd.value.newP })
    pwdMsg.value = '密码修改成功'
    pwdMsgType.value = 'ok'
    pwd.value = { old: '', newP: '', confirm: '' }
  } catch (e) {
    pwdMsg.value = e.message
    pwdMsgType.value = 'err'
  } finally {
    pwdLoading.value = false
  }
}
</script>

<style scoped>
/* 让卡片从背景图中“浮”出来，内部保持干净的近白底 */
.profile > .card {
  margin-bottom: 28px;
  border: 1px solid rgba(15, 23, 42, .06);
  background: rgba(255, 255, 255, .95);
  box-shadow: 0 10px 28px rgba(15, 23, 42, .06);
  backdrop-filter: blur(20px) saturate(130%);
  -webkit-backdrop-filter: blur(20px) saturate(130%);
}
.profile > .card:last-child { margin-bottom: 0; }

/* 两个核心时长数据 */
.profile-hours {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 4px 0 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(0, 0, 0, .05);
}
.profile-hours__item + .profile-hours__item {
  padding-left: 28px;
  border-left: 1px solid rgba(0, 0, 0, .05);
}
.profile-hours__label {
  display: block;
  margin-bottom: 7px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: .02em;
}
.profile-hours__value {
  color: #111;
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.profile-hours__value small {
  margin-left: 3px;
  color: #6b7280;
  font-size: 14px;
  font-weight: 600;
}

/* 基本信息：3 × 2 网格，细线切分 */
.profile-info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid rgba(0, 0, 0, .05);
  border-left: 1px solid rgba(0, 0, 0, .05);
}
.profile-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  padding: 14px 16px;
  border-right: 1px solid rgba(0, 0, 0, .05);
  border-bottom: 1px solid rgba(0, 0, 0, .05);
}
.profile-cell:nth-child(3n) { border-right: none; }
.profile-cell:nth-last-child(-n + 3) { border-bottom: none; }
.profile-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}
.profile-value {
  overflow: hidden;
  color: #111827;
  font-size: 14px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.profile-value--strong { font-weight: 600; }

/* 头像容器边框交给页面，圆形裁剪/加载失败回退逻辑在 UserAvatar 内 */
.profile-avatar { border: 3px solid var(--c-border); }
.fsd-level-badge {
  display: inline-block;
  width: fit-content;
  padding: 2px 8px;
  color: #2563eb;
  border-radius: 6px;
  background: #eff6ff;
  font-size: 12px;
  font-weight: 600;
}

/* 绑定设置：紧凑输入框 + 同行按钮 */
.profile-bind { max-width: 400px; }
.bind-field { margin-bottom: 16px; }
.bind-field > .profile-label { display: block; margin-bottom: 7px; }
.bind-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bind-input {
  flex: 1;
  min-width: 0;
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
}
.profile-bind > .bind-input {
  display: block;
  width: 100%;
  max-width: 400px;
}
.bind-btn {
  flex: 0 0 auto;
  height: 40px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  box-shadow: none;
  white-space: nowrap;
}
.bind-btn:hover { border: 0; box-shadow: none; }
.bind-btn--save { min-width: 112px; }
.bind-message { line-height: 1.5; }

/* 深色主题下保持同样的“实心卡片”可读性 */
html[data-theme='dark'] .profile > .card {
  border-color: rgba(255, 255, 255, .08);
  background: rgba(15, 23, 42, .92);
  box-shadow: 0 10px 28px rgba(0, 0, 0, .22);
}
html[data-theme='dark'] .profile-hours,
html[data-theme='dark'] .profile-hours__item + .profile-hours__item,
html[data-theme='dark'] .profile-info-grid,
html[data-theme='dark'] .profile-cell {
  border-color: rgba(255, 255, 255, .08);
}
html[data-theme='dark'] .profile-hours__value,
html[data-theme='dark'] .profile-value { color: #f8fafc; }
html[data-theme='dark'] .profile-hours__label,
html[data-theme='dark'] .profile-label,
html[data-theme='dark'] .profile-hours__value small { color: #94a3b8; }
html[data-theme='dark'] .fsd-level-badge { color: #93c5fd; background: rgba(37, 99, 235, .16); }

/* 界面布局切换卡片 */
.layout-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  max-width: 560px;
}
.layout-option {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--c-border-light);
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: var(--c-text);
  transition: border-color .18s ease, background-color .18s ease, transform .18s ease;
}
.layout-option:hover {
  border-color: var(--c-primary);
  background: rgba(0, 113, 227, .05);
  transform: translateY(-1px);
}
.layout-option.active {
  border-color: var(--c-primary);
  background: rgba(0, 113, 227, .08);
  box-shadow: inset 0 0 0 1px rgba(0, 113, 227, .18);
}
.layout-option__label { font-size: 14px; font-weight: 600; }
.layout-option__hint { font-size: 12px; color: var(--c-text-muted); line-height: 1.5; }
.layout-option__preview {
  position: relative;
  display: block;
  width: 100%;
  height: 62px;
  border-radius: 8px;
  background: var(--c-bg-soft, rgba(128, 128, 128, .08));
  overflow: hidden;
  margin-bottom: 2px;
}
.layout-option__preview i { position: absolute; display: block; border-radius: 3px; background: rgba(0, 113, 227, .35); }
.layout-option__preview--sidebar i:nth-child(1) { left: 0; top: 0; bottom: 0; width: 26%; background: rgba(0, 113, 227, .28); }
.layout-option__preview--sidebar i:nth-child(2) { left: 34%; right: 8%; top: 18%; height: 14%; }
.layout-option__preview--topbar i:nth-child(1) { left: 0; right: 0; top: 0; height: 24%; background: rgba(0, 113, 227, .28); }
.layout-option__preview--topbar i:nth-child(2) { left: 8%; right: 8%; top: 40%; height: 14%; }
html[data-theme='dark'] .layout-option:hover { background: rgba(10, 132, 255, .1); }
html[data-theme='dark'] .layout-option.active { background: rgba(10, 132, 255, .16); box-shadow: inset 0 0 0 1px rgba(138, 180, 255, .3); }

@media (max-width: 760px) {
  .profile-info-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .profile-cell:nth-child(3n) { border-right: 1px solid rgba(0, 0, 0, .05); }
  .profile-cell:nth-child(2n) { border-right: none; }
  .profile-cell:nth-last-child(-n + 2) { border-bottom: none; }
  .profile-cell:nth-last-child(3) { border-bottom: 1px solid rgba(0, 0, 0, .05); }
}

@media (max-width: 520px) {
  .profile-hours { grid-template-columns: 1fr; }
  .profile-hours__item + .profile-hours__item {
    margin-top: 16px;
    padding-top: 16px;
    padding-left: 0;
    border-top: 1px solid rgba(0, 0, 0, .05);
    border-left: 0;
  }
  .bind-row { gap: 6px; }
  .bind-btn { padding: 0 10px; font-size: 12px; }
}

</style>
