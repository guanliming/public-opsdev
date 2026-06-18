<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2 style="margin: 0; text-align: center;">DevOps</h2>
      </template>
      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" :disabled="locked" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            size="large"
            show-password
            :disabled="locked"
          />
        </el-form-item>
        <el-form-item prop="captcha_code">
          <div class="captcha-row">
            <el-input
              v-model="form.captcha_code"
              placeholder="验证码"
              prefix-icon="Picture"
              size="large"
              maxlength="6"
              :disabled="locked"
              @keyup.enter="handleLogin"
            />
            <div class="captcha-image" @click="refreshCaptcha" :title="'点击刷新验证码'">
              <img v-if="captchaImage" :src="captchaImage" alt="captcha" />
              <span v-else class="captcha-loading">加载中…</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="locked">
          <el-alert :title="lockMessage" type="error" :closable="false" show-icon />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            :disabled="locked"
            native-type="submit"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  captcha_token: '',
  captcha_code: '',
})

const captchaImage = ref('')
const locked = ref(false)
const lockedUntil = ref(null)
const remainingSeconds = ref(0)
let countdownTimer = null

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}

const lockMessage = computed(() => {
  if (!locked.value) return ''
  const mins = Math.max(1, Math.ceil(remainingSeconds.value / 60))
  return `账号已锁定,剩余 ${mins} 分钟后可重试`
})

async function refreshCaptcha() {
  try {
    const { data } = await request.get('/auth/captcha')
    form.captcha_token = data.captcha_token
    captchaImage.value = data.image
  } catch (e) {
    ElMessage.error('验证码加载失败')
  }
}

function startCountdown() {
  stopCountdown()
  if (!remainingSeconds.value || remainingSeconds.value <= 0) return
  countdownTimer = setInterval(() => {
    remainingSeconds.value -= 1
    if (remainingSeconds.value <= 0) {
      locked.value = false
      stopCountdown()
    }
  }, 1000)
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function applyLock(payload) {
  if (!payload) return
  locked.value = !!payload.locked
  lockedUntil.value = payload.locked_until || null
  remainingSeconds.value = payload.remaining_seconds || 0
  if (locked.value) {
    startCountdown()
  } else {
    stopCountdown()
  }
}

async function handleLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    const { data } = await request.post('/auth/login', { ...form })
    userStore.setToken(data.access_token, form.username, '')
    const { data: me } = await request.get('/auth/me')
    userStore.setToken(data.access_token, me.username, me.role)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    const detail = e.response?.data?.detail || '登录失败'
    if (e.response?.data?.lock) {
      applyLock(e.response.data.lock)
    }
    ElMessage.error(detail)
    await refreshCaptcha()
    form.captcha_code = ''
  } finally {
    loading.value = false
  }
}

onMounted(refreshCaptcha)
onUnmounted(stopCountdown)
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.login-card {
  width: 400px;
}
.captcha-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.captcha-row :deep(.el-input) {
  flex: 1;
}
.captcha-image {
  width: 140px;
  height: 40px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: #f5f7fa;
  overflow: hidden;
}
.captcha-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.captcha-loading {
  color: #909399;
  font-size: 12px;
}
</style>
