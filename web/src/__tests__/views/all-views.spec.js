import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

import Certificates from '../../views/Certificates.vue'
import Classes from '../../views/Classes.vue'
import ComplianceOperations from '../../views/ComplianceOperations.vue'
import CourseDetail from '../../views/CourseDetail.vue'
import CourseLearn from '../../views/CourseLearn.vue'
import CourseLessons from '../../views/CourseLessons.vue'
import Courses from '../../views/Courses.vue'
import Dashboard from '../../views/Dashboard.vue'
import Enrollments from '../../views/Enrollments.vue'
import Forbidden from '../../views/Forbidden.vue'
import Home from '../../views/Home.vue'
import Login from '../../views/Login.vue'
import NotFound from '../../views/NotFound.vue'
import Payments from '../../views/Payments.vue'
import Register from '../../views/Register.vue'
import Students from '../../views/Students.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn((url) => {
      if (url.includes('/watch-url')) return Promise.resolve({ data: { watch_url: 'http://watch' } })
      if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 0 } })
      if (url.includes('/courses/') && !url.includes('/lessons') && !url.includes('/learn')) {
        return Promise.resolve({ data: { id: '123', title: 'Curso' } })
      }
      return Promise.resolve({ data: [] })
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

const cases = [
  ['Certificates', Certificates, '/certificates'],
  ['Classes', Classes, '/classes'],
  ['ComplianceOperations', ComplianceOperations, '/operations/compliance'],
  ['CourseDetail', CourseDetail, '/courses/123'],
  ['CourseLearn', CourseLearn, '/courses/123/learn'],
  ['CourseLessons', CourseLessons, '/courses/123/lessons'],
  ['Courses', Courses, '/courses'],
  ['Dashboard', Dashboard, '/dashboard'],
  ['Enrollments', Enrollments, '/enrollments'],
  ['Forbidden', Forbidden, '/403'],
  ['Home', Home, '/'],
  ['Login', Login, '/login'],
  ['NotFound', NotFound, '/not-found'],
  ['Payments', Payments, '/payments'],
  ['Register', Register, '/register'],
  ['Students', Students, '/students'],
]

describe('Views render', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.userRole = 'admin'
    authStore.user = { id: '1', full_name: 'Admin', role: 'admin' }
  })

  it.each(cases)('mounts %s', async (name, component, route) => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>home</div>' } },
        { path: '/dashboard', component: { template: '<div>dash</div>' } },
        { path: '/courses', component: { template: '<div>courses</div>' } },
        { path: '/courses/:id', component: { template: '<div>detail</div>' } },
        { path: '/courses/:id/learn', component: { template: '<div>learn</div>' } },
        { path: '/courses/:id/lessons', component: { template: '<div>lessons</div>' } },
        { path: '/courses/:id/progress', component: { template: '<div>progress</div>' } },
        { path: '/cursos', component: { template: '<div>catalog</div>' } },
        { path: '/cursos/:id', component: { template: '<div>catalog-detail</div>' } },
        { path: '/certificates', component: { template: '<div>certificates</div>' } },
        { path: '/classes', component: { template: '<div>classes</div>' } },
        { path: '/enrollments', component: { template: '<div>enrollments</div>' } },
        { path: '/operations/compliance', component: { template: '<div>compliance</div>' } },
        { path: '/payments', component: { template: '<div>payments</div>' } },
        { path: '/students', component: { template: '<div>students</div>' } },
        { path: '/settings/white-label', component: { template: '<div>wl</div>' } },
        { path: '/super-admin', component: { template: '<div>sa</div>' } },
        { path: '/login', component: { template: '<div>login</div>' } },
        { path: '/register', component: { template: '<div>register</div>' } },
        { path: '/validar-certificado', component: { template: '<div>validate</div>' } },
        { path: '/seja-parceiro', component: { template: '<div>partner</div>' } },
        { path: '/recuperar-senha', component: { template: '<div>forgot</div>' } },
        { path: '/redefinir-senha', component: { template: '<div>reset</div>' } },
        { path: '/403', component: { template: '<div>forbidden</div>' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div>not-found</div>' } },
      ],
    })
    await router.push(route)
    await router.isReady()

    const wrapper = mount(component, {
      global: {
        plugins: [createPinia(), router],
      },
    })

    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })
})
