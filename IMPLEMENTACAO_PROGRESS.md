# 📊 Roadmap de Implementação — WR Plataforma de Cursos

> Atualizado em 22/08/2026 — reconciliação pós-PR #19 (Asaas Production Payments mergeado em `main`)
> e alinhamento com `docs/PRE_LAUNCH_STRATEGY.md` (decisão owner: PRE-LAUNCH/HOMOLOGAÇÃO).
>
> Este documento substitui o roadmap inicial, que já não refletia o estado real da plataforma. O foco atual deixou de ser apenas CRUD e passou a cobrir produção financeira, jornadas B2C/B2B, operação white-label, experiência de produto, segurança e escala.
>
> **Importante:** A decisão oficial do owner (registrada em `docs/PRE_LAUNCH_STRATEGY.md`)
> classifica o ambiente atual como **PRE-LAUNCH / HOMOLOGAÇÃO**. A ativação real do Asaas
> foi adiada para o Official Launch Gate e **não bloqueia** o desenvolvimento de Business Journeys.

---

## Classificação atual do ambiente

| Conceito | Estado |
|----------|--------|
| **Ambiente atual** | PRE-LAUNCH / HOMOLOGAÇÃO |
| **WR frontend** | Vercel / `wr-cursos-demo` |
| **Alfa frontend** | Vercel / `alfa-academy-demo` (white-label demo) |
| **Backend** | Railway / `wr-api-production.up.railway.app` |
| **Asaas code** | IMPLEMENTED / MERGED (PR #19) |
| **Real Asaas activation** | DEFERRED TO OFFICIAL LAUNCH GATE |
| **Business Journeys** | CURRENT DEVELOPMENT MACRO-PHASE |
| **Official domain** | NOT DEFINED YET |
| **Content readiness** | RECONCILED — 47 apostilas OCR'd, manifest built, importer ready |

---

## Estado atual de produção (Current Production Readiness)

> Snapshot conciso do estado real após o merge do PR #19.

| Área | Estado |
|------|--------|
| **Codebase** | `main` inclui PR #19 (merge `1cf7eca`) |
| **Payments — Asaas** | Código production-capable mergeado (não deployado) |
| **Backend tests** | 658 passaram, 0 falharam, 0 pulados |
| **Backend coverage** | 75.44% (gate 75%) |
| **Frontend tests** | 337 passaram |
| **Integration E2E** | 31 passaram |
| **UI-mocked E2E** | 63 passaram |
| **Database — Alembic** | Single head `a1b3c4d5e6f7` |
| **GitHub Actions** | Desativado intencionalmente pelo owner (controle de custo) |
| **Deploy verificado** | ❌ Não verificado nesta fase |
| **Asaas conta real conectada** | ❌ Não conectada ainda (deferida para Launch Gate) |
| **Próxima macrofase dev** | Compliance Operations & Retention Governance (em andamento) |
|| **NR Compliance Foundation (PR #34)** | ✅ IMPLEMENTED / MERGED |
|| **Training Evidence Runtime (PR #35)** | ✅ IMPLEMENTED / MERGED |
|| **Trusted Certificate Pipeline (PR #36)** | ✅ IMPLEMENTED / MERGED |
|| **PAdES Signing Orchestration (PR #37)** | ✅ IMPLEMENTED / MERGED |
|| **Certificate Studio (PR #38)** | ✅ IMPLEMENTED / MERGED |
|| **Compliance Operations & Retention Governance** | 🟡 IMPLEMENTED / PENDING MERGE |

---

## Legenda de status

| Ícone | Status | Significado |
|-------|--------|-------------|
| ✅ | IMPLEMENTED / MERGED | Código implementado, mergeado em `main`, testado localmente |
| 🟢 | VALIDATED LOCALLY | Validado em ambiente local/dev/test |
| 🟡 | PENDING OPERATIONAL VALIDATION | Requer validação contra ambiente real/produção |
| 🟠 | ROADMAP | Planejado, não iniciado |
| 🔴 | BLOCKER | Bloqueia produção |
| ⚪ | EXTERNAL / OWNER ACTION | Depende de ação externa/owner, não de código |

## Legenda de prioridade

- **P0 — Bloqueador de produção:** pode causar perda financeira, acesso incorreto, falha crítica de segurança ou impedir contratação/acesso.
- **P1 — Alta prioridade:** necessário para uma operação comercial confiável e profissional.
- **P2 — Evolução importante:** melhora escala, experiência, retenção e operação.
- **P3 — Futuro/otimização:** evolução posterior sem bloquear a operação atual.

---

# ✅ Concluído / Entrega histórica

> Itens já entregues e mergeados. Mantidos como registro histórico — não são trabalho pendente.

## Autenticação, segurança e multi-tenant
- ✅ Login por CPF ou e-mail.
- ✅ Registro público de alunos.
- ✅ JWT access + refresh tokens.
- ✅ Roles `STUDENT`, `ADMIN` e `SUPER_ADMIN`.
- ✅ Proteção de rotas frontend/backend.
- ✅ Resolução de tenant por domínio/contexto.
- ✅ Isolamento multi-tenant em grande parte dos módulos principais.
- ✅ Recuperação de senha e tokens one-time.
- ✅ Ativação de contas corporativas/parceiros.

## Cursos, turmas e aprendizagem
- ✅ CRUD de cursos.
- ✅ CRUD de turmas.
- ✅ Matrículas individuais e corporativas.
- ✅ Aulas com upload, YouTube e Vimeo.
- ✅ Materiais por aula.
- ✅ Progresso por aula.
- ✅ Curso liberado apenas para matrícula `CONFIRMADA`/`CONCLUIDA`.
- ✅ Certificados e validação pública.
- ✅ Upload/armazenamento tenant-aware para conteúdo de aulas.

## Empresas e onboarding corporativo
- ✅ CRUD de empresas.
- ✅ Cadastro de funcionários.
- ✅ Importação CSV de funcionários.
- ✅ Ativação de funcionário via token.
- ✅ Matrícula em lote.
- ✅ `EnrollmentSource.INDIVIDUAL` e `EnrollmentSource.CORPORATE`.
- ✅ `CorporateEnrollmentBatch`.
- ✅ Base para cobrança corporativa consolidada.

## White-label
- ✅ Tenant por parceiro.
- ✅ Logo, favicon e cores básicas.
- ✅ Domínio customizado.
- ✅ Isolamento WR / Alfa demo.
- ✅ Formulário público "Seja parceiro".
- ✅ Aprovação de parceiro pelo SUPER_ADMIN.
- ✅ Criação do tenant e administrador do parceiro.

## Frontend
- ✅ Vue 3 + Vite + Pinia.
- ✅ Application shell autenticado com sidebar/topbar.
- ✅ Layout público separado.
- ✅ Catálogo público de cursos.
- ✅ Página pública de detalhe do curso.
- ✅ Dashboard por role.
- ✅ Course player funcional.
- ✅ Componentes reutilizáveis (`AppButton`, `AppCard`, `AppModal`, `AppAlert`, etc.).
- ✅ Responsividade base.

## Qualidade
- ✅ Suíte backend extensa (658 testes, 75.44% cobertura).
- ✅ Vitest frontend (337 testes).
- ✅ Playwright E2E (31 integration + 63 ui-mocked).
- ✅ Testes de tenant isolation/security regressions.
- ✅ Alembic com single-head validado (`a1b3c4d5e6f7`).
- ⚪ CI GitHub Actions — desativado intencionalmente pelo owner (controle de custo); gates locais usados como evidência de release.

---

# 💳 Asaas Production Payments — PR #19 (mergeado)

> Código implementado e mergeado em `main`. Deploy e ativação produção são pendentes operacionais.

## Código — ✅ IMPLEMENTED / MERGED

- ✅ Payment provider abstraction (`PaymentProviderInterface`, base class).
- ✅ Asaas provider (`AsaasProvider`) com checkout, customer sync, refund, webhook CRUD.
- ✅ Mercado Pago provider (`MercadoPagoProvider`) compatível com a abstraction.
- ✅ Encrypted per-tenant Asaas credentials (`TenantSecret` + AES-GCM).
- ✅ Hosted checkout integration (PIX, Boleto, Cartão).
- ✅ Customer synchronization architecture (`PaymentCustomer` mapping, `payment_customer_sync`).
- ✅ `Payment.id` (UUID) como `externalReference` da cobrança.
- ✅ Webhook registration/reconciliation via Asaas API (list → update or create).
- ✅ Webhook auth token separado da API key (gerado, 32-255 chars, constant-time compare).
- ✅ Webhook idempotency ledger (`PaymentWebhookEvent` com state machine).
- ✅ Payment identity validation (provider_payment_id, externalReference, amount, customer).
- ✅ PIX canonical flow (`PAYMENT_CREATED → PAYMENT_RECEIVED` — unlock em `RECEIVED`).
- ✅ Payment return flow (UX "Estamos confirmando seu pagamento…").
- ✅ Finance settings UI (`Configurações → Financeiro → Conectar Asaas`).
- ✅ Write-only protected financial secrets (chave pode ser configurada/substituída/deletada/validada, nunca visualizada em plaintext).
- ✅ Corporate consolidated payment foundation (`PaymentCustomer` para empresa, `company_id` em `Payment`).
- ✅ Production mock-mode fail-closed (`validate_production_config()` recusa start se `ASAAS_MOCK_MODE=true` em produção).
- ✅ Fail-closed para `EMAIL_MOCK_MODE` em produção.
- ✅ Fail-closed para `MERCADO_PAGO_MOCK_MODE` em produção.
- ✅ Validação de prefixo `$aact_prod_` para chave de produção.
- ✅ HTTP error sanitization (erros Asaas nunca expõem `response.text` bruto ao cliente).
- ✅ `User-Agent` explícito em todas as chamadas Asaas.
- ✅ Tenant isolation tests (payment tenant isolation, webhook tenant scoping).
- ✅ Asaas local regression coverage (55 testes em `test_coverage_gaps.py` + suites dedicadas).
- ✅ Navegação real para `Configurações → Financeiro` no AppShell.
- ✅ `/integrations/asaas/status` reflete estado real do webhook/conexão.
- ✅ Tokens de ativação/reset não expostos em respostas HTTP de produção.

## Operacional — 🟡 PENDING OPERATIONAL VALIDATION

- 🟡 Deploy do `main` em produção.
- 🟡 Aplicar `alembic upgrade head` em produção.
- 🟡 Verificar `/health/live` em produção.
- 🟡 Verificar `/health/ready` em produção.
- 🟡 Verificar frontend WR em produção.
- 🟡 Verificar rota `Configurações → Financeiro` em produção.
- 🟡 Conexão segura da chave de produção Asaas pelo Admin WR.
- 🟡 Validação read-only da conta Asaas (autenticação).
- 🟡 Reconciliação/verificação do webhook de produção.
- 🟡 Verificar webhook `enabled=true` e `interrupted=false`.
- 🟡 Primeira compra real controlada (apenas com autorização explícita do owner).
- 🟡 Confirmar webhook → Payment → Enrollment → course access em produção.
- 🟡 Validação SMTP em produção (e-mail transacional real).

---

# 🟡 Production Activation — Asaas (DEFERRED TO OFFICIAL LAUNCH GATE)

> **Status:** 🟡 DEFERRED TO OFFICIAL LAUNCH GATE
>
> A ativação operacional do Asaas foi oficialmente adiada para o Official Launch Gate
> por decisão do owner (ver `docs/PRE_LAUNCH_STRATEGY.md`). O código Asaas já está
> mergeado e testável com mocks/fakes. **Nenhum bloqueio para Business Journeys.**
>
> Durante PRE-LAUNCH: não inserir chave Asaas real, não criar cobranças reais,
> não executar PIX/boleto/cartão/refund/transfer reais. Testes de pagamento usam mocks/fakes.

## Sequência requerida

1. Deploy do `main` mergeado.
2. Aplicar production Alembic `upgrade head`.
3. Verificar `/health/live`.
4. Verificar `/health/ready`.
5. Verificar frontend WR.
6. Login como WR admin.
7. `Configurações → Financeiro`.
8. Inserir a chave de API de produção Asaas através do formulário seguro da UI.
9. Validação read-only da conta (autenticação Asaas).
10. Reconciliação automática do webhook de produção.
11. Verificar webhook `enabled=true` e `interrupted=false`.
12. Realizar uma compra real controlada de baixo valor **apenas com autorização explícita do owner**.
13. Confirmar webhook → Payment → Enrollment → course access.

> ⚠️ **NUNCA** colocar a chave de API de produção em documentação, terminal logs, chat, commits, ou frontend/localStorage. A chave entra apenas pelo formulário seguro da UI.

> ⚠️ Após conexão, realizar **apenas** validação não-monetária primeiro: autenticação read-only, inspeção de webhook, endpoint de status. **NÃO** criar customer/charge/PIX/boleto/transaction/refund/transfer automaticamente com a chave de produção. Uma compra real controlada é uma ação explícita e autorizada separadamente.

---

# 🔥 Próxima macrofase dev — Business Journeys & Contracting Hardening

> **Status:** 🟠 ROADMAP (em andamento — PR #21: B2C identity and entry journey hardening)
>
> Objetivo: provar que pessoas e empresas conseguem chegar à plataforma, contratar, pagar, receber acesso e recuperar sua conta sem intervenção manual.
>
> **Pode iniciar imediatamente em PRE-LAUNCH** usando mocks/fakes. Não requer ativação real do Asaas.

## P0 — Jornada B2C completa

- 🟠 Criar `docs/BUSINESS_JOURNEY_MATRIX.md` como documento vivo de cenários e estados esperados.
- 🟠 Preservar `redirect` em toda a cadeia: curso → login → cadastro → login/auto-login → curso.
- 🟠 Implementar auto-login seguro após cadastro público.
- 🟠 Voltar automaticamente ao curso que originou o cadastro.
- 🟠 Login com conta existente retorna ao curso pretendido.
- 🟠 Criar e-mail de boas-vindas/conta criada sem jamais enviar senha.
- 🟠 Criar e-mail de pagamento confirmado / curso liberado.
- 🟠 Criar CTA seguro "Acessar meu curso" no e-mail.
- 🟠 Validar fluxo completo com E2E: visitante → cadastro → compra → webhook → acesso → logout → login → acesso continua.
- 🟠 Garantir retomada de checkout abandonado no dia seguinte sem cobrança duplicada.
- 🟠 Garantir double-click/duas abas/concurrent purchase sem matrícula ou cobrança duplicada.
- 🟠 Cursos gratuitos (`price == 0`) sem gateway — matrícula direta, acesso e certificado normais.
- 🟠 Compra duplicada: alerta/reconciliação, nunca dois acessos.
- 🟠 Reembolso: política explícita de acesso ao curso após reembolso parcial/total.
- 🟠 Chargeback: política explícita de acesso/certificado após chargeback.
- 🟠 Compra como presente (avaliar regra futura).

## P0 — Login multi-tenant correto

- 🟠 Alterar login para consultar diretamente por `tenant_id + email` ou `tenant_id + CPF`.
- 🟠 Eliminar busca global que possa ficar ambígua quando o mesmo CPF/e-mail existir em WR e em um parceiro.
- 🟠 Adicionar E2E: mesma pessoa cadastrada em WR e Alfa usando o mesmo e-mail/CPF.
- 🟠 Garantir recuperação de senha e ativação também tenant-scoped do início ao fim.

## P0/P1 — Tentativas de pagamento

- 🟠 Definir lifecycle formal de tentativas de pagamento.
- 🟠 Pagamento recusado deve permanecer no histórico.
- 🟠 Nova tentativa deve gerar novo `Payment`/charge quando necessário, sem sobrescrever histórico.
- 🟠 Pagamento expirado deve poder ser retomado ou recriado explicitamente.
- 🟠 Pagamento duplicado deve gerar alerta/reconciliação, nunca dois acessos diferentes.
- 🟠 Reembolso/chargeback deve seguir política explícita de acesso ao curso.
- 🟠 Definir comportamento de matrícula após reembolso parcial/total.
- 🟠 Definir comportamento de certificado já emitido após reembolso/chargeback.

## P0/P1 — CPF/CNPJ e dados de contratação

- 🟠 Implementar validação matemática de CPF.
- 🟠 Implementar validação matemática de CNPJ.
- 🟠 Normalizar documentos de forma única no backend.
- 🟠 Mensagens amigáveis no frontend antes de chamar gateway.
- 🟠 Garantir que dados inválidos nunca criem customer/cobrança real.

---

# 🏢 B2B — Empresas cliente de treinamento

> **Status:** 🟠 ROADMAP
>
> Diferenciar empresa cliente de treinamento de parceiro white-label. Empresa cliente compra treinamento para seus funcionários; parceiro white-label opera sua própria academia.

## Jornada B2B

```
Empresa interessada em treinamento de funcionários
→ solicitação comercial
→ registro da empresa (Company)
→ funcionários/licenças
→ turmas/cursos
→ matrícula corporativa
→ cobrança consolidada/pagamento se aplicável
→ ativação de funcionários
→ treinamento
→ certificados
→ relatórios
```

## P1 — Funil público B2B

- 🟠 Criar jornada pública "Treinamento para minha empresa".
- 🟠 Formulário de interesse/orçamento com empresa, CNPJ, contato, quantidade de colaboradores e cursos desejados.
- 🟠 Diferenciar esse lead de `PartnerLead` white-label.
- 🟠 Criar acompanhamento administrativo do lead B2B.
- 🟠 Permitir converter lead em Company/contrato sem retrabalho manual.
- 🟠 Definir contratação por orçamento, cobrança consolidada ou checkout B2B conforme regra comercial.

## P1 — Funcionário já existente

- 🟠 Se CPF/e-mail já existir no tenant, permitir vincular o Student existente à empresa em vez de falhar.
- 🟠 Preservar histórico individual anterior.
- 🟠 Evitar criação de conta duplicada.
- 🟠 Auditar mudanças de vínculo empresa ↔ aluno.

## P1 — Convites corporativos

- 🟠 "Reenviar convite de ativação".
- 🟠 Invalidar/substituir token antigo quando necessário.
- 🟠 Expiração clara de convite.
- 🟠 Estado visual: convite pendente / ativado / expirado.
- 🟠 E-mail tenant-aware com domínio correto.
- 🟠 Importação CSV deve disparar/gerenciar convites sem expor tokens.

## P1 — Gestão de licenças/vagas

- 🟠 Empresa compra N vagas e pode alocar em momentos diferentes.
- 🟠 Exibir contratadas / usadas / disponíveis.
- 🟠 Permitir substituir funcionário antes do início segundo regra definida.
- 🟠 Impedir alocação além do contratado.
- 🟠 Preservar auditoria das alocações.
- 🟠 Licenças não utilizadas — política clara.
- 🟠 Recertificação — fluxo de reciclagem/periodicidade quando aplicável.

## P1/P2 — Offboarding corporativo

- 🟠 Funcionário desligado da empresa.
- 🟠 Definir se mantém acesso até fim da turma/contrato.
- 🟠 Remover vínculo sem apagar histórico.
- 🟠 Preservar certificado válido já emitido.
- 🟠 Registrar motivo/data do desligamento quando necessário.
- 🟠 Funcionário muda de empregador depois de certificado — preservar acesso histórico.

## P1/P2 — Relatórios corporativos

- 🟠 Relatório por empresa: colaboradores, matrículas, progresso, conclusão e certificados.
- 🟠 Exportação CSV/PDF conforme necessidade.
- 🟠 Histórico de batches de matrícula.
- 🟠 Auditoria para RH/empresa cliente.
- 🟠 Empresa solicita auditoria/exportação de todos os certificados.

---

# 🤝 Parceiros White-label — Lifecycle completo

> **Status:** 🟠 ROADMAP
>
> Parceiro white-label opera sua própria academia. Distinto de empresa cliente de treinamento.

## Jornada White-label

```
Partner lead
→ aprovação WR
→ tenant criado
→ ativação do admin do parceiro
→ onboarding guiado
→ configuração de marca
→ domínio customizado
→ integração financeira (gateway próprio)
→ catálogo
→ co-branding de certificado
→ operação
```

## P1 — Onboarding do parceiro

- 🟠 Lead → análise → aprovação → tenant → admin → ativação → onboarding guiado.
- 🟠 Nunca retornar token de ativação em plaintext em produção.
- 🟠 Checklist de onboarding:
  - 🟠 Dados da empresa.
  - 🟠 Logo e identidade.
  - 🟠 Domínio.
  - 🟠 Gateway financeiro.
  - 🟠 Certificado.
  - 🟠 Catálogo.
  - 🟠 Publicação.
- 🟠 Status de readiness do tenant.

## P1 — Política de suspensão/encerramento

- 🟠 Definir comportamento se parceiro ficar inadimplente.
- 🟠 Não destruir histórico dos alunos.
- 🟠 Definir acesso de alunos com cursos em andamento.
- 🟠 Preservar validação de certificados após encerramento.
- 🟠 Processo de exportação/portabilidade de dados quando aplicável.
- 🟠 Desativar gateway/webhooks/domínio de forma segura no offboarding.
- 🟠 Parceiro troca gateway financeiro.
- 🟠 Domínio customizado do parceiro fica indisponível.

## P2 — Billing SaaS do parceiro

- 🟠 Manter cobrança da assinatura white-label separada de compras de cursos.
- 🟠 Definir planos, recorrência, trial, inadimplência e grace period antes de automatizar cobrança.
- 🟠 Não misturar `TenantSubscription` com `Payment` de aluno/empresa.
- 🟠 Empresa se torna parceira white-label — transição de Company para Partner.

---

# 🎨 Product Experience & White-Label Studio 2.0

> **Status:** 🟠 ROADMAP
>
> Iniciar **somente depois** dos P0/P1 críticos de contratação (Business Journeys). Visual work begins AFTER business-journey hardening.

## UX PR 1 — Design System 2.0

- 🟠 Auditoria de componentes e telas.
- 🟠 Tokens visuais tenant-aware via CSS variables.
- 🟠 Padronizar botões, inputs, cards, tabelas, modais, badges, filtros, estados vazios/loading/error.
- 🟠 Iconografia consistente.
- 🟠 Tipografia e spacing system.
- 🟠 Melhorar sidebar/topbar e hierarquia visual.

## UX PR 2 — Brand Studio

- 🟠 Substituir formulário técnico de URLs por upload real de assets.
- 🟠 Logo principal, claro, escuro, compacto, favicon, OG/social, login artwork e hero.
- 🟠 Biblioteca de marca tenant-scoped.
- 🟠 Cores expandidas e seguras.
- 🟠 Tipografia aprovada.
- 🟠 Presets: Corporativo, Moderno, Minimalista, Premium, Industrial/Safety.
- 🟠 Preview ao vivo Desktop/Mobile.
- 🟠 Preview de login, sidebar, dashboard, course card, storefront e certificado.
- 🟠 Atomic save ou Draft/Published.

## UX PR 3 — Certificate Studio

- 🟠 Templates profissionais de certificado.
- 🟠 Co-branding WR + parceiro.
- 🟠 Inserir logos de fato no PDF.
- 🟠 QR Code de validação.
- 🟠 Assinatura/selo configurável conforme regra.
- 🟠 Preview e PDF de teste marcado como MODELO.
- 🟠 Campos acadêmicos imutáveis pelo parceiro.
- 🟠 Snapshot/versionamento do template no momento da emissão.
- 🟠 Melhorar página pública de validação.

## UX PR 4 — Course Content & Materials Studio

- 🟠 Separar tabs: Visão Geral, Conteúdo, Materiais, Aparência, Comercial, Certificação e Configurações.
- 🟠 Curriculum builder com módulos/seções.
- 🟠 Drag-and-drop de aulas.
- 🟠 Diferenciar conteúdo oficial WR de conteúdo complementar do parceiro.
- 🟠 Impedir fork/destruição acidental do conteúdo master WR.
- 🟠 Multi-upload de materiais.
- 🟠 Preview, descrição, tipo, tamanho, origem e versão.
- 🟠 Versionamento/auditoria de materiais.
- 🟠 Flags de download/visibilidade/obrigatoriedade.

## UX PR 5 — Admin / Partner Experience

- 🟠 Dashboard comercial premium com dados reais.
- 🟠 Navegação reorganizada por Academia, Pessoas, Comercial, Certificação, Personalização e Integrações.
- 🟠 Padronizar Courses, Classes, Companies, Students, Enrollments, Payments e Certificates.
- 🟠 Filtros, buscas, paginação e ações em massa consistentes.
- 🟠 Onboarding checklist visual.

## UX PR 6 — Student Experience & Course Player

- 🟠 Dashboard "Continue de onde parou".
- 🟠 Cards de curso mais ricos.
- 🟠 Course Player 2.0 com vídeo + currículo lateral + materiais + navegação anterior/próxima.
- 🟠 Curriculum drawer no mobile.
- 🟠 Estados de erro/loading de vídeo profissionais.
- 🟠 Melhor experiência de certificados/conquistas.

## UX PR 7 — Storefront / Catálogo / Checkout

- 🟠 Catálogo premium e responsivo.
- 🟠 Busca e filtros reais.
- 🟠 Course Detail orientada à conversão.
- 🟠 Melhor apresentação de carga horária, público, conteúdo, certificado e provedor.
- 🟠 Checkout/retorno de pagamento claro e provider-agnostic.
- 🟠 Não expor infraestrutura técnica desnecessariamente.

## UX PR 8 — Accessibility / Responsive / Visual Regression

- 🟠 WCAG-oriented audit.
- 🟠 Keyboard/focus/modal accessibility.
- 🟠 Contraste e labels.
- 🟠 Responsive audit em 320/360/390/430/768/1024/1440/1920.
- 🟠 Visual screenshot regression para telas críticas.
- 🟠 `prefers-reduced-motion`.
- 🟠 Performance/bundle/image audit.

---

# 📈 Growth, aquisição e conversão

> **Status:** 🟠 ROADMAP

## P1/P2 — SEO e descoberta orgânica

- 🟠 Metadata dinâmica por curso/tenant.
- 🟠 Canonical URLs.
- 🟠 Sitemap de cursos públicos.
- 🟠 Robots corretamente configurado.
- 🟠 Open Graph/social cards.
- 🟠 Structured data/Schema.org quando adequado.
- 🟠 Garantir páginas indexáveis sem exigir autenticação.
- 🟠 Landing pages por categoria/curso quando fizer sentido.

## P2 — Funil e recuperação de abandono

- 🟠 Analytics de catálogo → curso → cadastro → checkout → pagamento → acesso.
- 🟠 Eventos de conversão tenant-aware.
- 🟠 Checkout abandonado.
- 🟠 E-mail de retomada quando permitido e consentido.
- 🟠 Métrica de conversão por curso/parceiro.
- 🟠 Não criar automações invasivas sem política de consentimento.

---

# 🔁 Cenários de negócio que devem possuir comportamento documentado/testado

> **Status:** 🟠 ROADMAP — cenários de validação para Business Journeys.

- 🟠 Pessoa encontra curso no Google e compra pela primeira vez.
- 🟠 Cliente existente compra segundo curso.
- 🟠 Cliente abandona checkout e volta horas/dias depois.
- 🟠 Pagamento Pix ocorre com navegador fechado.
- 🟠 Boleto é pago posteriormente.
- 🟠 Cartão é recusado e nova tentativa é feita.
- 🟠 Cobrança é duplicada pelo provider/retry.
- 🟠 Curso é gratuito.
- 🟠 Curso não possui turma aberta.
- 🟠 Todas as turmas estão lotadas.
- 🟠 Usuário abre compra em duas abas simultaneamente.
- 🟠 Mesmo CPF/e-mail existe em WR e parceiro white-label.
- 🟠 Cliente individual passa a ser funcionário de uma Company.
- 🟠 Funcionário já possui conta antes do convite corporativo.
- 🟠 Convite corporativo expira/não chega.
- 🟠 Empresa compra 100 vagas e usa apenas 60 inicialmente.
- 🟠 RH troca funcionário antes do início do treinamento.
- 🟠 Funcionário sai da empresa no meio do curso.
- 🟠 Funcionário muda de empregador depois de certificado.
- 🟠 Empresa compra treinamento sem querer ser parceira white-label.
- 🟠 Empresa se torna parceira white-label.
- 🟠 Parceiro fica inadimplente com alunos em andamento.
- 🟠 Parceiro encerra operação com certificados emitidos.
- 🟠 Parceiro troca gateway financeiro.
- 🟠 Domínio customizado do parceiro fica indisponível.
- 🟠 WR atualiza conteúdo oficial enquanto alunos estão cursando.
- 🟠 WR substitui material oficial após turmas anteriores concluírem.
- 🟠 Aluno precisa recertificar após prazo/regra do curso.
- 🟠 Cliente pede reembolso antes de iniciar.
- 🟠 Cliente pede reembolso depois de consumir parte do curso.
- 🟠 Chargeback ocorre depois da conclusão/certificação.
- 🟠 Compra é feita como presente para outra pessoa (avaliar regra futura).
- 🟠 Empresa solicita auditoria/exportação de todos os certificados.
- 🟠 Webhook fica indisponível e precisa de reconciliação posterior.
- 🟠 E-mail transacional falha, mas pagamento/matrícula continuam consistentes.

---

# 🔐 Segurança, LGPD e operação comercial

> **Status:** 🟠 ROADMAP

## P1

- 🟠 Revisar termos de uso, política de privacidade e aceite no cadastro/contratação.
- 🟠 Definir base legal/consentimento para comunicações transacionais e marketing.
- 🟠 Minimização e retenção de CPF/CNPJ/dados pessoais.
- 🟠 Fluxo de solicitação de dados/exclusão quando juridicamente aplicável, sem apagar registros obrigatórios.
- 🟠 Política formal de reembolso/cancelamento.
- 🟠 Definir emissão fiscal/NF e responsabilidade comercial/fiscal por tenant/WR antes de automatizar.
- 🟠 Audit log para ações administrativas sensíveis.
- 🟠 Observabilidade para falhas de e-mail, gateway e webhook.
- 🟠 Job/processo de reconciliação financeira periódica independente do webhook.
- 🟠 Alertas para pagamento aprovado sem matrícula confirmada e outros estados inconsistentes.

---

# 🧪 Quality Gates permanentes

> **Status:** 🟢 VALIDATED LOCALLY (gates atuais passando) / 🟠 ROADMAP (para novas jornadas)

- 🟢 `pytest -q` — 658 passaram, 0 falharam, 0 pulados.
- 🟢 Backend coverage — 75.44% (gate 75%).
- 🟢 `ruff check app tests` — sem erros.
- 🟢 `python -m compileall app` — passando.
- 🟢 Frontend unit tests — 337 passaram.
- 🟢 ESLint — sem erros.
- 🟢 Production build — passando.
- 🟢 Playwright integration E2E — 31 passaram.
- 🟢 Playwright ui-mocked E2E — 63 passaram.
- 🟢 White-label regression WR/Alfa.
- 🟢 Cross-tenant isolation regression.
- 🟢 Alembic — exatamente um head (`a1b3c4d5e6f7`).
- ⚪ CI sem necessidade de credencial financeira real.
- ⚪ Nenhum secret real em Git, logs, screenshots, testes ou PRs.
- 🟠 Toda nova jornada P0/P1 deve ter teste backend + E2E quando aplicável.
- 🟠 Fresh migration e upgrade de banco existente validados (para novas migrations).

---

# 🗺️ Ordem recomendada de execução

1. ✅ **Asaas Production Payments (#19)** — código mergeado em `main`.
2. � **PRE-LAUNCH / HOMOLOGAÇÃO** — Vercel + Railway atuais (decisão owner).
3. 🟠 **Business Journeys & Contracting Hardening** — P0/P1 B2C, multi-tenant identity, B2B e white-label lifecycle (em andamento).
4. 🟠 **Regras comerciais/fiscais/LGPD e lifecycle financeiro** — reembolso, corporate billing, fiscal/LGPD.
5. 🟠 **NR EAD Compliance & Trusted Certificates** — ver `docs/NR_EAD_COMPLIANCE_ROADMAP.md`.
6. 🟠 **Product Experience & White-Label Studio 2.0** — 8 PRs sequenciais (após business hardening).
7. 🟠 **Content Readiness + carga dos cursos reais + homologação CEO.**
8. 🟠 **Growth / SEO / Conversion** — aquisição e recuperação de abandono.
9. ⚪ **Domínio oficial definido/registrado.**
10. 🟡 **Official Launch Gate** — infraestrutura final + Asaas real + smoke/E2E controlado.
11. 🟡 **Real Asaas activation** — inserção da chave de produção pelo owner via UI segura.
12. ✅ **Lançamento comercial oficial**, após autorização do owner.

---

## Notas de arquitetura

- Backend: FastAPI + SQLAlchemy async + Alembic + PostgreSQL.
- Frontend: Vue 3 + Vite + Pinia + Tailwind.
- Multi-tenant: tenant resolvido por contexto/domínio + tenant scoping + RLS onde aplicável.
- Storage: tenant-aware com URLs presignadas.
- Payments: provider abstraction com Mercado Pago e Asaas (production-capable, mergeado).
- Deploy: backend em infraestrutura containerizada + frontends Vercel/white-label.

## Princípio de produto

A plataforma deve suportar três jornadas comerciais distintas sem confundi-las:

1. **B2C — Pessoa física:** encontra curso → cria conta → paga → estuda → certifica.
2. **B2B — Empresa cliente de treinamento:** contrata treinamento → cadastra/aloca funcionários → acompanha → certifica.
3. **White-label Partner:** torna-se parceiro → recebe tenant → configura marca/domínio/gateway → comercializa/opera sua academia.

> B2B (empresa cliente) e White-label Partner são fluxos distintos. Empresa cliente compra treinamento para seus funcionários. Parceiro white-label opera sua própria academia sob sua marca.
