<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h3 style="margin: 0;">虚拟机管理</h3>
      <el-button type="primary" @click="handleAdd">新增虚拟机</el-button>
    </div>

    <el-table :data="vms" v-loading="loading" border stripe>
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="host" label="地址" min-width="150" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑虚拟机' : '新增虚拟机'" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="虚拟机名称" />
        </el-form-item>
        <el-form-item label="地址" prop="host">
          <el-input v-model="form.host" placeholder="IP 或域名" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :placeholder="editingId ? '留空则不修改' : 'SSH 用户名'" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="editingId ? '留空则不修改' : 'SSH 密码'" />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="form.icon" placeholder="可选" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const vms = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  icon: '',
  sort_order: 0,
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
}

onMounted(() => fetchVms())

async function fetchVms() {
  loading.value = true
  try {
    const res = await request.get('/portal/vms')
    vms.value = res.data
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function handleAdd() {
  editingId.value = null
  form.name = ''
  form.host = ''
  form.port = 22
  form.username = ''
  form.password = ''
  form.icon = ''
  form.sort_order = 0
  dialogVisible.value = true
}

function handleEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.host = row.host
  form.port = row.port
  form.username = row.username
  form.password = ''
  form.icon = row.icon || ''
  form.sort_order = row.sort_order
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  if (!editingId.value) {
    if (!form.username || !form.password) {
      ElMessage.warning('新增时用户名和密码为必填')
      return
    }
  }
  saving.value = true
  try {
    const data = { ...form }
    if (editingId.value) {
      if (!data.username) delete data.username
      if (!data.password) delete data.password
    }
    if (editingId.value) {
      await request.put(`/portal/vms/${editingId.value}`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/portal/vms', data)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    fetchVms()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除「${row.name}」？`, '确认删除', { type: 'warning' })
  try {
    await request.delete(`/portal/vms/${row.id}`)
    ElMessage.success('删除成功')
    fetchVms()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}
</script>
