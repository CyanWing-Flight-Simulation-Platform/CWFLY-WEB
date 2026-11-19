<template>
  <div class="admin-page fade-in">
    <div class="page-header flex justify-between items-start flex-wrap gap-md">
      <div>
        <h1>会议记录管理</h1>
        <p>上传 PDF/Word 文档，系统自动解析为 HTML 供门户查看</p>
      </div>
      <label class="btn btn-primary btn-sm" style="cursor:pointer;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        上传文档
        <input type="file" accept=".pdf,.doc,.docx" hidden @change="uploadFile" />
      </label>
    </div>

    <div v-if="uploading" class="card p-md mb-md">
      <div class="flex justify-between mb-sm"><span>上传中...</span><span class="text-muted">{{ uploadProgress }}%</span></div>
      <div style="height:4px;background:var(--c-border);border-radius:99px;overflow:hidden;">
        <div :style="{ width: uploadProgress+'%', height:'100%', background:'var(--c-primary)', transition:'width .3s' }"></div>
      </div>
    </div>

    <div v-if="message" class="card p-md mb-md" :class="messageType === 'success' ? 'msg-success' : 'msg-error'">
      <div class="flex justify-between items-center">
        <div class="flex items-center gap-sm">
          <span class="msg-icon">{{ messageType === 'success' ? '✓' : '✕' }}</span>
          <span>{{ message }}</span>
        </div>
        <button class="btn btn-outline btn-sm" @click="message = ''" style="font-size:16px;line-height:1;padding:2px 8px;border:none;">&times;</button>
      </div>
    </div>

    <div v-if="loading" class="card p-lg text-center text-muted">正在加载会议记录...</div>
    <div v-else-if="list.length" class="card">
      <div v-for="item in list" :key="item.id" class="meeting-item flex justify-between items-center p-md" style="border-bottom:1px solid var(--c-border-light);">
        <div class="flex-1">
          <div class="font-bold">{{ item.title }}</div>
          <div class="text-sm text-muted mt-sm">{{ item.date }} &middot; {{ item.size }}</div>
        </div>
        <button class="btn btn-outline btn-sm" @click="previewItem = item">预览</button>
      </div>
    </div>
    <div v-else class="card p-lg text-center text-muted">暂无会议记录，点击右上角上传</div>

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
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { meetingsApi } from '@/api'
import { sanitizeHtml } from '@/utils/sanitize'

const list = ref([])
const loading = ref(true)
const uploading = ref(false)
const uploadProgress = ref(0)
const previewItem = ref(null)
const message = ref('')
const messageType = ref('success')
let messageTimer = null

function showMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
  if (messageTimer) clearTimeout(messageTimer)
  messageTimer = setTimeout(() => { message.value = '' }, 5000)
}

async function loadList() {
  loading.value = true
  try {
    const res = await meetingsApi.list()
    list.value = Array.isArray(res.data) ? res.data : []
  } catch (err) {
    showMessage(err.message || '会议记录加载失败，请检查权限。', 'error')
  } finally {
    loading.value = false
  }
}

async function uploadFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  message.value = ''
  uploading.value = true
  uploadProgress.value = 0
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await meetingsApi.upload(fd, {
      onUploadProgress: (event) => {
        if (event.total) uploadProgress.value = Math.min(99, Math.round((event.loaded / event.total) * 100))
      }
    })
    uploadProgress.value = 100
    if (res.data) list.value.unshift(res.data)
    setTimeout(() => {
      uploading.value = false
      showMessage(`上传成功：${file.name}`)
    }, 500)
  } catch (err) {
    uploading.value = false
    showMessage(err.message || '上传失败，请检查文件类型和大小（支持 PDF/DOC/DOCX，最大 20MB）', 'error')
  } finally {
    e.target.value = ''
  }
}

onMounted(loadList)
</script>

<style scoped>
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

.msg-success { border-left: 4px solid var(--c-success, #30d158); background: rgba(48, 209, 88, 0.08); }
.msg-error { border-left: 4px solid var(--c-danger, #ff453a); background: rgba(255, 69, 58, 0.08); }
.msg-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; font-size: 12px;
  font-weight: bold; flex-shrink: 0;
}
.msg-success .msg-icon { background: var(--c-success, #30d158); color: #fff; }
.msg-error .msg-icon { background: var(--c-danger, #ff453a); color: #fff; }
</style>
