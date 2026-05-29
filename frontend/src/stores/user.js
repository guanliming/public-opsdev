import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const role = ref(localStorage.getItem('role') || '')

  const isAdmin = computed(() => role.value === 'admin')

  function setToken(t, user, userRole) {
    token.value = t
    username.value = user
    role.value = userRole || ''
    localStorage.setItem('token', t)
    localStorage.setItem('username', user)
    localStorage.setItem('role', userRole || '')
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isAdmin, setToken, logout }
})
