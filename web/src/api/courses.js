import api from './client'

// Trailing slash is required: the backend route is mounted at
// /api/v1/courses/ and a no-slash request returns a 307 redirect. A
// cross-origin 307 from the browser can drop the tenant/auth context and
// surface as an empty list (or a CORS-style failure) on Home. Hit the
// canonical endpoint directly.
export function fetchPublicCourses() {
  return api.get('/api/v1/courses/', { params: { limit: 100 } })
}

export function fetchCourse(courseId) {
  return api.get(`/api/v1/courses/${courseId}`)
}
