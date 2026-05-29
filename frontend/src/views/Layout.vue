<template>
  <el-container style="height: 100vh">
    <el-header style="display: flex; align-items: center; justify-content: space-between; background: #001529; color: #fff;">
      <h3 style="margin: 0; color: #fff;">DevOps</h3>
      <div style="display: flex; align-items: center; gap: 16px;">
        <el-dropdown @command="handleCommand">
          <span style="color: #fff; cursor: pointer; display: flex; align-items: center; gap: 4px;">
            {{ userStore.username }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-container>
      <el-aside :width="collapsed ? '64px' : '200px'" style="background: #fff; border-right: 1px solid #e8e8e8; transition: width 0.3s;">
        <el-menu :default-active="route.path" router :collapse="collapsed">
          <el-menu-item index="/portal">
            <el-icon><HomeFilled /></el-icon>
            <template #title>首页</template>
          </el-menu-item>
          <el-menu-item index="/app-logs">
            <el-icon><Monitor /></el-icon>
            <template #title>应用日志</template>
          </el-menu-item>
          <el-menu-item index="/projects">
            <el-icon><Folder /></el-icon>
            <template #title>项目配置</template>
          </el-menu-item>
          <el-menu-item index="/deploy-logs">
            <el-icon><Document /></el-icon>
            <template #title>部署日志</template>
          </el-menu-item>
          <el-menu-item v-if="userStore.isAdmin" index="/users">
            <el-icon><UserIcon /></el-icon>
            <template #title>用户管理</template>
          </el-menu-item>
          <el-menu-item v-if="userStore.isAdmin" index="/vm-manage">
            <el-icon><SetUp /></el-icon>
            <template #title>虚拟机管理</template>
          </el-menu-item>
          <el-menu-item v-if="userStore.isAdmin" index="/menu-manage">
            <el-icon><MenuIcon /></el-icon>
            <template #title>菜单管理</template>
          </el-menu-item>
        </el-menu>
        <div style="text-align: center; padding: 12px 0; cursor: pointer; border-top: 1px solid #e8e8e8;" @click="collapsed = !collapsed">
          <el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </div>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>

    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="400px">
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="80px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="handleChangePassword">确定</el-button>
      </template>
    </el-dialog>

    <!-- AI Diagnosis -->
    <AiFloatingBall ref="floatingBallRef" @open="diagnosisVisible = true" />
    <AiDiagnosisDrawer ref="diagnosisDrawerRef" v-model="diagnosisVisible" :projects="allProjects" />
  </el-container>
</template>

<script setup>
import { ref, reactive, provide, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Folder, Document, Monitor, Fold, Expand, ArrowDown, User as UserIcon, HomeFilled, Menu as MenuIcon, SetUp } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import request from '../utils/request'
import AiFloatingBall from '../components/AiFloatingBall.vue'
import AiDiagnosisDrawer from '../components/AiDiagnosisDrawer.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const collapsed = ref(false)

const diagnosisVisible = ref(false)
const floatingBallRef = ref(null)
const diagnosisDrawerRef = ref(null)
const allProjects = ref([])

function openDiagnosis(projectId, errorLog, extraContext) {
  diagnosisDrawerRef.value?.open(projectId, errorLog, extraContext)
}

function openChat(projectId) {
  diagnosisDrawerRef.value?.openChat(projectId)
}

provide('openDiagnosis', openDiagnosis)
provide('openChat', openChat)

async function loadAllProjects() {
  try {
    const { data } = await request.get('/projects')
    allProjects.value = data
  } catch {}
}

onMounted(loadAllProjects)

const passwordDialogVisible = ref(false)
const passwordLoading = ref(false)
const passwordFormRef = ref(null)
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const passwordRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 6, message: '密码至少6位', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: (_, value, callback) => {
      if (value !== passwordForm.new_password) callback(new Error('两次密码不一致'))
      else callback()
    }, trigger: 'blur' }
  ],
}

function handleCommand(command) {
  if (command === 'password') {
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    passwordDialogVisible.value = true
  } else if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}

async function handleChangePassword() {
  await passwordFormRef.value.validate()
  passwordLoading.value = true
  try {
    await request.put('/auth/password', {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success('密码修改成功')
    passwordDialogVisible.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  } finally {
    passwordLoading.value = false
  }
}
</script>
