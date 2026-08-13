# Atualização de Branding - WR Plataforma de Cursos

**Data:** 12 de Agosto de 2026  
**Versão:** 1.0.0 com Design Tokens  
**Status:** ✅ Completo e Publicado no GitHub

---

## Resumo das Mudanças

A plataforma de cursos foi atualizada para usar a identidade visual oficial da **WR Consultoria e Soluções em QSMS**, extraída do arquivo `DESIGN_TOKENS.md` do site institucional.

### Cores Implementadas

#### Primária - Verde WR
- **#1B7A3A** - Verde escuro (botões, links, destaques)
- **#0F4620** - Verde muito escuro (hover, ativo)
- **#E8F5E9** - Verde muito claro (fundos, backgrounds)

#### Secundária - Azul Escuro
- **#1E3A5F** - Azul escuro (títulos, headings)
- **#0F1E35** - Azul muito escuro (hover, ativo)

#### Acentos
- **#FF6B35** - Laranja (destaque, CTAs secundárias)

#### Neutras
- **#FFFFFF** - Branco (backgrounds principais)
- **#F5F5F5 a #1A1A1A** - Escala de cinzas (textos, bordas, backgrounds)

---

## Arquivos Modificados

### Frontend (Vue 3)

#### 1. **tailwind.config.js**
- Atualizada paleta de cores com escalas completas
- Adicionadas fontes Poppins como primária
- Configuradas sombras e border-radius conforme design tokens

#### 2. **Views Atualizadas**
Todas as views foram atualizadas com as cores corretas:

- `Home.vue` - Landing page com gradiente verde/cinza
- `Login.vue` - Formulário com branding WR
- `Register.vue` - Cadastro com branding WR
- `Dashboard.vue` - Dashboard admin com cards e stats
- `Courses.vue` - Gerenciamento de cursos com design atualizado

**Mudanças em cada view:**
- Substituição de `primary-50` por `gray-50` em backgrounds
- Uso de `primary-600` para botões e links principais
- Uso de `secondary-900` para títulos
- Uso de `gray-600` para textos secundários
- Adição de `border border-gray-200` em cards
- Transições suaves com `transition-colors`

#### 3. **DESIGN_TOKENS.md** (Novo)
- Documentação completa da paleta de cores
- Referência aos tokens do Tailwind
- Guia de uso nas views
- Próximas etapas (logo, imagens, etc.)

### Backend (FastAPI)

- Sem mudanças necessárias (backend é agnóstico a cores)
- Certificados em PDF usarão cores primárias quando implementado

---

## Configuração Tailwind CSS

### Escala de Cores Primária (Verde WR)
```javascript
primary: {
  50: '#E8F5E9',   // Fundo muito claro
  100: '#C8E6C9',
  200: '#A5D6A7',
  300: '#81C784',
  400: '#66BB6A',
  500: '#1B7A3A',  // Verde principal
  600: '#1B7A3A',  // Verde principal
  700: '#0F4620',  // Verde escuro
  800: '#0F4620',  // Verde escuro
  900: '#0F4620',  // Verde muito escuro
}
```

### Escala de Cores Secundária (Azul Escuro)
```javascript
secondary: {
  50: '#F5F5F5',
  100: '#EEEEEE',
  200: '#E8E8E8',
  300: '#D0D0D0',
  400: '#B0B0B0',
  500: '#1E3A5F',  // Azul principal
  600: '#1E3A5F',  // Azul principal
  700: '#0F1E35',  // Azul escuro
  800: '#0F1E35',  // Azul escuro
  900: '#0F1E35',  // Azul muito escuro
}
```

---

## Padrões de Uso

### Botões Primários
```html
<button class="bg-primary-600 text-white hover:bg-primary-700 transition-colors">
  Ação Principal
</button>
```

### Títulos
```html
<h1 class="text-3xl font-bold text-secondary-900">Título</h1>
```

### Textos Secundários
```html
<p class="text-gray-600">Texto secundário</p>
```

### Cards
```html
<div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
  Conteúdo
</div>
```

### Links
```html
<a href="#" class="text-primary-600 hover:text-primary-700 transition-colors">
  Link
</a>
```

---

## Próximas Etapas

### Fase 2 - Assets Visuais
- [ ] Adicionar logo WR em SVG/PNG (colorida, branca, monocromática)
- [ ] Adicionar imagens de background/hero
- [ ] Implementar favicon com logo WR
- [ ] Criar componentes reutilizáveis (Button, Card, Input, etc.)

### Fase 3 - Refinamentos
- [ ] Testar contraste WCAG AA em todas as cores
- [ ] Implementar dark mode com cores WR
- [ ] Adicionar animações suaves
- [ ] Otimizar performance de CSS

### Fase 4 - Documentação
- [ ] Criar guia de estilo (style guide)
- [ ] Documentar componentes no Storybook
- [ ] Criar padrões de design reutilizáveis

---

## Referência Original

As cores foram extraídas do arquivo `DESIGN_TOKENS.md` do repositório do site institucional:
- **Repositório:** https://github.com/LeonardoRFragoso/wrconsultoriaesolucoes
- **Arquivo:** `DESIGN_TOKENS.md`
- **Versão:** 2.3.7

---

## Commit Git

```
feat: plataforma de cursos WR com design tokens e cores da marca

- Estrutura completa do projeto (backend FastAPI + frontend Vue 3)
- Autenticação JWT com RBAC (admin, instructor, student)
- Endpoints REST para cursos, turmas, alunos, matrículas, pagamentos, certificados
- Integração com Mercado Pago para pagamentos
- Geração de certificados em PDF
- Design tokens baseados na identidade visual da WR Consultoria
- Cores primárias (verde #1B7A3A), secundárias (azul #1E3A5F) e acentos (laranja #FF6B35)
- Tailwind CSS com paleta completa
- Docker + docker-compose para ambiente local
- Testes com pytest (backend) e Vitest (frontend)
- Documentação completa (README, ARCHITECTURE, CONTRIBUTING, DESIGN_TOKENS)
```

**Hash:** `05cf5e3`  
**Branch:** `main`  
**Remote:** `https://github.com/LeonardoRFragoso/Plataforma-Cursos-WRConsultoria.git`

---

## Verificação

✅ Cores primárias aplicadas em todos os botões  
✅ Cores secundárias aplicadas em títulos  
✅ Cores neutras aplicadas em textos e bordas  
✅ Tailwind config atualizado com paleta completa  
✅ Todas as views atualizadas com novo design  
✅ Design tokens documentados  
✅ Commit realizado e publicado no GitHub  
✅ Branding consistente em toda a plataforma  

---

## Contato

Para dúvidas sobre o branding ou design tokens, consulte:
- `DESIGN_TOKENS.md` - Documentação técnica
- `tailwind.config.js` - Configuração das cores
- `ARCHITECTURE.md` - Arquitetura geral
- `README.md` - Setup e instruções

**Plataforma pronta para desenvolvimento e deploy!** 🚀
