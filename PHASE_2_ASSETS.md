# Fase 2 — Assets Visuais (Em Progresso)

**Status:** Parcialmente completo  
**Branch:** `fix/branding-wr-identity`  
**Data:** 12 de Agosto de 2026

---

## ✅ Concluído

### 1. Resolução de Divergência de Cores
- **Problema:** Dois valores diferentes para o verde primário:
  - `#047F37` (usado no projeto)
  - `#1B7A3A` (documentado no site institucional)
- **Solução:** Corrigido para `#1B7A3A` (cor oficial)
- **Documentação:** Atualizado `DESIGN_TOKENS.md` explicando a decisão

### 2. Componentes Reutilizáveis
Criados 4 componentes Vue 3 básicos:

#### **AppButton**
- Variantes: `primary`, `secondary`, `outline`, `danger`
- Tamanhos: `sm`, `md`, `lg`
- Estados: `disabled`

#### **AppCard**
- Slots: `header`, default (conteúdo), `footer`
- Prop: `hoverable` (efeito hover)

#### **AppInput**
- Props: `type`, `label`, `placeholder`, `required`, `disabled`, `error`
- v-model support
- Validação com mensagem de erro

#### **AppLink**
- Suporte a links internos (router-link) e externos (a tag)
- Variantes: `primary`, `secondary`, `danger`
- Prop: `target` para links externos

**Documentação:** `web/src/components/README.md` com exemplos de uso

---

## ⏳ Pendente

### 1. Imagens de Hero/Background
- [ ] Adicionar imagem real de treinamento/segurança do trabalho na Home
- [ ] Usar como placeholder imagens públicas do site institucional
- [ ] Substituir ícones/emojis dos 3 cards por ícones outline em verde primário
- [ ] Marcar claramente que serão substituídas por fotos originais quando enviadas

### 2. Favicon
- [ ] Gerar favicon a partir da logo WR
- [ ] Atualizar referência no `index.html`

### 3. Versões da Logo
- [ ] Versão branca da logo (para uso sobre fundo escuro)
- [ ] Versão monocromática (se necessário)
- [ ] Marcar como placeholder até receber arquivos originais de `/home/leonardo/dev/Projeto Willy`

### 4. Substituição de Classes Tailwind Cruas
- [ ] Atualizar `Login.vue` para usar `<AppButton>` e `<AppInput>`
- [ ] Atualizar `Register.vue` para usar componentes
- [ ] Atualizar `Dashboard.vue` para usar `<AppCard>` e `<AppButton>`
- [ ] Atualizar `Courses.vue` para usar componentes
- [ ] Atualizar outras views conforme necessário

---

## Próximas Etapas (Ordem)

1. **Adicionar imagens de hero** (usando placeholders públicos)
2. **Gerar favicon**
3. **Substituir classes Tailwind cruas** nas views por componentes
4. **Validação visual** com screenshots
5. **Merge para `main`** e liberação da Fase 2 funcional

---

## Referências

- **Logo oficial:** `web/src/assets/brand/logo-wr-color.png`
- **Design tokens:** `DESIGN_TOKENS.md`
- **Componentes:** `web/src/components/`
- **Site institucional:** https://wrconsultoriaesolucoes.com.br/

---

## Notas

- A cor verde primária agora é `#1B7A3A` (alinhada com o site institucional)
- Todos os componentes usam a paleta oficial
- Imagens são placeholders até receber os arquivos originais
- Favicon será gerado a partir da logo existente
