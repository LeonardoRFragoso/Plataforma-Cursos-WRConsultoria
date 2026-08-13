import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || null)
  const refreshToken = ref(localStorage.getItem('refresh_token') || null)
  const user = ref(null)
  const userRole = ref(null)
  const initialized = ref(false)
  const initPromise = ref(null)

  const isAuthenticated = computed(() => !!token.value)

  const login = async (identifier, password) => {
    const response = await api.post('/api/v1/auth/login', { identifier, password })
    token.value = response.data.access_token
    refreshToken.value = response.data.refresh_token
    localStorage.setItem('access_token', token.value)
    localStorage.setItem('refresh_token', refreshToken.value)
    
    const meResponse = await api.get('/api/v1/auth/me')
    user.value = meResponse.data
    userRole.value = meResponse.data.role
    localStorage.setItem('user_role', userRole.value)
  }

  const register = async (email, fullName, password) => {
    await api.post('/api/v1/auth/register', {
      email,
      full_name: fullName,
      password,
    })
  }

  const logout = () => {
    token.value = null
    refreshToken.value = null
    user.value = null
    userRole.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_role')
  }

  const refreshAccessToken = async () => {
    if (!refreshToken.value) return
    
    try {
      const response = await api.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken.value,
      })
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      localStorage.setItem('access_token', token.value)
      localStorage.setItem('refresh_token', refreshToken.value)
    } catch (error) {
      logout()
      throw error
    }
  }

  const initializeUser = async () => {
    if (initPromise.value) return initPromise.value
    if (!token.value) {
      initialized.value = true
      return
    }

    initPromise.value = (async () => {
      try {
        const meResponse = await api.get('/api/v1/auth/me')
        user.value = meResponse.data
        userRole.value = meResponse.data.role
        localStorage.setItem('user_role', userRole.value)
        console.log('✓ User initialized from backend:', {
          role: userRole.value,
          name: user.value?.full_name,
          email: user.value?.email
        })
      } catch (error) {
        console.error('✗ Failed to initialize user:', error)
      } finally {
        initialized.value = true
      }
    })()

    return initPromise.value
  }

  return {
    token,
    refreshToken,
    user,
    userRole,
    initialized,
    isAuthenticated,
    login,
    register,
    logout,
    refreshAccessToken,
    initializeUser,
  }
})
