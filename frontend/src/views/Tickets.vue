<template>
  <div class="admin-page fade-in">
    <div class="page-header flex justify-between items-start flex-wrap gap-md">
      <div>
        <h1>工单中心</h1>
        <p>提交工单寻求帮助或反馈问题</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="showForm=true">+ 新建工单</button>
    </div>

    <!-- 新建工单表单 -->
    <div v-if="showForm" class="card p-lg mb-lg fade-in">
      <h3 class="mb-md">新建工单</h3>
      <div style="max-width:600px;">
        <div class="mb-md">
          <label class="text-sm font-bold mb-sm" style="display:block;">标题</label>
          <input v-model="form.title" class="input" placeholder="工单标题" />
        </div>
        <div class="mb-md">
          <label class="text-sm font-bold mb-sm" style="display:block;">内容</label>
          <textarea v-model="form.content" class="input" rows="6" placeholder="详细描述你的问题或建议..." style="resize:vertical;"></textarea>
        </div>
        <div class="mb-md">
          <label class="text-sm font-bold mb-sm" style="display:block;">附件</label>
          <input ref="fileInput" type="file" accept=".png,.jpg,.jpeg,.docx,.pdf" style="display:none;" @change="onFileChange" />
          <button type="button" class="btn btn-outline btn-sm" :disabled="uploading" @click="fileInput.click()">
            {{ uploading ? '上传中...' : '添加附件' }}
          </button>
          <div v-if="attachment" class="attachment-chip">
            <span>{{ attachment.name || '附件' }}</span>
            <button type="button" class="attachment-remove" aria-label="移除附件" @click="clearAttachment">×</button>
          </div>
          <p class="hint">支持 PNG / JPG / DOCX / PDF，最大 10MB</p>
        </div>
        <div class="flex gap-sm">
          <button class="btn btn-primary" @click="submitTicket" :disabled="submitting">
            {{ submitting ? '提交中...' : '提交工单' }}
          </button>
          <button class="btn btn-outline" @click="showForm=false;resetForm()">取消</button>
        </div>
      </div>
    </div>

    <!-- 工单列表 -->
    <div class="card">
      <div class="p-md" style="border-bottom:1px solid var(--c-border-light);">
        <h3 class="font-bold">我的工单</h3>
      </div>
      <!-- 加载态 Skeleton / 空态 EmptyState；表格仅在数据就绪时渲染 -->
      <div v-if="loading" class="p-lg" aria-busy="true" aria-label="正在加载我的工单">
        <Skeleton :lines="5" :height="16" />
      </div>
      <div v-else-if="!list.length" class="p-md">
        <EmptyState
          icon="ticket"
          title="暂无工单"
          description="提交工单后可以在这里跟踪处理进度。"
          action-text="+ 新建工单"
          @action="showForm = true"
        />
      </div>
      <div v-else class="table-wrap">
        <table v-sort>
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>附件</th>
              <th>状态</th>
              <th>回复</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in list" :key="t.id">
              <td>{{ t.id }}</td>
              <td class="font-bold">{{ t.title }}</td>
              <td>
                <a v-if="t.attachment" :href="t.attachment" class="attachment-link" target="_blank" rel="noopener">下载附件</a>
                <span v-else class="text-muted">-</span>
              </td>
              <td><span class="badge" :class="statusBadge(t.status)">{{ statusLabel(t.status) }}</span></td>
              <td class="text-sm text-muted" style="max-width:200px;">{{ t.reply || '等待回复' }}</td>
              <td class="text-muted text-sm">{{ t.createdAt }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ticketApi } from '@/api'
import EmptyState from '@/components/base/EmptyState.vue'
import Skeleton from '@/components/base/Skeleton.vue'

const list = ref([])
const loading = ref(false)
const showForm = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const fileInput = ref(null)
const attachment = ref(null)
const form = ref({ title: '', content: '' })

function statusBadge(s) {
  return s === 'open' ? 'badge-warning' : s === 'in_progress' ? 'badge-info' : s === 'resolved' ? 'badge-success' : 'badge-default'
}
function statusLabel(s) {
  return s === 'open' ? '待处理' : s === 'in_progress' ? '处理中' : s === 'resolved' ? '已解决' : '已关闭'
}
onMounted(async () => {
  loading.value = true
  try {
    const res = await ticketApi.list()
    list.value = res.data
  } catch { /* ignore */ } finally {
    loading.value = false
  }
})

function resetForm() {
  form.value = { title: '', content: '' }
  attachment.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function clearAttachment() {
  attachment.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['png', 'jpg', 'jpeg', 'docx', 'pdf'].includes(ext)) {
    alert('仅支持 PNG / JPG / DOCX / PDF 附件')
    e.target.value = ''
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('附件不能超过 10MB')
    e.target.value = ''
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await ticketApi.upload(fd)
    attachment.value = { url: res.data.url, name: res.data.name || file.name }
  } catch (err) {
    alert('附件上传失败: ' + err.message)
    e.target.value = ''
  } finally {
    uploading.value = false
  }
}

async function submitTicket() {
  if (!form.value.title || !form.value.content) return alert('请填写标题和内容')
  if (uploading.value) return alert('附件正在上传，请稍候')
  submitting.value = true
  try {
    const res = await ticketApi.create({ ...form.value, attachment: attachment.value?.url || '' })
    list.value.unshift(res.data)
    showForm.value = false
    resetForm()
    alert('工单已提交，请等待回复')
  } catch (e) {
    alert('提交失败: ' + e.message)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 640px) {
  .form-row { grid-template-columns: 1fr; }
}
.form-col { display: flex; flex-direction: column; }
.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--ui-ghost-bg);
  border: 1px solid var(--ui-ghost-border);
  color: var(--ui-text);
  font-size: 12px;
}
.attachment-remove {
  border: 0;
  background: transparent;
  color: var(--ui-text-secondary);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}
.attachment-remove:hover { color: var(--ui-danger-text); }
.attachment-link { color: var(--c-primary); font-size: 12px; text-decoration: none; }
.attachment-link:hover { text-decoration: underline; }
</style>
