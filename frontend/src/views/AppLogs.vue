<template>
  <div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">
      <h3 style="margin: 0;">应用日志</h3>
      <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 200px;" @change="onProjectChange">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="keyword" placeholder="关键词搜索" style="width: 350px;" clearable @keyup.enter="doSearch" />
      <el-button type="primary" @click="doSearch" :disabled="!selectedProjectId">搜索</el-button>
      <el-select v-model="tailLines" style="width: 150px;">
        <el-option :value="300" label="最近300行" />
        <el-option :value="500" label="最近500行" />
        <el-option :value="1000" label="最近1000行" />
        <el-option :value="2000" label="最近2000行" />
        <el-option :value="0" label="自定义行数" />
      </el-select>
      <el-input-number v-if="tailLines === 0" v-model="customLines" :min="100" :max="10000" :step="100" style="width: 130px;" />
      <el-button @click="loadTail" :disabled="!selectedProjectId">加载</el-button>
      <el-popover
        v-model:visible="moreLogsVisible"
        placement="bottom-start"
        :width="420"
        trigger="click"
        @show="loadLogFiles"
      >
        <template #reference>
          <el-button :disabled="!selectedProjectId" :loading="loadingFiles">更多日志</el-button>
        </template>
        <div v-loading="loadingFiles">
          <div v-if="!loadingFiles && logFiles.length === 0" style="text-align: center; color: #999; padding: 12px;">
            未发现其他日志文件
          </div>
          <div v-else style="max-height: 300px; overflow-y: auto;">
            <div
              v-for="f in logFiles"
              :key="f.path"
              @click="selectLogFile(f)"
              style="padding: 8px 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee;"
              :style="{ background: activeLogFile?.path === f.path ? '#ecf5ff' : '' }"
            >
              <span style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
                <el-tag size="small" :type="f.type === 'gz' ? 'warning' : 'success'">
                  {{ f.type === 'gz' ? 'GZ' : 'LOG' }}
                </el-tag>
                <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ f.name }}</span>
              </span>
              <el-tag v-if="f.type === 'log'" size="small" type="info">可实时</el-tag>
            </div>
          </div>
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee; text-align: right;">
            <el-button size="small" @click="resetToDefaultLog" :disabled="!activeLogFile">恢复默认日志</el-button>
          </div>
        </div>
      </el-popover>
      <el-switch v-model="streaming" active-text="实时" inactive-text="暂停" @change="toggleStream" :disabled="!selectedProjectId || activeLogFile?.type === 'gz'" />
      <span v-if="activeLogFile" style="font-size: 12px; color: #409eff;">
        当前: {{ activeLogFile.name }}
      </span>
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

const activeLogFile = ref(null)
const logFiles = ref([])
const moreLogsVisible = ref(false)
const loadingFiles = ref(false)

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

async function loadLogFiles() {
  if (!selectedProjectId.value) return
  loadingFiles.value = true
  try {
    const { data } = await request.get('/logs/files', {
      params: { project_id: selectedProjectId.value }
    })
    logFiles.value = data.files
  } catch (e) {
    ElMessage.error('加载日志文件列表失败')
  } finally {
    loadingFiles.value = false
  }
}

function selectLogFile(file) {
  activeLogFile.value = file
  moreLogsVisible.value = false
  if (file.type === 'gz' && streaming.value) {
    streaming.value = false
    stopStream()
  }
  loadTail()
}

function resetToDefaultLog() {
  activeLogFile.value = null
  moreLogsVisible.value = false
  loadTail()
}

async function loadTail() {
  if (!selectedProjectId.value) return
  const lines = tailLines.value === 0 ? customLines.value : tailLines.value
  const params = { project_id: selectedProjectId.value, lines }
  if (activeLogFile.value) {
    params.file_path = activeLogFile.value.path
  }
  try {
    const { data } = await request.get('/logs/tail', { params })
    terminal.clear()
    terminal.write(data.data)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载日志失败')
  }
}

async function doSearch() {
  if (!selectedProjectId.value) return
  if (!keyword.value) {
    loadTail()
    return
  }
  try {
    const params = { project_id: selectedProjectId.value, keyword: keyword.value }
    if (activeLogFile.value) {
      params.file_path = activeLogFile.value.path
    }
    const { data } = await request.get('/logs/search', { params })
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
  if (activeLogFile.value?.type === 'gz') return
  stopStream()

  const token = userStore.token
  let url = `/api/logs/stream?token=${token}&project_id=${selectedProjectId.value}`
  if (activeLogFile.value) {
    url += `&file_path=${encodeURIComponent(activeLogFile.value.path)}`
  }
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
  activeLogFile.value = null
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
  } else if (projects.value.length > 0) {
    selectedProjectId.value = projects.value[0].id
    await nextTick()
    onProjectChange(projects.value[0].id)
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
