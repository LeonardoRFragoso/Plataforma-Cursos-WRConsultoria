# Resumo Completo — WR Plataforma de Cursos

**Data:** 12 de Agosto de 2026  
**Status:** Em desenvolvimento (Fase 1 + Fase 2 em progresso)  
**Branch principal:** `main` | **Branch de desenvolvimento:** `fix/branding-wr-identity`

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [✅ Implementado](#implementado)
4. [⏳ Pendente](#pendente)
5. [Roadmap Completo](#roadmap-completo)
6. [Próximos Passos](#próximos-passos)

---

## Visão Geral

**Objetivo:** Substituir a assinatura mensal da plataforma Moodle white-label (Flex Ocupacional) por uma solução própria para vender e entregar cursos de segurança do trabalho (NRs).

**Stack:**
- **Frontend:** Vue 3 + Vite + Tailwind CSS
- **Backend:** FastAPI (Python 3.12)
- **Banco de dados:** PostgreSQL (assíncrono com SQLAlchemy)
- **Autenticação:** JWT (access_token + refresh_token)
- **Pagamentos:** Mercado Pago (integração via requests, sem SDK)
- **Hospedagem:** Netlify (frontend) + servidor próprio (backend)

**Repositório:** https://github.com/LeonardoRFragoso/Plataforma-Cursos-WRConsultoria

---

## Arquitetura

### Backend (`api/`)

```
api/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── auth.py          ✅ Login/Register/Refresh
│   │       ├── courses.py       ✅ CRUD de cursos
│   │       ├── classes.py       ✅ CRUD de turmas
│   │       ├── students.py      ✅ CRUD de alunos
│   │       ├── enrollments.py   ✅ CRUD de matrículas
│   │       ├── payments.py      ✅ CRUD de pagamentos
│   │       └── certificates.py  ✅ CRUD de certificados
│   ├── core/
│   │   ├── config.py            ✅ Configurações (env vars)
│   │   ├── database.py          ✅ SQLAlchemy async
│   │   └── security.py          ✅ JWT + hash de senha
│   ├── models/
│   │   ├── user.py              ✅ User + CPF
│   │   ├── course.py            ✅ Course + tipo_curso
│   │   ├── class_model.py       ✅ Class
│   │   ├── student.py           ✅ Student
│   │   ├── enrollment.py        ✅ Enrollment
│   │   ├── payment.py           ✅ Payment
│   │   ├── certificate.py       ✅ Certificate
│   │   └── attendance.py        ✅ Attendance
│   ├── schemas/
│   │   └── user.py              ✅ Pydantic schemas
│   ├── services/
│   │   └── mercado_pago_service.py  ✅ Integração MP (requests)
│   └── main.py                  ✅ FastAPI app + lifespan
├── requirements.txt             ✅ Dependências
└── venv/                        ✅ Virtual environment
```

### Frontend (`web/`)

```
web/
├── src/
│   ├── assets/
│   │   └── brand/
│   │       └── logo-wr-color.png    ✅ Logo oficial
│   ├── components/
│   │   ├── AppNavbar.vue            ✅ Header branco
│   │   ├── AppButton.vue            ✅ Botão reutilizável
│   │   ├── AppCard.vue              ✅ Card reutilizável
│   │   ├── AppInput.vue             ✅ Input reutilizável
│   │   ├── AppLink.vue              ✅ Link reutilizável
│   │   └── README.md                ✅ Documentação
│   ├── stores/
│   │   └── auth.js                  ✅ Pinia auth store
│   ├── views/
│   │   ├── Home.vue                 ✅ Landing page
│   │   ├── Login.vue                ✅ Login com CPF/email
│   │   ├── Register.vue             ✅ Cadastro
│   │   ├── Dashboard.vue            ✅ Dashboard admin/aluno
│   │   ├── Courses.vue              ✅ Listagem de cursos
│   │   ├── Classes.vue              ✅ Listagem de turmas
│   │   ├── Students.vue             ✅ Listagem de alunos
│   │   ├── Enrollments.vue          ✅ Listagem de matrículas
│   │   ├── Payments.vue             ✅ Listagem de pagamentos
│   │   ├── Certificates.vue         ✅ Listagem de certificados
│   │   ├── CourseDetail.vue         ✅ Detalhes do curso
│   │   └── NotFound.vue             ✅ Página 404
│   ├── api/
│   │   └── client.js                ✅ Axios client com interceptors
│   ├── style.css                    ✅ Estilos globais + Poppins
│   ├── App.vue                      ✅ Root component
│   └── main.js                      ✅ Entry point
├── index.html                       ✅ HTML base + favicon
├── tailwind.config.js               ✅ Tailwind config + cores WR
├── vite.config.js                   ✅ Vite config
└── package.json                     ✅ Dependências
```

---

## ✅ Implementado

### Fase 1 — Infraestrutura & Autenticação

#### Backend
- [x] **FastAPI app** com lifespan (startup/shutdown)
- [x] **PostgreSQL** com SQLAlchemy async
- [x] **Autenticação JWT** (access_token + refresh_token)
- [x] **Modelos de dados** (User, Course, Class, Student, Enrollment, Payment, Certificate, Attendance)
- [x] **Endpoints CRUD** para todas as entidades
- [x] **Validação** com Pydantic schemas
- [x] **CORS** configurado
- [x] **Mercado Pago** integrado (requests, sem SDK)
- [x] **Login por CPF ou e-mail** (identifier detection)
- [x] **Campo CPF** no modelo User (único, indexado)
- [x] **Campo tipo_curso** no modelo Course (formacao/reciclagem/inicial/periodico)

#### Frontend
- [x] **Vue 3** com Vite
- [x] **Pinia** para state management (auth store)
- [x] **Vue Router** com rotas protegidas
- [x] **Axios** com interceptors (JWT refresh automático)
- [x] **Tailwind CSS** com cores WR
- [x] **Responsividade** mobile-first
- [x] **Validação de formulários**
- [x] **Tratamento de erros** com mensagens amigáveis

### Fase 2 — Identidade Visual (Em Progresso)

#### Branding
- [x] **Logo oficial WR** integrada (`logo-wr-color.png`)
- [x] **Paleta de cores** alinhada com site institucional
  - Verde primário: `#1B7A3A` (conforme DESIGN_TOKENS.md oficial)
  - Azul secundário: `#1E3A5F`
  - Laranja acentuado: `#FF6B35`
- [x] **Fonte Poppins** aplicada globalmente (Google Fonts)
- [x] **Header branco** padronizado em todas as views
- [x] **Hero section verde** na Home com imagem de fundo
- [x] **Footer** com logo e copyright WR

#### Componentes Reutilizáveis
- [x] **AppButton** — 4 variantes (primary/secondary/outline/danger), 3 tamanhos (sm/md/lg)
- [x] **AppCard** — com slots para header/footer, prop hoverable
- [x] **AppInput** — com label, validação, mensagem de erro, v-model
- [x] **AppLink** — links internos/externos com variantes
- [x] **AppNavbar** — header reutilizável para views autenticadas

#### Documentação
- [x] **DESIGN_TOKENS.md** — Paleta oficial com explicação de divergência resolvida
- [x] **BRANDING_UPDATE.md** — Guia de aplicação de branding
- [x] **LEGACY_PLATFORM_ALIGNMENT.md** — Alinhamento com plataforma atual
- [x] **PHASE_2_ASSETS.md** — Status da Fase 2
- [x] **components/README.md** — Documentação dos componentes

### Dados & Catálogo

- [x] **55+ cursos** em seed data (todas as 19 NRs principais + programas complementares)
- [x] **Modalidades** (presencial, EAD, semipresencial)
- [x] **Tipos de curso** (formacao, reciclagem, inicial, periodico)
- [x] **Preços e cargas horárias** baseados na plataforma atual

### Integrações

- [x] **Mercado Pago** — Refatorado para usar `requests` (sem SDK)
- [x] **WhatsApp** — Botão de suporte na tela de login
- [x] **JWT** — Autenticação stateless com refresh automático

---

## ⏳ Pendente

### Fase 2 — Assets Visuais (Continuação)

#### Imagens & Favicon
- [ ] **Imagens de hero/background** — Adicionar fotos reais de treinamento
  - Placeholder: Usar imagens públicas do site institucional
  - Final: Substituir por fotos originais quando enviadas
- [ ] **Favicon** — Gerar a partir da logo WR
- [ ] **Versões da logo** — Branca/monocromática (para fundo escuro)

#### Refatoração de Views
- [ ] **Login.vue** — Substituir classes Tailwind cruas por componentes
- [ ] **Register.vue** — Usar `<AppInput>` e `<AppButton>`
- [ ] **Dashboard.vue** — Usar `<AppCard>` e `<AppButton>`
- [ ] **Courses.vue** — Usar componentes reutilizáveis
- [ ] **Outras views** — Classes, Students, Enrollments, Payments, Certificates

### Fase 3 — Funcionalidades Avançadas (Não iniciada)

#### Upload & Conteúdo
- [ ] **Upload de materiais didáticos** (PDF, vídeo, imagem)
- [ ] **Armazenamento** (AWS S3 ou similar)
- [ ] **Gerenciamento de arquivos** no backend

#### Player de Vídeo
- [ ] **Embed de vídeo** (Vimeo/YouTube ou player próprio)
- [ ] **Controle de progresso** (assistido/não assistido)
- [ ] **Certificação automática** após conclusão

#### Dashboard Financeiro
- [ ] **Relatório de vendas** (por período, por curso)
- [ ] **Gráficos** (revenue, alunos, taxa de conclusão)
- [ ] **Exportação** (CSV/Excel)
- [ ] **Reconciliação** com Mercado Pago

#### Relatórios
- [ ] **Relatório de alunos** (inscritos, em progresso, concluídos)
- [ ] **Relatório de turmas** (presença, notas, certificados)
- [ ] **Relatório de certificados** (emitidos, pendentes)
- [ ] **Exportação** em múltiplos formatos

#### Melhorias UX/Admin
- [ ] **Busca e filtros** avançados
- [ ] **Paginação** em listas
- [ ] **Bulk actions** (ações em massa)
- [ ] **Notificações** (email, SMS, push)
- [ ] **Agendamento** de turmas
- [ ] **Controle de acesso** granular (roles/permissions)

#### Segurança & Performance
- [ ] **Rate limiting** nos endpoints
- [ ] **Validação de CPF** (algoritmo de dígito verificador)
- [ ] **Criptografia** de dados sensíveis
- [ ] **Backup automático** do banco de dados
- [ ] **Cache** (Redis) para consultas frequentes
- [ ] **CDN** para assets estáticos

### Fora de Escopo (Por Enquanto)

- ❌ **NF-e (Nota Fiscal Eletrônica)** — Usar recibo simples por enquanto
- ❌ **Dark mode** — Adiar para depois da Fase 2 funcional
- ❌ **Testes automatizados** — Cobertura básica, não é prioridade
- ❌ **Storybook** — Documentação formal pode esperar
- ❌ **Internacionalização (i18n)** — Português apenas por enquanto
- ❌ **Mobile app nativa** — Web app responsivo é suficiente

---

## Roadmap Completo

### Fase 1 ✅ (Concluída)
**Objetivo:** Infraestrutura, autenticação, modelos de dados

**Duração estimada:** 2-3 semanas  
**Status:** ✅ Concluído

**Entregas:**
- FastAPI backend funcional
- PostgreSQL com modelos completos
- JWT autenticação
- Vue 3 frontend com roteamento
- Integração Mercado Pago (requests)
- Login por CPF ou e-mail
- 55+ cursos em seed data

---

### Fase 2 🔄 (Em Progresso)
**Objetivo:** Identidade visual, componentes reutilizáveis, assets

**Duração estimada:** 1-2 semanas  
**Status:** 🔄 60% concluído

**Entregas:**
- ✅ Logo oficial integrada
- ✅ Paleta de cores alinhada
- ✅ Fonte Poppins global
- ✅ Header branco padronizado
- ✅ 4 componentes reutilizáveis
- ✅ Documentação de design tokens
- ⏳ Imagens de hero/background
- ⏳ Favicon
- ⏳ Refatoração de views com componentes

**Próximo:** Adicionar imagens, gerar favicon, refatorar views

---

### Fase 3 📅 (Planejada)
**Objetivo:** Upload de conteúdo, player de vídeo, dashboard financeiro

**Duração estimada:** 3-4 semanas  
**Status:** 📅 Não iniciada

**Entregas:**
- Upload de PDF, vídeo, imagem
- Player de vídeo (Vimeo/YouTube ou próprio)
- Dashboard financeiro com gráficos
- Relatórios exportáveis
- Notificações (email, SMS)
- Agendamento de turmas

**Dependências:** Fase 2 concluída

---

### Fase 4 📅 (Planejada)
**Objetivo:** Segurança, performance, produção

**Duração estimada:** 2-3 semanas  
**Status:** 📅 Não iniciada

**Entregas:**
- Rate limiting
- Validação de CPF
- Criptografia de dados sensíveis
- Backup automático
- Cache (Redis)
- CDN para assets
- Testes de carga
- Documentação de deployment

**Dependências:** Fase 3 concluída

---

## Próximos Passos

### Imediato (Hoje/Amanhã)
1. **Validar visualmente** a Home, Login, Register em `localhost:5173`
2. **Adicionar imagens de hero** (usando placeholders públicos do site institucional)
3. **Gerar favicon** a partir da logo WR
4. **Refatorar views** para usar componentes reutilizáveis

### Curto Prazo (Esta Semana)
1. **Fazer merge** de `fix/branding-wr-identity` para `main`
2. **Testar fluxo completo** (login → dashboard → cursos)
3. **Validar integração Mercado Pago** (teste de pagamento)
4. **Documentar** endpoints da API (Swagger/OpenAPI)

### Médio Prazo (Próximas 2-3 Semanas)
1. **Iniciar Fase 3** — Upload de conteúdo
2. **Implementar player de vídeo**
3. **Criar dashboard financeiro**
4. **Adicionar relatórios**

### Longo Prazo (Após Fase 3)
1. **Otimizações de segurança** (Fase 4)
2. **Testes de carga** e performance
3. **Deployment em produção**
4. **Migração de dados** da plataforma legada (Moodle)

---

## Estatísticas do Projeto

### Código

| Métrica | Valor |
|---------|-------|
| **Linhas de código (Backend)** | ~2.500 |
| **Linhas de código (Frontend)** | ~3.500 |
| **Arquivos Python** | 25+ |
| **Arquivos Vue** | 15+ |
| **Componentes reutilizáveis** | 5 |
| **Endpoints API** | 40+ |
| **Modelos de dados** | 8 |
| **Cursos em seed data** | 55+ |

### Documentação

| Arquivo | Status |
|---------|--------|
| `DESIGN_TOKENS.md` | ✅ Completo |
| `BRANDING_UPDATE.md` | ✅ Completo |
| `LEGACY_PLATFORM_ALIGNMENT.md` | ✅ Completo |
| `PHASE_2_ASSETS.md` | ✅ Completo |
| `components/README.md` | ✅ Completo |
| `PROJECT_STATUS.md` | ✅ Completo |
| `PROJECT_SUMMARY.md` | ✅ Este arquivo |

---

## Contato & Referências

- **GitHub:** https://github.com/LeonardoRFragoso/Plataforma-Cursos-WRConsultoria
- **Site institucional:** https://wrconsultoriaesolucoes.com.br/
- **Plataforma legada (WooCommerce):** https://wrsst-treinamentos.com.br/
- **Plataforma legada (Moodle):** https://ead.wrsst-treinamentos.com.br/

---

**Última atualização:** 12 de Agosto de 2026, 22:42 UTC-03:00  
**Próxima revisão:** Após conclusão da Fase 2
