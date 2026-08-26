import api from './client'

export const getFinancialSummary = () => api.get('/api/v1/financial/summary')
export const listFinancialReviews = (params = {}) => api.get('/api/v1/financial/reviews', { params })
export const claimFinancialReview = (id, payload = {}) => api.post(`/api/v1/financial/reviews/${id}/claim`, payload)
export const resolveFinancialReview = (id, payload) => api.post(`/api/v1/financial/reviews/${id}/resolve`, payload)
export const openPaymentReview = (paymentId, payload) => api.post(`/api/v1/financial/payments/${paymentId}/review`, payload)
export const getFinancialReviewEvents = (id) => api.get(`/api/v1/financial/reviews/${id}/events`)
export const createCorporatePayment = (payload) => api.post('/api/v1/financial/corporate-payments', payload)
export const listCorporatePayments = (companyId) => api.get(`/api/v1/financial/corporate-payments/${companyId}`)
