<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
      <h3 style="margin: 0;">项目配置</h3>
      <el-button type="primary" @click="openDialog()">新增项目</el-button>
    </div>

    <el-table :data="projects" border stripe>
      <el-table-column prop="name" label="项目名称" width="150" />
      <el-table-column prop="ssh_url" label="SSH 地址" min-width="250" />
      <el-table-column prop="branch" label="部署分支" width="120" />
      <el-table-column prop="root_dir" label="项目根目录" width="140" />
      <el-table-column prop="deploy_script" label="部署脚本" width="160" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目' : '新增项目'" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="如：my-app" />
        </el-form-item>
        <el-form-item label="SSH 地址" prop="ssh_url">
          <el-input v-model="form.ssh_url" placeholder="git@github.com:org/repo.git" />
        </el-form-item>
        <el-form-item label="部署分支" prop="branch">
          <el-input v-model="form.branch" placeholder="main" />
        </el-form-item>
        <el-form-item label="项目根目录" prop="root_dir">
          <el-input v-model="form.root_dir" placeholder="/repo/" />
        </el-form-item>
        <el-form-item label="部署脚本" prop="deploy_script">
          <el-input v-model="form.deploy_script" placeholder="./deploy.sh" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const projects = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  ssh_url: '',
  branch: 'main',
  root_dir: '/repo/',
  deploy_script: './deploy.sh',
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  ssh_url: [{ required: true, message: '请输入 SSH 地址', trigger: 'blur' }],
  branch: [{ required: true, message: '请输入部署分支', trigger: 'blur' }],
}

async function loadProjects() {
  const { data } = await request.get('/projects')
  projects.value = data
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editingId.value = row.id
    Object.assign(form, { name: row.name, ssh_url: row.ssh_url, branch: row.branch, root_dir: row.root_dir, deploy_script: row.deploy_script })
  } else {
    isEdit.value = false
    editingId.value = null
    Object.assign(form, { name: '', ssh_url: '', branch: 'main', root_dir: '/repo/', deploy_script: './deploy.sh' })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (isEdit.value) {
      await request.put(`/projects/${editingId.value}`, form)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadProjects()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除项目「${row.name}」？`, '确认', { type: 'warning' })
  await request.delete(`/projects/${row.id}`)
  ElMessage.success('删除成功')
  await loadProjects()
}

onMounted(loadProjects)
</script>
