<template>
  <div class="admin-points">
    <header class="ap-head">
      <div>
        <h1>积分商城管理</h1>
        <p>配置获取规则、管理虚拟商品、审核宣传作品与执行积分结算。</p>
      </div>
    </header>

    <section class="ap-card">
      <div class="ap-card__head">
        <h2>获取规则</h2>
        <button type="button" class="ap-btn" :disabled="busy" @click="saveConfig">保存配置</button>
      </div>
      <div class="ap-form-grid">
        <label v-for="field in configFields" :key="field.key" class="ap-field">
          <span>{{ field.label }}</span>
          <input v-model="config[field.key]" type="number" min="0" step="any" />
          <small>{{ field.hint }}</small>
        </label>
      </div>
      <p v-if="configMsg" class="ap-msg">{{ configMsg }}</p>
    </section>

    <section class="ap-card">
      <div class="ap-card__head">
        <h2>虚拟商品</h2>
        <button type="button" class="ap-btn" @click="resetProduct">新增商品</button>
      </div>
      <div class="ap-product-form">
        <input v-model.trim="product.name" placeholder="商品名称" maxlength="120" />
        <input v-model.trim="product.icon" placeholder="图标字符" maxlength="8" />
        <input v-model.number="product.price" type="number" min="1" placeholder="所需积分" />
        <input v-model.number="product.stock" type="number" min="-1" placeholder="库存（-1 不限）" />
        <input v-model.trim="product.assetType" placeholder="资产类型" maxlength="32" />
        <textarea v-model.trim="product.description" rows="2" placeholder="商品说明" maxlength="500"></textarea>
        <button type="button" class="ap-btn" :disabled="busy" @click="saveProduct">
          {{ product.id ? '保存修改' : '创建商品' }}
        </button>
      </div>
      <div class="ap-list">
        <div v-for="item in products" :key="item.id" class="ap-row">
          <span class="ap-row__icon">{{ item.icon }}</span>
          <div class="ap-row__main">
            <strong>{{ item.name }}</strong>
            <span>{{ item.price }} 积分 · {{ item.unlimited ? '不限量' : `库存 ${item.stock}` }} · {{ item.assetType }}</span>
          </div>
          <button type="button" class="ap-btn ap-btn--ghost" @click="editProduct(item)">编辑</button>
          <button type="button" class="ap-btn ap-btn--ghost" @click="toggleProduct(item)">
            {{ item.status ? '下架' : '上架' }}
          </button>
        </div>
        <p v-if="!products.length" class="ap-empty">还没有商品</p>
      </div>
    </section>

    <section class="ap-card">
      <div class="ap-card__head">
        <h2>宣传作品审核</h2>
        <button type="button" class="ap-btn ap-btn--ghost" @click="loadVideos">刷新</button>
      </div>
      <div class="ap-list">
        <div v-for="video in videos" :key="video.id" class="ap-row">
          <div class="ap-row__main">
            <strong>{{ video.title }}</strong>
            <span>{{ video.userId }} · {{ video.status }} · {{ video.createdAt }}</span>
            <a :href="video.url" target="_blank" rel="noopener" class="ap-link">查看作品 ↗</a>
          </div>
          <template v-if="video.status === 'pending'">
            <button type="button" class="ap-btn" :disabled="busy" @click="reviewVideo(video, 'approved')">通过</button>
            <button type="button" class="ap-btn ap-btn--ghost" :disabled="busy" @click="reviewVideo(video, 'rejected')">驳回</button>
          </template>
          <span v-else class="ap-status">{{ video.status === 'approved' ? `已发放 ${video.reward} 积分` : '已驳回' }}</span>
        </div>
        <p v-if="!videos.length" class="ap-empty">暂无待审核作品</p>
      </div>
    </section>

    <section class="ap-card">
      <div class="ap-card__head"><h2>积分结算</h2></div>
      <div class="ap-settle">
        <input v-model.trim="eventId" placeholder="活动 ID" />
        <button type="button" class="ap-btn" :disabled="busy" @click="settleEvent">结算活动积分</button>
        <button type="button" class="ap-btn ap-btn--ghost" :disabled="busy" @click="settleHours">结算飞行时长积分</button>
      </div>
      <p v-if="settleMsg" class="ap-msg">{{ settleMsg }}</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { adminApi } from '@/api'

const configFields = [
  { key: 'points_per_hour', label: '每小时飞行积分', hint: '1 小时飞行折合积分' },
  { key: 'activity_points', label: '活动结算积分', hint: '单次活动发放积分' },
  { key: 'activity_min_hours', label: '活动最低飞行时长', hint: '未达到门槛不结算' },
  { key: 'video_points', label: '宣传作品积分', hint: '审核通过后发放' },
  { key: 'redeem_daily_limit', label: '每日兑换上限', hint: '0 表示不限制' },
  { key: 'redeem_cooldown_seconds', label: '兑换冷却（秒）', hint: '两次兑换的最小间隔' },
]

const config = reactive({})
const products = ref([])
const videos = ref([])
const busy = ref(false)
const configMsg = ref('')
const settleMsg = ref('')
const eventId = ref('')
const product = reactive({
  id: 0, name: '', description: '', icon: '✦', price: 100, stock: -1,
  assetType: 'virtual', status: 1, sortOrder: 0,
})

function apiData(res) {
  return res?.data?.data ?? res?.data ?? null
}

async function loadConfig() {
  const data = apiData(await adminApi.pointsConfig())
  for (const field of configFields) config[field.key] = data?.[field.key] ?? ''
}

async function loadProducts() {
  products.value = apiData(await adminApi.pointsProducts()) || []
}

async function loadVideos() {
  videos.value = apiData(await adminApi.pointsVideos({ status: 'pending' })) || []
}

async function saveConfig() {
  busy.value = true
  configMsg.value = ''
  try {
    await adminApi.updatePointsConfig({ ...config })
    configMsg.value = '规则已保存'
    await loadConfig()
  } catch (e) {
    configMsg.value = e.response?.data?.message || '保存失败'
  } finally { busy.value = false }
}

function resetProduct() {
  Object.assign(product, {
    id: 0, name: '', description: '', icon: '✦', price: 100, stock: -1,
    assetType: 'virtual', status: 1, sortOrder: 0,
  })
}

function editProduct(item) {
  Object.assign(product, {
    id: item.id, name: item.name, description: item.description, icon: item.icon,
    price: item.price, stock: item.stock, assetType: item.assetType,
    status: item.status, sortOrder: item.sortOrder,
  })
}

async function saveProduct() {
  busy.value = true
  try {
    const payload = {
      name: product.name, description: product.description, icon: product.icon,
      price: product.price, stock: product.stock, assetType: product.assetType,
      status: product.status, sortOrder: product.sortOrder,
    }
    if (product.id) await adminApi.updatePointsProduct(product.id, payload)
    else await adminApi.createPointsProduct(payload)
    resetProduct()
    await loadProducts()
  } catch (e) {
    alert(e.response?.data?.message || '保存商品失败')
  } finally { busy.value = false }
}

async function toggleProduct(item) {
  try {
    await adminApi.updatePointsProduct(item.id, { ...item, status: item.status ? 0 : 1 })
    await loadProducts()
  } catch (e) {
    alert(e.response?.data?.message || '操作失败')
  }
}

async function reviewVideo(video, status) {
  busy.value = true
  try {
    await adminApi.reviewPointsVideo(video.id, { status })
    await Promise.all([loadVideos(), loadConfig()])
  } catch (e) {
    alert(e.response?.data?.message || '审核失败')
  } finally { busy.value = false }
}

async function settleEvent() {
  busy.value = true
  settleMsg.value = ''
  try {
    const data = apiData(await adminApi.settlePointsEvent(Number(eventId.value)))
    settleMsg.value = `活动结算：发放 ${data?.awarded ?? 0} 人，未达时长 ${data?.belowHours ?? 0} 人，重复 ${data?.duplicate ?? 0} 人`
  } catch (e) {
    settleMsg.value = e.response?.data?.message || '结算失败'
  } finally { busy.value = false }
}

async function settleHours() {
  busy.value = true
  settleMsg.value = ''
  try {
    const data = apiData(await adminApi.settlePointsHours({}))
    settleMsg.value = `时长结算：${data?.users ?? 0} 人，共发放 ${data?.points ?? 0} 积分`
  } catch (e) {
    settleMsg.value = e.response?.data?.message || '结算失败'
  } finally { busy.value = false }
}

onMounted(async () => {
  try {
    await Promise.all([loadConfig(), loadProducts(), loadVideos()])
  } catch {
    configMsg.value = '数据加载失败'
  }
})
</script>

<style scoped>
.admin-points { max-width: 1180px; margin: 0 auto; padding: 8px 24px 48px; color: var(--c-text); }
.ap-head h1 { margin: 0 0 8px; font-size: 26px; }
.ap-head p { margin: 0 0 24px; color: var(--c-text-muted); font-size: 13px; }
.ap-card { margin-bottom: 18px; padding: 22px; border: 1px solid var(--c-border); border-radius: var(--radius-lg); background: var(--c-bg-card); box-shadow: var(--shadow-md); backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)); }
.ap-card__head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.ap-card__head h2 { margin: 0; font-size: 17px; }
.ap-form-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.ap-field { display: flex; flex-direction: column; gap: 5px; }
.ap-field span { color: var(--c-text-secondary); font-size: 12px; }
.ap-field input, .ap-product-form input, .ap-product-form textarea, .ap-settle input {
  width: 100%; padding: 9px 10px; border: 1px solid var(--field-border); border-radius: 8px;
  background: var(--field-bg); color: var(--c-text); font-family: inherit; font-size: 12px;
}
.ap-field small { color: var(--c-text-muted); font-size: 10px; }
.ap-btn { min-height: 34px; padding: 0 14px; border: 1px solid transparent; border-radius: 8px; background: var(--c-primary); color: var(--c-white); cursor: pointer; font-family: inherit; font-size: 12px; font-weight: 600; }
html[data-theme='dark'] .admin-points .ap-btn { color: var(--c-text); }
.ap-btn:disabled { opacity: .5; cursor: not-allowed; }
.ap-btn--ghost { border-color: var(--c-border); background: transparent; color: var(--c-text-secondary); }
.ap-btn--ghost:hover { background: var(--panel-hover); }
.ap-product-form { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 16px; }
.ap-product-form textarea { grid-column: span 3; resize: vertical; }
.ap-list { display: flex; flex-direction: column; }
.ap-row { display: flex; align-items: center; gap: 10px; padding: 12px 0; border-top: 1px solid var(--c-border-light); }
.ap-row__icon { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; flex-shrink: 0; border-radius: 9px; background: var(--c-primary-light); color: var(--c-primary); font-size: 17px; }
.ap-row__main { display: flex; flex: 1; flex-direction: column; gap: 3px; min-width: 0; }
.ap-row__main strong { font-size: 13px; }
.ap-row__main span { color: var(--c-text-muted); font-size: 11px; }
.ap-link { color: var(--c-primary); font-size: 11px; text-decoration: none; }
.ap-status { color: var(--c-text-muted); font-size: 11px; }
.ap-msg { margin: 12px 0 0; color: var(--c-text-muted); font-size: 12px; }
.ap-empty { padding: 18px 0; color: var(--c-text-muted); font-size: 12px; text-align: center; }
.ap-settle { display: flex; flex-wrap: wrap; gap: 8px; }
.ap-settle input { width: 160px; }
@media (max-width: 900px) {
  .ap-form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ap-product-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ap-product-form textarea { grid-column: span 2; }
}
@media (max-width: 560px) {
  .admin-points { padding: 0 16px 32px; }
  .ap-form-grid, .ap-product-form { grid-template-columns: 1fr; }
  .ap-product-form textarea { grid-column: auto; }
  .ap-row { align-items: flex-start; flex-wrap: wrap; }
}
</style>
