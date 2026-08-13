# Quick Start - WR Plataforma de Cursos

Comece em 5 minutos! 🚀

## Pré-requisitos

- Docker e Docker Compose instalados
- Git

## 1. Clone e Configure

```bash
git clone <repo-url>
cd WR-Plataforma-Cursos
cp .env.example .env
```

## 2. Inicie os Serviços

```bash
docker-compose up -d
```

Aguarde ~30 segundos para os serviços iniciarem.

## 3. Acesse a Aplicação

- **Frontend:** http://localhost:5173
- **API Swagger:** http://localhost:8000/docs
- **API ReDoc:** http://localhost:8000/redoc

## 4. Teste o Fluxo Completo

### Cadastro de Usuário
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "aluno@example.com",
    "full_name": "João Silva",
    "password": "senha123"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "aluno@example.com",
    "password": "senha123"
  }'
```

Copie o `access_token` retornado.

### Criar Curso (Admin)
```bash
curl -X POST http://localhost:8000/api/v1/courses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <seu-access-token>" \
  -d '{
    "code": "NR-10",
    "name": "Segurança em Instalações Elétricas",
    "category": "Segurança",
    "carga_horaria": 40,
    "modality": "presencial",
    "price": 500.00,
    "description": "Treinamento NR-10"
  }'
```

### Listar Cursos
```bash
curl http://localhost:8000/api/v1/courses/
```

## 5. Rodar Testes

```bash
# Backend
docker-compose exec api pytest tests/ -v

# Frontend
docker-compose exec web npm run test
```

## 6. Parar os Serviços

```bash
docker-compose down
```

## Próximos Passos

- Leia [README.md](README.md) para documentação completa
- Leia [ARCHITECTURE.md](ARCHITECTURE.md) para entender a estrutura
- Leia [CONTRIBUTING.md](CONTRIBUTING.md) para padrões de desenvolvimento

## Troubleshooting

### Porta 5173 ou 8000 já em uso?

```bash
# Mude a porta no docker-compose.yml
# Ou mate o processo:
lsof -i :5173
kill -9 <PID>
```

### Banco de dados não inicia?

```bash
# Limpe os volumes
docker-compose down -v
docker-compose up -d
```

### Erro de conexão com API?

```bash
# Verifique se os containers estão rodando
docker-compose ps

# Verifique os logs
docker-compose logs api
docker-compose logs web
```

## Estrutura Rápida

```
Backend (FastAPI)
├── Autenticação JWT ✅
├── CRUD Cursos ✅
├── CRUD Turmas ✅
├── CRUD Alunos ✅
├── CRUD Matrículas ✅
├── Pagamentos (Mercado Pago) ✅
└── Certificados (PDF) ✅

Frontend (Vue 3)
├── Login/Register ✅
├── Dashboard ✅
├── Gerenciamento de Cursos ✅
├── Gerenciamento de Turmas ✅
├── Gerenciamento de Alunos ✅
├── Gerenciamento de Matrículas ✅
├── Gerenciamento de Pagamentos ✅
└── Gerenciamento de Certificados ✅
```

## Credenciais Padrão

Não há usuário admin pré-criado. Você precisa:

1. Registrar um usuário via `/api/v1/auth/register`
2. Acessar o banco de dados e atualizar o `role` para `'admin'`

```bash
# Acesse o container do banco
docker-compose exec postgres psql -U postgres -d wr_cursos

# Atualize o role
UPDATE users SET role = 'admin' WHERE email = 'seu@email.com';
```

## Variáveis de Ambiente Importantes

```env
# JWT
SECRET_KEY=change-this-in-production

# Mercado Pago (opcional para testes locais)
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=

# SMTP (opcional para testes locais)
SMTP_USER=
SMTP_PASSWORD=
```

## Documentação Completa

- [README.md](README.md) - Setup detalhado e endpoints
- [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitetura e fluxos
- [CONTRIBUTING.md](CONTRIBUTING.md) - Padrões de código
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Status e roadmap

---

**Pronto para começar?** Abra http://localhost:5173 no seu navegador! 🎉
