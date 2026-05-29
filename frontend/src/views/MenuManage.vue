<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h3 style="margin: 0;">菜单管理</h3>
      <el-button type="primary" @click="handleAdd">新增链接</el-button>
    </div>

    <el-table :data="links" v-loading="loading" border stripe>
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="url" label="链接地址" min-width="200" show-overflow-tooltip />
      <el-table-column prop="icon" label="图标" width="100" />
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑链接' : '新增链接'" width="480px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="链接名称" />
        </el-form-item>
        <el-form-item label="地址" prop="url">
          <el-input v-model="form.url" placeholder="https://example.com" />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="form.icon" placeholder="可选，Element Plus 图标名" />
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

const links = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  url: '',
  icon: '',
  sort_order: 0,
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入链接地址', trigger: 'blur' }],
}

onMounted(() => fetchLinks())

async function fetchLinks() {
  loading.value = true
  try {
    const res = await request.get('/portal/links')
    links.value = res.data
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function handleAdd() {
  editingId.value = null
  form.name = ''
  form.url = ''
  form.icon = ''
  form.sort_order = 0
  dialogVisible.value = true
}

function handleEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.url = row.url
  form.icon = row.icon || ''
  form.sort_order = row.sort_order
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value) {
      await request.put(`/portal/links/${editingId.value}`, form)
      ElMessage.success('更新成功')
    } else {
      await request.post('/portal/links', form)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    fetchLinks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除「${row.name}」？`, '确认删除', { type: 'warning' })
  try {
    await request.delete(`/portal/links/${row.id}`)
    ElMessage.success('删除成功')
    fetchLinks()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}
</script>
