import api from './client'

export const asaasApi = {
  getStatus() {
    return api.get('/api/v1/integrations/asaas/status')
  },

  connect(apiKey) {
    return api.post('/api/v1/integrations/asaas/connect', { api_key: apiKey })
  },

  validate() {
    return api.post('/api/v1/integrations/asaas/validate')
  },

  disconnect() {
    return api.delete('/api/v1/integrations/asaas/')
  },
}
