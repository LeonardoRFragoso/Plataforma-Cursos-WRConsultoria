import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getHomeRoute } from '../utils/homeRoute'

export const routes = [
  // ──────────────────────────────────────────────────────────────
  // PUBLIC LAYOUT — centered, marketing-friendly, no app shell.
  // ──────────────────────────────────────────────────────────────
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/seja-parceiro',
    name: 'Partner',
    component: () => import('../views/Partner.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/validar-certificado',
    name: 'ValidateCertificate',
    component: () => import('../views/ValidateCertificate.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/recuperar-senha',
    name: 'ForgotPassword',
    component: () => import('../views/ForgotPassword.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/redefinir-senha',
    name: 'ResetPassword',
    component: () => import('../views/ResetPassword.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/cursos/:id',
    name: 'CourseDetail',
    component: () => import('../views/CourseDetail.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/cursos',
    name: 'CourseCatalog',
    component: () => import('../views/CourseCatalog.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('../views/Forbidden.vue'),
    meta: { layout: 'public' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
    meta: { layout: 'public' },
  },

  // ──────────────────────────────────────────────────────────────
  // AUTHENTICATED LAYOUT — persistent AppShell (sidebar + topbar +
  // full-width workspace).
  // ──────────────────────────────────────────────────────────────
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true, layout: 'authenticated' },
  },
  {
    path: '/courses',
    name: 'Courses',
    component: () => import('../views/Courses.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/courses/:id/learn',
    name: 'CourseLearn',
    component: () => import('../views/CourseLearn.vue'),
    meta: { requiresAuth: true, layout: 'authenticated' },
  },
  {
    path: '/courses/:id/lessons',
    name: 'CourseLessons',
    component: () => import('../views/CourseLessons.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/courses/:id/progress',
    name: 'CourseProgress',
    component: () => import('../views/CourseProgress.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/classes',
    name: 'Classes',
    component: () => import('../views/Classes.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/companies',
    name: 'Companies',
    component: () => import('../views/Companies.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/companies/:id',
    name: 'CompanyDetail',
    component: () => import('../views/CompanyDetail.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/students',
    name: 'Students',
    component: () => import('../views/Students.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/students/:id',
    name: 'StudentDetail',
    component: () => import('../views/StudentDetail.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/enrollments',
    name: 'Enrollments',
    component: () => import('../views/Enrollments.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/payments',
    name: 'Payments',
    component: () => import('../views/Payments.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/certificates',
    name: 'Certificates',
    component: () => import('../views/Certificates.vue'),
    meta: { requiresAuth: true, layout: 'authenticated' },
  },
  {
    path: '/settings/white-label',
    name: 'WhiteLabelSettings',
    component: () => import('../views/WhiteLabelSettings.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/super-admin',
    name: 'SuperAdmin',
    component: () => import('../views/SuperAdmin.vue'),
    meta: { requiresAuth: true, requiresSuperAdmin: true, layout: 'authenticated' },
  },
  {
    path: '/demo/payment/:paymentId',
    name: 'DemoPayment',
    component: () => import('../views/DemoPayment.vue'),
    meta: { requiresAuth: true, layout: 'authenticated' },
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
    return { path: getHomeRoute(authStore) }
  }

  if (to.meta.requiresSuperAdmin && userRole !== 'super_admin') {
    return { path: getHomeRoute(authStore) }
  }

  return true
}

router.beforeEach(navigationGuard)

export default router
