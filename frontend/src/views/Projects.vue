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
<el-table-column prop="build_type" label="打包类型" width="100">
        <template #default="{ row }">
          <el-tag :type="buildTypeTagType(row.build_type)" size="small">
            {{ buildTypeLabel(row.build_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="log_path" label="应用日志路径" width="160" />
      <el-table-column prop="env_info" label="环境信息" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="handleDeploy(row)">部署</el-button>
          <el-button size="small" type="warning" @click="goToLogs(row)">日志</el-button>
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目' : '新增项目'" width="750px">
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
<el-form-item label="打包类型" prop="build_type">
          <el-radio-group v-model="form.build_type">
            <el-radio value="jar">JAR (Maven)</el-radio>
            <el-radio value="docker">Docker (自定义构建脚本)</el-radio>
            <el-radio value="npm">NPM (Node 构建)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.build_type === 'docker' || form.build_type === 'npm'" label="构建脚本" prop="build_script">
          <el-input v-model="form.build_script" :placeholder="form.build_type === 'npm' ? '留空则执行: npm ci && npm run build' : '/opt/scripts/build.sh'" />
        </el-form-item>
        <el-form-item label="应用日志路径" prop="log_path">
          <el-input v-model="form.log_path" placeholder="/var/log/app.log" />
        </el-form-item>
        <el-form-item label="环境信息" prop="env_info">
          <el-input v-model="form.env_info" type="textarea" :rows="3" placeholder="如：Go 1.21 / Gin / PostgreSQL 15 / Redis 7 / Ubuntu 22.04" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 部署实时日志弹窗 -->
    <el-dialog v-model="deployDialogVisible" title="部署日志" width="700px" :close-on-click-modal="false">
      <div style="margin-bottom: 8px;">
        <el-tag :type="deployStatusType">{{ deployStatusText }}</el-tag>
        <span style="margin-left: 12px; color: #666;">{{ deployingProject }}</span>
      </div>
      <div ref="logContainer" style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px; height: 400px; overflow-y: auto; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all;">{{ deployLogContent }}</div>
      <template #footer>
        <el-button @click="deployDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const projects = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const deployDialogVisible = ref(false)
const deployLogContent = ref('')
const deployStatus = ref('')
const deployingProject = ref('')
const logContainer = ref(null)

const deployStatusType = computed(() => {
  if (deployStatus.value === 'running') return 'warning'
  if (deployStatus.value === 'success') return 'success'
  if (deployStatus.value === 'failed') return 'danger'
  return 'info'
})

function buildTypeLabel(t) {
  if (t === 'docker') return 'Docker'
  if (t === 'npm') return 'NPM'
  return 'JAR'
}

function buildTypeTagType(t) {
  if (t === 'docker') return 'warning'
  if (t === 'npm') return 'success'
  return ''
}

const deployStatusText = computed(() => {
  if (deployStatus.value === 'running') return '部署中...'
  if (deployStatus.value === 'success') return '部署成功'
  if (deployStatus.value === 'failed') return '部署失败'
  return '未知'
})

const form = reactive({
  name: '',
  ssh_url: '',
  branch: 'main',
  root_dir: '/repo/',
  deploy_script: './deploy.sh',
  log_path: '/var/log/',
  env_info: '',
  build_type: 'jar',
  build_script: '',
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
    Object.assign(form, { name: row.name, ssh_url: row.ssh_url, branch: row.branch, root_dir: row.root_dir, deploy_script: row.deploy_script, log_path: row.log_path, env_info: row.env_info || '', build_type: row.build_type || 'jar', build_script: row.build_script || '' })
  } else {
    isEdit.value = false
    editingId.value = null
    Object.assign(form, { name: '', ssh_url: '', branch: 'main', root_dir: '/repo/', deploy_script: './deploy.sh', log_path: '/var/log/', env_info: '', build_type: 'jar', build_script: '' })
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

function goToLogs(row) {
  router.push({ path: '/app-logs', query: { project: row.id } })
}

async function handleDeploy(row) {
  await ElMessageBox.confirm(`确定部署项目「${row.name}」（分支: ${row.branch}）？`, '确认部署', { type: 'warning' })

  deployLogContent.value = ''
  deployStatus.value = 'running'
  deployingProject.value = row.name
  deployDialogVisible.value = true

  try {
    const { data } = await request.post(`/projects/${row.id}/deploy`)
    const logId = data.id

    const token = userStore.token
    const evtSource = new EventSource(`/api/deploy-logs/${logId}/stream?token=${token}`)

    evtSource.onmessage = (event) => {
      deployLogContent.value += event.data.replace(/\\n/g, '\n') + '\n'
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
    }

    evtSource.addEventListener('done', (event) => {
      deployStatus.value = event.data
      evtSource.close()
    })

    evtSource.onerror = () => {
      if (deployStatus.value === 'running') {
        deployStatus.value = 'failed'
      }
      evtSource.close()
    }
  } catch (e) {
    deployStatus.value = 'failed'
    deployLogContent.value = e.response?.data?.detail || '部署请求失败'
  }
}

onMounted(loadProjects)
</script>
