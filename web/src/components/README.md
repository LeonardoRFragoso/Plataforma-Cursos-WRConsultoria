# Componentes Reutilizáveis — WR Plataforma de Cursos

Componentes Vue 3 reutilizáveis que implementam o design system da WR Consultoria.

## AppButton

Botão com variantes de estilo e tamanho.

```vue
<AppButton variant="primary" size="md" @click="handleClick">
  Clique aqui
</AppButton>
```

**Props:**
- `type`: `'button' | 'submit' | 'reset'` (padrão: `'button'`)
- `variant`: `'primary' | 'secondary' | 'outline' | 'danger'` (padrão: `'primary'`)
- `size`: `'sm' | 'md' | 'lg'` (padrão: `'md'`)
- `disabled`: `boolean` (padrão: `false`)

## AppCard

Card com suporte a header, conteúdo e footer.

```vue
<AppCard hoverable>
  <template #header>
    <h3 class="text-lg font-bold">Título</h3>
  </template>
  
  <p>Conteúdo do card</p>
  
  <template #footer>
    <AppButton>Ação</AppButton>
  </template>
</AppCard>
```

**Props:**
- `hoverable`: `boolean` (padrão: `false`) — Adiciona efeito hover

## AppInput

Input com label, validação e mensagem de erro.

```vue
<AppInput
  v-model="email"
  type="email"
  label="E-mail"
  placeholder="seu@email.com"
  required
  @update:modelValue="handleChange"
/>
```

**Props:**
- `modelValue`: `string` (padrão: `''`)
- `type`: `string` (padrão: `'text'`)
- `label`: `string` (padrão: `''`)
- `placeholder`: `string` (padrão: `''`)
- `required`: `boolean` (padrão: `false`)
- `disabled`: `boolean` (padrão: `false`)
- `error`: `string` (padrão: `''`) — Mensagem de erro exibida abaixo do input

**Emits:**
- `update:modelValue` — Emitido quando o valor muda (v-model)

## AppLink

Link interno (router-link) ou externo (a tag) com variantes.

```vue
<!-- Link interno -->
<AppLink to="/dashboard" variant="primary">
  Ir para Dashboard
</AppLink>

<!-- Link externo -->
<AppLink href="https://example.com" target="_blank" variant="secondary">
  Abrir site
</AppLink>
```

**Props:**
- `to`: `string` (padrão: `''`) — Rota interna (usa router-link)
- `href`: `string` (padrão: `''`) — URL externa (usa a tag)
- `variant`: `'primary' | 'secondary' | 'danger'` (padrão: `'primary'`)
- `target`: `string` (padrão: `'_self'`) — Target do link (ex. `'_blank'`)
- `underline`: `boolean` (padrão: `true`) — Mostrar underline

## Uso em Views

Importar os componentes no script setup:

```vue
<script setup>
import AppButton from '../components/AppButton.vue'
import AppCard from '../components/AppCard.vue'
import AppInput from '../components/AppInput.vue'
import AppLink from '../components/AppLink.vue'
</script>

<template>
  <AppCard>
    <AppInput v-model="name" label="Nome" required />
    <AppButton type="submit" variant="primary">Enviar</AppButton>
  </AppCard>
</template>
```

## Paleta de Cores

Todos os componentes usam a paleta definida em `DESIGN_TOKENS.md`:

- **Primária:** `#1B7A3A` (verde WR)
- **Secundária:** `#1E3A5F` (azul escuro)
- **Acentos:** `#FF6B35` (laranja)
- **Neutros:** Cinzas de `#FFFFFF` a `#1A1A1A`

## Próximas Melhorias

- [ ] Componente `AppSelect` (dropdown)
- [ ] Componente `AppCheckbox`
- [ ] Componente `AppRadio`
- [ ] Componente `AppModal`
- [ ] Componente `AppAlert`
- [ ] Componente `AppPagination`
- [ ] Suporte a dark mode
- [ ] Testes de acessibilidade WCAG AA
