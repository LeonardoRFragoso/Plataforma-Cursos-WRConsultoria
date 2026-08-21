/**
 * Central course media resolver — WR tenant-aware, family-based.
 *
 * WR-generated visual assets live under /assets/wr/ and are mapped to real
 * WR course families. All variations of a family (Formação, Reciclagem,
 * Básico, SEP, etc.) share the same base artwork. Non-WR tenants receive
 * NO /assets/wr/ references; they get a neutral, tenant-colored gradient
 * fallback instead.
 *
 * Resolution priority:
 *   1. course.cover_image_url (backend field — admin can set per-course)
 *   2. WR family mapping by code prefix (only when tenant slug is "wr")
 *   3. Neutral fallback (gradient + course code overlay)
 */
import { TENANT_SLUG } from '../utils/tenantSlug'

// ──────────────────────────────────────────────────────────────
// WR course cover mapping — keyed by family code prefix.
// All variations (NR-10-B, NR-10-R, NR-10-S, NR-10-AE, NR-10)
// resolve to the same family image.
// ──────────────────────────────────────────────────────────────
const WR_FAMILY_MEDIA = {
  // NR families (AI-generated artwork)
  'NR-01': { src: '/assets/wr/courses/nr-01-disposicoes-gerais.webp', alt: 'Treinamento NR-01 — Disposições Gerais das Normas Regulamentadoras' },
  'NR-05': { src: '/assets/wr/courses/nr-05-cipa.webp', alt: 'Treinamento NR-05 sobre CIPA e prevenção de acidentes' },
  'NR-06': { src: '/assets/wr/courses/nr-06-epi.webp', alt: 'Treinamento NR-06 sobre Equipamentos de Proteção Individual' },
  'NR-10': { src: '/assets/wr/courses/nr-10-eletricidade.webp', alt: 'Treinamento NR-10 sobre segurança em instalações e serviços em eletricidade' },
  'NR-11': { src: '/assets/wr/courses/nr-11-movimentacao-materiais.webp', alt: 'Treinamento NR-11 sobre movimentação e armazenagem de materiais' },
  'NR-12': { src: '/assets/wr/courses/nr-12-maquinas-e-equipamentos.webp', alt: 'Treinamento NR-12 sobre segurança no trabalho em máquinas e equipamentos' },
  'NR-17': { src: '/assets/wr/courses/nr-17-ergonomia.webp', alt: 'Treinamento NR-17 sobre ergonomia e saúde no trabalho' },
  'NR-18': { src: '/assets/wr/courses/nr-18-construcao-civil.webp', alt: 'Treinamento NR-18 sobre segurança na construção civil' },
  'NR-20': { src: '/assets/wr/courses/nr-20-inflamaveis-combustiveis.webp', alt: 'Treinamento NR-20 sobre segurança com inflamáveis e combustíveis' },
  'NR-22': { src: '/assets/wr/courses/nr-22-cipamin.webp', alt: 'Treinamento NR-22 — CIPAMIN, segurança na mineração' },
  'NR-23': { src: '/assets/wr/courses/nr-23-protecao-contra-incendios.webp', alt: 'Treinamento NR-23 sobre proteção contra incêndios' },
  'NR-26': { src: '/assets/wr/courses/nr-26-sinalizacao-seguranca.webp', alt: 'Treinamento NR-26 sobre sinalização de segurança' },
  'NR-29': { src: '/assets/wr/courses/nr-29-trabalho-portuario.webp', alt: 'Treinamento NR-29 sobre segurança no trabalho portuário' },
  'NR-31': { src: '/assets/wr/courses/nr-31-trabalho-rural.webp', alt: 'Treinamento NR-31 sobre segurança e saúde no trabalho rural' },
  'NR-32': { src: '/assets/wr/courses/nr-32-servicos-saude.webp', alt: 'Treinamento NR-32 sobre biossegurança em serviços de saúde' },
  'NR-33': { src: '/assets/wr/courses/nr-33-espaco-confinado.webp', alt: 'Treinamento NR-33 sobre segurança em espaço confinado' },
  'NR-34': { src: '/assets/wr/courses/nr-34-trabalho-naval.webp', alt: 'Treinamento NR-34 sobre segurança no trabalho naval' },
  'NR-35': { src: '/assets/wr/courses/nr-35-trabalho-em-altura.webp', alt: 'Treinamento NR-35 sobre trabalho em altura' },
  'NR-36': { src: '/assets/wr/courses/nr-36-frigorificos.webp', alt: 'Treinamento NR-36 sobre segurança em frigoríficos' },

  // Non-NR families (generated artwork matching WR style)
  'PS':   { src: '/assets/wr/courses/primeiros-socorros.webp', alt: 'Treinamento de primeiros socorros — atendimento inicial em emergências' },
  'PCA':  { src: '/assets/wr/courses/pca-conservacao-auditiva.webp', alt: 'Programa de Conservação Auditiva — proteção auditiva no trabalho' },
  'PPR':  { src: '/assets/wr/courses/ppr-protecao-respiratoria.webp', alt: 'Programa de Proteção Respiratória — proteção respiratória no trabalho' },
  'BV':   { src: '/assets/wr/courses/brigada-voluntaria.webp', alt: 'Brigada Voluntária — prevenção e combate a incêndios' },
  'DD':   { src: '/assets/wr/courses/direcao-defensiva.webp', alt: 'Direção Defensiva — segurança no trânsito' },
  'DP':   { src: '/assets/wr/courses/desenvolvimento-pessoal.webp', alt: 'Desenvolvimento Pessoal — crescimento profissional' },
  'GL':   { src: '/assets/wr/courses/ginastica-laboral.webp', alt: 'Ginástica Laboral — saúde e bem-estar no trabalho' },
  'LE':   { src: '/assets/wr/courses/lingua-estrangeira-ingles.webp', alt: 'Língua Estrangeira — inglês profissional' },
  'NEG':  { src: '/assets/wr/courses/negocios.webp', alt: 'Negócios — gestão e empreendedorismo' },
  'QP':   { src: '/assets/wr/courses/qualificacao-profissional.webp', alt: 'Qualificação Profissional — capacitação técnica' },
  'SAU':  { src: '/assets/wr/courses/saude.webp', alt: 'Saúde — promoção da saúde no trabalho' },
  'OPS':  { src: '/assets/wr/courses/operacional.webp', alt: 'Treinamento Operacional — procedimentos operacionais' },
  'RISC': { src: '/assets/wr/courses/gestao-riscos.webp', alt: 'Gestão de Riscos — avaliação e controle de riscos' },
  'SEG':  { src: '/assets/wr/courses/integracao-seguranca.webp', alt: 'Integração de Segurança — segurança do trabalho' },
}

// WR Home hero artwork.
const WR_HERO = {
  src: '/assets/wr/hero/wr-training-hero.webp',
  alt: 'Equipe de treinamentos WR — treinamentos que preparam equipes para trabalhar com segurança',
}

// WR auth visual panel image — a dedicated crop of the hero's photographic
// right side (workers/PPE/training area), WITHOUT the embedded marketing
// headline/WR logo that lives on the left side of the full hero artwork.
// This prevents text collision between the hero's embedded typography and
// the AuthLayout's overlay tagline.
const WR_AUTH_VISUAL = {
  src: '/assets/wr/auth/wr-auth-training.webp',
  alt: 'Equipe de treinamentos WR em ação — capacitação profissional em segurança do trabalho',
}

/**
 * Determine if the current tenant is WR.
 * Uses the tenant slug resolved at module load time.
 */
export function isWrTenant() {
  return TENANT_SLUG === 'wr'
}

/**
 * Extract the course family prefix from a course code.
 *
 * Examples:
 *   NR-10-B  → NR-10
 *   NR-10    → NR-10
 *   NR-10-AE → NR-10
 *   PS-F     → PS
 *   PCA-F    → PCA
 *   BV-F     → BV
 *   OPS-01   → OPS
 *   RISC-01  → RISC
 */
export function extractFamily(code) {
  if (!code || typeof code !== 'string') return null
  const trimmed = code.trim().toUpperCase()
  // NR-XX family: extract "NR-XX" (e.g. NR-10-B → NR-10)
  if (trimmed.startsWith('NR-')) {
    const parts = trimmed.split('-')
    if (parts.length >= 2) return `NR-${parts[1]}`
    return trimmed
  }
  // Non-NR families: take the prefix before the first dash
  // (e.g. PS-F → PS, PCA-F → PCA, OPS-01 → OPS)
  const dashIdx = trimmed.indexOf('-')
  if (dashIdx > 0) return trimmed.substring(0, dashIdx)
  return trimmed
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
 * Get the WR auth visual panel image for Login/Register/Forgot/Reset.
 * Returns null for non-WR tenants.
 * @returns {{ src: string, alt: string } | null}
 */
export function getWrAuthVisual() {
  if (!isWrTenant()) return null
  return { ...WR_AUTH_VISUAL }
}

/**
 * Resolve the cover media for a course.
 *
 * @param {object} course - The course object (must have at least `code`).
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

  // 2. WR family mapping (only for WR tenant)
  if (isWrTenant()) {
    const family = extractFamily(course?.code)
    if (family && WR_FAMILY_MEDIA[family]) {
      return { ...WR_FAMILY_MEDIA[family], isFallback: false }
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
    ...Object.values(WR_FAMILY_MEDIA).map((m) => m.src),
  ]
}
