# Alinhamento com Plataforma Legada (wrsst-treinamentos.com.br)

## Contexto

A WR Consultoria atualmente paga uma assinatura mensal para uma plataforma de terceiros (Moodle white-label operado por "Flex Ocupacional") para vender e entregar seus cursos. Este documento registra como a nova plataforma (`Plataforma-Cursos-WRConsultoria`) foi alinhada com a estrutura de dados e fluxos UX já validados em produção.

**Objetivo:** Substituir a assinatura mensal por uma solução própria, reutilizando a estrutura comprovada sem copiar código, visual ou conteúdo de terceiros.

---

## Mudanças Implementadas

### 1. Modelo de Dados — Tipo de Curso

**Campo adicionado:** `tipo_curso` (enum) no modelo `Course`

```python
class CourseType(str, PyEnum):
    FORMACAO = "formacao"      # Curso inicial completo
    RECICLAGEM = "reciclagem"  # Renovação periódica (carga horária menor)
    INICIAL = "inicial"        # Usado em algumas NRs (ex. NR 31)
    PERIODICO = "periodico"    # Usado em algumas NRs (ex. NR 34)
```

**Justificativa:** A plataforma atual oferece o mesmo código de NR em variações distintas:
- Um aluno que completou "Formação NR-35" precisa futuramente apenas da "Reciclagem NR-35" (mais curta, outro preço)
- Sem este campo, não conseguimos modelar a oferta real da WR

**Exemplo:**
- `NR-35-F` (Formação): 8 horas, R$ 149,90
- `NR-35-R` (Reciclagem): 4 horas, R$ 79,90

---

### 2. Autenticação — Login por CPF ou E-mail

**Campo adicionado:** `cpf` (string, único, indexado, opcional) no modelo `User`

**Endpoint atualizado:** `POST /api/v1/auth/login`

```json
{
  "identifier": "12345678901",  // CPF (11 dígitos) ou e-mail
  "password": "senha123"
}
```

**Lógica:**
- Se `identifier` tem 11 dígitos → busca por CPF
- Se `identifier` tem formato de e-mail → busca por e-mail
- Caso contrário → erro 400 (Bad Request)

**Justificativa:** O público-alvo (trabalhadores de segurança do trabalho) está acostumado a fazer login por CPF na plataforma atual. Muitos não usam e-mail regularmente no dia a dia.

---

### 3. Catálogo de Cursos — 55+ Cursos

**Arquivo:** `api/app/seeds/courses_seed.py`

**Cobertura:**
- **NRs principais:** NR-1, NR-5, NR-6, NR-10, NR-11, NR-12, NR-17, NR-18, NR-20, NR-22, NR-23, NR-26, NR-29, NR-31, NR-32, NR-33, NR-34, NR-35, NR-36
- **Programas complementares:** PCA (Conservação Auditiva), PPR (Proteção Respiratória), Primeiros Socorros
- **Cursos complementares:** Direção Defensiva, Ginástica Laboral, Desenvolvimento Pessoal, Língua Estrangeira, Negócios, Qualificação Profissional, Saúde, Brigada Voluntária

**Estrutura:**
- Cada NR oferecida em múltiplas modalidades (EAD, Semipresencial)
- Cada NR oferecida em múltiplos tipos (Formação, Reciclagem, Inicial, Periódico)
- Preços e cargas horárias baseados no catálogo atual

**Exemplo:**
```python
{
    "code": "NR-35-F",
    "name": "NR 35 - Trabalho em Altura - Formação",
    "category": "NR 35",
    "carga_horaria": 8,
    "modality": "semipresencial",
    "tipo_curso": "formacao",
    "price": 149.90
}
```

---

### 4. Interface — Login com CPF/E-mail e Suporte WhatsApp

**Arquivo:** `web/src/views/Login.vue`

**Mudanças:**
- Campo "Email" → "CPF ou E-mail" (aceita ambos)
- Placeholder: "CPF (11 dígitos) ou seu@email.com"
- Botão WhatsApp de suporte adicionado abaixo do link de cadastro

**Botão WhatsApp:**
```html
<a href="https://wa.me/5521974623559?text=Olá,%20preciso%20de%20ajuda%20com%20meu%20acesso%20à%20plataforma%20de%20cursos%20WR">
  Suporte WhatsApp
</a>
```

**Número:** (21) 97462-3559 (número de contato da WR já usado no site institucional)

**Justificativa:** A WR já usa WhatsApp como canal primário de atendimento. Isso reduz fricção para alunos com dúvidas de acesso.

---

### 5. Modalidades de Curso

**Confirmado:** O enum `CourseModality` já cobre os casos reais:
- `presencial` — Cursos 100% presenciais
- `ead` — Cursos 100% online
- `semipresencial` — Cursos com aulas práticas (ex. NR-33, NR-35)

Nenhuma mudança necessária.

---

## O que **NÃO** foi reaproveita

- ❌ Layout, cores ou imagens do wrsst-treinamentos.com.br (tema genérico de terceiro, não reflete identidade WR)
- ❌ Depoimentos/testimonials (são placeholders Lorem Ipsum, não reais)
- ❌ Estrutura de "loja" tipo WooCommerce/carrinho (nosso fluxo de matrícula + Mercado Pago substitui isso)
- ❌ Código ou HTML/CSS da plataforma Moodle (solução própria em Vue 3 + FastAPI)

---

## Próximas Etapas

1. **Migração de dados:** Quando a nova plataforma estiver em produção, exportar CPFs e histórico de certificados do Moodle atual
2. **Transição de alunos:** Definir estratégia (migração automática vs. re-cadastro)
3. **Desligamento da assinatura:** Após validação em produção, cancelar assinatura da Flex Ocupacional

---

## Pergunta em Aberto

**Coexistência ou substituição?**
- A nova plataforma vai **substituir** a assinatura mensal assim que estiver pronta?
- Ou as duas vão **coexistir** por um período de transição?

Isso influencia a prioridade de migração de dados de alunos já cadastrados no Moodle atual.

---

## Referências

- **Plataforma atual (WooCommerce):** https://wrsst-treinamentos.com.br/
- **EAD atual (Moodle):** https://ead.wrsst-treinamentos.com.br/
- **Site institucional WR:** https://wrconsultoriaesolucoes.com.br/
- **Repositório:** https://github.com/LeonardoRFragoso/Plataforma-Cursos-WRConsultoria

---

**Data:** 12 de Agosto de 2026  
**Branch:** `fix/branding-wr-identity`  
**Status:** Aguardando validação antes do merge para `main`
