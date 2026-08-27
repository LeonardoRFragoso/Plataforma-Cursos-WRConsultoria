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
    const routes = flat.map((l) => l.to)
    expect(new Set(routes).size).toBe(routes.length)
    expect(routes).not.toContain('/operations/certificate-studio')
  })

  it('admin gets Dashboard/Central Operacional flat + operational groups', () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'admin'
    const { navItems } = useNavConfig()

    expect(navItems.value.flat.map((l) => l.to)).toEqual([
      '/dashboard',
      '/operations',
    ])

    const labels = navItems.value.groups.map((g) => g.label)
    expect(labels).toEqual([
      'Gestão',
      'Operações',
      'Certificados',
      'Configurações',
    ])

    const management = navItems.value.groups.find((g) => g.testid === 'management')
    expect(management.items.map((i) => i.to)).toEqual([
      '/courses',
      '/classes',
      '/companies',
      '/students',
      '/enrollments',
      '/payments',
    ])

    const operations = navItems.value.groups.find((g) => g.testid === 'operations-group')
    expect(operations.items.map((i) => i.to)).toEqual([
      '/operations/corporate',
      '/operations/finance',
      '/operations/certificates',
    ])

    const certificates = navItems.value.groups.find((g) => g.testid === 'certificates-group')
    expect(certificates.items.map((i) => i.to)).toEqual([
      '/certificates',
      '/operations/certificate-studio',
    ])

    const config = navItems.value.groups.find((g) => g.testid === 'customization')
    expect(config.items.map((i) => i.to)).toEqual([
      '/settings/white-label',
      '/settings/financial',
    ])
  })

  it('admin sees Financeiro in Configurações — student does NOT', () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'admin'
    const { navItems: adminNav } = useNavConfig()
    const adminConfig = adminNav.value.groups.find((g) => g.testid === 'customization')
    expect(adminConfig.items.some((i) => i.to === '/settings/financial')).toBe(true)

    auth.userRole = 'student'
    const { navItems: studentNav } = useNavConfig()
    const allStudentLinks = [
      ...studentNav.value.flat.map((l) => l.to),
      ...studentNav.value.groups.flatMap((g) => g.items.map((i) => i.to)),
    ]
    expect(allStudentLinks).not.toContain('/settings/financial')
    expect(allStudentLinks).not.toContain('/operations/certificate-studio')
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
