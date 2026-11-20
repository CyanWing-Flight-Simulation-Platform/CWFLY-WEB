<template>
  <div class="admin-page fade-in">
    <div class="page-header flex justify-between items-start flex-wrap gap-md">
      <div>
        <h1>用户管理</h1>
        <p>管理系统注册用户</p>
      </div>
    </div>

    <div class="card users-table-card">
      <!-- 加载态：统一 Skeleton；空态：统一 EmptyState -->
      <div v-if="loading" class="p-lg" aria-busy="true" aria-label="正在加载用户列表">
        <Skeleton :lines="6" :height="16" />
      </div>
      <div v-else-if="!users.length" class="p-md">
        <EmptyState icon="users" title="暂无用户" description="当前没有可管理的用户，或列表尚未返回数据。" />
      </div>
      <div v-else class="table-wrap users-table-wrap">
        <table v-sort class="users-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>CID</th>
              <th>用户名</th>
              <th>角色</th>
              <th>FSD 权限</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.id }}</td>
              <td class="font-bold">{{ u.cid }}</td>
              <td :title="u.username">{{ u.username }}</td>
              <td>
                <UserTag :rating="u.rating ?? 0" />
              </td>
              <td>
                <span class="fsd-badge" :class="'fsd-' + (u.fsdLevel ?? 1)">{{ fsdLevelName(u.fsdLevel ?? 1) }}</span>
              </td>
              <td class="text-secondary text-sm" :title="u.createdAt">{{ formatDateTime(u.createdAt) }}</td>
              <td>
                <!-- 编辑/删除: 仅管理员(11)及以上可操作; 非超管不能操作管理员(11)及以上等级的用户 -->
                <div class="users-actions">
                  <button v-if="canManageUser(u)" type="button" class="users-action users-action--edit" @click="openEdit(u)">编辑</button>
                  <button v-if="canManageUser(u)" type="button" class="users-action users-action--delete" @click="delUser(u)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 编辑弹窗：AppModal 统一处理 Teleport / 焦点迁移与还原 / Esc / 滚动锁 -->
    <AppModal
      :open="!!editUser"
      title="编辑用户"
      width="540px"
      @update:open="(v) => { if (!v) closeEdit() }"
    >
      <template v-if="editUser">
        <div class="modal-field"><label>ID</label><span>{{ editUser.id }}</span></div>
        <div class="modal-field"><label>CID</label><span>{{ editUser.cid }}</span></div>
        <div class="modal-field">
          <label>角色</label>
          <SelectMenu
              :model-value="editRating"
              @update:model-value="editRating = $event"
              :options="[
                { value: 0, label: '普通用户' },
                { value: 8, label: '协管员' },
                { value: 9, label: '高级协管员' },
                ...(userStore.rating >= 12 ? [{ value: 11, label: '管理员' }, { value: 12, label: '超级管理员' }] : []),
              ]"
            />
        </div>
        <div class="modal-field">
          <label>FSD 等级</label>
          <SelectMenu v-model="editFsdLevel" :options="Object.entries(FSD_LEVEL_NAMES).map(([lv, name]) => ({ value: Number(lv), label: `${name}` }))" />
        </div>
        <button type="button" class="more-toggle" @click="expandMore = !expandMore">
          {{ expandMore ? '▽ 收起' : '△ 更多' }}
        </button>
        <div v-if="expandMore" class="more-panel">
          <div class="modal-field">
            <label>重置原因</label>
            <div class="flex gap-sm" style="flex:1;">
              <input v-model="editPasswordReason" class="input" type="text" placeholder="(可选)将随邮件通知用户" style="flex:1;" />
              <button type="button" class="btn btn-outline btn-sm" style="color:var(--c-danger);" @click="resetPassword">重置密码</button>
            </div>
          </div>
          <div class="modal-field">
            <label>双因素认证</label>
            <div class="flex gap-sm" style="flex:1;">
              <span class="text-sm text-muted" style="flex:1;">用户忘记设备密钥且恢复码丢失时，可在此重置</span>
              <button type="button" class="btn btn-outline btn-sm" style="color:var(--c-danger);" @click="reset2fa">重置 2FA</button>
            </div>
          </div>
          <!-- 以下敏感信息仅超级管理员可见 -->
          <template v-if="userStore.rating >= 12">
            <div class="modal-field"><label>注册 IP</label><span>{{ editUser.registerIp || '-' }}</span></div>
            <div class="modal-field"><label>注册时间</label><span>{{ formatDateTime(editUser.createdAt) }}</span></div>
            <div class="modal-field"><label>最近登录 IP</label><span>{{ editUser.lastLoginIp || '-' }}</span></div>
            <div class="modal-field"><label>最近登录时间</label><span>{{ editUser.lastLoginAt ? formatDateTime(editUser.lastLoginAt) : '-' }}</span></div>
            <div class="modal-field"><label>最近登录指纹</label><span>{{ editUser.lastLoginFp || '-' }}</span></div>
          </template>
        </div>
      </template>
      <template #footer>
        <button class="btn btn-outline" @click="closeEdit">取消</button>
        <button class="btn btn-primary" :disabled="saveSubmitting" @click="saveEdit">{{ saveSubmitting ? '保存中...' : '保存' }}</button>
      </template>
    </AppModal>

    <!-- 删除确认弹窗：AppModal + footer 插槽 -->
    <AppModal
      :open="!!deleteTarget"
      title="删除用户"
      width="540px"
      @update:open="(v) => { if (!v) closeDelete() }"
    >
      <template v-if="deleteTarget">
        <p class="modal-desc">
          确定删除用户 <b>{{ deleteTarget.username }}</b>（CID: {{ deleteTarget.cid }}）？此操作不可恢复。
        </p>
        <label class="ban-check">
          <CheckBox :model-value="deleteBan" @update:model-value="deleteBan = $event" />
          <span>同时加入黑名单</span>
        </label>
        <!-- 勾选黑名单后：预览将新增的封禁记录（IP/原因可输入/封禁人）；无有效 IP 时给出提示 -->
        <div v-if="deleteBan" class="ban-preview">
          <template v-if="banPreview.length">
            <div class="ban-preview-title">将新增 {{ banPreview.length }} 条封禁记录：</div>
            <div class="ban-reason-field">
              <span class="ban-preview-label">原因</span>
              <input class="input" v-model="banReason" placeholder="请输入封禁原因（可留空）" />
            </div>
            <div v-for="(item, i) in banPreview" :key="i" class="ban-preview-row">
              <div><span class="ban-preview-label">IP</span><span class="ban-preview-ip">{{ item.ip }}</span></div>
              <div><span class="ban-preview-label">封禁人</span><span>{{ item.bannedBy }}</span></div>
            </div>
          </template>
          <div v-else class="ban-preview-title">该用户无有效 IP，无法加入黑名单</div>
        </div>
      </template>
      <template #footer>
        <button class="btn btn-outline" @click="closeDelete">取消</button>
        <button class="btn btn-primary" :disabled="deleteSubmitting" style="background:var(--c-danger);border-color:var(--c-danger);" @click="confirmDelete">{{ deleteSubmitting ? '删除中...' : '确认删除' }}</button>
      </template>
    </AppModal>
  </div>
</template>

<script setup>
import { confirmDialog } from '@/utils/confirm'
import { ref, computed, onMounted } from 'vue'
import { adminApi } from '@/api'
import { useUserStore } from '@/store/user'
import AppModal from '@/components/base/AppModal.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import Skeleton from '@/components/base/Skeleton.vue'
import UserTag from '@/components/base/UserTag.vue'

/** 当前登录管理员信息（用于封禁人预览）
 *  调用时机：模块初始化时获取，供 banPreview 计算使用 */
const userStore = useUserStore()

const FSD_LEVEL_NAMES = {
  0: '飞行员', 1: '观察员', 2: '地面/放行 S1', 3: '塔台 S2',
  4: '终端 S3', 5: '区域 C1', 6: '区域 C2', 7: '区域 C3',
  8: '塔台教员 I1', 9: '进近教员 I2', 10: '区域教员 I3',
  11: 'SUP', 12: 'ADM'
}
function fsdLevelName(level) { return FSD_LEVEL_NAMES[level] || `未知(${level})` }

/** ISO/字符串时间 → 本地时间 YYYY-MM-DD HH:mm:ss（去掉 T/Z/毫秒） */
function formatDateTime(value) {
  if (!value) return '-'
  const raw = String(value)
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) {
    return raw.replace('T', ' ').replace(/\.\d+(Z)?$/, '').replace(/Z$/, '')
  }
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const users = ref([])
const loading = ref(false)
const saveSubmitting = ref(false)
const deleteSubmitting = ref(false)
const editUser = ref(null)
const editRating = ref(0)
const editFsdLevel = ref(1)
const expandMore = ref(false)
const editPasswordReason = ref('')
const deleteTarget = ref(null)
const deleteBan = ref(false)
/** 勾选黑名单后的自定义封禁原因（空白可输入，多条 IP 共用）
 *  调用时机：删除确认弹窗内由输入框双向绑定，confirmDelete 提交时读取 */
const banReason = ref('')

// 权限等级标签统一由 UserTag 渲染（语义色映射在组件内维护，避免页面重复实现）
// 编辑/删除权限: 仅管理员(11)/超管(12)可操作; 非超管不能操作管理员(11)及以上等级的用户
function canManageUser(u) {
  return userStore.rating >= 11 && (userStore.rating >= 12 || (u.rating ?? 0) < 11)
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await adminApi.users()
    users.value = res.data
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}
onMounted(loadUsers)

function openEdit(u) {
  editUser.value = u
  editRating.value = u.rating ?? 0
  editFsdLevel.value = u.fsdLevel ?? 1
  expandMore.value = false
  editPasswordReason.value = ''
}

function closeEdit() {
  editUser.value = null
}

async function saveEdit() {
  const u = editUser.value
  if (!u || saveSubmitting.value) return
  saveSubmitting.value = true
  try {
    await adminApi.updateUser(u.cid, {
      rating: editRating.value,
      fsdLevel: editFsdLevel.value
    })
    u.rating = editRating.value
    u.fsdLevel = editFsdLevel.value
    closeEdit()
    loadUsers() // 保存后重新拉取列表, 确保页面组件同步更新
  } catch (e) { alert(e.message) } finally { saveSubmitting.value = false }
}

/** 重置密码：确认后由后端生成随机强密码并邮件发送给用户 */
async function resetPassword() {
  const u = editUser.value
  if (!u) return
  if (!(await confirmDialog(`确定重置用户 ${u.username}（CID: ${u.cid}）的密码？\n系统将生成随机强密码并发送到用户邮箱。`))) return
  try {
    const res = await adminApi.resetUserPassword(u.cid, { reason: editPasswordReason.value.trim() })
    alert('密码已重置' + (res.data?.password ? '：' + res.data.password : ''))
  } catch (e) { alert(e.message) }
}

/** 重置 2FA：用户忘记设备密钥且恢复码丢失时，由超管清除其 2FA 绑定 */
async function reset2fa() {
  const u = editUser.value
  if (!u) return
  if (!(await confirmDialog(`确定重置用户 ${u.username}（CID: ${u.cid}）的 2FA？\n重置后该用户下次登录需重新注册本机设备密钥。`))) return
  try {
    await adminApi.resetUser2fa(u.cid)
    alert('2FA 已重置')
    closeEdit()
    loadUsers()
  } catch (e) { alert(e.message) }
}

function to24(ip) {
  const parts = String(ip || '').trim().split('.')
  if (parts.length !== 4) return ''
  return parts.slice(0, 3).join('.') + '.0/24'
}

/** 勾选"同时加入黑名单"后，将要新增的封禁记录预览（IP、封禁人）
 *  调用时机：删除确认弹窗内，deleteBan/deleteTarget 变化时由模板 computed 自动计算 */
const banPreview = computed(() => {
  const u = deleteTarget.value
  if (!deleteBan.value || !u) return []
  const ips = [...new Set([u.registerIp, u.lastLoginIp].map(to24).filter(Boolean))]
  const bannedBy = userStore.cid || '-'
  return ips.map(ip => ({ ip, bannedBy }))
})

function delUser(u) {
  deleteTarget.value = u
  deleteBan.value = false
  banReason.value = '' // 每次打开弹窗重置自定义原因
}

function closeDelete() {
  deleteTarget.value = null
}

async function confirmDelete() {
  const u = deleteTarget.value
  if (!u || deleteSubmitting.value) return
  deleteSubmitting.value = true
  try {
    // 非超管：删除/删除+封禁不立即生效，提交审批等待超级管理员审批
    if (userStore.rating < 12) {
      const ips = [...new Set([u.registerIp, u.lastLoginIp].map(to24).filter(Boolean))]
      await adminApi.submitUserDeletionRequest({
        cid: String(u.cid),
        username: u.username || '',
        action: deleteBan.value ? 'delete_ban' : 'delete',
        ips,
        reason: banReason.value.trim()
      })
      alert('已提交删除审批，等待超级管理员审批')
      closeDelete()
      return
    }
    // 超管：直接执行删除（+可选加入黑名单）
    if (deleteBan.value) {
      const ips = [...new Set([u.registerIp, u.lastLoginIp].map(to24).filter(Boolean))]
      const reason = banReason.value.trim() // 自定义封禁原因，可留空
      if (!ips.length) {
        alert('该用户无有效 IP，未加入黑名单')
      } else {
        for (const ip of ips) {
          // 同步到封禁管理：IP + 被封禁用户 CID + 原因；封禁人由后端取当前管理员 CID
          await adminApi.addIpBan({ ip, reason, hours: 0, bannedUser: String(u.cid) })
        }
      }
    }
    // 删除用户；勾选黑名单时后端同步封禁其设备指纹（防换小号注册/登录绕过）
    await adminApi.deleteUser(u.cid, deleteBan.value ? { banDevice: true } : undefined)
    users.value = users.value.filter(x => x.id !== u.id)
    closeDelete()
  } catch (e) { alert(e.message) } finally { deleteSubmitting.value = false }
}
</script>

<style scoped>

/* 弹窗外壳（遮罩/卡片/标题/底部按钮）由 base/AppModal.vue 统一提供，这里只保留字段排版 */
.modal-field {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.modal-field label {
  width: 110px;
  flex-shrink: 0;
  font-size: 13px;
  white-space: nowrap;
  color: var(--c-text-secondary, #6b7280);
}
.modal-field span {
  font-size: 14px;
  color: var(--c-text, #1d1d1f);
}
.modal-field .input {
  flex: 1;
}
.more-toggle {
  display: block;
  width: 100%;
  margin: 2px 0 6px;
  padding: 6px 0;
  border: none;
  background: transparent;
  color: var(--c-primary, #0071e3);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: center;
  border-top: 1px solid var(--glass-border);
}
.more-toggle:hover { opacity: .8; }
.more-panel {
  margin-bottom: 4px;
  padding-top: 4px;
}
.modal-desc {
  margin: 0 0 16px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--c-text, #1d1d1f);
}
.ban-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  cursor: pointer;
}
.ban-check input[type="checkbox"] {
  margin: 0;
  accent-color: var(--c-danger, #ff453a);
}
/* 黑名单新增记录预览 */
.ban-preview {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 69, 58, 0.06);
  border: 1px solid rgba(255, 69, 58, 0.25);
}
.ban-preview-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-danger, #ff453a);
}
.ban-preview-row {
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--glass-bg);
  font-size: 12px;
  line-height: 1.7;
  color: var(--c-text, #1d1d1f);
}
.ban-preview-row + .ban-preview-row {
  margin-top: 6px;
}
.ban-preview-label {
  display: inline-block;
  width: 44px;
  flex-shrink: 0;
  color: var(--c-text-secondary, #6b7280);
}
.ban-reason-field {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--field-bg);
}
.ban-reason-field .input {
  flex: 1;
  font-size: 12px;
}
.ban-preview-ip {
  font-weight: 600;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* ===== 用户表格：高不透明度毛玻璃底板 + 统一透明行 ===== */
.users-table-card {
  background: rgba(255, 255, 255, .88) !important;
  border: 1px solid rgba(0, 0, 0, .06) !important;
  -webkit-backdrop-filter: blur(16px) !important;
  backdrop-filter: blur(16px) !important;
  box-shadow: none !important;
  border-radius: 12px !important;
  overflow: hidden;
}
html[data-theme='dark'] .users-table-card {
  background: rgba(15, 20, 30, .84) !important;
  border-color: rgba(255, 255, 255, .1) !important;
}

.users-table-wrap {
  overflow-x: auto;
  border-radius: 12px;
  background: transparent !important;
}

.users-table {
  width: 100%;
  min-width: 980px;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
  background: transparent !important;
}
.users-table thead,
.users-table tbody,
.users-table tr {
  background: transparent !important;
}

/* 所有列强制不折行、透明底，由外层卡片统一托底 */
.users-table th,
.users-table td {
  padding: 16px 12px !important;
  white-space: nowrap;
  word-break: normal;
  overflow-wrap: normal;
  vertical-align: middle;
  color: var(--ui-text) !important;
  background: transparent !important;
  border-bottom: 1px solid rgba(0, 0, 0, .05) !important;
}

html[data-theme='dark'] .users-table th,
html[data-theme='dark'] .users-table td {
  color: var(--ui-text) !important;
  border-bottom-color: rgba(255, 255, 255, .06) !important;
}

.users-table th {
  color: #6B7280 !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  letter-spacing: .01em;
  text-transform: none;
  background: transparent !important;
  border-bottom: 1px solid rgba(0, 0, 0, .06) !important;
}
html[data-theme='dark'] .users-table th {
  color: rgba(255, 255, 255, .58) !important;
  border-bottom-color: rgba(255, 255, 255, .08) !important;
}

.users-table tbody tr:last-child td {
  border-bottom: 0 !important;
}

.users-table tbody tr:hover td {
  background: rgba(0, 0, 0, .025) !important;
}
html[data-theme='dark'] .users-table tbody tr:hover td {
  background: rgba(255, 255, 255, .04) !important;
}

/* 列宽：ID/CID 固定，用户名与注册时间留足空间，角色/FSD 紧凑 */
.users-table th:nth-child(1),
.users-table td:nth-child(1) { width: 64px; }
.users-table th:nth-child(2),
.users-table td:nth-child(2) { width: 96px; }
.users-table th:nth-child(3),
.users-table td:nth-child(3) { width: 22%; overflow: hidden; text-overflow: ellipsis; }
.users-table th:nth-child(4),
.users-table td:nth-child(4) { width: 112px; }
.users-table th:nth-child(5),
.users-table td:nth-child(5) { width: 128px; }
.users-table th:nth-child(6),
.users-table td:nth-child(6) { width: 180px; }

/* 操作列不再单独铺白底，也不再 sticky 造成分割块 */
.users-table th:nth-child(7),
.users-table td:nth-child(7) { width: 132px; background: transparent !important; }

/* 角色标签缩小为柔和药丸 */
.users-table :deep(.badge) {
  padding: 2px 8px;
  font-size: 12px;
  line-height: 1.6;
  border-radius: 6px;
  box-shadow: none;
}
/* 超管/管理员红标签降饱和 */
.users-table :deep(.badge-danger) {
  background: rgba(239, 68, 68, .08) !important;
  color: #DC2626 !important;
  border: 1px solid rgba(239, 68, 68, .16) !important;
}
html[data-theme='dark'] .users-table :deep(.badge-danger) {
  background: rgba(239, 68, 68, .12) !important;
  color: #FCA5A5 !important;
  border-color: rgba(239, 68, 68, .22) !important;
}

/* ADM 药丸：浅灰底 + 深灰字 */
.users-table :deep(.fsd-12) {
  background: rgba(0, 0, 0, .05) !important;
  color: #374151 !important;
  border: 1px solid rgba(0, 0, 0, .08) !important;
}
html[data-theme='dark'] .users-table :deep(.fsd-12) {
  background: rgba(255, 255, 255, .08) !important;
  color: rgba(255, 255, 255, .8) !important;
  border-color: rgba(255, 255, 255, .12) !important;
}

/* 编辑 / 删除：纯文字幽灵按钮，无白底无粗边框 */
.users-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 108px;
}
.users-action {
  padding: 4px 6px !important;
  border: 0 !important;
  border-radius: 6px !important;
  background: transparent !important;
  box-shadow: none !important;
  font-size: 12px !important;
  line-height: 1.6;
  cursor: pointer;
  transition: background .15s ease, color .15s ease;
}
.users-action--edit { color: #2563EB !important; }
.users-action--edit:hover { background: rgba(37, 99, 235, .08) !important; }
.users-action--delete { color: #DC2626 !important; }
.users-action--delete:hover { background: rgba(220, 38, 38, .08) !important; }
html[data-theme='dark'] .users-action--edit { color: #93C5FD !important; }
html[data-theme='dark'] .users-action--delete { color: #FCA5A5 !important; }

.permission-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}
.perm-checkbox {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.perm-checkbox input[type="checkbox"] {
  margin: 0;
  accent-color: var(--c-primary, #3b82f6);
}
</style>
