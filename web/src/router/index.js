import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
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
    path: '/courses/:id',
    name: 'CourseDetail',
    component: () => import('../views/CourseDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/classes',
    name: 'Classes',
    component: () => import('../views/Classes.vue'),
    meta: { requiresAuth: true, requiresInstructor: true },
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
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.meta.requiresAdmin && authStore.userRole !== 'admin') {
    next('/dashboard')
  } else if (to.meta.requiresInstructor && !['admin', 'instructor'].includes(authStore.userRole)) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
