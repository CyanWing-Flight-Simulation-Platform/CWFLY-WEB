/** OAuth2 客户端管理：内置（环境变量）只读，数据库注册的第三方应用可增删改与轮换密钥 */
<template>
  <div class="oc-page">
    <div class="oc-head">
      <div>
        <h1 class="oc-title">OAuth2 客户端</h1>
        <p class="oc-desc">供第三方应用（如 Merak）接入的授权客户端。密钥只显示一次，请立即保存。</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="openCreate">新增客户端</button>
    </div>

    <div v-if="err" class="alert alert-err">{{ err }}</div>

    <div class="oc-table">
      <div class="oc-row oc-row--head">
        <span>名称</span><span>Client ID</span><span>回调地址</span><span>Scopes</span><span>状态</span><span>操作</span>
      </div>
      <div v-if="!items.length" class="oc-empty">还没有客户端</div>
      <div v-for="c in items" :key="c.clientId" class="oc-row">
        <span class="oc-name">{{ c.name || '-' }}<em v-if="c.source === 'env'" class="oc-tag">内置</em></span>
        <span class="oc-mono">{{ c.clientId }}</span>
        <span class="oc-uris">{{ c.redirectUris.join('\n') }}</span>
        <span>{{ c.scopes.join(', ') }}</span>
        <span :class="c.enabled ? 'text-success' : 'text-muted'">{{ c.enabled ? '启用' : '停用' }}</span>
        <span class="oc-ops">
          <template v-if="c.editable">
            <button class="btn btn-outline btn-xs" @click="openEdit(c)">编辑</button>
            <button class="btn btn-outline btn-xs" @click="rotate(c)">轮换密钥</button>
            <button class="btn btn-outline btn-xs" @click="toggle(c)">{{ c.enabled ? '停用' : '启用' }}</button>
            <button class="btn btn-danger btn-xs" @click="remove(c)">删除</button>
          </template>
          <span v-else class="text-xs text-muted">环境变量管理</span>
        </span>
      </div>
    </div>

    <!-- 新增/编辑 -->
    <div v-if="dialogs.form" class="modal-overlay" @click.self="dialogs.form = false">
      <div class="modal card p-lg" style="max-width:560px;">
        <h3 class="mb-md">{{ editing ? '编辑客户端' : '新增客户端' }}</h3>
        <label class="oc-label">应用名称</label>
        <input v-model="form.name" class="input" maxlength="64" placeholder="如 Merak" />
        <label class="oc-label">应用主页</label>
        <input v-model="form.homepage" class="input" maxlength="255" placeholder="https://example.com" />
        <label class="oc-label">回调地址（每行一个，https）</label>
        <textarea v-model="form.redirectUris" class="input" rows="3" placeholder="https://example.com/api/oauth/callback"></textarea>
        <label class="oc-label">Scopes</label>
        <div class="oc-scopes">
          <label v-for="s in scopeChoices" :key="s" class="oc-check">
            <input v-model="form.scopes" type="checkbox" :value="s" /> {{ s }}
          </label>
        </div>
        <div class="flex gap-sm justify-end mt-md">
          <button class="btn btn-outline" @click="dialogs.form = false">取消</button>
          <button class="btn btn-primary" :disabled="saving" @click="save">{{ editing ? '保存' : '创建' }}</button>
        </div>
      </div>
    </div>

    <!-- 密钥展示 -->
    <div v-if="dialogs.secret" class="modal-overlay" @click.self="dialogs.secret = false">
      <div class="modal card p-lg" style="max-width:560px;">
        <h3 class="mb-sm">请立即保存密钥</h3>
        <p class="text-xs text-muted mb-sm">关闭后将无法再次查看，只能重新轮换。</p>
        <div class="oc-secret"><code>{{ newSecret.clientId }}</code></div>
        <div class="oc-secret"><code>{{ newSecret.clientSecret }}</code></div>
        <div class="flex gap-sm justify-end mt-md">
          <button class="btn btn-outline" @click="dialogs.secret = false">已保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { adminApi } from '@/api'
import { showToast } from '@/utils/banner'

const items = ref([])
const scopeChoices = ref(['profile', 'email', 'qq', 'openid'])
const err = ref('')
const saving = ref(false)
const dialogs = ref({ form: false, secret: false })
const editing = ref(null)
const form = ref({ name: '', homepage: '', redirectUris: '', scopes: ['profile', 'email', 'openid'] })
const newSecret = ref({ clientId: '', clientSecret: '' })

async function load() {
  err.value = ''
  try {
    const res = await adminApi.oauthClients()
    items.value = res.data?.items || []
    scopeChoices.value = res.data?.scopeChoices || scopeChoices.value
  } catch (e) {
    err.value = e?.response?.data?.message || '加载失败'
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', homepage: '', redirectUris: '', scopes: ['profile', 'email', 'openid'] }
  dialogs.value.form = true
}

function openEdit(c) {
  editing.value = c
  form.value = {
    name: c.name,
    homepage: c.homepage,
    redirectUris: c.redirectUris.join('\n'),
    scopes: [...c.scopes]
  }
  dialogs.value.form = true
}

async function save() {
  saving.value = true
  const payload = {
    name: form.value.name.trim(),
    homepage: form.value.homepage.trim(),
    redirectUris: form.value.redirectUris.split('\n').map((x) => x.trim()).filter(Boolean),
    scopes: form.value.scopes
  }
  try {
    if (editing.value) {
      await adminApi.updateOAuthClient(editing.value.clientId, payload)
      showToast('已保存')
    } else {
      const res = await adminApi.createOAuthClient(payload)
      newSecret.value = { clientId: res.data?.clientId, clientSecret: res.data?.clientSecret }
      dialogs.value.secret = true
    }
    dialogs.value.form = false
    load()
  } catch (e) {
    showToast(e?.response?.data?.message || '保存失败', { type: 'error' })
  } finally {
    saving.value = false
  }
}

async function rotate(c) {
  if (!window.confirm(`轮换 ${c.clientId} 的密钥？旧密钥会立即失效。`)) return
  try {
    const res = await adminApi.rotateOAuthClientSecret(c.clientId)
    newSecret.value = { clientId: res.data?.clientId, clientSecret: res.data?.clientSecret }
    dialogs.value.secret = true
  } catch (e) {
    showToast(e?.response?.data?.message || '轮换失败', { type: 'error' })
  }
}

async function toggle(c) {
  try {
    await adminApi.updateOAuthClient(c.clientId, { enabled: !c.enabled })
    load()
  } catch (e) {
    showToast(e?.response?.data?.message || '更新失败', { type: 'error' })
  }
}

async function remove(c) {
  if (!window.confirm(`删除客户端 ${c.clientId}？已签发的令牌不会被回收。`)) return
  try {
    await adminApi.deleteOAuthClient(c.clientId)
    showToast('已删除')
    load()
  } catch (e) {
    showToast(e?.response?.data?.message || '删除失败', { type: 'error' })
  }
}

onMounted(load)
</script>

<style scoped>
.oc-page { padding: 4px 0 32px; }
.oc-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.oc-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.oc-desc { font-size: 13px; color: var(--c-text-muted, #6b7280); margin: 0; }
.oc-table { border: 1px solid var(--c-border, rgba(15, 23, 42, .08)); border-radius: 12px; overflow: hidden; }
.oc-row { display: grid; grid-template-columns: 1.2fr 1.2fr 1.8fr 1fr .7fr 1.6fr; gap: 8px; align-items: start; padding: 10px 14px; font-size: 13px; border-top: 1px solid var(--c-border, rgba(15, 23, 42, .06)); }
.oc-row:first-child { border-top: 0; }
.oc-row--head { background: var(--c-bg-soft, rgba(15, 23, 42, .03)); font-weight: 700; font-size: 12px; }
.oc-name { font-weight: 600; }
.oc-tag { margin-left: 6px; padding: 1px 6px; border-radius: 6px; background: var(--c-bg-soft, rgba(15, 23, 42, .06)); font-size: 11px; font-style: normal; color: var(--c-text-muted, #6b7280); }
.oc-mono, .oc-uris { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.oc-ops { display: flex; flex-wrap: wrap; gap: 6px; }
.oc-empty { padding: 28px; text-align: center; font-size: 13px; color: var(--c-text-muted, #6b7280); }
.oc-label { display: block; margin: 12px 0 6px; font-size: 13px; font-weight: 600; }
.oc-scopes { display: flex; flex-wrap: wrap; gap: 12px; }
.oc-check { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.oc-secret { margin-top: 8px; padding: 10px 12px; border-radius: 8px; background: var(--c-bg-soft, rgba(15, 23, 42, .04)); }
.oc-secret code { font-size: 12px; word-break: break-all; }
.btn-xs { padding: 3px 9px; font-size: 12px; border-radius: 7px; }
</style>
