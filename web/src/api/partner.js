import api from './client'

export function submitPartnerLead(data) {
  return api.post('/api/v1/partner-leads', data)
}
