# Design Tokens - WR Plataforma de Cursos

Paleta de cores e design tokens baseados na identidade visual da WR Consultoria e Soluções em QSMS.

## Cores Primárias

**Verde WR** - Cor principal da marca
```
#1B7A3A (verde escuro)
#0F4620 (verde muito escuro)
#E8F5E9 (verde muito claro - fundo)
```

## Cores Secundárias

**Azul Escuro** - Cor secundária
```
#1E3A5F (azul escuro)
#0F1E35 (azul muito escuro)
```

## Cores de Acentos

**Laranja** - Destaque
```
#FF6B35 (laranja)
```

## Cores Neutras

```
#FFFFFF (branco)
#F5F5F5 (cinza muito claro)
#EEEEEE (cinza claro)
#E8E8E8 (cinza claro)
#D0D0D0 (cinza médio)
#B0B0B0 (cinza médio)
#999999 (cinza)
#666666 (cinza escuro)
#333333 (cinza muito escuro)
#1A1A1A (quase preto)
```

## Cores de Status

```
#4CAF50 (sucesso - verde)
#FFC107 (aviso - amarelo)
#F44336 (erro - vermelho)
#2196F3 (informação - azul)
```

## Tipografia

**Fonte Principal:** Poppins
- Fallback: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif

## Tailwind CSS Configuration

As cores foram configuradas no `tailwind.config.js` com as seguintes escalas:

### Primary (Verde WR)
- 50: #E8F5E9
- 100: #C8E6C9
- 200: #A5D6A7
- 300: #81C784
- 400: #66BB6A
- 500-900: #1B7A3A / #0F4620

### Secondary (Azul Escuro)
- 50: #F5F5F5
- 100: #EEEEEE
- 200: #E8E8E8
- 300: #D0D0D0
- 400: #B0B0B0
- 500-900: #1E3A5F / #0F1E35

### Accent (Laranja)
- 50: #FFF3E0
- 100: #FFE0B2
- 200: #FFCC80
- 300: #FFB74D
- 400: #FFA726
- 500-900: #FF6B35

### Gray (Neutras)
- 50: #FAFAFA
- 100: #F0F0F0
- 200: #E8E8E8
- 300: #D0D0D0
- 400: #B0B0B0
- 500: #999999
- 600: #666666
- 700: #333333
- 800: #1A1A1A
- 900: #000000

## Uso nas Views

Todas as views foram atualizadas para usar:
- **primary-600** para botões e elementos principais
- **secondary-900** para títulos
- **gray-600** para texto secundário
- **gray-200** para bordas
- **gray-50** para fundos

## Referência Original

Cores extraídas do arquivo `DESIGN_TOKENS.md` do site institucional da WR Consultoria:
https://github.com/LeonardoRFragoso/wrconsultoriaesolucoes

## Próximas Etapas

- [ ] Adicionar logo da WR em SVG/PNG
- [ ] Adicionar imagens de background
- [ ] Implementar componentes com estes tokens
- [ ] Testar contraste WCAG AA
