import { ref, readonly } from 'vue'

/**
 * Global toast notification composable.
 * Usage:
 *   const { toasts, showToast, removeToast } = useToast()
 *   showToast({ type: 'success', message: 'Saved!' })
 *
 * In App.vue, render the toasts:
 *   <Toast v-for="t in toasts" :key="t.id" v-bind="t" @dismiss="removeToast(t.id)" />
 */

const toasts = ref([])
let nextId = 0

export function useToast() {
  function showToast({ type = 'info', title = '', message, duration = 4000 }) {
    const id = ++nextId
    toasts.value.push({ id, type, title, message, duration })
    return id
  }

  function removeToast(id) {
    const idx = toasts.value.findIndex((t) => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  function success(message, title = '') {
    return showToast({ type: 'success', message, title })
  }

  function error(message, title = '') {
    return showToast({ type: 'error', message, title })
  }

  function info(message, title = '') {
    return showToast({ type: 'info', message, title })
  }

  return {
    toasts: readonly(toasts),
    showToast,
    removeToast,
    success,
    error,
    info,
  }
}
