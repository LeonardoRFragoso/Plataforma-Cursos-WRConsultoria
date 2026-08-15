import api from './client'

export const purchaseCourse = (courseId, method = 'BOLETO') => {
  return api.post('/api/v1/enrollments/purchase', { course_id: courseId, method })
}

export const createCheckout = (paymentId) => {
  return api.post(`/api/v1/payments/${paymentId}/checkout`)
}
