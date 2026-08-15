import api from './client'

export async function fetchTenantBranding(slug = 'wr') {
  const { data } = await api.get(`/api/v1/tenants/branding?slug=${slug}`)
  return data
}
