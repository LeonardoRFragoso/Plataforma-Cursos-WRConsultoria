import api from './client'

const BASE = '/api/v1/certificate-documents/studio'

export const listCertificateTemplates = (includeInactive = false) =>
  api.get(`${BASE}/templates`, { params: { include_inactive: includeInactive } })
export const createCertificateTemplate = (payload) => api.post(`${BASE}/templates`, payload)
export const updateCertificateTemplate = (id, payload) => api.patch(`${BASE}/templates/${id}`, payload)
export const listCertificateTemplateVersions = (templateId) => api.get(`${BASE}/templates/${templateId}/versions`)
export const createCertificateTemplateVersion = (templateId, visualConfig) =>
  api.post(`${BASE}/templates/${templateId}/versions`, { visual_config: visualConfig })
export const updateCertificateTemplateVersion = (templateId, versionId, visualConfig) =>
  api.patch(`${BASE}/templates/${templateId}/versions/${versionId}`, { visual_config: visualConfig })
export const publishCertificateTemplateVersion = (templateId, versionId) =>
  api.post(`${BASE}/templates/${templateId}/versions/${versionId}/publish`)
export const previewCertificateTemplate = (visualConfig) =>
  api.post(`${BASE}/preview`, { visual_config: visualConfig }, { responseType: 'blob' })
export const assignCertificateTemplate = (courseId, templateId) =>
  api.put(`${BASE}/courses/${courseId}/assignment`, { template_id: templateId })
export const resetCertificateTemplate = (courseId) => api.delete(`${BASE}/courses/${courseId}/assignment`)
export const getCertificateTemplateResolution = (courseId) => api.get(`${BASE}/courses/${courseId}/resolution`)
