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
      <el-aside :width="collapsed ? '64px' : '200px'" style="background: #fff; border-right: 1px solid #e8e8e8; transition: width 0.3s;">
        <el-menu :default-active="route.path" router :collapse="collapsed">
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
        </el-menu>
        <div style="text-align: center; padding: 12px 0; cursor: pointer; border-top: 1px solid #e8e8e8;" @click="collapsed = !collapsed">
          <el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </div>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Folder, Document, Monitor, Fold, Expand } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const collapsed = ref(false)

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>
