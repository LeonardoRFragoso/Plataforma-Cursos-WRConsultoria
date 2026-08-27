import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { TENANT_SLUG } from '../utils/tenantSlug'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// A single timeout covers all requests. Without it, a slow or unresponsive
// backend leaves the UI hanging indefinitely (the root cause of the prolonged
// white screen when /auth/me never returned). 15s is generous enough for a
// cold-start backend yet short enough that the user gets feedback instead of
// an infinite blank page.
const REQUEST_TIMEOUT = 15000

// Public routes that must never redirect to /login when a stale session is
// cleared. A visitor on / or /cursos with an expired token should see the
// public page, not be bounced to login.
const PUBLIC_PATHS = new Set([
  '/', '/login', '/register', '/recuperar-senha', '/redefinir-senha',
  '/ativar-conta', '/validar-certificado', '/cursos', '/seja-parceiro',
  '/treinamentos-para-empresas', '/403',
])
const isPublicPath = (path) =>
  PUBLIC_PATHS.has(path) || path.startsWith('/cursos/') || path.startsWith('/validar-certificado')

const api = axios.create({
  baseURL: API_URL,
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
    'X-Tenant-Slug': TENANT_SLUG,
  },
})

api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const authStore = useAuthStore()

    // Only attempt a token refresh on a 401 from a non-refresh request, and
    // only once per request (_retry guard). The /auth/refresh endpoint itself
    // must never trigger a recursive refresh — if refresh fails we log out.
    const isRefreshCall = originalRequest?.url?.includes('/auth/refresh')
    if (error.response?.status === 401 && !originalRequest?._retry && !isRefreshCall) {
      originalRequest._retry = true
      try {
        await authStore.refreshAccessToken()
        originalRequest.headers.Authorization = `Bearer ${authStore.token}`
        return api(originalRequest)
      } catch (refreshError) {
        authStore.logout()
        // Only redirect to /login when the user is on a protected page. On a
        // public page a stale token is silently cleared so the visitor keeps
        // seeing the public content.
        if (!isPublicPath(window.location.pathname)) {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default api
