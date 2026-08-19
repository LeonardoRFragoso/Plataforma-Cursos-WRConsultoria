import api from './client'
import { TENANT_SLUG } from '../utils/tenantSlug'

export async function fetchTenantBranding(slug = TENANT_SLUG) {
  const { data } = await api.get(`/api/v1/tenants/branding`, { params: { slug } })
  return data
}

export async function updateTenantBranding(payload) {
  const { data } = await api.put('/api/v1/tenants/branding', payload)
  return data
}
