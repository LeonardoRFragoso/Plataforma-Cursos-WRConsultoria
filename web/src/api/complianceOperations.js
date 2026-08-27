import api from './client'

const BASE = '/api/v1/compliance/operations'

export const getComplianceOperationsSummary = () => api.get(`${BASE}/summary`)
export const getComplianceClassReport = (classId) => api.get(`${BASE}/classes/${classId}/report`)
export const listRetentionPolicyVersions = () => api.get(`${BASE}/retention-policy/versions`)
export const createRetentionPolicyVersion = (payload) => api.post(`${BASE}/retention-policy/versions`, payload)
export const updateRetentionPolicyVersion = (id, payload) => api.patch(`${BASE}/retention-policy/versions/${id}`, payload)
export const approveRetentionPolicyVersion = (id) => api.post(`${BASE}/retention-policy/versions/${id}/approve`)
