import api from './client'

export function validateCertificate(code) {
  return api.post('/api/v1/certificates/validate', { validation_code: code })
}
