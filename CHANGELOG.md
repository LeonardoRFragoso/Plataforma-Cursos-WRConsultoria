# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

## [2.0.0] - 2026-08-15 — White-Label SaaS Commerce Completion

### Adicionado
- **Multi-tenant architecture** with Row Level Security (RLS) on all tenant-aware tables
- **Encrypted tenant secrets** (TenantSecret model, AES-GCM via TENANT_SECRET_ENCRYPTION_KEY)
- **Mercado Pago integration** using per-tenant encrypted access tokens
- **Storefront purchase flow**: public course detail → idempotent purchase → checkout → webhook reconciliation
- **SaaS billing**: Plan and TenantSubscription lifecycle APIs with WR-controlled plan ownership
- **Custom domain lifecycle** with TXT record verification
- **Rate limiting middleware** with Redis backend abstraction
- **CSV/XLSX export service** for admin reports
- **FORCE RLS** on tenant_secrets, tenant_subscriptions, plans
- **MERCADO_PAGO_MOCK_MODE** for testing without real MP API
- **E2E bootstrap script** (idempotent, E2E_TEST_MODE-gated)
- **Full-stack Playwright integration test** (real API + DB + frontend)
- **Production readiness**: Dockerfile.prod (non-root, multi-stage), nginx frontend,
  docker-compose.prod.yml, fail-closed config validation, /health/live + /health/ready,
  trusted proxy IP, structured JSON logging with request correlation
- **Operational docs**: DEPLOYMENT.md, RELEASE_RUNBOOK.md, BACKUP_RESTORE.md,
  DEPENDENCY_AUDIT.md, PRODUCTION_READINESS_AUDIT.md

### Alterado
- Plan catalog now fetched from database (single source of truth, no hardcoded values)
- Rate limiter uses get_client_ip() with trusted proxy support
- Health endpoints separated: /health/live (liveness), /health/ready (readiness)
- Swagger/OpenAPI exposure configurable via DOCS_ENABLED

### Segurança
- SECRET_KEY placeholder → fail at startup in production
- TENANT_SECRET_ENCRYPTION_KEY empty → fail at startup in production
- ALLOWED_HOSTS wildcard → fail at startup in production
- CORS_ORIGINS wildcard/localhost → fail at startup in production
- MERCADO_PAGO_MOCK_MODE=true → fail at startup in production
- E2E_TEST_MODE=true → fail at startup in production
- RATE_LIMIT_ENABLED=false → fail at startup in production

## [1.0.0] - 2024-01-XX

### Adicionado
- Estrutura inicial do projeto (backend FastAPI + frontend Vue 3)
- Autenticação com JWT (access + refresh token)
- RBAC com 3 roles: admin, instructor, student
- Modelos de dados completos (User, Course, Class, Student, Enrollment, Payment, Certificate, Attendance)
- Endpoints REST para:
  - Autenticação (login, register, refresh, me)
  - Cursos (CRUD)
  - Turmas (CRUD)
  - Alunos (CRUD)
  - Matrículas (CRUD)
  - Pagamentos (CRUD + webhook Mercado Pago)
  - Certificados (CRUD + validação pública)
- Frontend com páginas:
  - Home (landing page)
  - Login/Register
  - Dashboard
  - Gerenciamento de Cursos
  - Gerenciamento de Turmas
  - Gerenciamento de Alunos
  - Gerenciamento de Matrículas
  - Gerenciamento de Pagamentos
  - Gerenciamento de Certificados
- Integração com Mercado Pago (preferências de pagamento + webhook)
- Geração de certificados em PDF com ReportLab
- Testes unitários (pytest backend + Vitest frontend)
- Docker + docker-compose para ambiente local
- Documentação (README, ARCHITECTURE, CONTRIBUTING)
- Tailwind CSS para styling
- Pinia para state management
- Vue Router para navegação

### Próximas Fases
- [ ] Emissão de notas fiscais (NF-e)
- [ ] Upload de materiais didáticos
- [ ] Player de vídeo próprio
- [ ] Dashboard financeiro avançado
- [ ] Relatórios exportáveis (CSV/Excel)
- [ ] Portal do aluno completo
- [ ] Vitrine pública de cursos
- [ ] Sistema de avaliações
- [ ] Notificações por email
- [ ] Integração com CRM
