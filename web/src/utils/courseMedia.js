/**
 * Central course media resolver — WR tenant-aware.
 *
 * WR-generated visual assets live under /assets/wr/ and are mapped to real
 * WR course categories. Non-WR tenants receive NO /assets/wr/ references;
 * they get a neutral, tenant-colored gradient fallback instead.
 *
 * Resolution priority:
 *   1. course.cover_image_url (backend field — admin can set per-course)
 *   2. WR category mapping (only when tenant slug is "wr")
 *   3. Neutral fallback (gradient + course code overlay)
 */
import { TENANT_SLUG } from '../utils/tenantSlug'

// ──────────────────────────────────────────────────────────────
// WR course cover mapping — keyed by course category.
// Categories in the seed data use the format "NR 5", "NR 10", etc.
// ──────────────────────────────────────────────────────────────
const WR_COURSE_MEDIA = {
  'NR 5': {
    src: '/assets/wr/courses/nr-05-cipa.webp',
    alt: 'Treinamento NR-5 sobre CIPA e prevenção de acidentes',
  },
  'NR 10': {
    src: '/assets/wr/courses/nr-10-eletricidade.webp',
    alt: 'Treinamento NR-10 sobre segurança em instalações e serviços em eletricidade',
  },
  'NR 11': {
    src: '/assets/wr/courses/nr-11-movimentacao-materiais.webp',
    alt: 'Treinamento NR-11 sobre movimentação e armazenagem de materiais',
  },
  'NR 12': {
    src: '/assets/wr/courses/nr-12-maquinas-e-equipamentos.webp',
    alt: 'Treinamento NR-12 sobre segurança no trabalho em máquinas e equipamentos',
  },
  'NR 18': {
    src: '/assets/wr/courses/nr-18-construcao-civil.webp',
    alt: 'Treinamento NR-18 sobre segurança na construção civil',
  },
  'NR 20': {
    src: '/assets/wr/courses/nr-20-inflamaveis-combustiveis.webp',
    alt: 'Treinamento NR-20 sobre segurança com inflamáveis e combustíveis',
  },
  'NR 33': {
    src: '/assets/wr/courses/nr-33-espaco-confinado.webp',
    alt: 'Treinamento NR-33 sobre segurança em espaço confinado',
  },
  'NR 35': {
    src: '/assets/wr/courses/nr-35-trabalho-em-altura.webp',
    alt: 'Treinamento NR-35 sobre trabalho em altura',
  },
}

// Primeiros Socorros uses code "PS-F" in the seed, not a category match.
const WR_COURSE_CODE_MEDIA = {
  'PS-F': {
    src: '/assets/wr/courses/primeiros-socorros.webp',
    alt: 'Treinamento de primeiros socorros — atendimento inicial em situações de emergência',
  },
}

// WR Home hero artwork.
const WR_HERO = {
  src: '/assets/wr/hero/wr-training-hero.webp',
  alt: 'Equipe de treinamentos WR — treinamentos que preparam equipes para trabalhar com segurança',
}

/**
 * Determine if the current tenant is WR.
 * Uses the tenant slug resolved at module load time.
 */
export function isWrTenant() {
  return TENANT_SLUG === 'wr'
}

/**
 * Get the WR hero artwork for the Home page.
 * Returns null for non-WR tenants.
 * @returns {{ src: string, alt: string } | null}
 */
export function getWrHero() {
  if (!isWrTenant()) return null
  return { ...WR_HERO }
}

/**
 * Resolve the cover media for a course.
 *
 * @param {object} course - The course object (must have at least `code` and `category`).
 * @returns {{ src: string, alt: string, isFallback: boolean }}
 */
export function getCourseCover(course) {
  // 1. Backend-provided cover image (admin can set per-course)
  if (course?.cover_image_url && isValidMediaUrl(course.cover_image_url)) {
    return {
      src: course.cover_image_url,
      alt: course.cover_image_alt || course.name || '',
      isFallback: false,
    }
  }

  // 2. WR category/code mapping (only for WR tenant)
  if (isWrTenant()) {
    const byCategory = WR_COURSE_MEDIA[course?.category]
    if (byCategory) {
      return { ...byCategory, isFallback: false }
    }
    const byCode = WR_COURSE_CODE_MEDIA[course?.code]
    if (byCode) {
      return { ...byCode, isFallback: false }
    }
  }

  // 3. Neutral fallback — no /assets/wr/ reference
  return {
    src: '',
    alt: course?.name || '',
    isFallback: true,
  }
}

/**
 * Validate that a media URL is safe and usable.
 * Rejects javascript:, data:text/html, and other unsafe schemes.
 */
export function isValidMediaUrl(url) {
  if (!url || typeof url !== 'string') return false
  const trimmed = url.trim()
  if (!trimmed) return false
  // Allow relative paths (/assets/...) and http(s) URLs
  if (trimmed.startsWith('/')) return true
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return true
  // Explicitly reject dangerous schemes
  if (trimmed.toLowerCase().startsWith('javascript:')) return false
  if (trimmed.toLowerCase().startsWith('data:text/html')) return false
  return false
}

/**
 * Get the list of all WR media asset paths (for isolation testing).
 * Non-WR tenants should never reference any of these.
 */
export function getWrAssetPaths() {
  return [
    WR_HERO.src,
    ...Object.values(WR_COURSE_MEDIA).map((m) => m.src),
    ...Object.values(WR_COURSE_CODE_MEDIA).map((m) => m.src),
  ]
}
