# WR Plataforma de Cursos

Plataforma web de gestão e comercialização de cursos (LMS + backoffice administrativo) para a WR Consultoria e Soluções em QSMS.

## Stack Técnica

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy 2.x (async), Alembic, Pydantic v2
- **Frontend:** Vue 3 (Composition API) + TypeScript, Vite, Pinia, Vue Router, Tailwind CSS
- **Banco de Dados:** PostgreSQL 16
- **Autenticação:** JWT (access + refresh token) com RBAC
- **Infraestrutura:** Docker + docker-compose

## Requisitos

- Docker e Docker Compose
- Node.js 18+ (para desenvolvimento local sem Docker)
- Python 3.11+ (para desenvolvimento local sem Docker)

## Setup Local com Docker

### 1. Clone o repositório

```bash
git clone <repo-url>
cd WR-Plataforma-Cursos
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:

```env
# Database
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=wr_cursos

# JWT
SECRET_KEY=your-super-secret-key-change-in-production

# Mercado Pago (opcional para fase inicial)
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=

# Email (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Frontend
VITE_API_URL=http://localhost:8000
```

### 3. Inicie os serviços

```bash
docker-compose up -d
```

Isso irá:
- Criar e iniciar o banco de dados PostgreSQL
- Construir e iniciar a API FastAPI (porta 8000)
- Construir e iniciar o frontend Vue (porta 5173)

### 4. Acesse a aplicação

- **Frontend:** http://localhost:5173
- **API (Swagger):** http://localhost:8000/docs
- **API (ReDoc):** http://localhost:8000/redoc

## Migrations (Alembic)

O banco de dados é versionado com Alembic. Para criar as tabelas (ou atualizá-las após uma mudança de model):

```bash
cd api
source venv/bin/activate
alembic upgrade head
```

Ou, com Docker:

```bash
docker-compose exec api alembic upgrade head
```

Para gerar uma nova migration após alterar os models:

```bash
cd api
alembic revision --autogenerate -m "Nome da mudança"
```

## Setup Local sem Docker

### Backend

```bash
cd api
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure o banco de dados
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos"

# Crie/ative as tabelas
alembic upgrade head

# Popule o banco com dados de teste (opcional)
python seed_db.py

uvicorn app.main:app --reload
```

### Frontend

```bash
cd web
npm install
npm run dev
```

## Estrutura do Projeto

```
WR-Plataforma-Cursos/
├── api/                          # Backend FastAPI
│   ├── app/
│   │   ├── main.py              # Aplicação principal
│   │   ├── core/                # Configurações, segurança, banco de dados
│   │   ├── models/              # Modelos SQLAlchemy
│   │   ├── schemas/             # Schemas Pydantic
│   │   └── api/routes/          # Routers/endpoints
│   ├── requirements.txt
│   └── Dockerfile
├── web/                          # Frontend Vue 3
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/              # Vue Router
│   │   ├── stores/              # Pinia stores
│   │   ├── views/               # Páginas
│   │   ├── components/          # Componentes reutilizáveis
│   │   ├── api/                 # Cliente HTTP
│   │   └── style.css
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Modelos de Dados

### Usuários (User)
- Autenticação com JWT
- Roles: admin, student
- Email único

### Cursos (Course)
- Código NR único
- Modalidades: presencial, EAD, semipresencial
- Carga horária, preço, descrição

### Turmas (Class)
- Vinculadas a cursos
- Responsável (admin)
- Data início/fim, vagas, local/link EAD
- Status: aberta, em_andamento, concluida, cancelada

### Alunos (Student)
- Vinculados a usuários
- CPF único
- Dados pessoais e empresa

### Matrículas (Enrollment)
- Aluno + Turma
- Status: pendente, confirmada, cancelada, concluida
- Preço da matrícula

### Pagamentos (Payment)
- Vinculados a matrículas
- Métodos: cartão, boleto, PIX
- Status: pendente, processando, aprovado, recusado, reembolsado
- Integração com Mercado Pago

### Certificados (Certificate)
- Gerados automaticamente ao concluir
- Número único e código de validação
- Validação pública por código

### Presença (Attendance)
- Controle de frequência por aluno/turma
- Data e status (presente/ausente)

## Autenticação e Autorização

### Fluxo de Login

1. Usuário faz POST em `/api/v1/auth/login` com email e senha
2. API retorna `access_token` (JWT) e `refresh_token`
3. Frontend armazena tokens no localStorage
4. Requisições subsequentes incluem `Authorization: Bearer <token>`

### Refresh Token

- Access token expira em 30 minutos
- Refresh token expira em 7 dias
- Frontend intercepta 401 e tenta renovar automaticamente

### Roles (RBAC)

- **admin:** Acesso total (cursos, turmas, alunos, financeiro)
- **student:** Portal do aluno (matrículas, certificados)

## Endpoints Principais

### Autenticação
- `POST /api/v1/auth/register` - Cadastro de aluno
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Renovar token
- `GET /api/v1/auth/me` - Dados do usuário logado

### Cursos
- `GET /api/v1/courses/` - Listar cursos
- `POST /api/v1/courses/` - Criar curso (admin)
- `GET /api/v1/courses/{id}` - Detalhes do curso
- `PUT /api/v1/courses/{id}` - Atualizar curso (admin)
- `DELETE /api/v1/courses/{id}` - Deletar curso (admin)

### Turmas
- `GET /api/v1/classes/` - Listar turmas
- `POST /api/v1/classes/` - Criar turma (admin)
- `GET /api/v1/classes/{id}` - Detalhes da turma
- `PUT /api/v1/classes/{id}` - Atualizar turma (admin)
- `DELETE /api/v1/classes/{id}` - Deletar turma (admin)

### Alunos
- `GET /api/v1/students/` - Listar alunos (admin)
- `POST /api/v1/students/` - Criar aluno (admin)
- `GET /api/v1/students/{id}` - Detalhes do aluno
- `PUT /api/v1/students/{id}` - Atualizar aluno
- `DELETE /api/v1/students/{id}` - Deletar aluno (admin)

### Matrículas
- `GET /api/v1/enrollments/` - Listar matrículas (admin)
- `POST /api/v1/enrollments/` - Criar matrícula
- `GET /api/v1/enrollments/{id}` - Detalhes da matrícula
- `PUT /api/v1/enrollments/{id}` - Atualizar matrícula (admin)
- `DELETE /api/v1/enrollments/{id}` - Deletar matrícula (admin)

### Pagamentos
- `GET /api/v1/payments/` - Listar pagamentos (admin)
- `POST /api/v1/payments/` - Criar pagamento
- `GET /api/v1/payments/{id}` - Detalhes do pagamento
- `PUT /api/v1/payments/{id}` - Atualizar pagamento (admin)
- `POST /api/v1/payments/webhook/mercado-pago` - Webhook Mercado Pago

### Certificados
- `GET /api/v1/certificates/` - Listar certificados (admin)
- `POST /api/v1/certificates/` - Gerar certificado (admin)
- `GET /api/v1/certificates/{id}` - Detalhes do certificado
- `POST /api/v1/certificates/validate` - Validar certificado (público)
- `DELETE /api/v1/certificates/{id}` - Deletar certificado (admin)

## Testes

### Backend (pytest)

```bash
cd api
pytest tests/ -v
pytest tests/ --cov=app
```

### Frontend (Vitest)

```bash
cd web
npm run test
npm run test:coverage
npm run test:ui
```

## Deploy

### Railway/Render

1. Conecte o repositório GitHub
2. Configure as variáveis de ambiente
3. Defina o comando de build:
   - Backend: `pip install -r api/requirements.txt`
   - Frontend: `npm install && npm run build` (em `web/`)
4. Defina o comando de start:
   - Backend: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Frontend: Servir arquivos estáticos de `dist/`

### Variáveis de Ambiente Necessárias

```env
DATABASE_URL=postgresql://user:password@host:5432/db
SECRET_KEY=<gere-uma-chave-segura>
MERCADO_PAGO_ACCESS_TOKEN=<seu-token>
MERCADO_PAGO_PUBLIC_KEY=<sua-chave-publica>
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<seu-email>
SMTP_PASSWORD=<sua-senha-app>
CORS_ORIGINS=https://seu-dominio.com
VITE_API_URL=https://api.seu-dominio.com
```

## Fases do white-label SaaS concluídas

- [x] Fundação multi-tenant (`Tenant`, `tenant_id`, RLS, JWT tenant-aware)
- [x] Branding dinâmico (cores, logos, CSS variables via Pinia)
- [x] Onboarding de parceiros (`PartnerLead` + aprovação)
- [x] Vitrine pública de cursos e venda
- [x] Mercado Pago por tenant (credenciais em `Tenant.settings`)
- [x] Certificados e validação pública
- [x] Recuperação de senha (JWT reset token)
- [x] Dashboard financeiro e operacional
- [x] Planos e comercialização
- [x] Custom domains, hardening, health check com latência

## E2E Tests

Spec de exemplo criado em `web/e2e/home.spec.js` (Playwright).

## Próximas Fases

- [ ] Integração completa com Mercado Pago (notificações/webhooks)
- [ ] Emissão de notas fiscais (NF-e)
- [ ] Player de vídeo próprio ou integração com Vimeo
- [ ] Sistema de avaliações e notificações
- [ ] Relatórios exportáveis (CSV/Excel)

## Contribuindo

1. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
2. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
3. Push para a branch (`git push origin feature/AmazingFeature`)
4. Abra um Pull Request

## Vídeo-Aulas (Fase 3)

As aulas (`Lesson`) pertencem a um `Course` e podem ter três tipos de conteúdo:
- **UPLOAD**: vídeo hospedado em storage S3-compatível
- **YOUTUBE**: embed via URL do vídeo
- **VIMEO**: embed via URL do vídeo

### Configuração do Storage

Configure um bucket S3-compatível (Cloudflare R2, Backblaze B2, MinIO, AWS S3) e adicione ao `.env`:

```env
STORAGE_ENDPOINT=https://<accountid>.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your-access-key
STORAGE_SECRET_KEY=your-secret-key
STORAGE_BUCKET=wr-videos
STORAGE_REGION=auto
STORAGE_WATCH_URL_EXPIRATION=7200
```

- Upload é feito **diretamente do navegador** para o storage via URL pré-assinada.
- O backend só gera a URL e salva o `storage_key`.
- Para assistir, o backend gera uma URL de leitura pré-assinada com expiração curta.

### Acesso às Aulas

- Alunos só acessam aulas após `Enrollment` com status `CONFIRMADA` ou `CONCLUIDA`.
- Aulas `is_free_preview` podem ser acessadas sem matrícula.
- Concluir todas as aulas obrigatórias dispara a criação automática do `Certificate`.

## Licença

Propriedade da WR Consultoria e Soluções em QSMS.

## Contato

WR Consultoria e Soluções em QSMS
- Site: https://wrconsultoriaesolucoes.com.br/
- Email: contato@wrconsultoriaesolucoes.com.br
