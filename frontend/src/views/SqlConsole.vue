<template>
  <div class="sql-console">
    <div class="toolbar">
      <el-select
        v-model="selectedDs"
        placeholder="选择数据源"
        style="width: 200px;"
        @change="onDsChange"
      >
        <el-option
          v-for="ds in datasources"
          :key="ds.id"
          :label="ds.name"
          :value="ds.id"
        />
      </el-select>
      <el-select
        v-model="selectedDb"
        placeholder="选择数据库"
        style="width: 200px; margin-left: 8px;"
        :disabled="!selectedDs"
        @change="onDbChange"
      >
        <el-option
          v-for="db in databases"
          :key="db.name"
          :label="db.name"
          :value="db.name"
        />
      </el-select>
      <el-button
        style="margin-left: 8px;"
        :disabled="!selectedDb"
        @click="refreshTables"
      >刷新表</el-button>
      <el-tag v-if="rowLimitHint" type="warning" style="margin-left: 8px;">{{ rowLimitHint }}</el-tag>
    </div>

    <div class="body">
      <div class="sidebar">
        <el-input
          v-model="tableFilter"
          placeholder="搜索表"
          size="small"
          clearable
        />
        <el-scrollbar class="tables-list">
          <div
            v-for="t in filteredTables"
            :key="t.name"
            class="table-item"
            @click="insertAtCursor(`\`${t.name}\`")"
          >
            <el-icon><Grid /></el-icon>
            <span>{{ t.name }}</span>
            <span v-if="t.rows != null" class="row-count">{{ t.rows }}</span>
          </div>
          <div v-if="tables.length === 0 && selectedDb" class="empty-tip">暂无表</div>
        </el-scrollbar>
      </div>

      <div class="main">
        <div class="editor-wrap">
          <div class="editor-container">
            <div
              ref="editorRef"
              class="sql-editor"
              contenteditable="true"
              spellcheck="false"
              :data-placeholder="placeholder"
              @input="onEditorInput"
              @keydown="onEditorKeydown"
              @keyup="onEditorSelectionChange"
              @click="onEditorSelectionChange"
              @blur="onEditorBlur"
            ></div>
            <div
              v-if="completions.length > 0 && completionVisible"
              class="completion-popup"
              :style="popupStyle"
            >
              <div
                v-for="(item, idx) in completions"
                :key="item.label + '_' + idx"
                class="completion-item"
                :class="{ active: idx === activeCompletionIdx }"
                @mousedown.prevent="applyCompletion(item)"
                @mouseenter="activeCompletionIdx = idx"
              >
                <span class="completion-icon" :class="'kind-' + item.kind">{{ kindIcon(item.kind) }}</span>
                <span class="completion-label">{{ item.label }}</span>
                <span v-if="item.detail" class="completion-detail">{{ item.detail }}</span>
              </div>
            </div>
          </div>
          <div class="editor-actions">
            <el-button type="primary" :loading="running" @click="runSql">
              <el-icon><CaretRight /></el-icon>
              执行 (Ctrl+Enter)
            </el-button>
            <el-button @click="setEditorText('')">清空</el-button>
            <el-button @click="formatSql">格式化</el-button>
            <span v-if="hasSelection" class="exec-hint">
              <el-icon><Aim /></el-icon>
              将仅执行选中的 {{ selectedText.split(';').filter(s => s.trim()).length }} 条语句
            </span>
            <span v-if="completionVisible" class="exec-hint">
              <el-icon><Search /></el-icon>
              {{ completions.length }} 个建议 (↑↓ 选择, Tab/Enter 确认, Esc 取消)
            </span>
          </div>
        </div>

        <div class="result-area">
          <div v-if="!results" class="result-placeholder">执行 SQL 后将在此显示结果</div>
          <div v-else>
            <div class="result-summary">
              <span>{{ results.is_admin ? '管理员模式' : '普通用户模式' }}</span>
              <span>共 {{ results.statements.length }} 条语句</span>
              <span>累计耗时 {{ results.total_execution_time_ms }} ms</span>
              <span>累计影响 {{ results.total_affected_rows }} 行</span>
            </div>
            <div
              v-for="(stmt, idx) in results.statements"
              :key="idx"
              class="stmt-block"
            >
              <div class="stmt-header">
                <el-tag :type="tagType(stmt)" size="small">{{ stmt.kind }}</el-tag>
                <span v-if="stmt.error" style="color: #f56c6c; margin-left: 8px;">
                  {{ stmt.error }}
                </span>
                <span v-else-if="stmt.skipped" style="color: #909399; margin-left: 8px;">
                  {{ stmt.skip_reason }}
                </span>
                <span v-else style="color: #67c23a; margin-left: 8px;">
                  {{ stmt.kind === 'SELECT' ? `${stmt.affected_rows} 行` : `${stmt.affected_rows} 行受影响` }}
                  ({{ stmt.execution_time_ms }} ms)
                </span>
                <span v-if="stmt.truncated" style="color: #e6a23c; margin-left: 8px;">
                  结果已截断(最多展示 1000 行)
                </span>
              </div>
              <pre class="stmt-sql">{{ stmt.sql }}</pre>
              <el-table
                v-if="stmt.kind === 'SELECT' && stmt.rows && stmt.rows.length"
                :data="stmt.rows"
                border
                size="small"
                max-height="320"
              >
                <el-table-column
                  v-for="col in stmt.columns"
                  :key="col.name"
                  :prop="col.name"
                  :label="col.name"
                  show-overflow-tooltip
                  min-width="120"
                />
              </el-table>
              <div
                v-else-if="stmt.kind === 'SELECT' && (!stmt.rows || !stmt.rows.length) && !stmt.error"
                class="empty-result"
              >无数据</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Grid, CaretRight, Aim, Search } from '@element-plus/icons-vue'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const NON_ADMIN_MAX_ROWS = 20
const placeholder = "在此输入 SQL\n选中部分 SQL 后按 Ctrl+Enter 仅执行选中内容。"

const datasources = ref([])
const databases = ref([])
const tables = ref([])
const tableDetailCache = ref({})
const keywords = ref([])
const selectedDs = ref(null)
const selectedDb = ref('')
const tableFilter = ref('')
const editorRef = ref(null)
const selectedText = ref('')
const running = ref(false)
const results = ref(null)

const completionVisible = ref(false)
const completions = ref([])
const activeCompletionIdx = ref(0)
const popupStyle = ref({ top: '0px', left: '0px' })
let currentTokenInfo = null

const hasSelection = computed(() => !!selectedText.value.trim())

const rowLimitHint = computed(() => {
  if (userStore.isAdmin) return ''
  return `非管理员执行 UPDATE/DELETE/REPLACE 超过 ${NON_ADMIN_MAX_ROWS} 行将被拒绝`
})

const filteredTables = computed(() => {
  const f = (tableFilter.value || '').toLowerCase()
  if (!f) return tables.value
  return tables.value.filter((t) => t.name.toLowerCase().includes(f))
})

function tagType(stmt) {
  if (stmt.error) return 'danger'
  if (stmt.kind === 'SELECT') return 'success'
  if (stmt.kind === 'INSERT' || stmt.kind === 'UPDATE' || stmt.kind === 'REPLACE') return 'warning'
  if (stmt.kind === 'DELETE') return 'danger'
  if (stmt.kind === 'DDL') return 'info'
  return ''
}

function getEditorText() {
  return editorRef.value ? (editorRef.value.innerText || '').replace(/\u00a0/g, ' ') : ''
}

function setEditorText(text) {
  if (!editorRef.value) return
  editorRef.value.innerText = text
  moveCaretToEnd()
  onEditorSelectionChange()
}

function moveCaretToEnd() {
  const el = editorRef.value
  if (!el) return
  el.focus()
  const range = document.createRange()
  range.selectNodeContents(el)
  range.collapse(false)
  const sel = window.getSelection()
  sel.removeAllRanges()
  sel.addRange(range)
}

function insertAtCursor(text) {
  const el = editorRef.value
  if (!el) {
    setEditorText(text)
    return
  }
  el.focus()
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) {
    setEditorText(getEditorText() + text)
    return
  }
  const range = sel.getRangeAt(0)
  if (!el.contains(range.commonAncestorContainer)) {
    setEditorText(getEditorText() + text)
    return
  }
  range.deleteContents()
  const node = document.createTextNode(text)
  range.insertNode(node)
  range.setStartAfter(node)
  range.collapse(true)
  sel.removeAllRanges()
  sel.addRange(range)
  onEditorSelectionChange()
  hideCompletion()
}

function getCaretRect() {
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return null
  const range = sel.getRangeAt(0).cloneRange()
  if (range.collapsed) {
    const node = range.startContainer
    if (node.nodeType === Node.TEXT_NODE && node.parentElement) {
      const r = document.createRange()
      r.setStart(node, Math.max(0, range.startOffset - 1))
      r.setEnd(node, range.startOffset)
      return r.getBoundingClientRect()
    }
  }
  return range.getBoundingClientRect()
}

function findCurrentToken() {
  const el = editorRef.value
  if (!el) return null
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return null
  const range = sel.getRangeAt(0)
  if (range.collapsed !== true) return null
  if (!el.contains(range.startContainer)) return null

  const fullText = getEditorText()
  const caret = range.startOffset
  let containerText = fullText
  let caretInContainer = caret
  if (range.startContainer.nodeType === Node.TEXT_NODE) {
    const textNode = range.startContainer
    const parent = textNode.parentNode
    if (parent !== el) {
      let pos = 0
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null)
      let n
      while ((n = walker.nextNode())) {
        if (n === textNode) {
          caretInContainer = pos + caret
          containerText = fullText
          break
        }
        pos += n.nodeValue.length
      }
    } else {
      containerText = textNode.nodeValue
      caretInContainer = caret
    }
  }

  const before = containerText.substring(0, caretInContainer)
  const m = /([A-Za-z_][A-Za-z0-9_]*|[`"][^`"]*[`"])?$/.exec(before)
  const token = m && m[1] ? m[1] : ''
  const startOffset = caretInContainer - token.length
  const after = containerText.substring(caretInContainer)
  const followingWord = /^([A-Za-z0-9_`"]+)/.exec(after)
  const hasFollowing = !!followingWord
  return {
    token: token.replace(/^[`"]|[`"]$/g, ''),
    rawToken: token,
    startOffset,
    caretOffset: caretInContainer,
    fullText: containerText,
    hasFollowing,
  }
}

function findContextTable() {
  const info = currentTokenInfo
  if (!info) return null
  const before = info.fullText.substring(0, info.startOffset)
  const upcase = before.toUpperCase()
  const tail = upcase.slice(-200)
  const fromMatch = /FROM\s+([`"]?)([A-Za-z_][A-Za-z0-9_.]*)\1[^\w]?$/.exec(tail)
  if (fromMatch) return fromMatch[2]
  const joinMatch = /JOIN\s+([`"]?)([A-Za-z_][A-Za-z0-9_.]*)\1[^\w]?$/.exec(tail)
  if (joinMatch) return joinMatch[2]
  const updateMatch = /UPDATE\s+([`"]?)([A-Za-z_][A-Za-z0-9_.]*)\1[^\w]?$/.exec(tail)
  if (updateMatch) return updateMatch[2]
  const intoMatch = /INTO\s+([`"]?)([A-Za-z_][A-Za-z0-9_.]*)\1[^\w]?$/.exec(tail)
  if (intoMatch) return intoMatch[2]
  return null
}

function isInsideString() {
  const info = currentTokenInfo
  if (!info) return false
  if (info.rawToken && (info.rawToken.startsWith('`') || info.rawToken.startsWith('"'))) return true
  const before = info.fullText.substring(0, info.caretOffset)
  let inS = false, inD = false, inB = false
  for (let i = 0; i < before.length; i++) {
    const c = before[i]
    if (c === "'" && before[i - 1] !== "\\") inS = !inS
    else if (c === '"' && before[i - 1] !== "\\") inD = !inD
    else if (c === "`" && before[i - 1] !== "\\") inB = !inB
  }
  return inS || inD || inB
}

function isAfterFromOrJoin() {
  const info = currentTokenInfo
  if (!info) return false
  const before = info.fullText.substring(0, info.startOffset)
  const upcase = before.toUpperCase()
  return /(FROM|JOIN|UPDATE|INTO|TABLE)\s+[`"]?[A-Za-z0-9_.]*$/.test(upcase.slice(-200))
}

function kindIcon(kind) {
  if (kind === 'table') return 'T'
  if (kind === 'column') return 'C'
  if (kind === 'keyword') return 'K'
  return ' '
}

function buildCompletions(token) {
  if (!token) return []
  const upper = token.toUpperCase()
  const lower = token.toLowerCase()
  const items = []

  if (currentTokenInfo && isInsideString()) return []

  const ctxTable = findContextTable()
  if (ctxTable && isAfterFromOrJoin()) {
    for (const t of tables.value) {
      if (t.name.toLowerCase().startsWith(lower)) {
        items.push({ kind: 'table', label: t.name, detail: '表', value: `\`${t.name}\`` })
      }
    }
  } else if (ctxTable) {
    const cached = tableDetailCache.value[ctxTable.toLowerCase()]
    if (cached) {
      for (const col of cached) {
        if (col.name.toLowerCase().startsWith(lower)) {
          items.push({ kind: 'column', label: col.name, detail: col.type || '字段', value: '`' + col.name + '`' })
        }
      }
    }
    for (const t of tables.value) {
      if (t.name.toLowerCase().startsWith(lower)) {
        items.push({ kind: 'table', label: t.name, detail: '表', value: `\`${t.name}\`` })
      }
    }
  } else {
    for (const t of tables.value) {
      if (t.name.toLowerCase().startsWith(lower)) {
        items.push({ kind: 'table', label: t.name, detail: '表', value: `\`${t.name}\`` })
      }
    }
    for (const k of keywords.value) {
      if (k.toUpperCase().startsWith(upper) && k.toUpperCase() !== upper) {
        items.push({ kind: 'keyword', label: k, detail: '关键字', value: k + ' ' })
      }
    }
  }
  return items.slice(0, 20)
}

function showCompletion() {
  const info = findCurrentToken()
  if (!info) {
    hideCompletion()
    return
  }
  if (info.hasFollowing && !info.token) {
    hideCompletion()
    return
  }
  currentTokenInfo = info
  const items = buildCompletions(info.token)
  if (items.length === 0) {
    hideCompletion()
    return
  }
  completions.value = items
  activeCompletionIdx.value = 0
  completionVisible.value = true
  positionPopup()
}

function positionPopup() {
  const rect = getCaretRect()
  if (!rect) {
    popupStyle.value = { top: '0px', left: '0px' }
    return
  }
  const wrap = editorRef.value?.parentElement
  if (!wrap) {
    popupStyle.value = { top: '0px', left: '0px' }
    return
  }
  const wrapRect = wrap.getBoundingClientRect()
  popupStyle.value = {
    top: rect.bottom - wrapRect.top + 4 + 'px',
    left: rect.left - wrapRect.left + 'px',
  }
}

function hideCompletion() {
  completionVisible.value = false
  completions.value = []
}

function applyCompletion(item) {
  const info = currentTokenInfo
  if (!info) return
  const el = editorRef.value
  if (!el) return
  el.focus()
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return
  const range = sel.getRangeAt(0)
  if (!el.contains(range.startContainer)) return

  const fullText = info.fullText
  const before = fullText.substring(0, info.startOffset)
  const after = fullText.substring(info.caretOffset)
  const newText = before + item.value + after
  el.innerText = newText
  const newCaret = info.startOffset + item.value.length
  setCaretAt(el, newCaret)
  hideCompletion()
  onEditorSelectionChange()
}

function setCaretAt(el, offset) {
  el.focus()
  const text = el.firstChild
  if (!text || text.nodeType !== Node.TEXT_NODE) {
    moveCaretToEnd()
    return
  }
  const range = document.createRange()
  const safe = Math.min(offset, text.nodeValue.length)
  range.setStart(text, safe)
  range.collapse(true)
  const sel = window.getSelection()
  sel.removeAllRanges()
  sel.addRange(range)
}

function formatSql() {
  setEditorText((getEditorText() || '').replace(/\s+/g, ' ').trim())
}

function onEditorInput() {
  showCompletion()
}

function onEditorSelectionChange() {
  const el = editorRef.value
  if (!el) {
    selectedText.value = ''
    return
  }
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) {
    selectedText.value = ''
    return
  }
  const text = sel.toString()
  selectedText.value = text
  if (completionVisible.value) {
    showCompletion()
  }
}

function onEditorBlur() {
  setTimeout(() => {
    if (document.activeElement && document.activeElement.closest('.completion-popup')) return
    hideCompletion()
  }, 150)
}

function onEditorKeydown(e) {
  if (completionVisible.value) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      activeCompletionIdx.value = (activeCompletionIdx.value + 1) % completions.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      activeCompletionIdx.value = (activeCompletionIdx.value - 1 + completions.value.length) % completions.value.length
      return
    }
    if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
      const item = completions.value[activeCompletionIdx.value]
      if (item) {
        e.preventDefault()
        applyCompletion(item)
        return
      }
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      hideCompletion()
      return
    }
  }
  if (e.key === 'Tab' && !completionVisible.value) {
    e.preventDefault()
    const el = editorRef.value
    if (!el) return
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0) return
    const range = sel.getRangeAt(0)
    if (!el.contains(range.startContainer)) return
    range.deleteContents()
    const node = document.createTextNode('  ')
    range.insertNode(node)
    range.setStartAfter(node)
    range.collapse(true)
    sel.removeAllRanges()
    sel.addRange(range)
    onEditorSelectionChange()
    return
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    runSql()
  }
}

function getSqlToExecute() {
  if (selectedText.value.trim()) return selectedText.value
  return getEditorText()
}

async function loadDatasources() {
  try {
    const res = await request.get('/datasources')
    datasources.value = res.data
    if (datasources.value.length && !selectedDs.value) {
      selectedDs.value = datasources.value[0].id
      await onDsChange()
    }
  } catch (e) {
    ElMessage.error('加载数据源失败')
  }
}

async function loadKeywords() {
  try {
    const res = await request.get('/sql/keywords')
    keywords.value = res.data.keywords || []
  } catch (e) {
    keywords.value = []
  }
}

async function onDsChange() {
  databases.value = []
  tables.value = []
  tableDetailCache.value = {}
  selectedDb.value = ''
  if (!selectedDs.value) return
  try {
    const res = await request.get(`/sql/datasources/${selectedDs.value}/databases`)
    databases.value = res.data
    if (databases.value.length) {
      const ds = datasources.value.find((d) => d.id === selectedDs.value)
      const preferred = ds?.database && databases.value.find((d) => d.name === ds.database)
      selectedDb.value = preferred ? preferred.name : databases.value[0].name
      await onDbChange()
    }
  } catch (e) {
    ElMessage.error('加载数据库列表失败')
  }
}

async function onDbChange() {
  tables.value = []
  tableDetailCache.value = {}
  if (!selectedDs.value || !selectedDb.value) return
  try {
    const res = await request.get(`/sql/datasources/${selectedDs.value}/tables`, {
      params: { database: selectedDb.value, with_columns: true },
    })
    tables.value = res.data
    for (const t of res.data) {
      if (t.columns && t.columns.length) {
        tableDetailCache.value[t.name.toLowerCase()] = t.columns
      }
    }
  } catch (e) {
    ElMessage.error('加载表列表失败')
  }
}

async function refreshTables() {
  await onDbChange()
}

async function runSql() {
  if (!selectedDs.value) {
    ElMessage.warning('请先选择数据源')
    return
  }
  const text = getSqlToExecute()
  if (!text.trim()) {
    ElMessage.warning(selectedText.value.trim() ? '选中内容为空' : '请输入 SQL')
    return
  }
  await doExecute(false)
}

async function doExecute(confirmed) {
  running.value = true
  try {
    const text = getSqlToExecute()
    const res = await request.post(`/sql/datasources/${selectedDs.value}/execute`, {
      sql: text,
      database: selectedDb.value || null,
      max_rows: 1000,
      confirm_large_change: !!confirmed,
    })
    results.value = res.data
    if (res.data.statements.some((s) => s.error)) {
      ElMessage.warning('部分语句执行失败')
    } else {
      ElMessage.success('执行完成')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '执行失败')
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadDatasources()
  loadKeywords()
})

onUnmounted(() => {
  // nothing
})
</script>

<style scoped>
.sql-console {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 110px);
}
.toolbar {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 8px;
}
.body {
  display: flex;
  flex: 1;
  min-height: 0;
}
.sidebar {
  width: 240px;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  padding: 8px;
}
.tables-list {
  flex: 1;
  margin-top: 8px;
}
.table-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
}
.table-item:hover {
  background: #f5f7fa;
}
.table-item .row-count {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
}
.empty-tip, .empty-result {
  color: #909399;
  text-align: center;
  padding: 16px 0;
  font-size: 13px;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0 12px;
  min-width: 0;
}
.editor-wrap {
  display: flex;
  flex-direction: column;
  margin-bottom: 8px;
}
.editor-container {
  position: relative;
}
.sql-editor {
  width: 100%;
  min-height: 180px;
  max-height: 280px;
  padding: 10px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  outline: none;
  overflow: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  cursor: text;
  caret-color: #409eff;
  user-select: text;
  -webkit-user-select: text;
  background: #fff;
  line-height: 1.5;
}
.sql-editor:focus {
  border-color: #409eff;
}
.sql-editor:empty::before {
  content: attr(data-placeholder);
  color: #c0c4cc;
  white-space: pre-wrap;
  pointer-events: none;
}
.completion-popup {
  position: absolute;
  z-index: 2000;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  max-height: 240px;
  overflow-y: auto;
  min-width: 220px;
  max-width: 360px;
}
.completion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  font-size: 13px;
  cursor: pointer;
  line-height: 1.4;
  user-select: none;
}
.completion-item.active {
  background: #ecf5ff;
  color: #409eff;
}
.completion-icon {
  display: inline-flex;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: bold;
  color: #fff;
  flex-shrink: 0;
}
.completion-icon.kind-table { background: #409eff; }
.completion-icon.kind-column { background: #67c23a; }
.completion-icon.kind-keyword { background: #e6a23c; }
.completion-label {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.completion-detail {
  margin-left: auto;
  color: #909399;
  font-size: 11px;
  flex-shrink: 0;
}
.editor-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.exec-hint {
  margin-left: 12px;
  color: #67c23a;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.result-area {
  flex: 1;
  overflow: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
  background: #fafbfc;
  min-height: 200px;
}
.result-placeholder {
  color: #c0c4cc;
  text-align: center;
  padding: 60px 0;
}
.result-summary {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #606266;
  padding-bottom: 8px;
  border-bottom: 1px dashed #ebeef5;
  margin-bottom: 8px;
}
.stmt-block {
  margin-bottom: 16px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}
.stmt-header {
  display: flex;
  align-items: center;
  font-size: 13px;
  margin-bottom: 4px;
}
.stmt-sql {
  background: #f5f7fa;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 4px 0;
  max-height: 120px;
  overflow: auto;
}
</style>