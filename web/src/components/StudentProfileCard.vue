<template>
  <div
    class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    data-testid="student-profile-card"
  >
    <div class="flex items-center gap-4">
      <!-- Avatar with initials -->
      <div
        class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-lg font-bold text-white"
        :style="avatarStyle"
        aria-hidden="true"
      >
        {{ initials }}
      </div>
      <div class="min-w-0 flex-1">
        <p class="font-semibold text-secondary-900 truncate">
          {{ user?.full_name || '—' }}
        </p>
        <p class="text-sm text-gray-500 truncate">{{ user?.email || '' }}</p>
        <p class="mt-1">
          <StatusBadge
            status="CONFIRMADA"
            :custom-map="{ CONFIRMADA: { label: roleLabel, class: 'bg-primary-50 text-primary-700', dot: 'bg-primary-500' } }"
            test-id="profile-role-badge"
          />
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useTenantStore } from '../stores/tenant'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({
  user: { type: Object, default: () => ({}) },
  role: { type: String, default: 'student' },
})

const tenantStore = useTenantStore()

const roleMap = {
  admin: 'Administrador',
  student: 'Aluno',
  super_admin: 'Super Administrador',
}
const roleLabel = computed(
  () => roleMap[props.role?.toLowerCase()] || props.role || '—'
)

const initials = computed(() => {
  const name = props.user?.full_name || ''
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
})

const avatarStyle = computed(() => {
  const primary = tenantStore.primary_color || '#0056b3'
  const secondary = tenantStore.secondary_color || '#1a1a1a'
  return { background: `linear-gradient(135deg, ${primary}, ${secondary})` }
})
</script>
