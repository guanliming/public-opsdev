<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
      <h3 style="margin: 0;">部署日志</h3>
      <el-button @click="loadLogs">刷新</el-button>
    </div>

    <el-table :data="logs" border stripe>
      <el-table-column prop="project_name" label="项目名称" width="150" />
      <el-table-column prop="deployer" label="部署人员" width="120" />
      <el-table-column label="部署时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.started_at) }}
        </template>
      </el-table-column>
      <el-table-column label="部署结果" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="完成时间" width="180">
        <template #default="{ row }">
          {{ row.finished_at ? formatTime(row.finished_at) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewLog(row)">查看日志</el-button>
          <el-button size="small" type="primary" @click="diagnoseLog(row)" v-if="row.status === 'failed'">AI 诊断</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      @size-change="loadLogs"
      @current-change="loadLogs"
      style="margin-top: 16px; justify-content: flex-end;"
    />

    <!-- 日志详情弹窗 -->
    <el-dialog v-model="logDialogVisible" title="部署日志详情" width="700px">
      <div style="margin-bottom: 12px;">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="项目名称">{{ currentLog.project_name }}</el-descriptions-item>
          <el-descriptions-item label="部署人员">{{ currentLog.deployer }}</el-descriptions-item>
          <el-descriptions-item label="部署时间">{{ formatTime(currentLog.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="部署结果">
            <el-tag :type="statusType(currentLog.status)">{{ statusText(currentLog.status) }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <div style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; height: 400px; overflow-y: auto; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all;">{{ currentLog.log || '暂无日志' }}</div>
      <template #footer>
        <el-button @click="logDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, inject, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const openDiagnosis = inject('openDiagnosis')

const logs = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const logDialogVisible = ref(false)
const currentLog = reactive({
  project_name: '',
  deployer: '',
  status: '',
  started_at: '',
  finished_at: '',
  log: '',
})

let pollTimer = null

async function loadLogs() {
  try {
    const { data } = await request.get('/deploy-logs', { params: { page: page.value, page_size: pageSize.value } })
    logs.value = data.items || []
    total.value = data.total || 0
    startPollingIfNeeded()
  } catch (e) {
    console.error('加载部署日志失败', e)
  }
}

function startPollingIfNeeded() {
  stopPolling()
  const hasRunning = logs.value.some(l => l.status === 'running')
  if (hasRunning) {
    pollTimer = setInterval(async () => {
      const { data } = await request.get('/deploy-logs', { params: { page: page.value, page_size: pageSize.value } })
      logs.value = data.items
      total.value = data.total
      if (!data.items.some(l => l.status === 'running')) {
        stopPolling()
      }
    }, 3000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function viewLog(row) {
  const { data } = await request.get(`/deploy-logs/${row.id}`)
  Object.assign(currentLog, data)
  logDialogVisible.value = true
}

async function diagnoseLog(row) {
  const { data } = await request.get(`/deploy-logs/${row.id}`)
  if (openDiagnosis && data.log) {
    openDiagnosis(null, data.log, `部署失败 - 项目: ${data.project_name}, 部署人: ${data.deployer}`)
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm('确定删除该部署记录？', '确认', { type: 'warning' })
  await request.delete(`/deploy-logs/${row.id}`)
  ElMessage.success('删除成功')
  await loadLogs()
}

function statusType(status) {
  if (status === 'running') return 'warning'
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

function statusText(status) {
  if (status === 'running') return '部署中'
  if (status === 'success') return '成功'
  if (status === 'failed') return '失败'
  return '未知'
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(loadLogs)
onUnmounted(stopPolling)
</script>
