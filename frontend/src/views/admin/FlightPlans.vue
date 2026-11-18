<template>
  <div class="admin-page fade-in">
    <div class="page-header flex justify-between items-start flex-wrap gap-md">
      <div>
        <h1>飞行计划管理</h1>
        <p>管理所有用户的飞行计划</p>
      </div>
    </div>

    <div class="card flightplans-card">
      <div class="table-wrap flightplans-table-wrap">
        <table v-sort="{ index: 1 }" class="flightplans-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>CID</th>
              <th>呼号</th>
              <th>机型</th>
              <th>离场</th>
              <th>到达</th>
              <th>类型</th>
              <th>航路</th>
              <th>FSD</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in list" :key="p.id">
              <td>{{ p.id }}</td>
              <td class="font-bold">{{ p.userId }}</td>
              <td class="font-bold">{{ p.callsign }}</td>
              <td>{{ p.aircraft || '-' }}</td>
              <td>{{ p.depIcao }}</td>
              <td>{{ p.arrIcao }}</td>
              <td><span class="badge badge-info">{{ p.flightType }}</span></td>
              <td class="fp-route-cell" :title="p.route || '-'">{{ shortRoute(p.route) }}</td>
              <td>
                <span class="badge" :class="p.syncFsd ? 'badge-success' : 'badge-default'">
                  {{ p.syncFsd ? '已同步' : '未同步' }}
                </span>
              </td>
              <td class="text-muted text-sm">{{ p.filedAt }}</td>
              <td>
                <div class="fp-actions">
                  <button type="button" class="fp-action fp-action--detail" @click="openDetail(p)">详情</button>
                  <button type="button" class="fp-action fp-action--delete" @click="delPlan(p)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!list.length">
              <td colspan="11" class="text-center text-muted">暂无飞行计划</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="total > pageSize" class="flex justify-center gap-sm p-md flightplans-pager">
        <button class="btn btn-outline btn-sm" :disabled="page <= 1" @click="page--;load()">上一页</button>
        <span class="text-sm text-muted" style="display:flex;align-items:center;">第 {{ page }} / {{ maxPage }} 页</span>
        <button class="btn btn-outline btn-sm" :disabled="page >= maxPage" @click="page++;load()">下一页</button>
      </div>
    </div>

    <FlightPlanDetailModal
      :open="!!detailPlan"
      :plan="detailPlan"
      @update:open="(v) => { if (!v) detailPlan = null }"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminApi } from '@/api'
import FlightPlanDetailModal from '@/components/FlightPlanDetailModal.vue'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const detailPlan = ref(null)

const maxPage = computed(() => Math.ceil(total.value / pageSize) || 1)

onMounted(() => load())

async function load() {
  try {
    const res = await adminApi.flightplans({ page: page.value, pageSize })
    list.value = res.data.items
    total.value = res.data.total
  } catch { /* ignore */ }
}

function shortRoute(route) {
  const text = String(route || '').trim()
  if (!text) return '-'
  const points = text.split(/\s+/)
  if (points.length <= 3) return text
  return `${points.slice(0, 3).join(' ')} …`
}

function openDetail(plan) {
  detailPlan.value = plan
}

async function delPlan(p) {
  if (!confirm(`确定删除 ${p.callsign} 的飞行计划？`)) return
  try {
    await adminApi.deleteFlightplan(p.id)
    list.value = list.value.filter(x => x.id !== p.id)
    total.value--
  } catch (e) { alert(e.message) }
}
</script>

<style scoped>
/* 半透明主题面板 + 毛玻璃：保留飞机背景轮廓，同时避免线条穿字 */
.flightplans-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  border-radius: 16px;
  overflow: hidden;
}

.flightplans-table-wrap {
  overflow-x: auto;
  border-radius: 16px;
}

.flightplans-table {
  width: 100%;
  min-width: 1180px;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
}

.flightplans-table th,
.flightplans-table td {
  padding: 14px 10px;
  color: var(--table-text);
  border-bottom: 1px solid var(--table-border);
  vertical-align: middle;
  white-space: nowrap;
  word-break: normal;
  overflow-wrap: normal;
}

.flightplans-table th {
  color: var(--table-head-color);
  background: var(--table-head-bg);
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--table-head-border);
}

.flightplans-table tbody tr:last-child td {
  border-bottom: 0;
}

.flightplans-table tbody tr:hover td {
  background: var(--table-row-hover);
}

/* 列宽：短字段紧凑，航路列截断，操作列给按钮留足空间 */
.flightplans-table th:nth-child(1),
.flightplans-table td:nth-child(1) { width: 58px; }
.flightplans-table th:nth-child(2),
.flightplans-table td:nth-child(2) { width: 82px; }
.flightplans-table th:nth-child(3),
.flightplans-table td:nth-child(3) { width: 92px; }
.flightplans-table th:nth-child(4),
.flightplans-table td:nth-child(4) { width: 88px; }
.flightplans-table th:nth-child(5),
.flightplans-table td:nth-child(5) { width: 72px; }
.flightplans-table th:nth-child(6),
.flightplans-table td:nth-child(6) { width: 72px; }
.flightplans-table th:nth-child(7),
.flightplans-table td:nth-child(7) { width: 82px; }
.flightplans-table th:nth-child(8),
.flightplans-table td:nth-child(8) { width: 190px; }
.flightplans-table th:nth-child(9),
.flightplans-table td:nth-child(9) { width: 88px; }
.flightplans-table th:nth-child(10),
.flightplans-table td:nth-child(10) { width: 152px; }
.flightplans-table th:nth-child(11),
.flightplans-table td:nth-child(11) { width: 150px; }

.fp-route-cell {
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fp-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-action {
  padding: 4px 12px;
  border: 0;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.4;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: none;
  transition: background 0.15s ease, color 0.15s ease;
}

.fp-action--detail {
  background: var(--action-info-bg);
  color: var(--action-info-text);
}

.fp-action--detail:hover {
  background: var(--action-info-hover);
}

.fp-action--delete {
  background: var(--action-danger-bg);
  color: var(--action-danger-text);
}

.fp-action--delete:hover {
  background: var(--action-danger-hover);
}

.flightplans-pager {
  border-top: 1px solid var(--table-border);
}
</style>
