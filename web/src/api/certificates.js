import api from './client'

export function validateCertificate(code) {
  return api.post('/api/v1/certificates/validate', { validation_code: code })
}

/**
 * Fetch the authenticated student's certificates with joined course context.
 * Returns [] for non-student roles.
 */
export function fetchMyCertificates() {
  return api.get('/api/v1/certificates/me')
}
