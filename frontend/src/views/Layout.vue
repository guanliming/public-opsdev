<template>
  <el-container style="height: 100vh">
    <el-header style="display: flex; align-items: center; justify-content: space-between; background: #001529; color: #fff;">
      <h3 style="margin: 0; color: #fff;">OpsDevOps</h3>
      <div style="display: flex; align-items: center; gap: 16px;">
        <span>{{ userStore.username }}</span>
        <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #fff; border-right: 1px solid #e8e8e8;">
        <el-menu :default-active="route.path" router>
          <el-menu-item index="/projects">
            <el-icon><Folder /></el-icon>
            <span>项目配置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
import { Folder } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>
