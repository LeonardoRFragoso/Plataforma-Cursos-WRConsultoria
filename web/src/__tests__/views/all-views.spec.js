import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

import Certificates from '../../views/Certificates.vue'
import Classes from '../../views/Classes.vue'
import CourseDetail from '../../views/CourseDetail.vue'
import CourseLearn from '../../views/CourseLearn.vue'
import CourseLessons from '../../views/CourseLessons.vue'
import Courses from '../../views/Courses.vue'
import Dashboard from '../../views/Dashboard.vue'
import Enrollments from '../../views/Enrollments.vue'
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
  ['CourseDetail', CourseDetail, '/courses/123'],
  ['CourseLearn', CourseLearn, '/courses/123/learn'],
  ['CourseLessons', CourseLessons, '/courses/123/lessons'],
  ['Courses', Courses, '/courses'],
  ['Dashboard', Dashboard, '/dashboard'],
  ['Enrollments', Enrollments, '/enrollments'],
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
        { path: '/courses', component: { template: '<div>courses</div>' } },
        { path: '/courses/:id', component: { template: '<div>detail</div>' } },
        { path: '/courses/:id/learn', component: { template: '<div>learn</div>' } },
        { path: '/courses/:id/lessons', component: { template: '<div>lessons</div>' } },
        { path: '/certificates', component: { template: '<div>certificates</div>' } },
        { path: '/classes', component: { template: '<div>classes</div>' } },
        { path: '/enrollments', component: { template: '<div>enrollments</div>' } },
        { path: '/payments', component: { template: '<div>payments</div>' } },
        { path: '/students', component: { template: '<div>students</div>' } },
        { path: '/login', component: { template: '<div>login</div>' } },
        { path: '/register', component: { template: '<div>register</div>' } },
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
