# Proposta de Arquitetura Multi-Tenant White-Label — "Seja Parceiro"

> **NOTA (2026-08-15):** Esta era uma proposta de design. A arquitetura
> multi-tenant agora está IMPLEMENTADA e em produção (v2.0). Este
> documento é mantido como referência histórica do design. Para o
> estado atual, veja `CHANGELOG.md` e `docs/DEPLOYMENT.md`.

## 1. Visão geral

Transformar a plataforma de **single-tenant** (só a WR) para **multi-tenant** (WR + N parceiros), mantendo uma única instância de aplicação e um único banco de dados PostgreSQL.

Cada parceiro — incluindo a própria WR — é representado por um `Tenant` e acessa a plataforma com identidade visual e dados isolados. A abordagem escolhida é **shared database, tenant_id em cada linha** (shared database, separate schema row), com **Row-Level Security (RLS)** do PostgreSQL como camada extra de proteção.

---

## 2. Decisões de negócio assumidas (para validação)

| Pergunta | Decisão proposta | Racional |
|---|---|---|
| Modelo de cobrança | Assinatura mensal fixa, cobrada fora da plataforma por enquanto. | Simplifica o MVP; dá à WR liberdade para faturar por boleto/PIX/contrato manual. O `Tenant` já guarda `plan` para evoluir depois. |
| Onboarding | **Curado** (com aprovação manual da WR). | O produto é novo e a WR precisa validar cada parceiro antes de liberar a marca/reputação dela. |
| Domínio | **Subdomínio** (`parceiro.suaplataforma.com.br`) no início. | Mais simples de provisionar, não exige gerenciamento de DNS/CNAME por parceiro. Domínio customizado é fase futura. |
| WR como tenant | Sim — a própria WR é o primeiro `Tenant` (master). | Evita exceções de código e mantém o mesmo mecanismo para todos. |

---

## 3. Estratégia de isolamento: shared database + RLS

### 3.1 `tenant_id` em cada tabela

Todas as tabelas de domínio passam a ter uma coluna `tenant_id UUID NOT NULL` com FK para `tenants.id`. As tabelas atingidas são:

- `users`
- `courses`
- `classes`
- `students`
- `enrollments`
- `payments`
- `certificates`
- `companies`
- `attendances`
- `lessons`
- `lesson_materials`
- `lesson_progress`
- `partner_leads` (apenas `tenant_id` nulo durante captação, depois linkado)

> **Exceção intencional:** `tenants` não tem `tenant_id` (tabela global). Tabelas de catálogo/lookup, se aparecerem no futuro, podem ser globais (`tenant_id` opcional/null) ou por tenant, dependendo do caso.

### 3.2 Row-Level Security (RLS)

Habilitar RLS nas tabelas e definir políticas baseadas em `current_setting('app.current_tenant')`:

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_users ON users
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant')::UUID);
```

A aplicação executa, ao abrir a conexão ou no início de cada requisição:

```python
await db.execute(text("SET LOCAL app.current_tenant = :tenant_id"))
```

Isso impede vazamento mesmo se uma query esquecer o filtro de `tenant_id` por algum bug. A recomendação é usar **ambas** as camadas: filtro explícito no SQLAlchemy **e** RLS.

### 3.3 RLS no contexto de `super_admin`

Para `super_admin` (equipe da WR), as queries internas podem usar `BYPASSRLS` em uma role PostgreSQL específica, ou a aplicação pode setar `app.current_tenant` para `NULL`/`0000...` e usar políticas especiais. O caminho mais seguro é criar uma role PostgreSQL de aplicação `app_superadmin` com `BYPASSRLS` para funções internas de gestão global.

---

## 4. Novos modelos

### 4.1 `Tenant` (tabela global)

```
id: UUID PK
name: str              # razão social
slug: str unique       # parceiro -> parceiro.suaplataforma.com.br
custom_domain: str unique nullable  # fase futura
logo_url: str nullable
logo_white_url: str nullable
primary_color: str nullable
secondary_color: str nullable
accent_color: str nullable
status: enum(PENDENTE, ATIVO, SUSPENSO)
plan: str nullable     # placeholder do modelo de cobrança
contact_name: str
contact_email: str
contact_phone: str nullable
settings: JSONB nullable  # extensibilidade futura
created_at: datetime
updated_at: datetime
```

### 4.2 `PartnerLead` (captação de leads)

```
id: UUID PK
tenant_id: UUID FK nullable  # vazio até aprovação
company_name: str
cnpj: str nullable
contact_name: str
contact_email: str
contact_phone: str nullable
message: str nullable
status: enum(NOVO, EM_ANALISE, APROVADO, REPROVADO)
notes: str nullable         # observações do time WR
approved_at: datetime nullable
approved_by: UUID FK nullable (users.id, super_admin)
created_at: datetime
updated_at: datetime
```

### 4.3 `TenantSettings` / `TenantBilling` (fase futura)

Ficam fora do MVP inicial, mas podem ser adicionadas depois sem quebrar o core. O campo `settings` do tipo `JSONB` em `Tenant` já serve como extensibilidade.

---

## 5. Retrofit das tabelas existentes

### 5.1 Colunas a adicionar

Cada tabela listada na seção 3.1 ganha:

```sql
ALTER TABLE <tabela> ADD COLUMN tenant_id UUID NOT NULL DEFAULT 'wr-tenant-uuid';
ALTER TABLE <tabela> ADD CONSTRAINT fk_<tabela>_tenant
  FOREIGN KEY (tenant_id) REFERENCES tenants(id);
CREATE INDEX idx_<tabela>_tenant_id ON <tabela>(tenant_id);
```

### 5.2 Backfill de dados

A WR é inserida como primeiro `Tenant` durante a migration. Todos os registros existentes são atribuídos ao `tenant_id` da WR. Exemplo:

```sql
-- 1. Criar tenant da WR
INSERT INTO tenants (id, name, slug, status, contact_name, contact_email)
VALUES ('<wr-tenant-uuid>', 'WR Consultoria e Soluções em QSMS', 'wr', 'ATIVO', 'Admin WR', 'admin@wrcursos.com.br');

-- 2. Backfill tabelas existentes
UPDATE users SET tenant_id = '<wr-tenant-uuid>' WHERE tenant_id IS NULL;
UPDATE courses SET tenant_id = '<wr-tenant-uuid>' WHERE tenant_id IS NULL;
-- repetir para todas as tabelas de domínio
```

Atenção: a migration deve:
1. Criar `tenants`.
2. Inserir o tenant da WR.
3. Adicionar `tenant_id` nas tabelas **com default** igual ao UUID da WR para não quebrar `NOT NULL`.
4. Criar as FKs e índices.
5. Remover o default depois de preenchido (opcional, mas mais limpo).
6. Habilitar RLS e políticas (em migration separada para controle).

---

## 6. Resolução de tenant por requisição

### 6.1 Rota pública (`/`, `/seja-parceiro`, `/login`, `/register`, etc.)

O backend identifica o tenant pelo header `Host`:

```
parceiro.suaplataforma.com.br -> slug 'parceiro' -> tenant_id
```

Se for o domínio principal (ex. `suaplataforma.com.br` ou `wrcursos.com.br`), resolve para o tenant master (WR). Subdomínio não reconhecido retorna 404/tenant not found.

O middleware:
1. Lê `Host`.
2. Busca `Tenant` por `slug` (ou `custom_domain` quando houver).
3. Injeta `tenant_id` no `request.state`.
4. Para rotas autenticadas, valida se o `tenant_id` do token bate com o do header.

### 6.2 JWT

Os tokens continuam carregando `user_id` e `role`. Adiciona-se o `tenant_id` no payload:

```json
{
  "sub": "user-uuid",
  "role": "admin",
  "tenant_id": "tenant-uuid"
}
```

Assim, em rotas autenticadas, a aplicação não precisa consultar o `Host` de novo — usa o `tenant_id` do token. O middleware de validação cruzada garante que um admin de um parceiro não envie um token de outro tenant.

### 6.3 Aplicação do filtro em todas as queries

O `get_db` deve setar o `app.current_tenant` na conexão **antes** de devolver a sessão. Exemplo:

```python
async def get_db(request: Request):
    tenant_id = request.state.tenant_id
    async with AsyncSession(engine) as session:
        await session.execute(text("SET LOCAL app.current_tenant = :tenant_id"), {"tenant_id": str(tenant_id)})
        yield session
```

Todas as queries do SQLAlchemy devem incluir o filtro explícito:

```python
stmt = select(Course).where(Course.tenant_id == tenant_id)
```

O RLS atua como rede de segurança, mas o filtro de aplicação é a principal linha de defesa e ajuda o PostgreSQL a usar os índices corretos.

---

## 7. Roles e autorização

### 7.1 Novo role `super_admin`

- Acessa todos os tenants.
- Aprova/reprova `PartnerLead`.
- Provisiona novos parceiros.
- Vê painel global de tenants.

### 7.2 `admin` (por tenant)

- Escopado ao `tenant_id` do token.
- Não vê/gerencia outros tenants.
- Gestão de cursos, turmas, alunos, matrículas, pagamentos etc. do próprio tenant.

### 7.3 `student` (por tenant)

- Só vê cursos e turmas do seu tenant.
- Só se matricula em turmas do seu tenant.

### 7.4 `instructor`

Role removido recentemente; se for reintroduzido no futuro, também será por tenant.

---

## 8. Tema/branding dinâmico no frontend

### 8.1 Configuração pública do tenant

Endpoint `GET /api/v1/tenants/{slug}` (público, sem autenticação) retorna:

```json
{
  "name": "Parceiro X",
  "logo_url": "...",
  "logo_white_url": "...",
  "primary_color": "#1a365d",
  "secondary_color": "#2c5282",
  "accent_color": "#ed8936"
}
```

### 8.2 Aplicação do tema

No `App.vue` ou `AppNavbar.vue`, ao montar:

```js
const slug = window.location.hostname.split('.')[0]  // parceiro
const { data } = await api.get(`/api/v1/tenants/${slug}`)

// Aplica variáveis CSS
for (const [key, value] of Object.entries(data.colors)) {
  document.documentElement.style.setProperty(`--color-${key}`, value)
}
```

Substitui o branding fixo da WR. O Tailwind pode usar as variáveis CSS ou as cores são injetadas via estilos inline no `App.vue`.

---

## 9. Página "Seja Parceiro" e fluxo de aprovação

### 9.1 Página pública

Rota `/seja-parceiro` (acessível por qualquer subdomínio/domínio principal, sem login). Formulário captura:

- Nome da empresa
- CNPJ
- Nome do contato
- E-mail
- Telefone
- Mensagem

### 9.2 Backend

`POST /api/v1/partner-leads` cria `PartnerLead` com `status=NOVO` e `tenant_id=NULL`.

### 9.3 Painel `super_admin`

- `GET /api/v1/partner-leads` (super_admin only)
- `POST /api/v1/partner-leads/{id}/approve` → cria `Tenant`, cria usuário `admin` do parceiro (com senha temporária/envio de e-mail), vincula `PartnerLead.tenant_id`.
- `POST /api/v1/partner-leads/{id}/reject` → atualiza status e permite `notes`.

---

## 10. Plano de migration passo a passo

1. **Migration 1 — Criar tabelas globais**
   - `tenants`
   - `partner_leads`
   - Inserir tenant da WR com UUID fixo/gerado.

2. **Migration 2 — Adicionar `tenant_id` em todas as tabelas de domínio**
   - Adicionar coluna `tenant_id` com `DEFAULT '<wr-tenant-uuid>'`.
   - Backfill (o próprio default já faz, mas explicitar para segurança).
   - Criar FKs e índices.
   - Tornar `NOT NULL` (se ainda não estiver).

3. **Migration 3 — Atualizar modelos e lógica da aplicação**
   - Adicionar `tenant_id` nos models.
   - Criar `Tenant` e `PartnerLead` models/schemas/routes.
   - Criar middleware de resolução de tenant.
   - Atualizar `get_db` para setar `app.current_tenant`.

4. **Migration 4 — Habilitar RLS e políticas**
   - `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`
   - Criar `tenant_isolation_*` para cada tabela.

5. **Migration 5 — Dados do super_admin**
   - Promover ou criar usuário da WR com role `super_admin`.
   - Garantir que todos os usuários existentes tenham `tenant_id` da WR.

---

## 11. Riscos e pontos de atenção

| Risco | Impacto | Mitigação |
|---|---|---|
| Vazamento de dados entre tenants por query sem `tenant_id` | Alto | Filtrar toda query; ativar RLS; testar integração cross-tenant. |
| Performance: cada query ganha um filtro a mais | Médio | Índices em `tenant_id` em todas as tabelas; RLS ajuda o planner quando a query é bem filtrada. |
| Regressão em funcionalidades já existentes (matrícula corporativa, vídeos, certificados) | Alto | Mudança gradual: primeiro schema + backfill, depois lógica. Testar após cada passo. |
| Dados reais da WR precisam ser migrados com zero downtime | Alto | Usar migrations com `DEFAULT` e backfill; rodar em horário de baixa atividade; backup antes. |
| Subdomínio não resolvido corretamente em ambiente de desenvolvimento | Médio | Configurar `/etc/hosts` local ou usar `x.localhost` com testes; middleware com fallback para tenant master. |
| Cobrança de parceiros ainda indefinida | Médio | Deixar `plan` e `TenantBilling` como placeholders; cobrança manual fora da plataforma no início. |
| Domínio customizado é complexo | Baixo-Médio | Deixar `custom_domain` nullable; implementar depois do MVP multi-tenant. |
| Uploads de vídeo e storage — bucket por tenant ou bucket compartilhado? | Médio | Usar **bucket compartilhado com prefixo por tenant** (`{tenant_id}/lessons/...`) para simplificar. Avaliar separar no futuro se o volume crescer. |

---

## 12. Estimativa de esforço

> Nota: estimativas são grossas e dependem de revisão do escopo. Consideram 1 desenvolvedor em paralelo com testes manuais.

| Etapa | Esforço estimado |
|---|---|
| Schema `Tenant` e `PartnerLead` + migration 1 | 1 dia |
| Retrofit `tenant_id` em todas as tabelas (models, schemas, migration 2) | 2 dias |
| Middleware de resolução de tenant, filtros em todas as queries, ajuste do `get_db` | 3-4 dias |
| Roles: adicionar `super_admin` e escopar `admin` por tenant | 1-2 dias |
| Tema dinâmico no frontend + endpoint público de configuração | 2-3 dias |
| Página "Seja Parceiro" + painel de aprovação/provisionamento | 3-4 dias |
| Ajustes em testes e documentação | 1-2 dias |
| QA, testes cross-tenant, correções | 2-3 dias |
| **Total estimado** | **14-19 dias** |

---

## 13. Ordem de execução recomendada (revisada)

1. Validar este documento com o CEO/time de produto.
2. Aprovar as decisões de negócio assumidas (cobrança, onboarding, domínio).
3. Implementar `Tenant`, `PartnerLead` e o tenant master da WR.
4. Retrofit das tabelas existentes com `tenant_id` e backfill.
5. Middleware de resolução de tenant e filtro nas queries.
6. RLS.
7. Tema dinâmico e página "Seja Parceiro".
8. Painel `super_admin` de aprovação.
9. QA cross-tenant e ajustes.

---

## 14. Próximos passos

Aguardar validação deste documento antes de alterar qualquer model, migration ou rota existente. Após aprovação, o primeiro commit deverá conter **apenas** a criação das tabelas `tenants` e `partner_leads`, sem tocar nas tabelas de domínio.
