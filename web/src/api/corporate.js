import api from './client'

export const createCorporateRequest = (payload) => api.post('/api/v1/corporate/requests', payload)
export const listCorporateRequests = (params = {}) => api.get('/api/v1/corporate/requests', { params })
export const updateCorporateRequest = (id, payload) => api.patch(`/api/v1/corporate/requests/${id}`, payload)
export const convertCorporateRequest = (id, payload = {}) => api.post(`/api/v1/corporate/requests/${id}/convert`, payload)
export const linkCompanyEmployee = (companyId, payload) => api.post(`/api/v1/corporate/companies/${companyId}/employees/link`, payload)
export const inviteCompanyEmployee = (companyId, payload) => api.post(`/api/v1/corporate/companies/${companyId}/invites`, payload)
export const resendCompanyActivation = (companyId, studentId) => api.post(`/api/v1/corporate/companies/${companyId}/employees/${studentId}/resend-activation`)
export const listCompanyLinkEvents = (companyId) => api.get(`/api/v1/corporate/companies/${companyId}/link-events`)
export const annotateCompanyLinkEvent = (companyId, studentId, reason) => api.patch(`/api/v1/corporate/companies/${companyId}/employees/${studentId}/link-events/latest`, { reason })
export const offboardCompanyEmployee = async (companyId, studentId, payload = {}) => {
  const { reason, ...offboardPayload } = payload
  const response = await api.post(`/api/v1/corporate/companies/${companyId}/employees/${studentId}/offboard`, offboardPayload)
  if (reason) await annotateCompanyLinkEvent(companyId, studentId, reason)
  return response
}
export const listSeatAllocations = (companyId) => api.get(`/api/v1/corporate/companies/${companyId}/seat-allocations`)
export const saveSeatAllocation = (companyId, payload) => api.post(`/api/v1/corporate/companies/${companyId}/seat-allocations`, payload)
export const bulkEnrollCompany = (companyId, payload) => api.post(`/api/v1/corporate/companies/${companyId}/bulk-enroll`, payload)
export const getCompanyTrainingReport = (companyId) => api.get(`/api/v1/corporate/companies/${companyId}/training-report`)
