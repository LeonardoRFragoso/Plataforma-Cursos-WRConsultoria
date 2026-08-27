function digitsOnly(value) {
  return String(value || '').replace(/\D/g, '')
}

function checkDigit(base, weights) {
  const total = base.split('').reduce((sum, digit, index) => sum + Number(digit) * weights[index], 0)
  const remainder = total % 11
  return remainder < 2 ? 0 : 11 - remainder
}

export function normalizeCnpj(value) {
  return digitsOnly(value)
}

export function isValidCnpj(value) {
  const digits = normalizeCnpj(value)
  if (digits.length !== 14 || /^(\d)\1{13}$/.test(digits)) return false
  const first = checkDigit(digits.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
  if (Number(digits[12]) !== first) return false
  const second = checkDigit(digits.slice(0, 13), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
  return Number(digits[13]) === second
}

export function formatCnpj(value) {
  const digits = normalizeCnpj(value)
  if (digits.length !== 14) return value || ''
  return digits.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5')
}

export function apiDetailMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const first = detail.find((item) => item?.msg)
    if (first?.msg) return first.msg.replace(/^Value error,\s*/i, '')
  }
  return fallback
}
