# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

## [1.0.0] - 2024-01-XX

### Adicionado
- Estrutura inicial do projeto (backend FastAPI + frontend Vue 3)
- Autenticação com JWT (access + refresh token)
- RBAC com 3 roles: admin, instructor, student
- Modelos de dados completos (User, Course, Class, Student, Enrollment, Payment, Certificate, Attendance)
- Endpoints REST para:
  - Autenticação (login, register, refresh, me)
  - Cursos (CRUD)
  - Turmas (CRUD)
  - Alunos (CRUD)
  - Matrículas (CRUD)
  - Pagamentos (CRUD + webhook Mercado Pago)
  - Certificados (CRUD + validação pública)
- Frontend com páginas:
  - Home (landing page)
  - Login/Register
  - Dashboard
  - Gerenciamento de Cursos
  - Gerenciamento de Turmas
  - Gerenciamento de Alunos
  - Gerenciamento de Matrículas
  - Gerenciamento de Pagamentos
  - Gerenciamento de Certificados
- Integração com Mercado Pago (preferências de pagamento + webhook)
- Geração de certificados em PDF com ReportLab
- Testes unitários (pytest backend + Vitest frontend)
- Docker + docker-compose para ambiente local
- Documentação (README, ARCHITECTURE, CONTRIBUTING)
- Tailwind CSS para styling
- Pinia para state management
- Vue Router para navegação

### Próximas Fases
- [ ] Emissão de notas fiscais (NF-e)
- [ ] Upload de materiais didáticos
- [ ] Player de vídeo próprio
- [ ] Dashboard financeiro avançado
- [ ] Relatórios exportáveis (CSV/Excel)
- [ ] Portal do aluno completo
- [ ] Vitrine pública de cursos
- [ ] Sistema de avaliações
- [ ] Notificações por email
- [ ] Integração com CRM
