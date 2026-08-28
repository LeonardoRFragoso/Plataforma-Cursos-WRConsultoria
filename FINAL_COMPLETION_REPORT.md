# Relatório final de conclusão — B2B, isolamento multi-tenant e progresso acadêmico

Data: 2026-08-28  
Branch: `feat/central-b2b-readonly-api`

## Resumo executivo

Foram concluídas e validadas as fases técnicas 1–29, incluindo hardening B2B, isolamento multi-tenant, progresso acadêmico, SSO, compliance regulatório, evidências, certificados, pagamentos, documentação e gate de migrações. As alterações foram separadas em commits pequenos e auditáveis.

As fases de regressão completa e smoke foram executadas conforme autorização após o freeze. Todos os 86 testes Playwright passam após correção de porta (API_BASE :8001) e mocks alinhados com o frontend atual. O smoke test Central WR → LMS foi executado com sucesso (happy-path, casos negativos, LMS offline fail-closed).

## Entregas concluídas

### Fases 1–2 — Contexto B2B e RLS

- Rotas `/api/v1/b2b/*` bypassam o `TenantResolver` genérico.
- O `B2BClient.tenant_id` é a autoridade do tenant para requisições B2B.
- Enforcement de assinatura ocorre após autenticação B2B.
- Removido o uso desnecessário de `bypass_rls` no contexto B2B.
- Contexto de sessão B2B não usa `app.bypass_rls = '1'`.

### Fase 3 — RLS com migrações reais

- Criado `api/tests/test_b2b_rls_migration_isolation.py`.
- O teste cria um banco temporário, executa migrações Alembic reais até a revisão de schema necessária e verifica `pg_class`/`pg_policies`.
- Verificada a existência de RLS nas tabelas acadêmicas e isolamento por tenant via HTTP.
- Resultado: 9 testes passando.

### Fase 4 — Concorrência multi-tenant

- Criado `api/tests/test_b2b_concurrent_isolation.py`.
- Uso de `asyncio.gather` com requisições concorrentes para context, summary, courses, enrollments e combinações mistas.
- Verificados reset de `ContextVar`, isolamento RLS e ausência de mistura de respostas.
- Resultado: 5 testes passando.

### Fase 5 — Filtros explícitos e fail-closed

- Adicionados filtros explícitos `tenant_id` nos joins B2B de cursos, turmas, alunos, matrículas, certificados e progresso.
- `get_enrollment` retorna 404 quando uma referência inconsistente aponta para turma/curso de outro tenant.
- Criado `api/tests/test_b2b_tenant_filter_failclosed.py` com registros deliberadamente inconsistentes e RLS desativado.
- Resultado: 4 testes passando.

### Fase 6 — Progresso acadêmico canônico

- Criado `api/app/services/progress_service.py`.
- Regra única: `completed_required / required_lessons * 100`.
- Aulas opcionais não influenciam percentual nem elegibilidade de certificado.
- B2B e endpoint de progresso do aluno usam o mesmo serviço/regra.
- Criado `api/tests/test_progress_canonical.py`.
- Resultado: 5 testes passando.

### Fase 7 — Taxonomia de status

- Removido `in_progress = total - completed`.
- `in_progress` agora conta explicitamente apenas matrículas `CONFIRMADA` (em andamento).
- `PENDENTE` é pendente (sem acesso ao curso) e não é contado como ativo ou em andamento.
- `active_students` e `active_enrollments` no B2B summary contam apenas `CONFIRMADA`.
- Matrículas canceladas e estados terminais não são classificadas como em andamento.
- Coberto pelo teste canônico de progresso e por `test_b2b_summarypendente_not_counted_as_active`.

### Fase 8 — Hardening do SSO

- Usuário LMS `student` existente não é mais promovido para `admin` via SSO.
- Tentativa de login SSO para conta local sem perfil administrativo retorna 403.
- A conta permanece com o papel original.
- Teste existente foi atualizado para validar rejeição sem promoção.
- Resultado: 31 testes SSO passando.

### Fase 9 — Versão da API

- `B2BContextResponse` inclui `api_version: str = "1"`.
- `/api/v1/b2b/context` retorna explicitamente `api_version="1"`.

### Fase 10 — Paginação tipada

- `B2BPageResponse[T]` implementado com genérico Pydantic.
- Endpoints de courses, classes, students, enrollments e certificates declaram o tipo concreto do envelope.
- Ruff passou nos arquivos de schema/rota alterados.

## Commits realizados

- `ac0a7f0` — teste RLS com migrações Alembic reais
- `df73592` — teste de stress concorrente multi-tenant
- `0427b5b` — filtros explícitos de tenant, fail-closed e `api_version`
- `0045834` — cálculo canônico de progresso obrigatório
- `8e26c84` — taxonomia explícita de status de matrícula
- `cca48d1` — rejeição de promoção SSO de estudante local e paginação tipada
- `e5073c6` — hardening de segredos B2B e rate limiting
- `5f32437` — migrações fresh/downgrade seguras e freeze matrix

### Fases 11–12 — Segredos e rate limiting

- Bootstrap B2B exige segredo mínimo de 32 caracteres.
- Rotação via `B2B_NEW_SECRET` sem segredo em argumentos/logs.
- Rate limit B2B por `client_id`, com limites configuráveis e Redis opcional.
- 14 testes de rate limit passando.

### Fases 13–16 — Frontend e hardening

- Thumbnail/media de cursos e estados de erro/retry de `CourseLearn.vue` validados.
- Controles P0/P1, Tutor NR, autenticação e identity hardening validados.
- 65 testes frontend focados e 80 testes backend focados passando.

### Fases 17–26 — Compliance, evidências e operação

- Regulatory Matrix, catálogo prioritário, regras de carga/modalidade/prática/reciclagem.
- Profissionais, blockers fail-closed e Projeto Pedagógico versionado.
- Official Certificate Readiness gate.
- `StudentSignatureEvidence`, snapshot imutável, PDF e PAdES fail-closed.
- Asaas/SMTP, backup/restore, observability e documentação operacional.

### Fases 28–29 — Freeze e migrações

- `docs/FREEZE_GAP_MATRIX.md` criado.
- Fresh DB `upgrade head` concluído.
- Ciclo descartável `upgrade head → downgrade base → upgrade head` concluído.
- `alembic heads`: exatamente uma head, `1ba7b99712b3`.

## Validação executada

### Testes focados integrados

Com banco PostgreSQL de teste isolado:

```text
54 passed, 2 warnings
70 passed, 2 warnings (compliance/certificates/payments/SMTP)
80 passed, 2 warnings (Tutor/auth/identity hardening)
```

Conjunto executado:

- `tests/test_b2b_rls_migration_isolation.py`
- `tests/test_b2b_concurrent_isolation.py`
- `tests/test_b2b_tenant_filter_failclosed.py`
- `tests/test_progress_canonical.py`
- `tests/test_sso.py`

Também foram validados separadamente:

- B2B API: 29 testes passando.
- Testes de lessons: 36 testes passando.
- Testes SSO: 31 testes passando.

### Regressões autorizadas após o freeze

- Backend completo: **1017 testes passando**.
- Frontend unitário completo: **444 testes passando em 44 arquivos**.
- Frontend lint + build: **passando**.
- Playwright `ui-mocked`: **86/86 testes passando**.
- Smoke Central WR→LMS real: **PASS** — happy-path, casos negativos, LMS offline fail-closed. Relatório em `analysis/central-lms-smoke.md`.

### Migrações

```text
alembic heads -> 1ba7b99712b3 (head)
fresh upgrade head -> passed
fresh upgrade head -> downgrade base -> upgrade head -> passed
```

Existe exatamente uma head Alembic.

### Lint

- Ruff passou nos arquivos diretamente alterados de schema/rota durante a implementação.
- O lint global `ruff check app/ tests/` ainda falha com violações preexistentes em vários arquivos do repositório, incluindo imports, `datetime` sem timezone, `noqa` obsoleto e regras de testes. Essas violações não foram mascaradas nem atribuídas indevidamente às fases concluídas.

## Gaps e blockers externos

- Emissão de certificado com validade oficial: `EXTERNAL BLOCKER` por depender de aprovação regulatória e dados/provedor reais.
- Lint global: há violações preexistentes fora do escopo deste ciclo; o lint dos arquivos alterados e o build frontend passaram.
- Nenhuma operação financeira, envio SMTP real, deploy ou alteração de produção foi executada.

## Estado final

As implementações técnicas das fases 1–29 estão commitadas e os gates de backend/frontend foram executados após o freeze. Todos os 86 testes Playwright passam. O smoke test Central WR→LMS foi executado com sucesso. Os itens dependentes de infraestrutura/credenciais/aprovação humana permanecem como blockers externos. O relatório foi atualizado após as validações finais.
