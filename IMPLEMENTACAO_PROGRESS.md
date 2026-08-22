# 📊 Roadmap de Implementação — WR Plataforma de Cursos

> Atualizado em 22/08/2026.
>
> Este documento substitui o roadmap inicial, que já não refletia o estado real da plataforma. O foco atual deixou de ser apenas CRUD e passou a cobrir produção financeira, jornadas B2C/B2B, operação white-label, experiência de produto, segurança e escala.

## Legenda de prioridade

- **P0 — Bloqueador de produção:** pode causar perda financeira, acesso incorreto, falha crítica de segurança ou impedir contratação/acesso.
- **P1 — Alta prioridade:** necessário para uma operação comercial confiável e profissional.
- **P2 — Evolução importante:** melhora escala, experiência, retenção e operação.
- **P3 — Futuro/otimização:** evolução posterior sem bloquear a operação atual.

---

# ✅ Concluído / Base atual

## Autenticação, segurança e multi-tenant
- [x] Login por CPF ou e-mail.
- [x] Registro público de alunos.
- [x] JWT access + refresh tokens.
- [x] Roles `STUDENT`, `ADMIN` e `SUPER_ADMIN`.
- [x] Proteção de rotas frontend/backend.
- [x] Resolução de tenant por domínio/contexto.
- [x] Isolamento multi-tenant em grande parte dos módulos principais.
- [x] Recuperação de senha e tokens one-time.
- [x] Ativação de contas corporativas/parceiros.

## Cursos, turmas e aprendizagem
- [x] CRUD de cursos.
- [x] CRUD de turmas.
- [x] Matrículas individuais e corporativas.
- [x] Aulas com upload, YouTube e Vimeo.
- [x] Materiais por aula.
- [x] Progresso por aula.
- [x] Curso liberado apenas para matrícula `CONFIRMADA`/`CONCLUIDA`.
- [x] Certificados e validação pública.
- [x] Upload/armazenamento tenant-aware para conteúdo de aulas.

## Empresas e onboarding corporativo
- [x] CRUD de empresas.
- [x] Cadastro de funcionários.
- [x] Importação CSV de funcionários.
- [x] Ativação de funcionário via token.
- [x] Matrícula em lote.
- [x] `EnrollmentSource.INDIVIDUAL` e `EnrollmentSource.CORPORATE`.
- [x] `CorporateEnrollmentBatch`.
- [x] Base para cobrança corporativa consolidada.

## White-label
- [x] Tenant por parceiro.
- [x] Logo, favicon e cores básicas.
- [x] Domínio customizado.
- [x] Isolamento WR / Alfa demo.
- [x] Formulário público “Seja parceiro”.
- [x] Aprovação de parceiro pelo SUPER_ADMIN.
- [x] Criação do tenant e administrador do parceiro.

## Frontend
- [x] Vue 3 + Vite + Pinia.
- [x] Application shell autenticado com sidebar/topbar.
- [x] Layout público separado.
- [x] Catálogo público de cursos.
- [x] Página pública de detalhe do curso.
- [x] Dashboard por role.
- [x] Course player funcional.
- [x] Componentes reutilizáveis (`AppButton`, `AppCard`, `AppModal`, `AppAlert`, etc.).
- [x] Responsividade base.

## Qualidade
- [x] Suíte backend extensa.
- [x] Vitest frontend.
- [x] Playwright E2E.
- [x] CI GitHub Actions.
- [x] Testes de tenant isolation/security regressions.
- [x] Alembic com single-head validado nas fases recentes.

---

# 🚧 Em andamento agora

## P0 — Asaas Production Payments / PR #19

> Esta fase está sendo finalizada antes de qualquer grande redesign.

- [ ] Finalizar hardening do PR #19 e manter CI totalmente verde.
- [ ] Implementar/reconciliar webhook real no Asaas via API, evitando configuração manual frágil.
- [ ] Garantir `User-Agent` explícito em todas as chamadas Asaas.
- [ ] Sanitizar erros do provider para não devolver `response.text` bruto ao cliente.
- [ ] Usar `Payment.id` como `externalReference` da cobrança.
- [ ] Validar no webhook: tenant, provider, provider payment ID, `externalReference`, valor e customer quando aplicável.
- [ ] Corrigir race condition webhook ↔ persistência do `provider_payment_id`.
- [ ] Tornar ledger de webhook recuperável (`RECEIVED/PENDING_MATCH/PROCESSED/...`) e realmente idempotente sob concorrência.
- [ ] Reconciliar mapa de eventos com a documentação atual do Asaas.
- [ ] Fail-closed em produção para `ASAAS_MOCK_MODE=true`.
- [ ] Fail-closed/estado explícito para `EMAIL_MOCK_MODE` em produção.
- [ ] Validar prefixo da chave de produção `$aact_prod_` sem remover `$`.
- [ ] Garantir navegação real para `Configurações → Financeiro` no AppShell atual.
- [ ] Fazer `/integrations/asaas/status` refletir estado remoto real do webhook/conexão.
- [ ] Finalizar UX de retorno do pagamento (“Estamos confirmando seu pagamento…”).
- [ ] Tornar cobrança corporativa consolidada realmente utilizável ou remover opção incompleta.
- [ ] Garantir que tokens de ativação/reset não sejam expostos em respostas HTTP de produção.
- [ ] Mergear PR #19 somente após todos os P0 acima + CI verde.
- [ ] Deploy, migrations, health checks e conexão segura da chave de produção pelo Admin WR.
- [ ] Primeira compra real controlada após go-live, sem criar transações artificiais de teste.

---

# 🔥 Próxima macrofase — Business Journeys & Contracting Hardening

> Objetivo: provar que pessoas e empresas conseguem chegar à plataforma, contratar, pagar, receber acesso e recuperar sua conta sem intervenção manual.

## P0 — Jornada B2C completa

- [ ] Criar `docs/BUSINESS_JOURNEY_MATRIX.md` como documento vivo de cenários e estados esperados.
- [ ] Preservar `redirect` em toda a cadeia: curso → login → cadastro → login/auto-login → curso.
- [ ] Implementar auto-login seguro após cadastro público.
- [ ] Voltar automaticamente ao curso que originou o cadastro.
- [ ] Criar e-mail de boas-vindas/conta criada sem jamais enviar senha.
- [ ] Criar e-mail de pagamento confirmado / curso liberado.
- [ ] Criar CTA seguro “Acessar meu curso” no e-mail.
- [ ] Validar fluxo completo com E2E: visitante → cadastro → compra → webhook → acesso → logout → login → acesso continua.
- [ ] Garantir retomada de checkout abandonado no dia seguinte sem cobrança duplicada.
- [ ] Garantir double-click/duas abas/concurrent purchase sem matrícula ou cobrança duplicada.

## P0 — Login multi-tenant correto

- [ ] Alterar login para consultar diretamente por `tenant_id + email` ou `tenant_id + CPF`.
- [ ] Eliminar busca global que possa ficar ambígua quando o mesmo CPF/e-mail existir em WR e em um parceiro.
- [ ] Adicionar E2E: mesma pessoa cadastrada em WR e Alfa usando o mesmo e-mail/CPF.
- [ ] Garantir recuperação de senha e ativação também tenant-scoped do início ao fim.

## P0 — Cursos gratuitos

- [ ] Implementar fluxo `price == 0` sem gateway.
- [ ] Criar matrícula diretamente em estado permitido pelas regras do produto.
- [ ] Não criar cobrança Asaas/Mercado Pago para curso gratuito.
- [ ] Garantir acesso e certificado normalmente após conclusão.
- [ ] Criar E2E de curso gratuito.

## P0/P1 — Tentativas de pagamento

- [ ] Definir lifecycle formal de tentativas de pagamento.
- [ ] Pagamento recusado deve permanecer no histórico.
- [ ] Nova tentativa deve gerar novo `Payment`/charge quando necessário, sem sobrescrever histórico.
- [ ] Pagamento expirado deve poder ser retomado ou recriado explicitamente.
- [ ] Pagamento duplicado deve gerar alerta/reconciliação, nunca dois acessos diferentes.
- [ ] Reembolso/chargeback deve seguir política explícita de acesso ao curso.
- [ ] Definir comportamento de matrícula após reembolso parcial/total.
- [ ] Definir comportamento de certificado já emitido após reembolso/chargeback.

## P0/P1 — CPF/CNPJ e dados de contratação

- [ ] Implementar validação matemática de CPF.
- [ ] Implementar validação matemática de CNPJ.
- [ ] Normalizar documentos de forma única no backend.
- [ ] Mensagens amigáveis no frontend antes de chamar gateway.
- [ ] Garantir que dados inválidos nunca criem customer/cobrança real.

---

# 🏢 B2B — Empresas comprando treinamentos

> Diferenciar empresa cliente de treinamento de parceiro white-label.

## P1 — Funil público B2B

- [ ] Criar jornada pública “Treinamento para minha empresa”.
- [ ] Formulário de interesse/orçamento com empresa, CNPJ, contato, quantidade de colaboradores e cursos desejados.
- [ ] Diferenciar esse lead de `PartnerLead` white-label.
- [ ] Criar acompanhamento administrativo do lead B2B.
- [ ] Permitir converter lead em Company/contrato sem retrabalho manual.
- [ ] Definir contratação por orçamento, cobrança consolidada ou checkout B2B conforme regra comercial.

## P1 — Funcionário já existente

- [ ] Se CPF/e-mail já existir no tenant, permitir vincular o Student existente à empresa em vez de falhar.
- [ ] Preservar histórico individual anterior.
- [ ] Evitar criação de conta duplicada.
- [ ] Auditar mudanças de vínculo empresa ↔ aluno.

## P1 — Convites corporativos

- [ ] “Reenviar convite de ativação”.
- [ ] Invalidar/substituir token antigo quando necessário.
- [ ] Expiração clara de convite.
- [ ] Estado visual: convite pendente / ativado / expirado.
- [ ] E-mail tenant-aware com domínio correto.
- [ ] Importação CSV deve disparar/gerenciar convites sem expor tokens.

## P1 — Gestão de licenças/vagas

- [ ] Empresa compra N vagas e pode alocar em momentos diferentes.
- [ ] Exibir contratadas / usadas / disponíveis.
- [ ] Permitir substituir funcionário antes do início segundo regra definida.
- [ ] Impedir alocação além do contratado.
- [ ] Preservar auditoria das alocações.

## P1/P2 — Offboarding corporativo

- [ ] Funcionário desligado da empresa.
- [ ] Definir se mantém acesso até fim da turma/contrato.
- [ ] Remover vínculo sem apagar histórico.
- [ ] Preservar certificado válido já emitido.
- [ ] Registrar motivo/data do desligamento quando necessário.

## P1/P2 — Relatórios corporativos

- [ ] Relatório por empresa: colaboradores, matrículas, progresso, conclusão e certificados.
- [ ] Exportação CSV/PDF conforme necessidade.
- [ ] Histórico de batches de matrícula.
- [ ] Auditoria para RH/empresa cliente.

---

# 🤝 Parceiros White-label — Lifecycle completo

## P1 — Onboarding do parceiro

- [ ] Lead → análise → aprovação → tenant → admin → ativação → onboarding guiado.
- [ ] Nunca retornar token de ativação em plaintext em produção.
- [ ] Checklist de onboarding:
  - [ ] Dados da empresa.
  - [ ] Logo e identidade.
  - [ ] Domínio.
  - [ ] Gateway financeiro.
  - [ ] Certificado.
  - [ ] Catálogo.
  - [ ] Publicação.
- [ ] Status de readiness do tenant.

## P1 — Política de suspensão/encerramento

- [ ] Definir comportamento se parceiro ficar inadimplente.
- [ ] Não destruir histórico dos alunos.
- [ ] Definir acesso de alunos com cursos em andamento.
- [ ] Preservar validação de certificados após encerramento.
- [ ] Processo de exportação/portabilidade de dados quando aplicável.
- [ ] Desativar gateway/webhooks/domínio de forma segura no offboarding.

## P2 — Billing SaaS do parceiro

- [ ] Manter cobrança da assinatura white-label separada de compras de cursos.
- [ ] Definir planos, recorrência, trial, inadimplência e grace period antes de automatizar cobrança.
- [ ] Não misturar `TenantSubscription` com `Payment` de aluno/empresa.

---

# 🎨 Product Experience & White-Label Studio 2.0

> Iniciar somente depois dos P0/P1 críticos de contratação.

## UX PR 1 — Design System 2.0

- [ ] Auditoria de componentes e telas.
- [ ] Tokens visuais tenant-aware via CSS variables.
- [ ] Padronizar botões, inputs, cards, tabelas, modais, badges, filtros, estados vazios/loading/error.
- [ ] Iconografia consistente.
- [ ] Tipografia e spacing system.
- [ ] Melhorar sidebar/topbar e hierarquia visual.

## UX PR 2 — Brand Studio

- [ ] Substituir formulário técnico de URLs por upload real de assets.
- [ ] Logo principal, claro, escuro, compacto, favicon, OG/social, login artwork e hero.
- [ ] Biblioteca de marca tenant-scoped.
- [ ] Cores expandidas e seguras.
- [ ] Tipografia aprovada.
- [ ] Presets: Corporativo, Moderno, Minimalista, Premium, Industrial/Safety.
- [ ] Preview ao vivo Desktop/Mobile.
- [ ] Preview de login, sidebar, dashboard, course card, storefront e certificado.
- [ ] Atomic save ou Draft/Published.

## UX PR 3 — Certificate Studio

- [ ] Templates profissionais de certificado.
- [ ] Co-branding WR + parceiro.
- [ ] Inserir logos de fato no PDF.
- [ ] QR Code de validação.
- [ ] Assinatura/selo configurável conforme regra.
- [ ] Preview e PDF de teste marcado como MODELO.
- [ ] Campos acadêmicos imutáveis pelo parceiro.
- [ ] Snapshot/versionamento do template no momento da emissão.
- [ ] Melhorar página pública de validação.

## UX PR 4 — Course Content & Materials Studio

- [ ] Separar tabs: Visão Geral, Conteúdo, Materiais, Aparência, Comercial, Certificação e Configurações.
- [ ] Curriculum builder com módulos/seções.
- [ ] Drag-and-drop de aulas.
- [ ] Diferenciar conteúdo oficial WR de conteúdo complementar do parceiro.
- [ ] Impedir fork/destruição acidental do conteúdo master WR.
- [ ] Multi-upload de materiais.
- [ ] Preview, descrição, tipo, tamanho, origem e versão.
- [ ] Versionamento/auditoria de materiais.
- [ ] Flags de download/visibilidade/obrigatoriedade.

## UX PR 5 — Admin / Partner Experience

- [ ] Dashboard comercial premium com dados reais.
- [ ] Navegação reorganizada por Academia, Pessoas, Comercial, Certificação, Personalização e Integrações.
- [ ] Padronizar Courses, Classes, Companies, Students, Enrollments, Payments e Certificates.
- [ ] Filtros, buscas, paginação e ações em massa consistentes.
- [ ] Onboarding checklist visual.

## UX PR 6 — Student Experience & Course Player

- [ ] Dashboard “Continue de onde parou”.
- [ ] Cards de curso mais ricos.
- [ ] Course Player 2.0 com vídeo + currículo lateral + materiais + navegação anterior/próxima.
- [ ] Curriculum drawer no mobile.
- [ ] Estados de erro/loading de vídeo profissionais.
- [ ] Melhor experiência de certificados/conquistas.

## UX PR 7 — Storefront / Catálogo / Checkout

- [ ] Catálogo premium e responsivo.
- [ ] Busca e filtros reais.
- [ ] Course Detail orientada à conversão.
- [ ] Melhor apresentação de carga horária, público, conteúdo, certificado e provedor.
- [ ] Checkout/retorno de pagamento claro e provider-agnostic.
- [ ] Não expor infraestrutura técnica desnecessariamente.

## UX PR 8 — Accessibility / Responsive / Visual Regression

- [ ] WCAG-oriented audit.
- [ ] Keyboard/focus/modal accessibility.
- [ ] Contraste e labels.
- [ ] Responsive audit em 320/360/390/430/768/1024/1440/1920.
- [ ] Visual screenshot regression para telas críticas.
- [ ] `prefers-reduced-motion`.
- [ ] Performance/bundle/image audit.

---

# 📈 Growth, aquisição e conversão

## P1/P2 — SEO e descoberta orgânica

- [ ] Metadata dinâmica por curso/tenant.
- [ ] Canonical URLs.
- [ ] Sitemap de cursos públicos.
- [ ] Robots corretamente configurado.
- [ ] Open Graph/social cards.
- [ ] Structured data/Schema.org quando adequado.
- [ ] Garantir páginas indexáveis sem exigir autenticação.
- [ ] Landing pages por categoria/curso quando fizer sentido.

## P2 — Funil e recuperação de abandono

- [ ] Analytics de catálogo → curso → cadastro → checkout → pagamento → acesso.
- [ ] Eventos de conversão tenant-aware.
- [ ] Checkout abandonado.
- [ ] E-mail de retomada quando permitido e consentido.
- [ ] Métrica de conversão por curso/parceiro.
- [ ] Não criar automações invasivas sem política de consentimento.

---

# 🔁 Cenários de negócio que devem possuir comportamento documentado/testado

- [ ] Pessoa encontra curso no Google e compra pela primeira vez.
- [ ] Cliente existente compra segundo curso.
- [ ] Cliente abandona checkout e volta horas/dias depois.
- [ ] Pagamento Pix ocorre com navegador fechado.
- [ ] Boleto é pago posteriormente.
- [ ] Cartão é recusado e nova tentativa é feita.
- [ ] Cobrança é duplicada pelo provider/retry.
- [ ] Curso é gratuito.
- [ ] Curso não possui turma aberta.
- [ ] Todas as turmas estão lotadas.
- [ ] Usuário abre compra em duas abas simultaneamente.
- [ ] Mesmo CPF/e-mail existe em WR e parceiro white-label.
- [ ] Cliente individual passa a ser funcionário de uma Company.
- [ ] Funcionário já possui conta antes do convite corporativo.
- [ ] Convite corporativo expira/não chega.
- [ ] Empresa compra 100 vagas e usa apenas 60 inicialmente.
- [ ] RH troca funcionário antes do início do treinamento.
- [ ] Funcionário sai da empresa no meio do curso.
- [ ] Funcionário muda de empregador depois de certificado.
- [ ] Empresa compra treinamento sem querer ser parceira white-label.
- [ ] Empresa se torna parceira white-label.
- [ ] Parceiro fica inadimplente com alunos em andamento.
- [ ] Parceiro encerra operação com certificados emitidos.
- [ ] Parceiro troca gateway financeiro.
- [ ] Domínio customizado do parceiro fica indisponível.
- [ ] WR atualiza conteúdo oficial enquanto alunos estão cursando.
- [ ] WR substitui material oficial após turmas anteriores concluírem.
- [ ] Aluno precisa recertificar após prazo/regra do curso.
- [ ] Cliente pede reembolso antes de iniciar.
- [ ] Cliente pede reembolso depois de consumir parte do curso.
- [ ] Chargeback ocorre depois da conclusão/certificação.
- [ ] Compra é feita como presente para outra pessoa (avaliar regra futura).
- [ ] Empresa solicita auditoria/exportação de todos os certificados.
- [ ] Webhook fica indisponível e precisa de reconciliação posterior.
- [ ] E-mail transacional falha, mas pagamento/matrícula continuam consistentes.

---

# 🔐 Segurança, LGPD e operação comercial

## P1

- [ ] Revisar termos de uso, política de privacidade e aceite no cadastro/contratação.
- [ ] Definir base legal/consentimento para comunicações transacionais e marketing.
- [ ] Minimização e retenção de CPF/CNPJ/dados pessoais.
- [ ] Fluxo de solicitação de dados/exclusão quando juridicamente aplicável, sem apagar registros obrigatórios.
- [ ] Política formal de reembolso/cancelamento.
- [ ] Definir emissão fiscal/NF e responsabilidade comercial/fiscal por tenant/WR antes de automatizar.
- [ ] Audit log para ações administrativas sensíveis.
- [ ] Observabilidade para falhas de e-mail, gateway e webhook.
- [ ] Job/processo de reconciliação financeira periódica independente do webhook.
- [ ] Alertas para pagamento aprovado sem matrícula confirmada e outros estados inconsistentes.

---

# 🧪 Quality Gates permanentes

- [ ] Toda nova jornada P0/P1 deve ter teste backend + E2E quando aplicável.
- [ ] `pytest -q` sem falhas.
- [ ] `ruff check app tests` sem erros.
- [ ] `python -m compileall app` passando.
- [ ] Frontend unit tests sem falhas.
- [ ] ESLint sem erros.
- [ ] Production build passando.
- [ ] Playwright ui-mocked/full-stack conforme escopo.
- [ ] White-label regression WR/Alfa.
- [ ] Cross-tenant isolation regression.
- [ ] Alembic com exatamente um head.
- [ ] Fresh migration e upgrade de banco existente validados.
- [ ] CI sem necessidade de credencial financeira real.
- [ ] Nenhum secret real em Git, logs, screenshots, testes ou PRs.

---

# 🗺️ Ordem recomendada de execução

1. **Concluir Asaas Production Hardening (#19)** — P0 financeiro.
2. **Business Journeys & Contracting Hardening** — P0/P1 B2C e B2B.
3. **Fechar regras comerciais pendentes** — reembolso, corporate billing, fiscal/LGPD.
4. **Product Experience & White-Label Studio 2.0** — 8 PRs sequenciais.
5. **Growth / SEO / Conversion** — aquisição e recuperação de abandono.
6. **Escala operacional** — reconciliação, auditoria, alertas, relatórios avançados e automações.

---

## Notas de arquitetura

- Backend: FastAPI + SQLAlchemy async + Alembic + PostgreSQL.
- Frontend: Vue 3 + Vite + Pinia + Tailwind.
- Multi-tenant: tenant resolvido por contexto/domínio + tenant scoping + RLS onde aplicável.
- Storage: tenant-aware com URLs presignadas.
- Payments: provider abstraction com Mercado Pago e evolução atual para Asaas.
- Deploy: backend em infraestrutura containerizada + frontends Vercel/white-label.

## Princípio de produto

A plataforma deve suportar três jornadas comerciais distintas sem confundi-las:

1. **B2C — Pessoa física:** encontra curso → cria conta → paga → estuda → certifica.
2. **B2B — Empresa cliente:** contrata treinamento → cadastra/aloca funcionários → acompanha → certifica.
3. **White-label Partner:** torna-se parceiro → recebe tenant → configura marca/domínio/gateway → comercializa/opera sua academia.

Toda nova funcionalidade deve declarar explicitamente qual dessas jornadas afeta e possuir comportamento definido para happy path, abandono, erro, retry e recuperação.