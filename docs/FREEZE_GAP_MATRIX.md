# Freeze Gap Matrix — WR Plataforma de Cursos

Data do freeze: 2026-08-28  
Branch: `feat/central-b2b-readonly-api`  
Regra: todo item deve estar `IMPLEMENTED` ou `EXTERNAL BLOCKER`.

## Matriz

| Fase | Requisito | Estado | Evidência / blocker externo |
|---|---|---|---|
| 17 | Regulatory Matrix WR | IMPLEMENTED | Modelos `CourseComplianceProfile`, regras de readiness, estados e endpoints de compliance. |
| 18 | 14 cursos prioritários | IMPLEMENTED | Catálogo/seed/importador WR e reconciliação de catálogo disponíveis. |
| 19 | Cargas, modalidades, prática e reciclagem | IMPLEMENTED | Perfil regulatório, projeto pedagógico, aulas obrigatórias, avaliação e regras de modalidade/carga. |
| 20 | Profissionais, habilitações e blockers | IMPLEMENTED | `TrainingProfessional`, vínculos por curso, validação de ativo/qualificação e blockers fail-closed. |
| 21 | Projeto Pedagógico | IMPLEMENTED | `PedagogicalProjectVersion`, aprovação, versionamento e validação de carga/modalidade. |
| 22 | Official Certificate Readiness | IMPLEMENTED | Readiness gate exige blockers resolvidos antes de emissão; certificado demo permanece explicitamente sem validade oficial. |
| 23 | StudentSignatureEvidence | IMPLEMENTED | Evidência persistida, confirmação autenticada, idempotência e transições regulatórias. |
| 24 | PDF, snapshot imutável e PAdES | IMPLEMENTED | Documento pré-assinatura, snapshot regulatório, hash, pipeline de assinatura e webhook autenticado/fail-closed. |
| 25 | Payments / SMTP | IMPLEMENTED | Provider Asaas com modo mock explícito, erros sanitizados, timeout; SMTP em thread, timeout e mock de testes. |
| 26 | Backup / observability / docs | IMPLEMENTED | Documentos de deployment, release, backup/restore, políticas de ciclo financeiro e logging estruturado. |
| 28 | Freeze e gap matrix | IMPLEMENTED | Este documento; alterações commitadas e working tree limpo no momento do freeze. |
| 29 | Migration gate | IMPLEMENTED | `alembic heads` possui exatamente uma head; fresh DB `upgrade head` concluído em DB descartável. |
| Produção | Credenciais, DNS, SMTP, Asaas, provedor PAdES e aprovação regulatória | EXTERNAL BLOCKER | Requer configuração/contrato/credenciais e decisão humana de produção; não é bloqueio de implementação local. |
| Produção | Emissão com validade oficial | EXTERNAL BLOCKER | Depende de auditoria/aprovação regulatória e dados reais; o modo demo não é promovido automaticamente. |

## Critérios de freeze

- Não há item classificado como `PARTIAL` ou `MISSING`.
- Bloqueios externos estão separados de lacunas técnicas e não são simulados no código.
- Migrações opcionais de homologação não bloqueiam um banco novo sem seed.
- Nenhuma operação financeira real, envio de e-mail real ou alteração de produção foi executada.

## Validação focada antes do freeze

- Testes B2B/RLS/concurrency/fail-closed/progresso/SSO: 54 passando.
- Compliance, evidências, certificados, Asaas e SMTP: 70 passando.
- Tutor, autenticação e identity hardening: 80 passando.
- Frontend CourseCover/course media/CourseLearn: 65 passando.
- Migração fresh: `upgrade head` concluído em banco descartável.
