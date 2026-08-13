# Arquitetura da Plataforma WR Cursos

## Visão Geral

A plataforma WR Cursos é uma aplicação web full-stack para gestão de cursos e treinamentos normativos (NRs). A arquitetura segue padrões modernos de desenvolvimento com separação clara entre frontend e backend.

## Stack Técnica

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy 2.x (async)
- **Banco de Dados:** PostgreSQL 16
- **Autenticação:** JWT (access + refresh token)
- **Validação:** Pydantic v2
- **Migrations:** Alembic
- **Testes:** pytest

### Frontend
- **Framework:** Vue 3 (Composition API)
- **Bundler:** Vite
- **State Management:** Pinia
- **Roteamento:** Vue Router
- **Styling:** Tailwind CSS
- **Testes:** Vitest + Playwright
- **HTTP Client:** Axios

### Infraestrutura
- **Containerização:** Docker + Docker Compose
- **Deploy:** Railway/Render (PaaS)

## Estrutura do Projeto

```
WR-Plataforma-Cursos/
├── api/                              # Backend FastAPI
│   ├── app/
│   │   ├── main.py                  # Aplicação principal
│   │   ├── core/
│   │   │   ├── config.py            # Configurações (variáveis de ambiente)
│   │   │   ├── database.py          # Conexão e sessão do banco
│   │   │   └── security.py          # JWT, hash de senha, RBAC
│   │   ├── models/                  # Modelos SQLAlchemy (ORM)
│   │   │   ├── user.py
│   │   │   ├── course.py
│   │   │   ├── class_model.py
│   │   │   ├── student.py
│   │   │   ├── enrollment.py
│   │   │   ├── payment.py
│   │   │   ├── certificate.py
│   │   │   └── attendance.py
│   │   ├── schemas/                 # Schemas Pydantic (validação)
│   │   │   ├── user.py
│   │   │   ├── course.py
│   │   │   ├── class_schema.py
│   │   │   ├── student.py
│   │   │   ├── enrollment.py
│   │   │   ├── payment.py
│   │   │   └── certificate.py
│   │   ├── api/
│   │   │   └── routes/              # Routers/endpoints
│   │   │       ├── auth.py
│   │   │       ├── courses.py
│   │   │       ├── classes.py
│   │   │       ├── students.py
│   │   │       ├── enrollments.py
│   │   │       ├── payments.py
│   │   │       └── certificates.py
│   │   └── services/                # Lógica de negócio
│   │       ├── mercado_pago_service.py
│   │       └── certificate_service.py
│   ├── tests/                       # Testes unitários e integração
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pytest.ini
├── web/                             # Frontend Vue 3
│   ├── src/
│   │   ├── main.js                 # Entry point
│   │   ├── App.vue                 # Componente raiz
│   │   ├── router/
│   │   │   └── index.js            # Configuração de rotas
│   │   ├── stores/
│   │   │   └── auth.js             # Pinia store de autenticação
│   │   ├── views/                  # Páginas/componentes principais
│   │   │   ├── Home.vue
│   │   │   ├── Login.vue
│   │   │   ├── Register.vue
│   │   │   ├── Dashboard.vue
│   │   │   ├── Courses.vue
│   │   │   ├── Classes.vue
│   │   │   ├── Students.vue
│   │   │   ├── Enrollments.vue
│   │   │   ├── Payments.vue
│   │   │   ├── Certificates.vue
│   │   │   ├── CourseDetail.vue
│   │   │   └── NotFound.vue
│   │   ├── components/             # Componentes reutilizáveis
│   │   ├── api/
│   │   │   └── client.js           # Cliente HTTP (Axios)
│   │   ├── style.css               # Estilos globais
│   │   └── __tests__/              # Testes
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── vitest.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── .eslintrc.cjs
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── ARCHITECTURE.md
```

## Padrões de Arquitetura

### Backend - Arquitetura em Camadas

```
Request → Router → Security (JWT) → Service → Repository → Database
                                        ↓
                                    Validation (Pydantic)
```

1. **Routers (API Routes):** Definem os endpoints HTTP
2. **Security:** Autenticação JWT e RBAC
3. **Services:** Lógica de negócio (Mercado Pago, Certificados)
4. **Models:** Representação dos dados no banco (SQLAlchemy)
5. **Schemas:** Validação de entrada/saída (Pydantic)

### Frontend - Composição Vue 3

```
Router → View Component → Pinia Store → API Client → Backend
                              ↓
                         localStorage
```

1. **Router:** Navegação entre páginas
2. **Views:** Componentes de página
3. **Stores:** Gerenciamento de estado (Pinia)
4. **API Client:** Requisições HTTP com interceptadores
5. **localStorage:** Persistência de tokens

## Fluxo de Autenticação

### Login

```
1. Usuário preenche formulário (email + senha)
2. Frontend POST /api/v1/auth/login
3. Backend valida credenciais
4. Backend gera access_token (JWT, 30 min) + refresh_token (7 dias)
5. Frontend armazena tokens em localStorage
6. Frontend redireciona para /dashboard
```

### Requisições Autenticadas

```
1. Frontend adiciona Authorization: Bearer <access_token> em todas as requisições
2. Backend valida JWT em cada endpoint protegido
3. Se token expirado, frontend intercepta 401
4. Frontend POST /api/v1/auth/refresh com refresh_token
5. Backend retorna novo access_token
6. Frontend retenta requisição original
```

### Logout

```
1. Usuário clica em "Sair"
2. Frontend limpa tokens do localStorage
3. Frontend redireciona para /login
```

## Fluxo de Matrícula → Pagamento → Certificado

```
1. Aluno clica em "Matricular" em um curso
   → POST /api/v1/enrollments/ (status: PENDENTE)

2. Sistema cria preferência de pagamento no Mercado Pago
   → POST /api/v1/payments/ (status: PENDENTE)
   → Mercado Pago retorna link de pagamento

3. Aluno paga via Mercado Pago (PIX, boleto, cartão)

4. Mercado Pago envia webhook
   → POST /api/v1/payments/webhook/mercado-pago
   → Backend atualiza payment.status = APROVADO
   → Backend atualiza enrollment.status = CONFIRMADA

5. Admin gera certificado
   → POST /api/v1/certificates/ (enrollment_id)
   → Backend gera PDF com dados do aluno/curso
   → Certificado armazenado com código de validação

6. Aluno acessa /certificates para visualizar/baixar certificado

7. Público pode validar certificado
   → POST /api/v1/certificates/validate (validation_code)
   → Retorna dados do certificado (nome, curso, data)
```

## Modelos de Dados

### User
- Autenticação e autorização
- Roles: admin, instructor, student
- Email único

### Course
- Informações do curso (código NR, nome, carga horária, preço)
- Modalidade: presencial, EAD, semipresencial
- Status: ativo/inativo

### Class
- Turma de um curso
- Instrutor responsável
- Data início/fim, vagas, local/link EAD
- Status: aberta, em_andamento, concluida, cancelada

### Student
- Dados pessoais do aluno (CPF, telefone, empresa)
- Vinculado a um User

### Enrollment
- Matrícula de aluno em turma
- Status: pendente, confirmada, cancelada, concluida
- Preço da matrícula

### Payment
- Pagamento de matrícula
- Método: cartão, boleto, PIX
- Status: pendente, processando, aprovado, recusado, reembolsado
- ID do Mercado Pago para rastreamento

### Certificate
- Certificado de conclusão
- Número único e código de validação
- Caminho do PDF gerado

### Attendance
- Controle de frequência
- Aluno + Turma + Data
- Status: presente/ausente

## Segurança

### Autenticação
- Senhas com hash bcrypt
- JWT com expiração
- Refresh token para renovação

### Autorização (RBAC)
- **Admin:** Acesso total
- **Instructor:** Gestão de turmas e presença
- **Student:** Portal do aluno

### Validação
- Pydantic valida todos os inputs
- Email-validator para emails
- Rate limiting em endpoints sensíveis (future)

### CORS
- Configurável por variável de ambiente
- Apenas origens permitidas podem acessar API

## Integração com Mercado Pago

### Fluxo
1. Backend cria preferência com dados da matrícula
2. Mercado Pago retorna URL de checkout
3. Aluno é redirecionado para pagar
4. Mercado Pago envia webhook ao backend
5. Backend processa webhook e atualiza status de pagamento

### Webhook
- Endpoint: `POST /api/v1/payments/webhook/mercado-pago`
- Valida assinatura do Mercado Pago
- Atualiza status do pagamento e matrícula

## Geração de Certificados

### Processo
1. Admin solicita geração de certificado para uma matrícula
2. Backend busca dados do aluno, curso e turma
3. Backend gera PDF com ReportLab
4. PDF é armazenado no servidor ou S3
5. Certificado registrado no banco com código de validação

### Validação Pública
- Qualquer pessoa pode validar certificado
- Endpoint público: `POST /api/v1/certificates/validate`
- Retorna dados do certificado sem expor informações sensíveis

## Deployment

### Docker
- Cada serviço (API, Frontend, DB) em container separado
- docker-compose orquestra os containers
- Volumes para persistência de dados

### Railway/Render
- Conectar repositório GitHub
- Configurar variáveis de ambiente
- Deploy automático em cada push

### Variáveis de Ambiente
- `DATABASE_URL`: Conexão PostgreSQL
- `SECRET_KEY`: Chave para JWT
- `MERCADO_PAGO_ACCESS_TOKEN`: Token de autenticação
- `SMTP_*`: Configurações de email
- `CORS_ORIGINS`: Origens permitidas
- `FRONTEND_URL`: URL do frontend (para webhooks)

## Próximas Melhorias

1. **Testes E2E:** Playwright para fluxos críticos
2. **Cache:** Redis para sessões e cache
3. **Filas:** Celery para processamento assíncrono (emails, PDFs)
4. **Logging:** Estruturado com ELK ou similar
5. **Monitoramento:** Sentry para erros, Prometheus para métricas
6. **CI/CD:** GitHub Actions para testes e deploy automático
7. **Documentação:** OpenAPI/Swagger automático (já incluído)
