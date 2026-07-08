<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h3 style="margin: 0;">数据源管理</h3>
      <el-button type="primary" @click="handleAdd">新增数据源</el-button>
    </div>

    <el-table :data="datasources" v-loading="loading" border stripe>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="db_type" label="类型" width="80" />
      <el-table-column prop="host" label="地址" min-width="160" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="database" label="数据库" min-width="120" />
      <el-table-column label="密码" width="80">
        <template #default="{ row }">
          <el-tag :type="row.has_password ? 'success' : 'danger'" size="small">
            {{ row.has_password ? '已配置' : '未配置' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleTest(row)">测试连接</el-button>
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑数据源' : '新增数据源'" width="540px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="数据源名称" :disabled="editingId" />
        </el-form-item>
        <el-form-item label="类型" prop="db_type">
          <el-select v-model="form.db_type" style="width: 100%" :disabled="editingId">
            <el-option label="MySQL" value="mysql" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址" prop="host">
          <el-input v-model="form.host" placeholder="IP 或域名" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" :prop="editingId ? '' : 'password'">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editingId ? '留空则不修改' : '请输入密码'"
          />
        </el-form-item>
        <el-form-item label="默认数据库">
          <el-input v-model="form.database" placeholder="可选" />
        </el-form-item>
        <el-form-item label="字符集">
          <el-input v-model="form.charset" placeholder="默认 utf8mb4" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button @click="handleTestInDialog" :loading="testing">测试连接</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="testResultVisible" title="连接测试结果" width="420px">
      <div v-if="testResult?.ok" class="test-ok">
        <el-result icon="success" :title="'连接成功'">
          <template #sub-title>
            <div>版本: {{ testResult.version }}</div>
          </template>
        </el-result>
      </div>
      <div v-else class="test-fail">
        <el-result icon="error" :title="'连接失败'" :sub-title="testResult?.error">
        </el-result>
      </div>
      <template #footer>
        <el-button @click="testResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const datasources = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const testing = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const testResultVisible = ref(false)
const testResult = ref(null)

const form = reactive({
  name: '',
  db_type: 'mysql',
  host: '',
  port: 3306,
  username: '',
  password: '',
  database: '',
  charset: 'utf8mb4',
  description: '',
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const res = await request.get('/datasources')
    datasources.value = res.data
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    name: '',
    db_type: 'mysql',
    host: '',
    port: 3306,
    username: '',
    password: '',
    database: '',
    charset: 'utf8mb4',
    description: '',
  })
}

function handleAdd() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    db_type: row.db_type,
    host: row.host,
    port: row.port,
    username: row.username,
    password: '',
    database: row.database || '',
    charset: row.charset || 'utf8mb4',
    description: row.description || '',
  })
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value) {
      const payload = { ...form }
      if (!payload.password) delete payload.password
      await request.put(`/datasources/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/datasources', form)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleTestInDialog() {
  testing.value = true
  try {
    const res = await request.post('/datasources/test', form)
    testResult.value = res.data
    testResultVisible.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}

async function handleTest(row) {
  try {
    const res = await request.post(`/datasources/${row.id}/test`)
    testResult.value = res.data
    testResultVisible.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除数据源「${row.name}」？`, '确认', { type: 'warning' })
    await request.delete(`/datasources/${row.id}`)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}
</script>

<style scoped>
.test-ok, .test-fail {
  padding: 8px 0;
}
</style>