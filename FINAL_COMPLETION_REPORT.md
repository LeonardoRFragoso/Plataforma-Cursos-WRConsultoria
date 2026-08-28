# Relatório final de conclusão — B2B, isolamento multi-tenant e progresso acadêmico

Data: 2026-08-28  
Branch: `feat/central-b2b-readonly-api`

## Resumo executivo

Foram concluídas e validadas as fases 1–10 relacionadas ao hardening da API B2B, isolamento multi-tenant, progresso acadêmico, SSO e contrato de paginação. As alterações foram separadas em commits pequenos e auditáveis.

As fases posteriores da lista original — frontend, rate limiting, rotação de segredos, assinatura/PAdES, matriz regulatória, smoke tests completos e atualização de PR — não foram implementadas neste ciclo e permanecem pendentes. Este relatório não as marca como concluídas.

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
- `in_progress` agora conta explicitamente apenas matrículas `PENDENTE` e `CONFIRMADA`.
- Matrículas canceladas e estados terminais não são classificadas como em andamento.
- Coberto pelo teste canônico de progresso.

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

## Validação executada

### Testes focados integrados

Com banco PostgreSQL de teste isolado:

```text
54 passed, 2 warnings
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

### Migrações

```text
alembic heads -> 9193813510de (head)
```

Existe exatamente uma head Alembic.

### Lint

- Ruff passou nos arquivos diretamente alterados de schema/rota durante a implementação.
- O lint global `ruff check app/ tests/` ainda falha com violações preexistentes em vários arquivos do repositório, incluindo imports, `datetime` sem timezone, `noqa` obsoleto e regras de testes. Essas violações não foram mascaradas nem atribuídas indevidamente às fases concluídas.

## Fases ainda pendentes

Permanecem pendentes, sem implementação neste ciclo:

- Fases 11–12: hardening/rotação de segredo B2B e rate limit por `client_id`.
- Fases 13–14: correções frontend de cards mobile e revalidação de acesso/estados de erro.
- Fases 15–16: matriz P0/P1 e verificação completa do Tutor NR.
- Fases 17–26: matriz regulatória, catálogo, profissionais, projetos pedagógicos, certificados oficiais, assinatura, PAdES, pagamentos, SMTP, backup e observabilidade.
- Fase 28: documento de freeze gap matrix.
- Fase 29: gate completo de migrações além da verificação de head única.
- Fases 30–33: regressão backend/frontend completa, Playwright E2E e smoke Central→LMS.
- Fase 36: atualização da descrição do PR #46.

## Estado final

O conjunto B2B/RLS/progresso/SSO/paginação está implementado, testado e commitado na branch atual. O repositório está sem alterações não commitadas no momento da geração deste relatório.
