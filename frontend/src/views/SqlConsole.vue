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
            @click="insertTableName(t.name)"
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
          <textarea
            v-model="sqlText"
            class="sql-editor"
            placeholder="在此输入 SQL,支持多语句(以分号分隔)。SELECT/INSERT/UPDATE/DELETE/REPLACE。&#10;例如: SELECT * FROM users LIMIT 10;"
            spellcheck="false"
            @keydown.tab.prevent="handleTab"
          ></textarea>
          <div class="editor-actions">
            <el-button type="primary" :loading="running" @click="runSql">
              <el-icon><CaretRight /></el-icon>
              执行 (Ctrl+Enter)
            </el-button>
            <el-button @click="sqlText = ''">清空</el-button>
            <el-button @click="formatSql">格式化</el-button>
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

    <el-dialog
      v-model="confirmDialogVisible"
      title="确认执行"
      width="480px"
    >
      <p>{{ confirmMessage }}</p>
      <p style="color: #909399; font-size: 12px;">提示: 非管理员用户的 UPDATE/DELETE/REPLACE 受影响行数超过 {{ NON_ADMIN_MAX_ROWS }} 会被系统拒绝。</p>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doExecute(true)">确认执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Grid, CaretRight } from '@element-plus/icons-vue'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const NON_ADMIN_MAX_ROWS = 20

const datasources = ref([])
const databases = ref([])
const tables = ref([])
const selectedDs = ref(null)
const selectedDb = ref('')
const tableFilter = ref('')
const sqlText = ref('')
const running = ref(false)
const results = ref(null)
const confirmDialogVisible = ref(false)
const confirmMessage = ref('')

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

function handleTab(e) {
  const el = e.target
  const start = el.selectionStart
  const end = el.selectionEnd
  const v = sqlText.value
  sqlText.value = v.substring(0, start) + '  ' + v.substring(end)
  setTimeout(() => {
    el.selectionStart = el.selectionEnd = start + 2
  }, 0)
}

function insertTableName(name) {
  sqlText.value = (sqlText.value || '').trimEnd()
  if (sqlText.value && !sqlText.value.endsWith(' ')) sqlText.value += ' '
  sqlText.value += `\`${name}\``
}

function formatSql() {
  sqlText.value = (sqlText.value || '').replace(/\s+/g, ' ').trim()
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

async function onDsChange() {
  databases.value = []
  tables.value = []
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
  if (!selectedDs.value || !selectedDb.value) return
  try {
    const res = await request.get(`/sql/datasources/${selectedDs.value}/tables`, {
      params: { database: selectedDb.value },
    })
    tables.value = res.data
  } catch (e) {
    ElMessage.error('加载表列表失败')
  }
}

async function refreshTables() {
  await onDbChange()
}

function hasDestructive() {
  if (!sqlText.value) return false
  return /\b(UPDATE|DELETE|REPLACE)\b/i.test(sqlText.value)
}

async function runSql() {
  if (!selectedDs.value) {
    ElMessage.warning('请先选择数据源')
    return
  }
  if (!sqlText.value.trim()) {
    ElMessage.warning('请输入 SQL')
    return
  }
  if (!userStore.isAdmin && hasDestructive()) {
    try {
      await ElMessageBox.confirm(
        `检测到 UPDATE/DELETE/REPLACE 语句,非管理员执行超过 ${NON_ADMIN_MAX_ROWS} 行将被系统拒绝。是否继续?`,
        '确认',
        { type: 'warning' },
      )
    } catch (e) {
      return
    }
  }
  await doExecute(false)
}

async function doExecute(confirmed) {
  confirmDialogVisible.value = false
  running.value = true
  try {
    const res = await request.post(`/sql/datasources/${selectedDs.value}/execute`, {
      sql: sqlText.value,
      database: selectedDb.value || null,
      max_rows: 1000,
      confirm_large_change: confirmed,
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

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    runSql()
  }
}

onMounted(() => {
  loadDatasources()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
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
.sql-editor {
  width: 100%;
  min-height: 180px;
  max-height: 280px;
  padding: 10px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  resize: vertical;
  outline: none;
}
.sql-editor:focus {
  border-color: #409eff;
}
.editor-actions {
  margin-top: 8px;
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