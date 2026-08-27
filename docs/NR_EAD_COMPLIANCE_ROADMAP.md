# NR EAD Compliance & Trusted Certificates — Roadmap

> Planejamento futuro para evolução da WR Plataforma de Cursos.
>
> Objetivo: alinhar a experiência de cursos EAD de SST com os requisitos aplicáveis da NR-1 e das NRs específicas, mantendo uma jornada simples para o aluno e uma trilha forte de autenticidade, rastreabilidade e auditoria.
>
> Este documento é de engenharia/produto e não substitui validação jurídica ou técnica do responsável de SST da WR para cada NR específica.

## Estado atual dos macrofases

> Atualizado em 27/08/2026 — reconciliação pós-PR #34 a PR #38 e início de `feat/compliance-operations-closure`.

| Macrofase | PR | Status real | O que existe | O que ainda falta |
|-----------|----|-------------|--------------|-------------------|
| NR Compliance Foundation | #34 | IMPLEMENTED / MERGED | `CourseComplianceProfile`, profissionais, matriz por curso, `COMPLIANCE_READY` blocker | Final de aprovação real do responsável técnico da WR; matriz preenchida com dados reais de cada NR |
| Regulatory Training Evidence Runtime | #35 | IMPLEMENTED / MERGED | `EnrollmentComplianceProgress`, `TrainingAccessEvent`, state machine, aula/log de acesso, confirmação do aluno, componente prático | Validação de manifestação juridicamente aceita; critérios por NR específica |
| Trusted Certificate Document Pipeline | #36 | IMPLEMENTED / MERGED | Certificado imutável, snapshot, `CertificatePDFContext`, storage/hash, QR/validação pública | Campos regulatórios pendentes de auditoria NR-01 Anexo II |
| PAdES Signing Orchestration | #37 | IMPLEMENTED / MERGED | Fila de assinatura, `CertificateSigningProfile`, MOCK provider, webhook flow | Conexão real com provedor ICP-Brasil/PAdES; credenciais reais |
| Certificate Studio | #38 | IMPLEMENTED / MERGED | Templates versionados, atribuição por curso, reemissão regulatória | Definição de template regulatoriamente completo; aprovação de layout |
| Compliance Operations & Retention Governance | — | IMPLEMENTED / PENDING MERGE | Dashboard `ComplianceOperations.vue`, política versionada de retenção, RLS, concorrência, testes | Go-live e decisão jurídica/LGPD sobre prazos reais |

### Legenda dos status

- **IMPLEMENTED / MERGED**: código implementado e mergeado em `main`.
- **IMPLEMENTED / PENDING OPERATIONAL VALIDATION**: código implementado, mas precisa de validação em ambiente real (dados, credenciais, aprovações).
- **EXTERNAL / OWNER ACTION**: depende de decisão ou dado externo (SST, jurídico, credenciais).
- **LEGAL / REGULATORY INPUT REQUIRED**: depende de validação normativa/jurídica antes de ser considerado apto.

## Princípio

A plataforma não deve adicionar biometria, reconhecimento facial, gravação por câmera ou proctoring remoto sem necessidade regulatória real.

A solução-alvo deve privilegiar:

- conta individual do aluno;
- identificação por CPF/e-mail;
- senha individual;
- progresso e logs rastreáveis;
- avaliação de aprendizagem;
- evidência eletrônica de manifestação do aluno;
- responsável técnico identificado;
- assinatura digital ICP-Brasil no documento quando aplicável;
- QR Code único por certificado;
- página pública de validação;
- PDF final imutável e auditável.

---

# 1. P0/P1 — Matriz regulatória por curso/NR

- [ ] Criar uma matriz de conformidade para cada curso regulatório oferecido pela WR.
- [ ] Registrar a NR relacionada e a versão normativa utilizada.
- [ ] Definir modalidade permitida: `EAD`, `SEMIPRESENCIAL` ou `PRESENCIAL`.
- [ ] Registrar se existem atividades práticas obrigatórias.
- [ ] Não assumir que toda NR pode ser ministrada integralmente em EAD apenas porque a NR-1 permite capacitação a distância.
- [ ] Validar requisitos adicionais da NR específica antes de publicar o curso.
- [ ] Registrar carga horária mínima/regra aplicável.
- [ ] Registrar exigência de reciclagem/periodicidade quando aplicável.
- [ ] Registrar pré-requisitos regulatórios.
- [ ] Definir quais dados devem obrigatoriamente constar no certificado daquele curso.
- [ ] Exigir aprovação do responsável técnico da WR antes de marcar um curso como `COMPLIANCE_READY`.

## Modelo sugerido

Criar entidade ou estrutura equivalente a `CourseComplianceProfile` com campos como:

- `course_id`
- `regulatory_standard`
- `regulatory_version`
- `delivery_mode`
- `requires_practical_component`
- `requires_final_assessment`
- `minimum_score`
- `validity_period_months`
- `technical_responsible_id`
- `pedagogical_project_version_id`
- `last_compliance_review_at`
- `next_compliance_review_at`
- `status`

Estados sugeridos:

- `DRAFT`
- `IN_REVIEW`
- `COMPLIANCE_READY`
- `REVIEW_REQUIRED`
- `ARCHIVED`

---

# 2. P1 — Projeto Pedagógico versionado

- [ ] Criar conceito estruturado de Projeto Pedagógico por curso/versão.
- [ ] Registrar objetivo geral e objetivos específicos.
- [ ] Registrar público-alvo.
- [ ] Registrar estratégia pedagógica.
- [ ] Registrar conteúdo programático.
- [ ] Registrar carga horária.
- [ ] Registrar modalidade.
- [ ] Registrar materiais didáticos.
- [ ] Registrar critérios e metodologia de avaliação.
- [ ] Registrar instrutores.
- [ ] Registrar responsável técnico.
- [ ] Registrar versão e data de aprovação.
- [ ] Permitir nova versão sem apagar a anterior.
- [ ] Vincular cada turma/matrícula ao projeto pedagógico vigente no momento da realização.
- [ ] Criar lembrete/status de revisão periódica, inclusive após alteração normativa relevante.

---

# 3. P1 — Instrutores e Responsável Técnico

Criar cadastro próprio para profissionais ligados à certificação e treinamento.

## Dados mínimos sugeridos

- nome completo;
- CPF;
- função;
- formação/qualificação;
- registro profissional, quando aplicável;
- conselho/órgão;
- número do registro;
- situação ativa/inativa;
- cursos/NRs aos quais está vinculado.

## Tarefas

- [ ] Criar entidade `TrainingProfessional` ou equivalente.
- [ ] Diferenciar `INSTRUCTOR` e `TECHNICAL_RESPONSIBLE`.
- [ ] Permitir mais de um instrutor por curso/turma.
- [ ] Definir um responsável técnico por curso/versão quando necessário.
- [ ] Preservar snapshot dos profissionais no certificado emitido.
- [ ] Não usar automaticamente o `ADMIN` da plataforma como responsável técnico.

---

# 4. P0/P1 — Avaliação final de aprendizagem

Hoje a conclusão das aulas obrigatórias não deve ser o único critério para cursos regulatórios que exigem avaliação de aprendizagem.

- [ ] Criar módulo de avaliações por curso.
- [ ] Suportar banco de questões.
- [ ] Suportar múltipla escolha e outros formatos seguros quando necessários.
- [ ] Permitir situações práticas/cenários representativos da rotina laboral.
- [ ] Definir nota mínima por curso.
- [ ] Registrar tentativa, início, término, respostas e resultado.
- [ ] Resultado final regulatório: `SATISFATORIO` ou `INSATISFATORIO`.
- [ ] Definir política de novas tentativas.
- [ ] Impedir emissão de certificado quando avaliação obrigatória não for satisfatória.
- [ ] Vincular avaliação ao usuário autenticado e tenant correto.
- [ ] Exigir autenticação individual durante o processo.
- [ ] Registrar trilha de auditoria suficiente para demonstrar quem realizou a avaliação.

## E2E obrigatório

`aluno autenticado → curso → aulas obrigatórias → avaliação → resultado satisfatório → confirmação → certificado`

E negativos:

- avaliação insuficiente → sem certificado;
- aluno A não pode submeter avaliação de aluno B;
- tenant A não pode acessar avaliação do tenant B;
- tentativa duplicada/concurrent submission não gera dois resultados finais inconsistentes.

---

# 5. P1 — Training Access Log e retenção

- [ ] Criar ledger de acesso/atividade específico para treinamentos regulatórios.
- [ ] Registrar eventos relevantes sem capturar dados excessivos.
- [ ] Eventos sugeridos:
  - login relacionado ao curso;
  - abertura de aula;
  - início/fim de sessão;
  - progresso;
  - conclusão de aula;
  - início da avaliação;
  - envio da avaliação;
  - confirmação de conclusão;
  - emissão de certificado.
- [ ] Campos possíveis:
  - `tenant_id`
  - `student_id`
  - `enrollment_id`
  - `course_id`
  - `lesson_id`
  - `event_type`
  - `occurred_at`
  - `session_id`
  - IP conforme política LGPD/necessidade de auditoria;
  - user-agent de forma controlada.
- [ ] Definir política de retenção compatível com as exigências regulatórias aplicáveis.
- [ ] Não permitir exclusão administrativa casual de evidências regulatórias.
- [ ] Criar exportação de trilha de auditoria para fiscalização/cliente autorizado.

---

# 6. P1 — Confirmação/assinatura eletrônica do aluno

O aluno não deve ser obrigado a possuir e-CPF para utilizar a plataforma.

Fluxo proposto ao final do treinamento:

`curso concluído → avaliação satisfatória → confirmar identidade → confirmar conclusão → emitir certificado`

## UX proposta

Exibir:

> Para confirmar sua identidade e a conclusão deste treinamento, informe novamente sua senha.

E uma declaração equivalente a:

> Declaro que fui eu quem realizou esta capacitação e avaliação e confirmo a conclusão do treinamento.

## Evidência a persistir

- [ ] `user_id`
- [ ] `student_id`
- [ ] `enrollment_id`
- [ ] `course_id`
- [ ] timestamp UTC;
- [ ] método de autenticação;
- [ ] versão do texto aceito;
- [ ] hash do payload/documento que será certificado;
- [ ] sessão;
- [ ] IP/user-agent quando juridicamente/operacionalmente justificável.

- [ ] Criar entidade `StudentSignatureEvidence` ou equivalente.
- [ ] Nunca armazenar senha em plaintext.
- [ ] Nunca imprimir a senha no certificado.
- [ ] O certificado pode informar que houve confirmação/assinatura eletrônica pelo ambiente da plataforma, sem qualificá-la falsamente como ICP-Brasil do aluno.

---

# 7. P1 — Assinatura do Responsável Técnico / ICP-Brasil

- [ ] Implementar suporte a assinatura digital do PDF pelo responsável técnico quando aplicável.
- [ ] Preferir padrão PAdES para PDF.
- [ ] Permitir integração segura com certificado ICP-Brasil do responsável técnico.
- [ ] Avaliar assinatura adicional com e-CNPJ da WR como emissora.
- [ ] Nunca guardar chave privada do certificado de forma insegura no banco ou frontend.
- [ ] Utilizar secret store/HSM/serviço seguro compatível com a estratégia adotada.
- [ ] Registrar status da assinatura digital.
- [ ] Registrar timestamp da assinatura.
- [ ] Registrar fingerprint/identificador público do certificado sem expor chave privada.
- [ ] Tratar expiração/renovação do certificado digital sem invalidar documentos históricos já assinados.

Estados possíveis:

- `PENDING_SIGNATURE`
- `SIGNED`
- `SIGNATURE_FAILED`

---

# 8. P1 — QR Code único por certificado

O QR Code deve ser único por certificado, não por aluno.

Exemplo:

`Aluno A → NR-10 → Certificado 1 → QR 1`

`Aluno A → NR-35 → Certificado 2 → QR 2`

## Tarefas

- [ ] Gerar token público forte e não sequencial por certificado.
- [ ] QR deve apontar diretamente para a página pública daquele certificado.
- [ ] Não expor CPF completo no QR/URL.
- [ ] Permitir leitura sem login.
- [ ] QR antigo deve continuar resolvendo mesmo após revogação, mostrando o status correto.
- [ ] Não reutilizar token entre certificados.
- [ ] Adicionar testes de colisão/uniqueness.

---

# 9. P0/P1 — Snapshot imutável do certificado

Hoje o PDF não deve continuar sendo regenerado indefinidamente a partir de dados mutáveis atuais.

Na emissão:

`conclusão → snapshot → PDF → hash SHA-256 → assinatura → storage imutável`

- [ ] Criar snapshot dos dados regulatórios no momento da emissão.
- [ ] Preservar nome do aluno conforme emitido.
- [ ] Preservar curso, código, carga horária e modalidade.
- [ ] Preservar conteúdo programático.
- [ ] Preservar período/data/local de realização quando aplicável.
- [ ] Preservar instrutores e qualificações.
- [ ] Preservar responsável técnico e qualificação.
- [ ] Preservar resultado da avaliação.
- [ ] Preservar projeto pedagógico/versão normativa.
- [ ] Preservar identidade visual/template utilizado.
- [ ] Gerar PDF final uma única vez por versão do certificado.
- [ ] Salvar `pdf_storage_key`.
- [ ] Calcular e armazenar `pdf_sha256`.
- [ ] Download futuro deve entregar o PDF original armazenado, não regenerar silenciosamente com dados atuais.

---

# 10. P1 — Certificado de duas páginas

## Página 1 — certificado visual

Deve conter, conforme regra aplicável ao curso:

- nome do aluno;
- identificação adequada;
- nome e código do curso;
- carga horária;
- modalidade;
- data/período;
- local quando aplicável;
- responsável técnico;
- evidência de assinatura/manifestação do aluno;
- QR Code;
- número do certificado;
- identidade WR e co-branding quando permitido.

## Página 2 — detalhes/compliance

- conteúdo programático;
- instrutores;
- qualificações;
- responsável técnico;
- resultado da avaliação;
- versão do projeto pedagógico;
- informações do emissor;
- versão normativa/referência regulatória quando apropriado;
- demais campos exigidos pela NR específica.

- [ ] Criar template robusto e responsivo para conteúdo variável.
- [ ] Não permitir que parceiro white-label altere fatos acadêmicos/regulatórios.
- [ ] Permitir personalização apenas da camada visual/co-branding autorizada.

---

# 11. P1 — Estados do certificado: nunca hard-delete

Substituir exclusão destrutiva por lifecycle documental.

Estados sugeridos:

- `VALID`
- `REVOKED`
- `SUPERSEDED`

- [ ] Remover/desabilitar hard-delete de certificado emitido em produção.
- [ ] Implementar revogação com motivo obrigatório.
- [ ] Registrar `revoked_at` e `revoked_by`.
- [ ] Implementar reemissão vinculada ao certificado anterior.
- [ ] Campo `reissued_from_id`/`superseded_by_id` ou equivalente.
- [ ] Página pública deve mostrar claramente certificado revogado/substituído.
- [ ] QR e URL antigos continuam funcionando para auditoria.
- [ ] Histórico nunca deve ser apagado por simples correção cadastral.

---

# 12. P1 — Página pública de validação avançada

Evoluir a página atual de validação.

Quando válido, exibir de forma segura:

- status `CERTIFICADO VÁLIDO`;
- número;
- titular;
- curso;
- carga horária;
- modalidade;
- conclusão/emissão;
- resultado satisfatório quando aplicável;
- emissor;
- responsável técnico;
- qualificação/registro profissional quando apropriado;
- status de assinatura digital;
- status de integridade do documento.

Ações:

- [ ] “Baixar certificado original”.
- [ ] Validação direta pelo QR sem exigir digitação do código.

Privacidade:

- [ ] Não exibir CPF completo publicamente.
- [ ] Não exibir endereço, e-mail, telefone ou dados desnecessários.
- [ ] Avaliar mascaramento adicional conforme política LGPD.

Quando revogado:

> CERTIFICADO REVOGADO

com motivo público apenas quando apropriado e referência ao substituto se existir.

---

# 13. P1 — Integridade documental

- [ ] Calcular SHA-256 do PDF final.
- [ ] Salvar hash de forma imutável.
- [ ] Verificar hash no download/validação quando necessário.
- [ ] Detectar arquivo divergente/corrompido.
- [ ] Não considerar QR Code sozinho como prova criptográfica de integridade do PDF.
- [ ] QR representa a consulta ao registro oficial da plataforma.
- [ ] Assinatura digital representa autoria/integridade criptográfica do documento conforme tecnologia adotada.

---

# 14. P1 — Course completion state machine regulatória

Criar fluxo explícito para cursos com compliance habilitado.

Exemplo:

`ENROLLED`
→ `IN_PROGRESS`
→ `CONTENT_COMPLETED`
→ `ASSESSMENT_PENDING`
→ `ASSESSMENT_SATISFACTORY`
→ `STUDENT_CONFIRMATION_PENDING`
→ `CERTIFICATE_PENDING_SIGNATURE`
→ `CERTIFIED`

Estados alternativos:

- `ASSESSMENT_UNSATISFACTORY`
- `PRACTICAL_COMPONENT_PENDING`
- `COMPLIANCE_REVIEW_REQUIRED`

- [ ] Não emitir certificado apenas porque todas as aulas possuem `completed=True` quando o curso exige outras condições.
- [ ] Centralizar regras de elegibilidade em serviço próprio.
- [ ] Evitar lógica de emissão duplicada em endpoints diferentes.

---

# 15. P1 — Componentes práticos

- [ ] Criar suporte a requisito prático quando uma NR específica exigir.
- [ ] Permitir registrar realização presencial/prática separadamente.
- [ ] Registrar instrutor, data, local e resultado da etapa prática.
- [ ] Certificado somente pode ser emitido quando todos os componentes obrigatórios estiverem satisfeitos.
- [ ] Não permitir que parceiro marque um curso como 100% EAD se o compliance profile exigir prática.

---

# 16. P1 — White-label e responsabilidade documental

Separar claramente:

- `CONTENT_PROVIDER`: WR;
- `CERTIFICATE_ISSUER`: entidade definida pela regra comercial/regulatória;
- `COMMERCIAL_PARTNER`: parceiro que comercializou/disponibilizou;
- `TECHNICAL_RESPONSIBLE`: profissional responsável;
- `INSTRUCTORS`: profissionais do treinamento.

- [ ] Partner admin não pode editar nome/carga horária/conteúdo oficial após conclusão para alterar certificado histórico.
- [ ] Partner admin não pode trocar responsável técnico de certificado já emitido.
- [ ] Co-branding deve deixar claro o papel da WR e do parceiro.
- [ ] Definir quem assina o certificado por modelo comercial antes de permitir publicação.

---

# 17. P1 — Retenção e LGPD

- [ ] Definir matriz de retenção para certificado, avaliação, logs e evidências.
- [ ] Preservar registros obrigatórios mesmo diante de pedido de exclusão quando houver obrigação legal legítima.
- [ ] Minimizar dados públicos.
- [ ] Documentar base legal e finalidade de logs de treinamento.
- [ ] Restringir acesso administrativo às evidências.
- [ ] Criar audit log para leitura/exportação de dados sensíveis de compliance.

---

# 18. P1 — Testes regulatórios automatizados

Backend:

- [ ] curso regulatório sem avaliação satisfatória não certifica;
- [ ] curso com avaliação satisfatória e demais requisitos certifica;
- [ ] assinatura eletrônica do aluno gera evidência imutável;
- [ ] certificado gera token público único;
- [ ] QR resolve o certificado correto;
- [ ] snapshot não muda quando curso/tenant muda depois da emissão;
- [ ] PDF hash permanece consistente;
- [ ] certificado revogado não volta a `VALID` acidentalmente;
- [ ] reemissão preserva relação histórica;
- [ ] tenant isolation em todas as entidades novas;
- [ ] aluno não consegue assinar/concluir em nome de outro;
- [ ] parceiro não altera campos acadêmicos protegidos.

E2E:

- [ ] login;
- [ ] estudo;
- [ ] conclusão das aulas;
- [ ] avaliação final;
- [ ] resultado satisfatório;
- [ ] reconfirmação de senha;
- [ ] emissão;
- [ ] download;
- [ ] QR/public validation;
- [ ] revogação administrativa;
- [ ] QR antigo mostrando estado revogado;
- [ ] reemissão e novo certificado válido.

---

# 19. P2 — Operação e auditoria

- [ ] Dashboard de compliance por curso.
- [ ] Certificados aguardando assinatura.
- [ ] Avaliações pendentes.
- [ ] Cursos com revisão regulatória vencendo.
- [ ] Certificado digital do responsável próximo da expiração.
- [ ] Logs incompletos/inconsistentes.
- [ ] Exportação de evidências de treinamento por aluno/empresa.
- [ ] Relatório de conformidade por turma.

---

# 20. Integração com Product Experience / Certificate Studio

A futura fase `Certificate Studio` deve respeitar este roadmap.

O parceiro poderá personalizar:

- template;
- cores;
- logos/co-branding permitido;
- fundo;
- bordas;
- tipografia;
- selo visual;
- disposição dentro de presets aprovados.

O parceiro NÃO poderá alterar:

- titular;
- curso oficial;
- código;
- carga horária;
- resultado;
- período;
- conteúdo programático oficial;
- instrutores históricos;
- responsável técnico histórico;
- número do certificado;
- QR/token de validação;
- hash;
- estado documental;
- dados regulatórios obrigatórios.

---

# Ordem recomendada desta macrofase

1. Matriz regulatória por NR/curso.
2. Compliance Profile + Projeto Pedagógico versionado.
3. Instrutores + Responsável Técnico.
4. Módulo de avaliação.
5. Training Access Log.
6. State machine de conclusão regulatória.
7. Evidência eletrônica do aluno.
8. Snapshot imutável.
9. QR por certificado.
10. PDF duas páginas.
11. Página pública avançada.
12. Revogação/reemissão.
13. Assinatura PAdES/ICP-Brasil.
14. Retenção/LGPD.
15. E2E e auditoria operacional.
16. Integração final com Certificate Studio/white-label.

---

# Critério de aceite da macrofase

Esta fase só deve ser considerada concluída quando:

- um curso regulatório possui regras explícitas de conclusão;
- o sistema sabe se o curso pode ser EAD/semipresencial/presencial;
- avaliação obrigatória é realmente aplicada quando necessária;
- responsável técnico e instrutores estão estruturados;
- o aluno confirma eletronicamente sua conclusão em sessão autenticada;
- o certificado é criado a partir de snapshot imutável;
- cada certificado possui QR/token próprio;
- o PDF final possui hash persistido;
- o PDF não é regenerado silenciosamente com dados futuros;
- a página pública valida o documento e seu estado;
- documentos emitidos são revogados/reemitidos, nunca apagados casualmente;
- assinatura digital ICP-Brasil/PAdES está integrada conforme decisão técnica/regulatória;
- evidências e logs possuem política de retenção;
- tenant isolation permanece integral;
- testes backend/E2E comprovam o fluxo completo.
