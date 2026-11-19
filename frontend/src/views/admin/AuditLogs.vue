<template>
  <div class="admin-page fade-in">
    <div class="page-header">
      <h1>审计日志</h1>
      <p>记录用户行为、权限变更、内容管理与风险事件</p>
    </div>

    <div class="card p-md mb-md">
      <div class="flex items-center gap-sm flex-wrap">
        <button
          v-for="d in dayOptions"
          :key="d.value"
          class="btn btn-sm"
          :class="days === d.value ? 'btn-primary' : 'btn-outline'"
          @click="setDays(d.value)"
        >{{ d.label }}</button>

        <input
          v-model="q"
          class="input"
          placeholder="搜索操作人 / 动作 / 详情 / 对象"
          style="max-width:280px;height:34px;"
          @keyup.enter="search"
        />
        <button class="btn btn-primary btn-sm" @click="search">搜索</button>
      </div>

      <div class="flex items-center gap-sm flex-wrap mt-sm">
        <button
          class="btn btn-sm"
          :class="category === '' ? 'btn-primary' : 'btn-outline'"
          @click="setCategory('')"
        >全部</button>
        <button
          v-for="c in byCategory"
          :key="c.category"
          class="btn btn-sm"
          :class="category === c.category ? 'btn-primary' : 'btn-outline'"
          @click="setCategory(c.category)"
        >{{ c.label }}，{{ c.count }}</button>
      </div>
    </div>

    <div class="card">
      <div v-if="loading" class="p-lg text-center text-muted">加载中...</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>类别</th>
              <th>操作人</th>
              <th>行为</th>
              <th>对象</th>
              <th>详情</th>
              <th>IP / UA</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td class="text-sm text-muted" style="white-space:nowrap;">{{ log.time }}</td>
              <td><span class="badge" :class="badgeClass(log.category)">{{ log.categoryLabel }}</span></td>
              <td>
                <div class="font-bold">{{ log.actorName || log.operator || '系统' }}</div>
                <div class="text-xs text-muted">{{ log.actorRole || '—' }}</div>
              </td>
              <td class="font-bold">{{ log.action }}</td>
              <td class="text-sm">
                <template v-if="log.targetType || log.targetId">
                  {{ log.targetType }}<template v-if="log.targetId"> #{{ log.targetId }}</template>
                </template>
                <span v-else>—</span>
              </td>
              <td class="text-sm text-muted" style="max-width:320px;">{{ log.detail || '—' }}</td>
              <td class="text-xs text-muted">
                <div>{{ log.ip || '—' }}</div>
                <div v-if="log.uaLabel">{{ log.uaLabel }}{{ log.uaBot ? ' · 脚本' : '' }}</div>
              </td>
            </tr>
            <tr v-if="!logs.length">
              <td colspan="7" class="text-center text-muted p-lg">暂无审计记录</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="total > pageSize" class="flex justify-center gap-sm p-md" style="border-top:1px solid var(--c-border-light);">
        <button class="btn btn-outline btn-sm" :disabled="page <= 1" @click="prevPage">上一页</button>
        <span class="text-sm text-muted" style="display:flex;align-items:center;">第 {{ page }} / {{ maxPage }} 页</span>
        <button class="btn btn-outline btn-sm" :disabled="page >= maxPage" @click="nextPage">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { adminApi } from '@/api'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const days = ref(7)
const category = ref('')
const q = ref('')
const loading = ref(false)
const byCategory = ref([])

const dayOptions = [
  { value: 1, label: '今天' },
  { value: 7, label: '近 7 天' },
  { value: 30, label: '近 30 天' }
]
const maxPage = computed(() => Math.ceil(total.value / pageSize) || 1)

function badgeClass(cat) {
  if (cat === 'risk') return 'badge-danger'
  if (cat === 'permission') return 'badge-warning'
  if (cat === 'auth') return 'badge-info'
  return 'badge-success'
}

async function load() {
  loading.value = true
  try {
    const res = await adminApi.auditLogs({
      page: page.value,
      pageSize,
      days: days.value,
      category: category.value,
      q: q.value.trim()
    })
    logs.value = res.data.items || []
    total.value = res.data.total || 0
    byCategory.value = res.data.byCategory || []
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}

function setDays(value) {
  days.value = value
  page.value = 1
  load()
}

function setCategory(value) {
  category.value = value
  page.value = 1
  load()
}

function search() {
  page.value = 1
  load()
}

function prevPage() {
  if (page.value <= 1) return
  page.value -= 1
  load()
}

function nextPage() {
  if (page.value >= maxPage.value) return
  page.value += 1
  load()
}

onMounted(load)
</script>
