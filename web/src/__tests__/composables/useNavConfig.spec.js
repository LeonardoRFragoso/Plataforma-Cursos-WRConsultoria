import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { useNavConfig } from '../../composables/useNavConfig'

describe('useNavConfig', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('student gets Dashboard, Catálogo, Certificados — no admin links, no duplication', () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    const { navItems } = useNavConfig()
    const flat = navItems.value.flat
    expect(flat.map((l) => l.to)).toEqual(['/dashboard', '/cursos', '/certificates'])
    expect(navItems.value.groups).toEqual([])
    // No duplicate routes
    const routes = flat.map((l) => l.to)
    expect(new Set(routes).size).toBe(routes.length)
  })

  it('admin gets Dashboard flat + Gestão/Certificados/Personalização groups', () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'admin'
    const { navItems } = useNavConfig()
    expect(navItems.value.flat.map((l) => l.to)).toEqual(['/dashboard'])
    const labels = navItems.value.groups.map((g) => g.label)
    expect(labels).toEqual(['Gestão', 'Certificados', 'Personalização'])
    const management = navItems.value.groups.find((g) => g.testid === 'management')
    expect(management.items.map((i) => i.to)).toEqual([
      '/courses',
      '/classes',
      '/companies',
      '/students',
      '/enrollments',
      '/payments',
    ])
  })

  it('super_admin gets Gestão Global only — no tenant-admin groups', () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'super_admin'
    const { navItems } = useNavConfig()
    expect(navItems.value.flat.map((l) => l.to)).toEqual(['/super-admin'])
    expect(navItems.value.groups).toEqual([])
  })

  it('unknown role yields empty nav', () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null
    const { navItems } = useNavConfig()
    expect(navItems.value.flat).toEqual([])
    expect(navItems.value.groups).toEqual([])
  })
})
