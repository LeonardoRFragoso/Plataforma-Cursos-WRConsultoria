import { describe, expect, it } from 'vitest'
import { apiDetailMessage, formatCnpj, isValidCnpj, normalizeCnpj } from '../../utils/brazilianDocuments'

describe('brazilianDocuments', () => {
  it('normalizes, validates and formats a valid CNPJ', () => {
    expect(normalizeCnpj('11.222.333/0001-81')).toBe('11222333000181')
    expect(isValidCnpj('11.222.333/0001-81')).toBe(true)
    expect(isValidCnpj('11222333000181')).toBe(true)
    expect(formatCnpj('11222333000181')).toBe('11.222.333/0001-81')
  })

  it.each([
    '11.222.333/0001-80',
    '00000000000000',
    '11111111111111',
    '123',
  ])('rejects invalid CNPJ %s', (value) => {
    expect(isValidCnpj(value)).toBe(false)
  })

  it('extracts friendly FastAPI validation messages', () => {
    const error = { response: { data: { detail: [{ msg: 'Value error, CNPJ inválido' }] } } }
    expect(apiDetailMessage(error, 'fallback')).toBe('CNPJ inválido')
  })
})
