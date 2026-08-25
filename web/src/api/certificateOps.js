import api from './client'

export const listCertificatesAdmin = () => api.get('/api/v1/certificates/')
export const revokeCertificate = (id, reason) => api.post(`/api/v1/certificates/${id}/revoke`, { reason })
export const reissueCertificate = (id, reason) => api.post(`/api/v1/certificates/${id}/reissue`, { reason })
export const getCertificateHistory = (id) => api.get(`/api/v1/certificates/${id}/history`)
