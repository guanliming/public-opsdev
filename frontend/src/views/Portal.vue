<template>
  <div class="portal-page">
    <div class="portal-section" v-if="links.length">
      <h3 class="section-title">快捷链接</h3>
      <div class="card-grid">
        <div
          v-for="link in links"
          :key="'link-' + link.id"
          class="portal-card"
          @click="openLink(link.url)"
        >
          <el-icon :size="40" class="card-icon">
            <Link />
          </el-icon>
          <span class="card-name">{{ link.name }}</span>
        </div>
      </div>
    </div>

    <div class="portal-section" v-if="vms.length">
      <h3 class="section-title">虚拟机工具</h3>
      <div class="card-grid">
        <div
          v-for="vm in vms"
          :key="'vm-' + vm.id"
          class="portal-card vm-card"
          @click="connectVm(vm)"
        >
          <el-icon :size="40" class="card-icon">
            <Monitor />
          </el-icon>
          <span class="card-name">{{ vm.name }}</span>
          <span class="card-desc">{{ vm.host }}:{{ vm.port }}</span>
        </div>
      </div>
    </div>

    <el-empty v-if="!links.length && !vms.length && !loading" description="暂无配置，请联系管理员添加" />

    <el-dialog
      v-model="terminalVisible"
      :title="'终端 - ' + currentVm?.name"
      width="80%"
      :close-on-click-modal="false"
      :destroy-on-close="true"
      :trap-focus="false"
      @closed="onTerminalClose"
      class="terminal-dialog"
    >
      <div ref="terminalRef" class="terminal-container"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, Monitor } from '@element-plus/icons-vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const links = ref([])
const vms = ref([])
const loading = ref(true)
const terminalVisible = ref(false)
const terminalRef = ref(null)
const currentVm = ref(null)
let terminal = null
let fitAddon = null
let ws = null

onMounted(async () => {
  try {
    const [linksRes, vmsRes] = await Promise.all([
      request.get('/portal/links'),
      request.get('/portal/vms'),
    ])
    links.value = linksRes.data
    vms.value = vmsRes.data
  } catch (e) {
    ElMessage.error('加载门户数据失败')
  } finally {
    loading.value = false
  }
})

function openLink(url) {
  window.open(url, '_blank')
}

async function connectVm(vm) {
  currentVm.value = vm
  terminalVisible.value = true
  await nextTick()
  await nextTick()
  initTerminal(vm)
}

function initTerminal(vm) {
  terminal = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Consolas, "Courier New", monospace',
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
    },
    rightClickSelectsWord: true,
    allowProposedApi: true,
  })
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalRef.value)
  fitAddon.fit()
  terminal.focus()

  terminal.writeln('正在连接 ' + vm.host + ':' + vm.port + ' ...')

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/ssh/${vm.id}?token=${userStore.token}`
  ws = new WebSocket(wsUrl)
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    terminal.writeln('连接成功!\r\n')
    const dims = fitAddon.proposeDimensions()
    if (dims) {
      ws.send(`\x1b[resize:${dims.cols},${dims.rows}]`)
    }
  }

  ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      terminal.write(new Uint8Array(event.data))
    } else {
      terminal.write(event.data)
    }
  }

  ws.onerror = () => {
    terminal.writeln('\r\n连接错误')
  }

  ws.onclose = () => {
    terminal.writeln('\r\n连接已断开')
  }

  terminal.attachCustomKeyEventHandler((event) => {
    if (event.ctrlKey && event.key === 'c' && event.type === 'keydown') {
      if (terminal.hasSelection()) {
        navigator.clipboard.writeText(terminal.getSelection()).catch(() => {})
        terminal.clearSelection()
        return false
      }
    }
    if (event.ctrlKey && event.key === 'v' && event.type === 'keydown') {
      navigator.clipboard.readText().then((text) => {
        if (text && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(text)
        }
      }).catch(() => {})
      return false
    }
    return true
  })

  terminal.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      if (/^\x1b\[M/.test(data) || /^\x1b\[</.test(data)) {
        return
      }
      ws.send(data)
    }
  })

  terminal.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(`\x1b[resize:${cols},${rows}]`)
    }
  })

  const resizeObserver = new ResizeObserver(() => {
    fitAddon.fit()
  })
  resizeObserver.observe(terminalRef.value)
}

function onTerminalClose() {
  if (ws) {
    ws.close()
    ws = null
  }
  if (terminal) {
    terminal.dispose()
    terminal = null
  }
  fitAddon = null
  currentVm.value = null
}
</script>

<style scoped>
.portal-page {
  padding: 20px;
}

.portal-section {
  margin-bottom: 32px;
}

.section-title {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}

.portal-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  background: #fff;
}

.portal-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
  transform: translateY(-2px);
}

.vm-card:hover {
  border-color: #67c23a;
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.15);
}

.card-icon {
  color: #409eff;
  margin-bottom: 12px;
}

.vm-card .card-icon {
  color: #67c23a;
}

.card-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  text-align: center;
  word-break: break-all;
}

.card-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.terminal-container {
  height: 600px;
  background: #1e1e1e;
  border-radius: 4px;
  overflow: hidden;
}

:deep(.terminal-dialog .el-dialog__body) {
  padding: 4px;
}
</style>
