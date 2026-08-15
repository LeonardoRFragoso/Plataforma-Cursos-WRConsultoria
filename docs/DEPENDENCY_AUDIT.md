# Dependency Security Audit

**Date:** 2026-08-15  
**Branch:** `chore/production-readiness`

## Summary

| Category | Count |
|----------|-------|
| Python vulnerabilities | 43 across 11 packages |
| npm vulnerabilities | 13 (2 moderate, 7 high, 4 critical) |

**No automatic `npm audit fix --force` or breaking upgrades were performed.**
This is a report only. P0 exploitable runtime issues should be fixed in
atomic commits; breaking major upgrades must be proposed and reviewed.

---

## Python (pip-audit)

### Runtime dependencies with vulnerabilities

| Package | Version | Vulnerabilities | Fix Version | Severity |
|---------|---------|----------------|-------------|----------|
| **fastapi** | 0.104.1 | PYSEC-2024-38 | 0.109.1 | High |
| **starlette** | 0.27.0 | 6 vulnerabilities | 1.0.1+ | High |
| **python-jose** | 3.3.0 | 3 vulnerabilities | 3.4.0 | High |
| **python-multipart** | 0.0.6 | 7 vulnerabilities | 0.0.7+ | High |
| **jinja2** | 3.1.2 | 5 vulnerabilities | 3.1.6 | Medium |
| **requests** | 2.31.0 | 3 vulnerabilities | 2.33.0 | Medium |
| **cryptography** | 44.0.3 | 5 vulnerabilities | 46.0.6 | Medium |
| **aiosmtplib** | 3.0.1 | 1 vulnerability | 5.1.1 | Medium |
| **python-dotenv** | 1.0.0 | 1 vulnerability | 1.2.2 | Low |

### Dev-only dependencies with vulnerabilities

| Package | Version | Vulnerabilities | Fix Version |
|---------|---------|----------------|-------------|
| pytest | 7.4.3 | 1 vulnerability | 9.0.3 |

### Recommended action

1. **P0 (fix before production):** `fastapi`, `starlette`, `python-jose`
   — these handle HTTP requests and JWT authentication. Upgrade to
   `fastapi>=0.109.1` (pulls in `starlette>=0.35`), `python-jose>=3.4.0`.
2. **P1 (fix before production):** `python-multipart` — handles file
   uploads. Upgrade to `>=0.0.7`.
3. **P2 (fix soon):** `jinja2`, `requests`, `cryptography` — upgrade to
   latest patch versions.
4. **P3 (dev-only):** `pytest` — upgrade when convenient.

**Note:** Upgrading `fastapi` and `starlette` to latest may require code
changes (breaking API changes between 0.104 and 0.109+). This should be
a separate, reviewed PR — not part of the production-readiness commit.

---

## npm (frontend)

### Direct dependencies with vulnerabilities

| Package | Severity | Type | Notes |
|---------|----------|------|-------|
| `@typescript-eslint/eslint-plugin` | High | Dev | Linting only, no runtime risk |
| `@typescript-eslint/parser` | High | Dev | Linting only, no runtime risk |
| `@vitest/coverage-v8` | Critical | Dev | Test coverage only |
| `@vitest/ui` | Critical | Dev | Test UI only |
| `happy-dom` | Critical | Dev | Test DOM only |
| `vite` | High | Dev | Build tool, not in runtime image |
| `vitest` | Critical | Dev | Test runner only |

### Transitive dependencies

| Package | Severity | Via |
|---------|----------|-----|
| `esbuild` | Moderate | vite |
| `minimatch` | High | @typescript-eslint |
| `vite-node` | Moderate | vitest |
| `@typescript-eslint/*` | High | eslint plugin |

### Assessment

**All npm vulnerabilities are in dev-only dependencies.** The production
frontend image (`web/Dockerfile.prod`) uses a multi-stage build:
- Stage 1 (builder): Node 20 + npm ci + vite build → static `dist/`
- Stage 2 (runtime): nginx:alpine serves static files

**No node_modules exist in the runtime image.** The vulnerabilities
affect the build environment only, not the deployed application.

### Recommended action

1. **No P0 action required** — no runtime vulnerabilities.
2. **P2:** Run `npm audit fix` (non-breaking) to resolve what can be
   resolved without `--force`.
3. **P3:** Consider upgrading `vitest`, `@typescript-eslint/*`, and
   `vite` to latest major versions in a separate PR.

---

## Conclusion

The most critical runtime vulnerabilities are in Python packages
(`fastapi`, `starlette`, `python-jose`, `python-multipart`). These
should be upgraded in a dedicated, reviewed PR before production
deployment. The npm vulnerabilities are all in dev-only dependencies
and do not affect the production runtime image.

This audit is recorded as an item for the security/dependency audit
pre-production milestone. No breaking upgrades were performed in this
production-readiness commit.
