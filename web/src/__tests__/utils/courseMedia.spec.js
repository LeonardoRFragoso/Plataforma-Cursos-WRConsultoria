import { describe, it, expect, vi, beforeEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

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
  getWrAuthVisual,
  getCourseCover,
  extractFamily,
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

describe('courseMedia — getWrAuthVisual', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'wr'
  })

  it('returns auth visual for WR tenant', () => {
    const visual = getWrAuthVisual()
    expect(visual).not.toBeNull()
    expect(visual.src).toBe('/assets/wr/auth/wr-auth-training.webp')
  })

  it('returns null for non-WR tenant', () => {
    tenantSlugMock.value = 'alfa'
    const visual = getWrAuthVisual()
    expect(visual).toBeNull()
  })
})

describe('courseMedia — extractFamily', () => {
  it('extracts NR-10 from NR-10-B', () => {
    expect(extractFamily('NR-10-B')).toBe('NR-10')
  })

  it('extracts NR-10 from NR-10-AE', () => {
    expect(extractFamily('NR-10-AE')).toBe('NR-10')
  })

  it('extracts NR-10 from NR-10 (no suffix)', () => {
    expect(extractFamily('NR-10')).toBe('NR-10')
  })

  it('extracts NR-05 from NR-05-F', () => {
    expect(extractFamily('NR-05-F')).toBe('NR-05')
  })

  it('extracts PS from PS-F', () => {
    expect(extractFamily('PS-F')).toBe('PS')
  })

  it('extracts PCA from PCA-F', () => {
    expect(extractFamily('PCA-F')).toBe('PCA')
  })

  it('extracts OPS from OPS-01', () => {
    expect(extractFamily('OPS-01')).toBe('OPS')
  })

  it('extracts RISC from RISC-01', () => {
    expect(extractFamily('RISC-01')).toBe('RISC')
  })

  it('returns code as-is when no dash', () => {
    expect(extractFamily('NR10')).toBe('NR10')
  })

  it('handles null gracefully', () => {
    expect(extractFamily(null)).toBeNull()
  })

  it('handles undefined gracefully', () => {
    expect(extractFamily(undefined)).toBeNull()
  })

  it('normalizes to uppercase', () => {
    expect(extractFamily('nr-10-b')).toBe('NR-10')
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

  it('resolves NR-01 family from code NR-01-F', () => {
    const cover = getCourseCover({ category: 'NR 1', code: 'NR-01-F', name: 'NR 1 - Disposições Gerais' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/nr-01-disposicoes-gerais.webp')
  })

  it('resolves NR-01 family from code NR-01-R (reciclagem shares base art)', () => {
    const cover = getCourseCover({ category: 'NR 1', code: 'NR-01-R', name: 'NR 1 - Reciclagem' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/nr-01-disposicoes-gerais.webp')
  })

  it('resolves Brigada Voluntária from code BV-F', () => {
    const cover = getCourseCover({ category: 'Complementares', code: 'BV-F', name: 'Brigada Voluntária' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/brigada-voluntaria.webp')
  })

  it('resolves Gestão de Riscos from code RISC-01', () => {
    const cover = getCourseCover({ category: 'Engenharia', code: 'RISC-01', name: 'Gestão de Riscos' })
    expect(cover.isFallback).toBe(false)
    expect(cover.src).toBe('/assets/wr/courses/gestao-riscos.webp')
  })

  it('returns fallback for unmapped WR course', () => {
    const cover = getCourseCover({ category: 'Unknown', code: 'UNK-F', name: 'Unknown' })
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
  it('returns all asset paths (1 hero + 33 course families = 34)', () => {
    const paths = getWrAssetPaths()
    expect(paths).toHaveLength(34)
    paths.forEach((p) => {
      expect(p).toContain('/assets/wr/')
    })
  })

  it('includes hero path', () => {
    const paths = getWrAssetPaths()
    expect(paths).toContain('/assets/wr/hero/wr-training-hero.webp')
  })

  it('includes original 9 AI-generated course paths', () => {
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

  it('includes generated course family paths', () => {
    const paths = getWrAssetPaths()
    expect(paths).toContain('/assets/wr/courses/nr-01-disposicoes-gerais.webp')
    expect(paths).toContain('/assets/wr/courses/nr-06-epi.webp')
    expect(paths).toContain('/assets/wr/courses/nr-17-ergonomia.webp')
    expect(paths).toContain('/assets/wr/courses/nr-22-cipamin.webp')
    expect(paths).toContain('/assets/wr/courses/nr-23-protecao-contra-incendios.webp')
    expect(paths).toContain('/assets/wr/courses/nr-26-sinalizacao-seguranca.webp')
    expect(paths).toContain('/assets/wr/courses/nr-29-trabalho-portuario.webp')
    expect(paths).toContain('/assets/wr/courses/nr-31-trabalho-rural.webp')
    expect(paths).toContain('/assets/wr/courses/nr-32-servicos-saude.webp')
    expect(paths).toContain('/assets/wr/courses/nr-34-trabalho-naval.webp')
    expect(paths).toContain('/assets/wr/courses/nr-36-frigorificos.webp')
    expect(paths).toContain('/assets/wr/courses/pca-conservacao-auditiva.webp')
    expect(paths).toContain('/assets/wr/courses/ppr-protecao-respiratoria.webp')
    expect(paths).toContain('/assets/wr/courses/brigada-voluntaria.webp')
    expect(paths).toContain('/assets/wr/courses/direcao-defensiva.webp')
    expect(paths).toContain('/assets/wr/courses/desenvolvimento-pessoal.webp')
    expect(paths).toContain('/assets/wr/courses/ginastica-laboral.webp')
    expect(paths).toContain('/assets/wr/courses/lingua-estrangeira-ingles.webp')
    expect(paths).toContain('/assets/wr/courses/negocios.webp')
    expect(paths).toContain('/assets/wr/courses/qualificacao-profissional.webp')
    expect(paths).toContain('/assets/wr/courses/saude.webp')
    expect(paths).toContain('/assets/wr/courses/operacional.webp')
    expect(paths).toContain('/assets/wr/courses/gestao-riscos.webp')
    expect(paths).toContain('/assets/wr/courses/integracao-seguranca.webp')
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

describe('courseMedia — WR asset files exist on disk', () => {
  beforeEach(() => {
    tenantSlugMock.value = 'wr'
  })

  // Resolve web/public as the public root. __dirname in vitest points to the
  // test file's directory (web/src/__tests__/utils), so web/public is 3 levels up.
  const publicDir = path.resolve(__dirname, '..', '..', '..', 'public')

  it('all WR_FAMILY_MEDIA src paths resolve to existing files', () => {
    const paths = getWrAssetPaths()
    const missing = []
    for (const p of paths) {
      // p is like "/assets/wr/courses/nr-10-eletricidade.webp"
      const fullPath = path.join(publicDir, p)
      if (!fs.existsSync(fullPath)) {
        missing.push(p)
      }
    }
    expect(missing).toEqual([])
  })

  it('WR_HERO asset file exists', () => {
    const hero = getWrHero()
    expect(hero).not.toBeNull()
    const fullPath = path.join(publicDir, hero.src)
    expect(fs.existsSync(fullPath)).toBe(true)
  })

  it('WR_AUTH_VISUAL asset file exists', () => {
    const visual = getWrAuthVisual()
    expect(visual).not.toBeNull()
    const fullPath = path.join(publicDir, visual.src)
    expect(fs.existsSync(fullPath)).toBe(true)
  })

  it('no WR asset path is a directory or empty file', () => {
    const paths = getWrAssetPaths()
    for (const p of paths) {
      const fullPath = path.join(publicDir, p)
      const stat = fs.statSync(fullPath)
      expect(stat.isFile()).toBe(true)
      expect(stat.size).toBeGreaterThan(0)
    }
  })
})
