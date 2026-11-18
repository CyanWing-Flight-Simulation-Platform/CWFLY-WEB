<template>
  <AppModal
    :open="open"
    title="飞行计划详情"
    width="760px"
    variant="solid"
    @update:open="$emit('update:open', $event)"
  >
    <div v-if="plan" class="fp-detail">
      <div class="fp-detail__hero">
        <span class="fp-detail__callsign">{{ plan.callsign || '-' }}</span>
        <span class="fp-chip fp-chip--type">{{ plan.flightType || '-' }}</span>
        <span class="fp-chip" :class="plan.syncFsd ? 'fp-chip--sync-ok' : 'fp-chip--sync-off'">
          <span class="fp-chip__dot" aria-hidden="true"></span>
          {{ plan.syncFsd ? '已同步 FSD' : '未同步 FSD' }}
        </span>
      </div>

      <div class="fp-detail__grid">
        <div v-for="item in fields" :key="item.label" class="fp-detail__item">
          <span class="fp-detail__label">{{ item.label }}</span>
          <span class="fp-detail__value" :class="{ 'fp-detail__value--mono': item.mono }">{{ item.value }}</span>
        </div>
      </div>

      <div class="fp-detail__section">
        <h4 class="fp-detail__section-title">完整航路</h4>
        <pre class="fp-detail__route">{{ plan.route || '未填写' }}</pre>
      </div>

      <div v-if="plan.remarks" class="fp-detail__section">
        <h4 class="fp-detail__section-title">备注</h4>
        <p class="fp-detail__remarks">{{ plan.remarks }}</p>
      </div>
    </div>

    <template #footer>
      <button type="button" class="fp-detail__close" @click="$emit('update:open', false)">关闭</button>
    </template>
  </AppModal>
</template>

<script setup>
import { computed } from 'vue'
import AppModal from '@/components/base/AppModal.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  plan: { type: Object, default: null }
})

defineEmits(['update:open'])

function text(value) {
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

const fields = computed(() => {
  const p = props.plan || {}
  return [
    { label: '计划 ID', value: text(p.id), mono: true },
    { label: '分享 ID', value: text(p.shareId), mono: true },
    { label: '用户 CID', value: text(p.userId), mono: true },
    { label: '呼号', value: text(p.callsign), mono: true },
    { label: '机型', value: text(p.aircraft) },
    { label: '尾流类别', value: text(p.wakeCategory) },
    { label: '设备', value: text(p.equipment) },
    { label: '应答机', value: text(p.transponder), mono: true },
    { label: '起飞机场', value: text(p.depIcao), mono: true },
    { label: '起飞时间', value: text(p.depTime) },
    { label: '巡航高度', value: text(p.cruiseAlt) },
    { label: '巡航速度', value: text(p.cruiseSpeed) },
    { label: '降落机场', value: text(p.arrIcao), mono: true },
    { label: '备降机场', value: text(p.alternate), mono: true },
    { label: '飞行时间', value: text(p.flightTime) },
    { label: '续航时间', value: text(p.endurance) },
    { label: '提交时间', value: text(p.filedAt) }
  ]
})
</script>

<style scoped>
.fp-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: var(--field-value);
}

.fp-detail__hero {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--field-border);
}

.fp-detail__callsign {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--field-value);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.fp-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border: 1px solid var(--field-border);
  border-radius: 6px;
  background: var(--chip-bg);
  color: var(--chip-text);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  white-space: nowrap;
}

.fp-chip--type {
  background: var(--chip-bg);
  color: var(--chip-text);
}

.fp-chip--sync-ok {
  border-color: var(--chip-success-bg);
  background: var(--chip-success-bg);
  color: var(--chip-success-text);
}

.fp-chip--sync-off {
  border-color: var(--field-border);
  background: var(--chip-bg);
  color: var(--chip-text);
}

.fp-chip__dot {
  width: 6px;
  height: 6px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.65;
}

.fp-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: stretch;
  gap: 12px 14px;
}

.fp-detail__item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  min-width: 0;
  min-height: 58px;
  box-sizing: border-box;
  padding: 12px 14px;
  border: 1px solid var(--field-border);
  border-radius: 8px;
  background: var(--field-bg);
}

.fp-detail__label {
  font-size: 12px;
  line-height: 1.4;
  color: var(--field-label);
}

.fp-detail__value {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--field-value);
  word-break: break-word;
}

.fp-detail__value--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  letter-spacing: 0.01em;
}

.fp-detail__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fp-detail__section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--field-label);
}

.fp-detail__route {
  margin: 0;
  padding: 12px 14px;
  max-height: 220px;
  overflow: auto;
  border: 1px solid var(--field-border);
  border-radius: 8px;
  background: var(--field-bg);
  color: var(--field-value);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.fp-detail__remarks {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid var(--field-border);
  border-radius: 8px;
  background: var(--field-bg);
  color: var(--field-value);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.fp-detail__close {
  padding: 6px 16px;
  border: 0;
  border-radius: 8px;
  background: #111111;
  color: #ffffff;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.5;
  cursor: pointer;
  box-shadow: none;
  transition: background-color 0.18s ease;
}

.fp-detail__close:hover {
  background: #2b2b2b;
}

.fp-detail__close:active {
  background: #000000;
}

@media (max-width: 640px) {
  .fp-detail__grid {
    grid-template-columns: 1fr;
  }

  .fp-detail__callsign {
    font-size: 18px;
  }
}
</style>
