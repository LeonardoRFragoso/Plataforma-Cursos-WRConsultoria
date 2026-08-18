import api from './client'

// Plans
export async function listPlans() {
  const { data } = await api.get('/api/v1/super-admin/plans')
  return data
}

export async function createPlan(payload) {
  const { data } = await api.post('/api/v1/super-admin/plans', payload)
  return data
}

// Subscriptions
export async function listSubscriptions() {
  const { data } = await api.get('/api/v1/super-admin/subscriptions')
  return data
}

export async function createSubscription(payload) {
  const { data } = await api.post('/api/v1/super-admin/subscriptions', payload)
  return data
}

export async function activateSubscription(id) {
  const { data } = await api.post(`/api/v1/super-admin/subscriptions/${id}/activate`)
  return data
}

export async function suspendSubscription(id) {
  const { data } = await api.post(`/api/v1/super-admin/subscriptions/${id}/suspend`)
  return data
}

export async function cancelSubscription(id) {
  const { data } = await api.post(`/api/v1/super-admin/subscriptions/${id}/cancel`)
  return data
}

export async function renewSubscription(id) {
  const { data } = await api.post(`/api/v1/super-admin/subscriptions/${id}/renew`)
  return data
}

// Partner leads
export async function listPartnerLeads() {
  const { data } = await api.get('/api/v1/partner-leads')
  return data
}

export async function approvePartnerLead(id) {
  const { data } = await api.post(`/api/v1/partner-leads/${id}/approve`)
  return data
}

// Tenants (list all — via privileged session)
export async function listTenants() {
  const { data } = await api.get('/api/v1/super-admin/tenants')
  return data
}
