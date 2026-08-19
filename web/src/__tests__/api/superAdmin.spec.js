import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

import api from '../../api/client'
import {
  listTenants,
  listPlans,
  createPlan,
  listSubscriptions,
  activateSubscription,
  suspendSubscription,
  cancelSubscription,
  renewSubscription,
  listPartnerLeads,
  approvePartnerLead,
} from '../../api/superAdmin'

describe('superAdmin API wrappers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listTenants calls GET /super-admin/tenants', async () => {
    api.get.mockResolvedValue({ data: [{ id: 't1' }] })
    const result = await listTenants()
    expect(api.get).toHaveBeenCalledWith('/api/v1/super-admin/tenants')
    expect(result).toEqual([{ id: 't1' }])
  })

  it('listPlans calls GET /super-admin/plans', async () => {
    api.get.mockResolvedValue({ data: [{ id: 'p1' }] })
    const result = await listPlans()
    expect(api.get).toHaveBeenCalledWith('/api/v1/super-admin/plans')
    expect(result).toEqual([{ id: 'p1' }])
  })

  it('createPlan calls POST /super-admin/plans', async () => {
    api.post.mockResolvedValue({ data: { id: 'p2' } })
    await createPlan({ name: 'New', price: 100 })
    expect(api.post).toHaveBeenCalledWith('/api/v1/super-admin/plans', { name: 'New', price: 100 })
  })

  it('listSubscriptions calls GET /super-admin/subscriptions', async () => {
    api.get.mockResolvedValue({ data: [{ id: 's1' }] })
    const result = await listSubscriptions()
    expect(api.get).toHaveBeenCalledWith('/api/v1/super-admin/subscriptions')
    expect(result).toEqual([{ id: 's1' }])
  })

  it('activateSubscription calls POST /super-admin/subscriptions/:id/activate', async () => {
    api.post.mockResolvedValue({ data: {} })
    await activateSubscription('s1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/super-admin/subscriptions/s1/activate')
  })

  it('suspendSubscription calls POST /super-admin/subscriptions/:id/suspend', async () => {
    api.post.mockResolvedValue({ data: {} })
    await suspendSubscription('s1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/super-admin/subscriptions/s1/suspend')
  })

  it('cancelSubscription calls POST /super-admin/subscriptions/:id/cancel', async () => {
    api.post.mockResolvedValue({ data: {} })
    await cancelSubscription('s1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/super-admin/subscriptions/s1/cancel')
  })

  it('renewSubscription calls POST /super-admin/subscriptions/:id/renew', async () => {
    api.post.mockResolvedValue({ data: {} })
    await renewSubscription('s1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/super-admin/subscriptions/s1/renew')
  })

  it('listPartnerLeads calls GET /partner-leads', async () => {
    api.get.mockResolvedValue({ data: [{ id: 'pl1' }] })
    const result = await listPartnerLeads()
    expect(api.get).toHaveBeenCalledWith('/api/v1/partner-leads')
    expect(result).toEqual([{ id: 'pl1' }])
  })

  it('approvePartnerLead calls POST /partner-leads/:id/approve', async () => {
    api.post.mockResolvedValue({ data: {} })
    await approvePartnerLead('pl1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/partner-leads/pl1/approve')
  })
})
