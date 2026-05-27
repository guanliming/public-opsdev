<template>
  <div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">
      <h3 style="margin: 0;">应用日志</h3>
      <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 200px;" @change="onProjectChange">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="keyword" placeholder="关键词搜索" style="width: 200px;" clearable @keyup.enter="doSearch" />
      <el-button type="primary" @click="doSearch" :disabled="!selectedProjectId || !keyword">搜索</el-button>
      <el-button @click="loadTail" :disabled="!selectedProjectId">加载最近500行</el-button>
      <el-switch v-model="streaming" active-text="实时" inactive-text="暂停" @change="toggleStream" :disabled="!selectedProjectId" />
    </div>
    <div ref="terminalContainer" style="height: calc(100vh - 200px); border: 1px solid #dcdfe6; border-radius: 4px; overflow: hidden;"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
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
const terminalContainer = ref(null)

let terminal = null
let fitAddon = null
let ws = null
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

function connectWs(projectId) {
  disconnectWs()

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const token = userStore.token
  const url = `${protocol}//${host}/api/ws/logs?token=${token}&project_id=${projectId}`

  ws = new WebSocket(url)

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'bulk') {
      terminal.clear()
      terminal.write(msg.data)
    } else if (msg.type === 'line') {
      terminal.write(msg.data)
    } else if (msg.type === 'search_result') {
      terminal.clear()
      if (!msg.data) {
        terminal.writeln('\x1b[33m未找到匹配内容\x1b[0m')
      } else {
        const highlighted = msg.data.replace(
          new RegExp(escapeRegex(msg.keyword), 'gi'),
          match => `\x1b[43m\x1b[30m${match}\x1b[0m`
        )
        terminal.write(highlighted)
      }
    } else if (msg.type === 'error') {
      ElMessage.error(msg.data)
    }
  }

  ws.onclose = (event) => {
    if (event.code === 4001) {
      ElMessage.error('认证失败，请重新登录')
    }
  }

  ws.onerror = () => {
    ElMessage.error('WebSocket 连接失败')
  }
}

function disconnectWs() {
  if (ws) {
    ws.close()
    ws = null
  }
  streaming.value = false
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function sendWsMessage(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg))
  } else {
    ElMessage.warning('连接未就绪，请先选择项目')
  }
}

function onProjectChange(projectId) {
  if (!projectId) return
  terminal.clear()
  connectWs(projectId)
  setTimeout(() => loadTail(), 300)
}

function loadTail() {
  sendWsMessage({ action: 'tail' })
}

function doSearch() {
  if (!keyword.value) return
  sendWsMessage({ action: 'search', keyword: keyword.value })
}

function toggleStream(val) {
  if (val) {
    sendWsMessage({ action: 'stream_start' })
  } else {
    sendWsMessage({ action: 'stream_stop' })
  }
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
  disconnectWs()
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (terminal) {
    terminal.dispose()
  }
})
</script>
