import api from './client'

export function fetchPublicCourses() {
  return api.get('/api/v1/courses')
}

export function fetchCourse(courseId) {
  return api.get(`/api/v1/courses/${courseId}`)
}
