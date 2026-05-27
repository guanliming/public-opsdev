<template>
  <div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">
      <h3 style="margin: 0;">应用日志</h3>
      <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 200px;" @change="onProjectChange">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="keyword" placeholder="关键词搜索" style="width: 350px;" clearable @keyup.enter="doSearch" />
      <el-button type="primary" @click="doSearch" :disabled="!selectedProjectId || !keyword">搜索</el-button>
      <el-select v-model="tailLines" style="width: 150px;">
        <el-option :value="300" label="最近300行" />
        <el-option :value="500" label="最近500行" />
        <el-option :value="1000" label="最近1000行" />
        <el-option :value="2000" label="最近2000行" />
        <el-option :value="0" label="自定义行数" />
      </el-select>
      <el-input-number v-if="tailLines === 0" v-model="customLines" :min="100" :max="10000" :step="100" style="width: 130px;" />
      <el-button @click="loadTail" :disabled="!selectedProjectId">加载</el-button>
      <el-switch v-model="streaming" active-text="实时" inactive-text="暂停" @change="toggleStream" :disabled="!selectedProjectId" />
    </div>
    <div ref="terminalContainer" style="height: calc(100vh - 200px); border: 1px solid #dcdfe6; border-radius: 4px; overflow: hidden;"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const route = useRoute()
const userStore = useUserStore()

const projects = ref([])
const selectedProjectId = ref(null)
const keyword = ref('')
const streaming = ref(false)
const tailLines = ref(500)
const customLines = ref(500)
const terminalContainer = ref(null)

let terminal = null
let fitAddon = null
let eventSource = null
let resizeObserver = null

async function loadProjects() {
  const { data } = await request.get('/projects')
  projects.value = data
}

function initTerminal() {
  terminal = new Terminal({
    cursorBlink: false,
    disableStdin: true,
    fontSize: 13,
    fontFamily: 'Consolas, "Courier New", monospace',
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
    },
    convertEol: true,
    scrollback: 5000,
  })
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalContainer.value)
  fitAddon.fit()

  resizeObserver = new ResizeObserver(() => {
    fitAddon.fit()
  })
  resizeObserver.observe(terminalContainer.value)
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

async function loadTail() {
  if (!selectedProjectId.value) return
  const lines = tailLines.value === 0 ? customLines.value : tailLines.value
  try {
    const { data } = await request.get('/logs/tail', { params: { project_id: selectedProjectId.value, lines } })
    terminal.clear()
    terminal.write(data.data)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载日志失败')
  }
}

async function doSearch() {
  if (!selectedProjectId.value || !keyword.value) return
  try {
    const { data } = await request.get('/logs/search', {
      params: { project_id: selectedProjectId.value, keyword: keyword.value }
    })
    terminal.clear()
    if (!data.data) {
      terminal.writeln('\x1b[33m未找到匹配内容\x1b[0m')
    } else {
      const highlighted = data.data.replace(
        new RegExp(escapeRegex(data.keyword), 'gi'),
        match => `\x1b[43m\x1b[30m${match}\x1b[0m`
      )
      terminal.write(highlighted)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '搜索失败')
  }
}

function toggleStream(val) {
  if (val) {
    startStream()
  } else {
    stopStream()
  }
}

function startStream() {
  if (!selectedProjectId.value) return
  stopStream()

  const token = userStore.token
  const url = `/api/logs/stream?token=${token}&project_id=${selectedProjectId.value}`
  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    terminal.writeln(event.data)
  }

  eventSource.onerror = () => {
    streaming.value = false
    eventSource.close()
    eventSource = null
  }
}

function stopStream() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

function onProjectChange(projectId) {
  if (!projectId) return
  stopStream()
  terminal.clear()
  streaming.value = true
  startStream()
}

onMounted(async () => {
  await loadProjects()
  await nextTick()
  initTerminal()

  const queryProject = route.query.project
  if (queryProject) {
    const id = Number(queryProject)
    if (projects.value.some(p => p.id === id)) {
      selectedProjectId.value = id
      await nextTick()
      onProjectChange(id)
    }
  }
})

onUnmounted(() => {
  stopStream()
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (terminal) {
    terminal.dispose()
  }
})
</script>
