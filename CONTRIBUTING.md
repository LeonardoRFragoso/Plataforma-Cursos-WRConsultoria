# Guia de Contribuição

## Desenvolvimento Local

### Pré-requisitos
- Docker e Docker Compose
- Git

### Setup

1. Clone o repositório
```bash
git clone <repo-url>
cd WR-Plataforma-Cursos
```

2. Configure variáveis de ambiente
```bash
cp .env.example .env
```

3. Inicie os serviços
```bash
docker-compose up -d
```

4. Acesse a aplicação
- Frontend: http://localhost:5173
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

## Fluxo de Desenvolvimento

### Backend

1. Faça alterações em `api/app/`
2. Os testes rodam automaticamente com `pytest`
3. Verifique a documentação Swagger em http://localhost:8000/docs

```bash
# Rodar testes
docker-compose exec api pytest tests/ -v

# Rodar com coverage
docker-compose exec api pytest tests/ --cov=app
```

### Frontend

1. Faça alterações em `web/src/`
2. O Vite recarrega automaticamente
3. Verifique em http://localhost:5173

```bash
# Rodar testes
docker-compose exec web npm run test

# Rodar com UI
docker-compose exec web npm run test:ui

# Build para produção
docker-compose exec web npm run build
```

## Padrões de Código

### Backend (Python)

- Siga PEP 8
- Use type hints
- Docstrings em funções públicas
- Nomes descritivos para variáveis

```python
async def create_course(
    course_data: CourseCreate,
    db: AsyncSession = Depends(get_db),
) -> CourseResponse:
    """Cria um novo curso."""
    course = Course(**course_data.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course
```

### Frontend (Vue 3)

- Use Composition API
- Nomes de componentes em PascalCase
- Props e emits tipados
- Comentários para lógica complexa

```vue
<script setup>
import { ref, computed } from 'vue'

const count = ref(0)
const doubled = computed(() => count.value * 2)

const increment = () => {
  count.value++
}
</script>

<template>
  <div>
    <p>Count: {{ count }}</p>
    <p>Doubled: {{ doubled }}</p>
    <button @click="increment">Increment</button>
  </div>
</template>
```

## Commits

Use mensagens descritivas:

```
feat: adiciona novo endpoint de pagamento
fix: corrige validação de email
docs: atualiza README com instruções de deploy
test: adiciona testes para autenticação
refactor: simplifica lógica de certificados
```

## Pull Requests

1. Crie uma branch para sua feature
```bash
git checkout -b feature/minha-feature
```

2. Faça commits com mensagens claras
3. Abra um PR com descrição do que foi feito
4. Aguarde review
5. Faça ajustes se necessário
6. Merge após aprovação

## Testes

### Backend

Sempre escreva testes para novas funcionalidades:

```python
def test_create_course(test_course_data):
    response = client.post("/api/v1/courses/", json=test_course_data)
    assert response.status_code == 201
    assert response.json()["name"] == test_course_data["name"]
```

### Frontend

Testes para componentes e stores:

```javascript
it('renders login form', () => {
  const wrapper = mount(Login)
  expect(wrapper.find('input[type="email"]').exists()).toBe(true)
})
```

## Documentação

- Mantenha README.md atualizado
- Documente novos endpoints no Swagger
- Adicione comentários para lógica complexa
- Atualize ARCHITECTURE.md se mudar estrutura

## Reportar Bugs

1. Verifique se o bug já foi reportado
2. Descreva o comportamento esperado vs atual
3. Forneça passos para reproduzir
4. Inclua logs ou screenshots se relevante

## Sugestões de Melhorias

1. Abra uma issue descrevendo a melhoria
2. Explique o problema que resolve
3. Sugira uma solução se possível
4. Aguarde feedback antes de implementar

## Dúvidas?

Entre em contato com a equipe de desenvolvimento ou abra uma issue com a tag `question`.
