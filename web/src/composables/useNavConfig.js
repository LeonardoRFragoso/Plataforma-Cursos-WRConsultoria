import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

export function useNavConfig() {
  const authStore = useAuthStore()
  const role = computed(() => authStore.userRole?.toLowerCase())
  const navItems = computed(() => {
    if (role.value === 'student') return { flat: [
      { to: '/dashboard', label: 'Dashboard', testid: 'dashboard', icon: 'home' },
      { to: '/cursos', label: 'Catálogo', testid: 'catalog', icon: 'catalog' },
      { to: '/certificates', label: 'Certificados', testid: 'certificates', icon: 'cert' },
    ], groups: [] }
    if (role.value === 'admin') return {
      flat: [
        { to: '/dashboard', label: 'Dashboard', testid: 'dashboard', icon: 'home' },
        { to: '/operations', label: 'Central operacional', testid: 'operations', icon: 'pulse' },
      ],
      groups: [
        { label: 'Gestão', testid: 'management', icon: 'layers', items: [
          { to: '/courses', label: 'Cursos', testid: 'courses', icon: 'catalog' },
          { to: '/classes', label: 'Turmas', testid: 'classes', icon: 'calendar' },
          { to: '/companies', label: 'Empresas', testid: 'companies', icon: 'building' },
          { to: '/students', label: 'Alunos', testid: 'students', icon: 'users' },
          { to: '/enrollments', label: 'Matrículas', testid: 'enrollments', icon: 'clipboard' },
          { to: '/payments', label: 'Pagamentos', testid: 'payments', icon: 'card' },
        ]},
        { label: 'Operações', testid: 'operations-group', icon: 'pulse', items: [
          { to: '/operations/corporate', label: 'Corporativo B2B', testid: 'corporate-operations', icon: 'briefcase' },
          { to: '/operations/finance', label: 'Reconciliação financeira', testid: 'financial-reconciliation', icon: 'chart' },
          { to: '/operations/certificates', label: 'Certificados confiáveis', testid: 'certificate-operations', icon: 'shield' },
        ]},
        { label: 'Certificados', testid: 'certificates-group', icon: 'cert', items: [
          { to: '/certificates', label: 'Certificados', testid: 'certificates', icon: 'cert' },
        ]},
        { label: 'Configurações', testid: 'customization', icon: 'settings', items: [
          { to: '/settings/white-label', label: 'White Label', testid: 'white-label', icon: 'palette' },
          { to: '/settings/financial', label: 'Financeiro', testid: 'financial-settings', icon: 'card' },
        ]},
      ],
    }
    if (role.value === 'super_admin') return { flat: [
      { to: '/super-admin', label: 'Gestão Global', testid: 'super-admin', icon: 'globe' },
    ], groups: [] }
    return { flat: [], groups: [] }
  })
  return { navItems, role }
}
