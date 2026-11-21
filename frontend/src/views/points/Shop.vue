<template>
  <div class="shop-page">
    <header class="shop-hero">
      <div class="shop-hero__copy">
        <h1>积分商城</h1>
        <p>用飞行时长、活动参与与社区贡献积累的积分，兑换专属虚拟权益。</p>
        <div class="shop-rates">
          <span>1 小时飞行 = {{ rates.pointsPerHour ?? '—' }} 积分</span>
          <span>活动需满 {{ rates.activityMinHours ?? '—' }} 小时</span>
          <span>活动结算 {{ rates.activityPoints ?? '—' }} 积分</span>
        </div>
        <div class="shop-frequent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
          <div>
            <span>常旅客飞行时长</span>
            <strong>当前累计飞行：{{ formatHours(totalHours) }} 小时</strong>
          </div>
        </div>
      </div>
      <div class="shop-balance">
        <span class="shop-balance__label">可用积分</span>
        <strong>{{ balance }}</strong>
        <div class="shop-balance__actions">
          <button type="button" class="shop-btn shop-btn--ghost" @click="openDrawer('history')">积分明细</button>
          <button type="button" class="shop-btn shop-btn--ghost" @click="openDrawer('assets')">我的背包</button>
        </div>
      </div>
    </header>

    <p v-if="error" class="shop-alert">{{ error }}</p>

    <section class="shop-section">
      <div class="shop-section__head">
        <h2>虚拟权益</h2>
        <span>积分兑换 · 无任何现实货币参与</span>
      </div>
      <div v-if="loading" class="shop-empty">正在加载商品…</div>
      <div v-else-if="!products.length" class="shop-empty shop-empty--products">
        <svg class="shop-empty__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 8.5 12 4l8 4.5v7L12 20l-8-4.5z" />
          <path d="M4 8.5 12 13l8-4.5M12 13v7" />
        </svg>
        <p>暂无商品哦，敬请期待</p>
      </div>
      <div v-else class="shop-grid">
        <article
          v-for="product in products"
          :key="product.id"
          class="shop-card"
          :class="{
            'shop-card--soldout': product.stock === 0,
            'shop-card--locked': isLocked(product),
          }"
        >
          <div class="shop-card__top">
            <span class="shop-card__icon" aria-hidden="true">{{ product.icon }}</span>
            <span class="shop-card__type">{{ product.assetType }}</span>
          </div>
          <h3>{{ product.name }}</h3>
          <p>{{ product.description }}</p>
          <div class="shop-card__meta">
            <strong>{{ product.price }} <small>积分</small></strong>
            <span>{{ product.unlimited ? '不限量' : (product.stock > 0 ? `剩余 ${product.stock}` : '已兑完') }}</span>
          </div>
          <button
            type="button"
            class="shop-btn"
            :disabled="redeeming || isLocked(product) || product.stock === 0 || balance < product.price"
            @click="redeem(product)"
          >
            {{ productButtonText(product) }}
          </button>
        </article>
      </div>
    </section>

    <section class="shop-section shop-video">
      <div class="shop-section__head">
        <h2>宣传激励</h2>
        <span>作品审核通过后发放积分</span>
      </div>
      <div class="shop-video__panel">
        <p>提交你为 CWFLY 制作的宣传视频，审核通过后可获得 {{ rates.videoPoints ?? '—' }} 积分。</p>
        <div class="shop-video__form">
          <input v-model.trim="video.title" type="text" maxlength="120" placeholder="作品标题" />
          <input v-model.trim="video.url" type="url" maxlength="500" placeholder="作品链接（https://）" />
          <button type="button" class="shop-btn" :disabled="videoBusy" @click="submitVideo">提交审核</button>
        </div>
        <p v-if="videoMsg" class="shop-video__msg">{{ videoMsg }}</p>
      </div>
    </section>

    <div v-if="drawer" class="shop-drawer-mask" @click.self="drawer = ''">
      <aside class="shop-drawer" role="dialog" aria-modal="true">
        <div class="shop-drawer__head">
          <div class="shop-tabs">
            <button type="button" :class="{ active: drawer === 'history' }" @click="openDrawer('history')">积分明细</button>
            <button type="button" :class="{ active: drawer === 'assets' }" @click="openDrawer('assets')">我的背包</button>
          </div>
          <button type="button" class="shop-drawer__close" aria-label="关闭" @click="drawer = ''">×</button>
        </div>
        <div class="shop-drawer__body">
          <p v-if="drawerLoading" class="shop-empty">加载中…</p>
          <template v-else-if="drawer === 'history'">
            <div v-if="!transactions.length" class="shop-empty">还没有积分记录。</div>
            <div v-for="item in transactions" :key="item.id" class="shop-row">
              <div>
                <strong>{{ item.description || item.kind }}</strong>
                <span>{{ formatDate(item.createdAt) }}</span>
              </div>
              <b :class="{ minus: item.amount < 0 }">{{ item.amount > 0 ? '+' : '' }}{{ item.amount }}</b>
            </div>
          </template>
          <template v-else>
            <div v-if="!assets.length" class="shop-empty">背包还是空的，去兑换一份虚拟权益吧。</div>
            <div v-for="asset in assets" :key="asset.id" class="shop-row shop-row--asset">
              <span class="shop-row__icon">{{ asset.icon }}</span>
              <div>
                <strong>{{ asset.name }}</strong>
                <span>{{ asset.assetType }} · {{ formatDate(asset.createdAt) }}</span>
              </div>
              <b>×{{ asset.quantity }}</b>
            </div>
          </template>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { pointsApi } from '@/api'

const balance = ref(0)
const totalHours = ref(0)
const products = ref([])
const rates = ref({})
const loading = ref(true)
const error = ref('')
const redeeming = ref(false)
const drawer = ref('')
const drawerLoading = ref(false)
const transactions = ref([])
const assets = ref([])
const video = reactive({ title: '', url: '' })
const videoBusy = ref(false)
const videoMsg = ref('')

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}

function formatHours(value) {
  return (Number(value) || 0).toFixed(1)
}

function isLocked(product) {
  return Number(totalHours.value) < Number(product.minFlightHours || 0)
}

function productButtonText(product) {
  if (isLocked(product)) return `需飞行 ${Number(product.minFlightHours || 0)} 小时解锁`
  if (product.stock === 0) return '已兑完'
  if (balance.value < product.price) return '积分不足'
  return '立即兑换'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await pointsApi.shop()
    const data = res.data?.data || res.data || {}
    balance.value = Number(data.balance) || 0
    totalHours.value = Number(data.totalHours ?? data.user_total_hours) || 0
    products.value = data.products || []
    rates.value = data.rates || {}
  } catch (e) {
    error.value = e.response?.data?.message || '商城加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function redeem(product) {
  if (redeeming.value) return
  if (isLocked(product)) return
  if (!window.confirm(`确认使用 ${product.price} 积分兑换「${product.name}」？`)) return
  redeeming.value = true
  error.value = ''
  try {
    await pointsApi.redeem(product.id)
    await load()
    await openDrawer('assets')
  } catch (e) {
    error.value = e.response?.data?.message || '兑换失败，请稍后重试'
  } finally {
    redeeming.value = false
  }
}

async function openDrawer(type) {
  drawer.value = type
  drawerLoading.value = true
  try {
    if (type === 'history') {
      const res = await pointsApi.transactions()
      transactions.value = res.data?.data || res.data || []
    } else {
      const res = await pointsApi.assets()
      assets.value = res.data?.data || res.data || []
    }
  } catch {
    if (type === 'history') transactions.value = []
    else assets.value = []
  } finally {
    drawerLoading.value = false
  }
}

async function submitVideo() {
  if (videoBusy.value) return
  videoMsg.value = ''
  if (!video.title || !video.url) {
    videoMsg.value = '请填写作品标题和链接'
    return
  }
  videoBusy.value = true
  try {
    await pointsApi.submitVideo({ title: video.title, url: video.url })
    video.title = ''
    video.url = ''
    videoMsg.value = '已提交，等待管理员审核'
  } catch (e) {
    videoMsg.value = e.response?.data?.message || '提交失败，请稍后重试'
  } finally {
    videoBusy.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.shop-page {
  --shop-on-primary: var(--c-white);
  max-width: 1180px;
  margin: 0 auto;
  padding: 8px 24px 48px;
  color: var(--c-text);
}
.shop-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 28px 30px;
  border: 1px solid var(--glass-border-strong);
  border-radius: var(--radius-lg);
  background: var(--glass-bg-strong);
  box-shadow: var(--glass-shadow);
  backdrop-filter: blur(var(--glass-blur-lg)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg)) saturate(var(--glass-saturate));
}
.shop-hero__copy h1 { margin: 0 0 8px; font-size: 26px; letter-spacing: -.02em; }
.shop-hero__copy p { margin: 0; color: var(--c-text-secondary); font-size: 13px; line-height: 1.7; }
.shop-rates { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 16px; color: var(--c-text-muted); font-size: 11px; }
.shop-frequent { display: inline-flex; align-items: center; gap: 10px; margin-top: 18px; padding: 10px 14px; border: 1px solid var(--c-border); border-radius: 10px; background: var(--c-primary-light); }
.shop-frequent svg { width: 22px; height: 22px; flex-shrink: 0; color: var(--c-primary); }
.shop-frequent div { display: flex; flex-direction: column; gap: 2px; }
.shop-frequent span { color: var(--c-text-muted); font-size: 10px; }
.shop-frequent strong { color: var(--c-primary); font-size: 14px; font-variant-numeric: tabular-nums; }
.shop-balance { flex-shrink: 0; min-width: 190px; padding: 16px 20px; border-radius: var(--radius-md); background: var(--c-primary-light); }
.shop-balance__label { display: block; color: var(--c-text-muted); font-size: 11px; }
.shop-balance strong { display: block; margin: 4px 0 10px; color: var(--c-primary); font-size: 32px; font-variant-numeric: tabular-nums; line-height: 1; }
.shop-balance__actions { display: flex; flex-wrap: wrap; gap: 6px; }
.shop-section { margin-top: 30px; }
.shop-section__head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.shop-section__head h2 { margin: 0; font-size: 17px; letter-spacing: -.01em; }
.shop-section__head span { color: var(--c-text-muted); font-size: 11px; }
.shop-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.shop-card {
  display: flex;
  flex-direction: column;
  min-height: 232px;
  padding: 18px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-card);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
}
.shop-card:hover { transform: translateY(-3px); border-color: var(--glass-border-strong); box-shadow: var(--shadow-lg); }
.shop-card--soldout { opacity: .62; }
.shop-card--locked { opacity: .72; }
.shop-card--locked .shop-card__icon { color: var(--c-text-muted); background: var(--c-bg-subtle, var(--c-border-light)); }
.shop-card__top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.shop-card__icon { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 11px; background: var(--c-primary-light); color: var(--c-primary); font-size: 20px; }
.shop-card__type { color: var(--c-text-muted); font-size: 10px; letter-spacing: .04em; }
.shop-card h3 { margin: 16px 0 7px; font-size: 15px; font-weight: 650; }
.shop-card p { flex: 1; margin: 0 0 16px; color: var(--c-text-secondary); font-size: 12px; line-height: 1.7; }
.shop-card__meta { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
.shop-card__meta strong { color: var(--c-primary); font-size: 20px; font-variant-numeric: tabular-nums; }
.shop-card__meta small { color: var(--c-text-muted); font-size: 10px; font-weight: 400; }
.shop-card__meta span { color: var(--c-text-muted); font-size: 11px; }
.shop-btn {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: var(--c-primary);
  color: var(--shop-on-primary);
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  transition: opacity .2s ease, transform .2s ease;
}
.shop-btn:hover:not(:disabled) { opacity: .9; transform: translateY(-1px); }
.shop-btn:disabled { cursor: not-allowed; opacity: .45; }
.shop-btn--ghost { min-height: 30px; padding: 0 10px; border-color: var(--c-border); background: transparent; color: var(--c-text-secondary); font-size: 11px; }
.shop-btn--ghost:hover:not(:disabled) { background: var(--panel-hover); }
.shop-empty { padding: 28px; border: 1px dashed var(--c-border); border-radius: var(--radius-md); color: var(--c-text-muted); font-size: 12px; text-align: center; }
.shop-empty--products {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 260px;
  gap: 14px;
  border-style: solid;
  border-color: var(--c-border);
  background: var(--c-bg-card);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
}
.shop-empty__icon { width: 52px; height: 52px; color: var(--c-text-muted); opacity: .7; }
.shop-empty--products p { margin: 0; color: var(--c-text-muted); font-size: 13px; letter-spacing: .02em; }
.shop-alert { margin: 18px 0 0; padding: 10px 14px; border: 1px solid color-mix(in srgb, var(--c-danger) 35%, transparent); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--c-danger) 10%, transparent); color: var(--c-danger); font-size: 12px; }
.shop-video__panel { padding: 20px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-card); }
.shop-video__panel p { margin: 0 0 12px; color: var(--c-text-secondary); font-size: 12px; }
.shop-video__form { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto; gap: 8px; }
.shop-video__form input { min-width: 0; padding: 9px 11px; border: 1px solid var(--field-border); border-radius: 8px; background: var(--field-bg); color: var(--c-text); font-family: inherit; font-size: 12px; }
.shop-video__msg { margin: 10px 0 0; color: var(--c-text-muted); font-size: 11px; }
.shop-drawer-mask { position: fixed; inset: 0; z-index: 1200; display: flex; justify-content: flex-end; background: color-mix(in srgb, var(--c-text) 30%, transparent); }
.shop-drawer { display: flex; flex-direction: column; width: min(420px, 100%); height: 100%; border-left: 1px solid var(--panel-border); background: var(--panel-bg-solid); box-shadow: var(--shadow-xl); }
.shop-drawer__head { display: flex; align-items: center; justify-content: space-between; padding: 16px 18px; border-bottom: 1px solid var(--c-border-light); }
.shop-tabs { display: flex; gap: 4px; }
.shop-tabs button { padding: 6px 10px; border: 0; border-radius: 7px; background: transparent; color: var(--c-text-muted); cursor: pointer; font-family: inherit; font-size: 12px; }
.shop-tabs button.active { background: var(--c-primary-light); color: var(--c-primary); }
.shop-drawer__close { border: 0; background: transparent; color: var(--c-text-muted); cursor: pointer; font-size: 22px; line-height: 1; }
.shop-drawer__body { flex: 1; overflow-y: auto; padding: 14px 18px; }
.shop-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--c-border-light); }
.shop-row div { min-width: 0; }
.shop-row strong { display: block; overflow: hidden; color: var(--c-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.shop-row span { display: block; margin-top: 3px; color: var(--c-text-muted); font-size: 10px; }
.shop-row b { flex-shrink: 0; color: var(--c-success); font-size: 13px; }
.shop-row b.minus { color: var(--c-danger); }
.shop-row__icon { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; flex-shrink: 0; border-radius: 8px; background: var(--c-primary-light); color: var(--c-primary); font-size: 16px; }
@media (max-width: 960px) {
  .shop-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .shop-hero { align-items: flex-start; flex-direction: column; }
  .shop-balance { width: 100%; }
}
@media (max-width: 600px) {
  .shop-page { padding: 0 16px 32px; }
  .shop-grid, .shop-video__form { grid-template-columns: 1fr; }
  .shop-hero { padding: 20px; }
  .shop-section__head { align-items: flex-start; flex-direction: column; gap: 4px; }
}
html[data-theme='dark'] .shop-page { --shop-on-primary: var(--c-text); }
</style>
