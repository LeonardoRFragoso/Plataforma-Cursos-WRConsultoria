# Audit Baseline — MVP Stabilization Phase 3

## Data e hora (UTC)

2026-08-13 15:40:53

## Repositório e remote

- Repositório local: `/home/leonardo/dev/WR-Plataforma-Cursos`
- Remote `origin`: `https://github.com/LeonardoRFragoso/Plataforma-Cursos-WRConsultoria.git`
- Acesso: push/pull via HTTPS (usado para push anteriores)

## Branch inicial

- Branch atual: `fix/branding-wr-identity`
- SHA inicial (HEAD local): `7189a43696a5805f065cfa5a648863386ede7574`
- SHA `origin/main`: `c9a206121d6be6ecc22b4921087e0fe201933d4e`
- SHA `origin/fix/branding-wr-identity`: `7189a43696a5805f065cfa5a648863386ede7574`
- Merge base `origin/main...origin/fix/branding-wr-identity`: `062ddd3de0c2ca2c363cd7e98d16a074b6db9da2`
- Divergência: `origin/main` está 4 commits à frente e 3 commits atrás de `origin/fix/branding-wr-identity`

## Working tree inicial

?? AUDIT_BASELINE.md
Working tree inicial está limpa (nenhuma alteração rastreada pendente).

## Commits exclusivos da branch `fix/branding-wr-identity` em relação à `origin/main`

Do mais antigo para o mais novo:

1. `0896ce0` — feat: remove perfil de instrutor do sistema
2. `0c85c5f` — feat: fase 3 - vídeo-aulas, player e progresso
3. `7189a43` — docs: proposta de arquitetura multi-tenant white-label

## Histórico recente

7189a43 (HEAD -> fix/branding-wr-identity, origin/fix/branding-wr-identity) docs: proposta de arquitetura multi-tenant white-label\n\n- Adiciona MULTI_TENANT_ARCHITECTURE.md com:\n  - decisões de negócio a validar\n  - estratégia de isolamento (tenant_id + RLS)\n  - schema de Tenant, PartnerLead e retrofit das tabelas\n  - resolução de tenant por subdomínio/JWT\n  - plano de migration, riscos e estimativa de 14-19 dias
0c85c5f feat: fase 3 - vídeo-aulas, player e progresso
0896ce0 feat: remove perfil de instrutor do sistema
062ddd3 fix: seed_db.py não tenta mais recriar tabelas
b637fd2 feat: matrícula em lote com pagamento consolidado
a554309 feat: corrigir cadastro de aluno, adicionar Company e migration
abf6ef3 fix: ajustar payload ao salvar turma
b177d11 docs: adicionar testes e atualizar README, QUICKSTART e PROJECT_STATUS
2513781 ui: substituir imagem de hero do Unsplash por gradiente local
1097b62 feat: adicionar seeds para classes, students, enrollments, payments e certificates
0a0d86d feat: configurar Alembic e gerar migration inicial
66f81f2 fix: token de refresh agora preserva a role do usuário
2c4ecdd fix: usar .then no router guard para aguardar initializeUser
c1ae9fa fix: corrigir redirecionamento ao atualizar página com fallback do localStorage
6d91492 fix: corrigir redirecionamento ao atualizar página

## Arquivos diferentes em relação à `origin/main...HEAD`

```
 .env.example                                       |   9 +
 ARCHITECTURE.md                                    |   5 +-
 IMPLEMENTACAO_PROGRESS.md                          |   3 +-
 MULTI_TENANT_ARCHITECTURE.md                       | 375 +++++++++++++++
 PROJECT_STATUS.md                                  |   4 +-
 QUICKSTART.md                                      |   1 -
 README.md                                          |  41 +-
 USUARIOS_TESTE.md                                  |   6 -
 api/alembic/env.py                                 |   1 +
 .../21ff61f1fa3f_remove_instructor_role.py         |  32 ++
 .../versions/a7438f7a1ab2_add_lesson_models.py     |  70 +++
 api/app/api/routes/classes.py                      |   8 +-
 api/app/api/routes/lessons.py                      | 518 +++++++++++++++++++++
 api/app/core/config.py                             |   8 +
 api/app/core/security.py                           |   7 -
 api/app/core/storage.py                            |  96 ++++
 api/app/main.py                                    |   3 +-
 api/app/models/lesson.py                           |  62 +++
 api/app/models/user.py                             |   1 -
 api/app/schemas/lesson.py                          |  95 ++++
 api/app/seeds/classes_seed.py                      |  12 +-
 api/app/seeds/users_seed.py                        |   7 -
 api/app/services/certificate_service.py            |   2 +-
 api/populate_users.py                              |  16 +-
 api/requirements.txt                               |   1 +
 web/src/__tests__/stores/auth.spec.js              |   7 -
 web/src/router/index.js                            |  16 +-
 web/src/views/Classes.vue                          |   5 +-
 web/src/views/CourseLearn.vue                      | 300 ++++++++++++
 web/src/views/CourseLessons.vue                    | 280 +++++++++++
 web/src/views/Courses.vue                          |   5 +-
 web/src/views/Dashboard.vue                        |  16 -
 32 files changed, 1918 insertions(+), 94 deletions(-)
```

### Status por arquivo

M	.env.example
M	ARCHITECTURE.md
M	IMPLEMENTACAO_PROGRESS.md
A	MULTI_TENANT_ARCHITECTURE.md
M	PROJECT_STATUS.md
M	QUICKSTART.md
M	README.md
M	USUARIOS_TESTE.md
M	api/alembic/env.py
A	api/alembic/versions/21ff61f1fa3f_remove_instructor_role.py
A	api/alembic/versions/a7438f7a1ab2_add_lesson_models.py
M	api/app/api/routes/classes.py
A	api/app/api/routes/lessons.py
M	api/app/core/config.py
M	api/app/core/security.py
A	api/app/core/storage.py
M	api/app/main.py
A	api/app/models/lesson.py
M	api/app/models/user.py
A	api/app/schemas/lesson.py
M	api/app/seeds/classes_seed.py
M	api/app/seeds/users_seed.py
M	api/app/services/certificate_service.py
M	api/populate_users.py
M	api/requirements.txt
M	web/src/__tests__/stores/auth.spec.js
M	web/src/router/index.js
M	web/src/views/Classes.vue
A	web/src/views/CourseLearn.vue
A	web/src/views/CourseLessons.vue
M	web/src/views/Courses.vue
M	web/src/views/Dashboard.vue

## Estado das PRs

- PRs #1, #2, #3 e #4 já mescladas conforme contexto histórico.
- Nenhuma PR aberta identificada no início desta tarefa.
- `.github/workflows` não existe na `origin/main`.

## Limitações do ambiente

- Ambiente local com PostgreSQL já existente (dados reais da WR não devem ser alterados nesta fase).
- Testes com Mercado Pago, SMTP e S3 devem usar mocks/fakes/sandbox.
- Sem acesso a domínios, subdomínios, credenciais reais ou serviços pagos para testes.
- Nenhum CI pré-existente configurado.

## Próxima ação planejada

- Criar nova branch `fix/mvp-stabilization-phase-3` a partir de `origin/main`.
- Cherry-pick dos commits exclusivos `0896ce0`, `0c85c5f`, `7189a43` na ordem correta.
- Realizar auditoria forense do código e testes.
