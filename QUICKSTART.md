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

## 3. Migrations e Seed

Crie as tabelas e popule o banco com dados de teste:

```bash
# Migrations Alembic
docker-compose exec api alembic upgrade head

# Seed de dados de teste (cria admin, instrutor, alunos, cursos, turmas etc.)
docker-compose exec api python seed_db.py
```

Ou, sem Docker:

```bash
cd api
source venv/bin/activate
alembic upgrade head
python seed_db.py
```

## 4. Acesse a Aplicação

- **Frontend:** http://localhost:5173
- **API Swagger:** http://localhost:8000/docs
- **API ReDoc:** http://localhost:8000/redoc

## 5. Teste o Fluxo Completo

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
    "identifier": "aluno@example.com",
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
    "modality": "PRESENCIAL",
    "tipo_curso": "FORMACAO",
    "price": 500.00,
    "description": "Treinamento NR-10"
  }'
```

### Listar Cursos
```bash
curl http://localhost:8000/api/v1/courses/
```

## 6. Rodar Testes

```bash
# Backend
docker-compose exec api pytest tests/ -v

# Frontend
docker-compose exec web npm run test
```

## 7. Parar os Serviços

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

Os usuários de teste são criados automaticamente pelo `seed_db.py`:

| Usuário | Senha | Role |
|---|---|---|
| `admin@wrcursos.com.br` | `admin123` | `admin` |
| `student@wrcursos.com.br` | `student123` | `student` |

Se precisar criar um admin manualmente, acesse o banco e atualize o `role`:

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
