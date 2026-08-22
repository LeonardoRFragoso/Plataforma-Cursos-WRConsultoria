# PRE-LAUNCH / HOMOLOGAÇÃO — Estratégia até o lançamento oficial

> Decisão do owner registrada em 22/08/2026.
>
> Este documento define a classificação operacional do ambiente atual e o gate de lançamento oficial da WR Plataforma de Cursos. Em caso de conflito de sequência com versões anteriores do roadmap, esta decisão prevalece até a reconciliação de `IMPLEMENTACAO_PROGRESS.md`.

---

## 1. Decisão atual

A plataforma permanecerá nos ambientes atuais de demonstração/homologação enquanto o CEO da WR reúne e valida os conteúdos, apostilas e demais materiais dos cursos que serão oferecidos oficialmente.

O ambiente atual **não deve ser tratado como lançamento comercial oficial**, ainda que Vercel/Railway utilizem internamente nomes como `production` para branches/deployments.

Classificação funcional atual:

**PRE-LAUNCH / HOMOLOGAÇÃO**

Objetivos desta fase:

- continuar o desenvolvimento funcional e de produto;
- validar jornadas B2C/B2B/white-label;
- evoluir compliance, certificados, UX e operação;
- preparar o conteúdo real dos cursos;
- permitir homologação progressiva pelo CEO;
- manter pagamentos reais desativados até o Launch Gate.

---

## 2. Infraestrutura observada atualmente

### WR frontend

- Provider: Vercel
- Projeto: `wr-cursos-demo`
- Ambiente atual: PRE-LAUNCH / HOMOLOGAÇÃO
- Deploy automático a partir do repositório GitHub.

### Alfa frontend

- Provider: Vercel
- Projeto: `alfa-academy-demo`
- Finalidade: white-label/demo e regressão multi-tenant.

### Backend

- API observada no bundle Vercel WR:
  - `https://wr-api-production.up.railway.app`
- Provider observado: Railway
- Arquitetura atual: Vercel frontend → Railway FastAPI backend.

Os artefatos Docker/Compose do repositório continuam válidos como opção de deployment, mas não substituem a infraestrutura Vercel/Railway atualmente observada sem decisão explícita do owner.

---

## 3. Política de pagamentos durante PRE-LAUNCH

O código Asaas implementado no PR #19 permanece disponível e testável por mocks/fakes e integrações não monetárias controladas.

Durante PRE-LAUNCH:

- **não inserir a chave Asaas real de produção**;
- **não criar cobranças reais automaticamente**;
- **não executar PIX, boleto, cartão, refund ou transfer reais**;
- **não armazenar credenciais financeiras reais em Git, Devin, ChatGPT, screenshots ou logs**;
- testes automatizados de pagamento devem continuar usando mocks/fakes;
- a integração real fica adiada para o Official Launch Gate.

A ausência de ativação Asaas real **não bloqueia** o desenvolvimento de Business Journeys.

---

## 4. Próxima macrofase de desenvolvimento

A próxima macrofase passa a ser:

**Business Journeys & Contracting Hardening**

Ela pode começar imediatamente em PRE-LAUNCH usando gateways mockados/fakes e os ambientes Vercel/Railway atuais para homologação funcional.

Prioridade inicial:

1. identidade/login realmente tenant-scoped;
2. continuidade curso → login → cadastro → retorno ao curso;
3. auto-login seguro após cadastro;
4. recuperação/ativação tenant-scoped;
5. matriz viva de jornadas B2C/B2B/white-label;
6. depois evoluir lifecycle de compra, tentativas, cursos gratuitos, concorrência e e-mails transacionais.

Nenhuma dessas tarefas exige a chave real do Asaas.

---

## 5. Content Readiness — responsabilidade antes do lançamento

O lançamento oficial depende de conteúdo real suficiente e validado para os cursos que entrarão no catálogo.

Para cada curso candidato ao lançamento, controlar no mínimo:

| Item | Estado esperado antes do lançamento |
|---|---|
| Nome oficial do curso | Aprovado |
| Código/categoria | Aprovado |
| Descrição comercial | Aprovada |
| Público-alvo | Aprovado |
| Pré-requisitos | Definidos |
| Carga horária | Definida |
| Modalidade | Definida |
| Conteúdo programático/ementa | Completo |
| Módulos e aulas | Completos |
| Vídeos/aulas gravadas | Disponíveis ou marcadas conforme plano |
| Apostilas | Versão final disponível |
| Materiais complementares | Disponíveis |
| Avaliação | Definida quando aplicável |
| Nota/critério de aprovação | Definido quando aplicável |
| Instrutor(es) | Identificados |
| Qualificação do(s) instrutor(es) | Registrada quando aplicável |
| Responsável técnico | Definido quando aplicável |
| Requisitos NR/compliance | Validados quando aplicável |
| Validade/recertificação | Definida quando aplicável |
| Preço | Aprovado |
| Política comercial | Aprovada |
| Certificado/template | Homologado |
| Imagem/capa | Final |
| Revisão pelo CEO | Aprovada |

Para cursos regulados/NR, a prontidão de conteúdo deve ser cruzada com `docs/NR_EAD_COMPLIANCE_ROADMAP.md` e validada pelo responsável técnico competente da WR antes da publicação oficial.

---

## 6. Domínio oficial

O domínio definitivo da nova plataforma de cursos ainda não é requisito para o desenvolvimento PRE-LAUNCH.

Antes do lançamento oficial, o owner/CEO definirá e registrará o domínio final da plataforma.

Até essa decisão:

- não assumir `wr-cursos-demo.vercel.app` como domínio comercial definitivo;
- não inventar subdomínio ou domínio em código/configuração;
- não amarrar a chave Asaas real ao ambiente demo;
- URLs finais de e-mail, CORS, redirects, certificados e webhook devem ser revisadas no Launch Gate.

---

## 7. Official Launch Gate

A ativação comercial oficial somente deve ocorrer quando o owner autorizar explicitamente.

Checklist mínimo:

### Produto e conteúdo

1. cursos de lançamento definidos;
2. conteúdo/apostilas/materiais carregados e revisados;
3. cargas horárias, ementas e responsáveis validados;
4. avaliações/compliance definidos quando aplicável;
5. certificados homologados;
6. CEO aprova catálogo e experiência.

### Domínio e frontend

7. domínio oficial definido/registrado;
8. domínio configurado no Vercel;
9. WR frontend validado no domínio definitivo;
10. redirects e links públicos revisados;
11. Alfa/demo permanece isolado do ambiente WR oficial.

### Backend e banco

12. Railway/backend final auditado;
13. revision Alembic confirmada e `upgrade head` aplicado quando necessário;
14. `/health/live` = saudável;
15. `/health/ready` = saudável;
16. CORS/hosts/trusted origins ajustados ao domínio definitivo;
17. storage/Redis/SMTP reais validados.

### Segurança e operação

18. nenhuma mock mode habilitada no ambiente comercial;
19. secrets definitivos configurados de forma segura;
20. termos, privacidade, reembolso e responsabilidades comerciais/fiscais aprovados;
21. observabilidade e recuperação operacional mínimas verificadas.

### Asaas real

22. owner acessa `Configurações → Financeiro`;
23. owner insere a chave Asaas de produção diretamente na UI segura;
24. backend faz validação read-only;
25. webhook de produção é criado/reconciliado com token separado;
26. confirmar `enabled=true` e `interrupted=false`;
27. executar uma compra real controlada de baixo valor somente com autorização explícita;
28. confirmar webhook → Payment → Enrollment → acesso;
29. validar e-mail transacional real;
30. somente então liberar operação comercial oficial.

---

## 8. Ordem prática revisada

1. ✅ Asaas Production Payments — código implementado/mergeado.
2. ✅ Roadmap pós-Asaas — documentado.
3. 🟢 PRE-LAUNCH / HOMOLOGAÇÃO — Vercel + Railway atuais.
4. 🟠 Business Journeys & Contracting Hardening.
5. 🟠 Regras comerciais/fiscais/LGPD e lifecycle financeiro.
6. 🟠 NR EAD Compliance & Trusted Certificates.
7. 🟠 Product Experience & White-Label Studio 2.0.
8. 🟠 Content Readiness + carga dos cursos reais + homologação CEO.
9. 🟠 Growth/SEO/conversão e preparação de lançamento.
10. ⚪ Domínio oficial definido/registrado.
11. 🟡 Official Launch Gate — infraestrutura final + Asaas real + smoke/E2E controlado.
12. ✅ Lançamento comercial oficial, após autorização do owner.

---

## 9. Regra de segurança para esta fase

Enquanto o projeto estiver classificado como PRE-LAUNCH/HOMOLOGAÇÃO:

- desenvolvimento pode continuar normalmente;
- gateways reais não são necessários para validar regras de negócio;
- não solicitar a chave Asaas ao owner;
- não habilitar transações monetárias reais;
- GitHub Actions permanece desativado por decisão de controle de custo;
- gates de qualidade devem ser executados localmente;
- mudanças devem preservar isolamento WR/Alfa e tenant isolation.

---

## 10. Critério para sair de PRE-LAUNCH

PRE-LAUNCH termina somente quando houver decisão explícita do owner após:

- conteúdo mínimo de lançamento pronto;
- validação do CEO;
- domínio oficial definido;
- roadmap crítico de negócio/compliance suficientemente concluído;
- infraestrutura final auditada;
- Launch Gate preparado.

Até lá, `wr-cursos-demo` e `alfa-academy-demo` permanecem ambientes de homologação/demonstração, independentemente do rótulo técnico `production` usado pelo provider de hosting.
