import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

export const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
  },
  {
    path: '/seja-parceiro',
    name: 'Partner',
    component: () => import('../views/Partner.vue'),
  },
  {
    path: '/validar-certificado',
    name: 'ValidateCertificate',
    component: () => import('../views/ValidateCertificate.vue'),
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/courses',
    name: 'Courses',
    component: () => import('../views/Courses.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/cursos/:id',
    name: 'CourseDetail',
    component: () => import('../views/CourseDetail.vue'),
  },
  {
    path: '/cursos',
    name: 'CourseCatalog',
    component: () => import('../views/Home.vue'),
  },
  {
    path: '/courses/:id/learn',
    name: 'CourseLearn',
    component: () => import('../views/CourseLearn.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/courses/:id/lessons',
    name: 'CourseLessons',
    component: () => import('../views/CourseLessons.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/classes',
    name: 'Classes',
    component: () => import('../views/Classes.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/students',
    name: 'Students',
    component: () => import('../views/Students.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/enrollments',
    name: 'Enrollments',
    component: () => import('../views/Enrollments.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/payments',
    name: 'Payments',
    component: () => import('../views/Payments.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/certificates',
    name: 'Certificates',
    component: () => import('../views/Certificates.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings/white-label',
    name: 'WhiteLabelSettings',
    component: () => import('../views/WhiteLabelSettings.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/super-admin',
    name: 'SuperAdmin',
    component: () => import('../views/SuperAdmin.vue'),
    meta: { requiresAuth: true, requiresSuperAdmin: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export async function navigationGuard(to) {
  const authStore = useAuthStore()

  if (authStore.token && !authStore.initialized) {
    await authStore.initializeUser()
  }

  const userRole = authStore.userRole?.toLowerCase()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { path: '/login' }
  }

  if (to.meta.requiresAdmin && userRole !== 'admin' && userRole !== 'super_admin') {
    return { path: '/dashboard' }
  }

  if (to.meta.requiresSuperAdmin && userRole !== 'super_admin') {
    return { path: '/dashboard' }
  }

  return true
}

router.beforeEach(navigationGuard)

export default router
