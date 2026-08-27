# Tutor NR — Arquitetura de Conhecimento com RAG

## 1. Visão geral

O Tutor NR evoluiu de um motor determinístico baseado em resumos estáticos para um sistema de **Recuperação Aumentada por Geração (RAG)** usando os materiais reais dos 15 treinamentos.

```
Pergunta do aluno
        ↓
identificação da intenção/NR/curso (scope detection)
        ↓
busca full-text em português nos chunks
        ↓
seleção dos melhores trechos (Top-K)
        ↓
construção de resposta fundamentada
        ↓
resposta em português simples + fontes
```

## 2. Componentes

### 2.1 Fontes de conhecimento

- 15 arquivos `extracted-text.md` no workspace local (`/home/leonardo/dev/Cursos-WR/analysis/...`)
- Registro canônico em `app/services/tutor/sources.py`
- Não são commitados no GitHub

### 2.2 Modelos de dados (PostgreSQL + RLS)

- `TutorKnowledgeDocument`: metadata do documento privado
- `TutorKnowledgeChunk`: fragmento indexável com `search_vector` (TSVECTOR português)
- Alembic: `i9d0e1f2a3b4_tutor_knowledge_rag.py`
- RLS/FORCE RLS ativados para `tutor_knowledge_documents` e `tutor_knowledge_chunks`

### 2.3 Ingestion

- `app/scripts/ingest_nr_tutor_knowledge.py`
- Dry-run por padrão
- Chunking estruturado por Markdown
- Idempotente por hash SHA-256
- Versionamento automático ao alterar documentos

### 2.4 Chunking

- `app/services/tutor/chunking.py`
- Orientado por headings (`#`, `##`, `###`)
- Preserva `heading_path`
- ~200–4800 caracteres por chunk
- Remove ruído de OCR (números de página, headers repetidos)

### 2.5 Scope detection

- `app/services/tutor/scope.py`
- Identifica NR e variantes por termos do aluno
- Usado como **boost** no ranking, não como filtro restritivo
- Permite perguntas multi-NR

### 2.6 Retrieval

- `app/services/tutor/retrieval.py`
- PostgreSQL full-text search (`plainto_tsquery('portuguese', ...)`)
- GIN index no `search_vector`
- Ranking: `ts_rank_cd` + scope boost
- Tenant filter explícito na query

### 2.7 Answer engine

- `app/services/tutor/answer.py`
- Proteção contra prompt injection e extração integral
- Fallback grounded (sem LLM)
- Abstração de LLM via variáveis de ambiente (`TUTOR_LLM_PROVIDER`, `TUTOR_LLM_API_KEY`, `TUTOR_LLM_MODEL`)
- Nunca expõe conteúdo integral

### 2.8 Endpoint

- `POST /api/v1/tutor/ask`
- `GET /api/v1/tutor/coverage`
- Autenticado, rate-limited
- Arquitetura multi-tenant

### 2.9 Frontend

- `web/src/components/NrTutorAssistant.vue`
- Chama `POST /api/v1/tutor/ask`
- Exibe loading, fontes, sugestões, retry, follow-up
- Fallback para motor determinístico antigo se backend indisponível

## 3. Segurança

- Conteúdo integral NUNCA retornado
- Nenhuma URL pública ou presigned URL para documentos
- RLS por tenant
- Proteção contra prompt injection e extração
- Logs sem conteúdo sensível

## 4. Testes

- Backend: `tests/test_tutor_knowledge.py` (25 testes)
- Frontend: `web/src/__tests__/components/NrTutorAssistant.spec.js` (7 testes)
- E2E: `web/e2e/ui-mocked/tutor-nr.spec.js` (4 testes)

## 5. Execução

```bash
# Backend lint
venv/bin/python -m ruff check app/services/tutor app/models/tutor_knowledge.py app/schemas/tutor.py app/api/routes/tutor.py app/scripts/ingest_nr_tutor_knowledge.py

# Ingestion dry-run
cd api
venv/bin/python -m app.scripts.ingest_nr_tutor_knowledge --dry-run

# Frontend lint/test/build
cd web
npm run lint
npm run test
npm run build
```

## 6. Cobertura

Ver `analysis/tutor/knowledge-coverage.json` e `analysis/tutor/knowledge-coverage.md`.
