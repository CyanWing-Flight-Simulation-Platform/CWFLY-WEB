<template>
  <div class="meetings fade-in">
    <div class="meetings__inner">
      <div class="page-header">
        <h1>会议记录</h1>
        <p>查看平台公开的会议纪要与资料</p>
      </div>

      <div v-if="loading" class="card p-lg text-center text-muted">正在加载会议记录...</div>
      <div v-else-if="error" class="card p-lg text-center text-muted">{{ error }}</div>
      <div v-else-if="list.length" class="card">
        <div v-for="item in list" :key="item.id" class="meeting-item flex justify-between items-center p-md" style="border-bottom:1px solid var(--c-border-light);">
          <div class="flex-1">
            <div class="font-bold">{{ item.title }}</div>
            <div class="text-sm text-muted mt-sm">{{ item.date }} &middot; {{ item.size }}</div>
          </div>
          <button class="btn btn-outline btn-sm" @click="previewItem = item">预览</button>
        </div>
      </div>
      <div v-else class="card p-lg text-center text-muted">暂无会议记录</div>

      <Teleport to="body">
        <div v-if="previewItem" class="modal-overlay" @click.self="previewItem = null">
          <div class="modal card">
            <div class="modal__header flex justify-between items-center p-md" style="border-bottom:1px solid var(--c-border-light);">
              <h3>{{ previewItem.title }}</h3>
              <button class="btn btn-outline btn-sm" @click="previewItem = null">&times;</button>
            </div>
            <div class="modal__body p-lg" v-html="sanitizeHtml(previewItem.content)"></div>
          </div>
        </div>
      </Teleport>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { meetingsApi } from '@/api'
import { sanitizeHtml } from '@/utils/sanitize'

const list = ref([])
const loading = ref(false)
const error = ref('')
const previewItem = ref(null)

onMounted(async () => {
  loading.value = true
  try {
    const res = await meetingsApi.list()
    list.value = Array.isArray(res.data) ? res.data : []
  } catch (err) {
    error.value = err.message || '会议记录加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.meetings__inner { max-width: 860px; margin: 0 auto; padding: 0 24px; }
.meeting-item:last-child { border-bottom: none !important; }

.modal-overlay {
  position: fixed; inset: 0; z-index: 2000;
  background: rgba(0,0,0,.4);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.modal {
  width: 100%; max-width: 700px; max-height: 80vh;
  display: flex; flex-direction: column;
}
.modal__body { overflow-y: auto; }
.modal__body :deep(h1), .modal__body :deep(h2), .modal__body :deep(h3) { margin: 16px 0 8px; }
.modal__body :deep(p) { margin-bottom: 8px; line-height: 1.7; }
.modal__body :deep(img) { max-width: 100%; }
</style>
