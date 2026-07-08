import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('../views/Layout.vue'),
    redirect: '/portal',
    children: [
      {
        path: 'portal',
        name: 'Portal',
        component: () => import('../views/Portal.vue'),
      },
      {
        path: 'app-logs',
        name: 'AppLogs',
        component: () => import('../views/AppLogs.vue'),
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('../views/Projects.vue'),
      },
      {
        path: 'deploy-logs',
        name: 'DeployLogs',
        component: () => import('../views/DeployLogs.vue'),
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/Users.vue'),
      },
      {
        path: 'menu-manage',
        name: 'MenuManage',
        component: () => import('../views/MenuManage.vue'),
      },
{
        path: 'vm-manage',
        name: 'VmManage',
        component: () => import('../views/VmManage.vue'),
      },
      {
        path: 'datasources',
        name: 'DataSources',
        component: () => import('../views/DataSources.vue'),
      },
      {
        path: 'sql-console',
        name: 'SqlConsole',
        component: () => import('../views/SqlConsole.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (to.name !== 'Login' && !userStore.token) {
    return { name: 'Login' }
  }
})

export default router
