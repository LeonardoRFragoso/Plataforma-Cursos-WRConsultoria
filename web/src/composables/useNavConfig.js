import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

/**
 * Role-aware navigation configuration for the authenticated application shell.
 *
 * Single source of truth for the sidebar navigation tree. Returns a structure
 * of flat links plus collapsible groups, mirroring the information architecture
 * defined for ADMIN / STUDENT / SUPER_ADMIN.
 *
 *   ADMIN:
 *     Dashboard
 *     Gestão        → Cursos, Turmas, Alunos, Matrículas, Pagamentos
 *     Certificados  → Certificados
 *     Personalização→ White Label
 *
 *   STUDENT:
 *     Dashboard
 *     Catálogo
 *     Certificados
 *
 *   SUPER_ADMIN:
 *     Gestão Global
 */
export function useNavConfig() {
  const authStore = useAuthStore()

  const role = computed(() => authStore.userRole?.toLowerCase())

  const navItems = computed(() => {
    if (role.value === 'student') {
      return {
        flat: [
          { to: '/dashboard', label: 'Dashboard', testid: 'dashboard', icon: 'home' },
          { to: '/cursos', label: 'Catálogo', testid: 'catalog', icon: 'catalog' },
          { to: '/certificates', label: 'Certificados', testid: 'certificates', icon: 'cert' },
        ],
        groups: [],
      }
    }

    if (role.value === 'admin') {
      return {
        flat: [
          { to: '/dashboard', label: 'Dashboard', testid: 'dashboard' },
        ],
        groups: [
          {
            label: 'Gestão',
            testid: 'management',
            items: [
              { to: '/courses', label: 'Cursos', testid: 'courses' },
              { to: '/classes', label: 'Turmas', testid: 'classes' },
              { to: '/companies', label: 'Empresas', testid: 'companies' },
              { to: '/students', label: 'Alunos', testid: 'students' },
              { to: '/enrollments', label: 'Matrículas', testid: 'enrollments' },
              { to: '/payments', label: 'Pagamentos', testid: 'payments' },
            ],
          },
          {
            label: 'Certificados',
            testid: 'certificates-group',
            items: [
              { to: '/certificates', label: 'Certificados', testid: 'certificates' },
            ],
          },
          {
            label: 'Personalização',
            testid: 'customization',
            items: [
              { to: '/settings/white-label', label: 'White Label', testid: 'white-label' },
            ],
          },
        ],
      }
    }

    if (role.value === 'super_admin') {
      return {
        flat: [
          { to: '/super-admin', label: 'Gestão Global', testid: 'super-admin' },
        ],
        groups: [],
      }
    }

    return { flat: [], groups: [] }
  })

  return { navItems, role }
}
