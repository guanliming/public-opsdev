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
    redirect: '/projects',
    children: [
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
