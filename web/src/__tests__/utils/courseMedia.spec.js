import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock tenantSlug before importing courseMedia
const tenantSlugMock = vi.hoisted(() => ({ value: 'wr' }))
vi.mock('../../utils/tenantSlug', () => ({
  get TENANT_SLUG() {
    return tenantSlugMock.value
  },
}))

import {
  isWrTenant,
  getWrHero,
  getCourseCover,
  isValidMediaUrl,
  getWrAssetPaths,
} from '../../utils/courseMedia'

describe('courseMedia — isWrTenant', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'wr'
  })

  it('returns true when tenant slug is wr', () => {
    tenantSlugMock.value = 'wr'
    expect(isWrTenant()).toBe(true)
  })

  it('returns false when tenant slug is alfa', () => {
    tenantSlugMock.value = 'alfa'
    expect(isWrTenant()).toBe(false)
  })

  it('returns false when tenant slug is some-other-tenant', () => {
    tenantSlugMock.value = 'some-other-tenant'
    expect(isWrTenant()).toBe(false)
  })
})

describe('courseMedia — getWrHero', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'wr'
  })

  it('returns hero artwork for WR tenant', () => {
    const hero = getWrHero()
    expect(hero).not.toBeNull()
    expect(hero.src).toBe('/assets/wr/hero/wr-training-hero.webp')
    expect(hero.alt).toContain('segurança')
  })

  it('returns null for non-WR tenant', () => {
    tenantSlugMock.value = 'alfa'
    const hero = getWrHero()
    expect(hero).toBeNull()
  })
})

describe('courseMedia — getCourseCover (WR tenant)', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'wr'
  })

  it('resolves NR 10 by category', () => {
    const cover = getCourseCover({ category: 'NR 10', code: 'NR-10-B', name: 'NR 10 - Básico' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/nr-10-eletricidade.webp')
    expect(cover.alt).toContain('NR-10')
  })

  it('resolves NR 5 by category', () => {
    const cover = getCourseCover({ category: 'NR 5', code: 'NR-05-F', name: 'NR 5 - CIPA' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/nr-05-cipa.webp')
  })

  it('resolves Primeiros Socorros by code PS-F', () => {
    const cover = getCourseCover({ category: 'Programas', code: 'PS-F', name: 'Primeiros Socorros' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/primeiros-socorros.webp')
  })

  it('returns fallback for unmapped WR course', () => {
    const cover = getCourseCover({ category: 'NR 1', code: 'NR-01-F', name: 'NR 1' })
    expect(cover.isFallback).toBe(true)
    expect(cover.src).toBe('')
  })

  it('prioritizes backend cover_image_url over WR mapping', () => {
    const cover = getCourseCover({
      category: 'NR 10',
      code: 'NR-10-B',
      name: 'NR 10',
      cover_image_url: 'https://example.com/custom.webp',
      cover_image_alt: 'Custom alt',
    })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('https://example.com/custom.webp')
    expect(cover.alt).toBe('Custom alt')
  })
})

describe('courseMedia — getCourseCover (non-WR tenant)', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'alfa'
  })

  it('returns fallback for Alfa tenant even with NR 10 category', () => {
    const cover = getCourseCover({ category: 'NR 10', code: 'NR-10-B', name: 'NR 10' })
    expect(cover.isFallback).toBe(true)
    expect(cover.src).toBe('')
  })

  it('returns fallback with no /assets/wr/ reference', () => {
    const cover = getCourseCover({ category: 'NR 5', code: 'NR-05-F', name: 'NR 5' })
    expect(cover.src).not.toContain('/assets/wr/')
  })

  it('still respects backend cover_image_url for non-WR tenant', () => {
    const cover = getCourseCover({
      category: 'Some Category',
      code: 'SC-F',
      name: 'Some Course',
      cover_image_url: 'https://alfa.com/cover.webp',
    })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('https://alfa.com/cover.webp')
  })
})

describe('courseMedia — isValidMediaUrl', () => {
  it('accepts relative paths', () => {
    expect(isValidMediaUrl('/assets/wr/courses/nr-10.webp')).toBe(true)
  })

  it('accepts https URLs', () => {
    expect(isValidMediaUrl('https://example.com/image.webp')).toBe(true)
  })

  it('accepts http URLs', () => {
    expect(isValidMediaUrl('http://localhost:8000/img.webp')).toBe(true)
  })

  it('rejects javascript: scheme', () => {
    expect(isValidMediaUrl('javascript:alert(1)')).toBe(false)
  })

  it('rejects data:text/html scheme', () => {
    expect(isValidMediaUrl('data:text/html,<script>alert(1)</script>')).toBe(false)
  })

  it('rejects empty string', () => {
    expect(isValidMediaUrl('')).toBe(false)
  })

  it('rejects null', () => {
    expect(isValidMediaUrl(null)).toBe(false)
  })

  it('rejects non-string', () => {
    expect(isValidMediaUrl(123)).toBe(false)
  })
})

describe('courseMedia — getWrAssetPaths', () => {
  it('returns all 10 asset paths', () => {
    const paths = getWrAssetPaths()
    expect(paths).toHaveLength(10)
    paths.forEach((p) => {
      expect(p).toContain('/assets/wr/')
    })
  })

  it('includes hero path', () => {
    const paths = getWrAssetPaths()
    expect(paths).toContain('/assets/wr/hero/wr-training-hero.webp')
  })

  it('includes all 9 course paths', () => {
    const paths = getWrAssetPaths()
    expect(paths).toContain('/assets/wr/courses/nr-10-eletricidade.webp')
    expect(paths).toContain('/assets/wr/courses/nr-05-cipa.webp')
    expect(paths).toContain('/assets/wr/courses/nr-11-movimentacao-materiais.webp')
    expect(paths).toContain('/assets/wr/courses/nr-12-maquinas-e-equipamentos.webp')
    expect(paths).toContain('/assets/wr/courses/nr-18-construcao-civil.webp')
    expect(paths).toContain('/assets/wr/courses/nr-20-inflamaveis-combustiveis.webp')
    expect(paths).toContain('/assets/wr/courses/nr-33-espaco-confinado.webp')
    expect(paths).toContain('/assets/wr/courses/nr-35-trabalho-em-altura.webp')
    expect(paths).toContain('/assets/wr/courses/primeiros-socorros.webp')
  })
})

describe('courseMedia — null/invalid media handling', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'wr'
  })

  it('handles null course gracefully', () => {
    const cover = getCourseCover(null)
    expect(cover.isFallback).toBe(true)
    expect(cover.src).toBe('')
  })

  it('handles undefined course gracefully', () => {
    const cover = getCourseCover(undefined)
    expect(cover.isFallback).toBe(true)
  })

  it('handles course with invalid cover_image_url (javascript:)', () => {
    const cover = getCourseCover({
      category: 'NR 10',
      code: 'NR-10-B',
      name: 'NR 10',
      cover_image_url: 'javascript:alert(1)',
    })
    // Should fall through to WR mapping since javascript: is invalid
    expect(cover.src).toBe('/assets/wr/courses/nr-10-eletricidade.webp')
  })

  it('handles course with empty cover_image_url', () => {
    const cover = getCourseCover({
      category: 'NR 10',
      code: 'NR-10-B',
      name: 'NR 10',
      cover_image_url: '',
    })
    expect(cover.src).toBe('/assets/wr/courses/nr-10-eletricidade.webp')
  })
})
