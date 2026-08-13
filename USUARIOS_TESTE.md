# Usuários de Teste — WR Plataforma de Cursos

Para testar a plataforma, use um dos usuários abaixo ou crie um novo cadastro.

## Usuários Pré-configurados

### Admin (Gerenciador)
- **E-mail:** `admin@wrcursos.com.br`
- **CPF:** `12345678901`
- **Senha:** `admin123`
- **Acesso:** Dashboard completo, gerenciamento de cursos, turmas, alunos, pagamentos

### Aluno
- **E-mail:** `student@wrcursos.com.br`
- **CPF:** `11122233344`
- **Senha:** `student123`
- **Acesso:** Visualizar cursos disponíveis, inscrever-se, acompanhar progresso

---

## Como Logar

### Opção 1: Com E-mail
1. Vá para `http://localhost:5173/login`
2. Campo "CPF ou E-mail": `admin@wrcursos.com.br`
3. Campo "Senha": `admin123`
4. Clique em "Entrar"

### Opção 2: Com CPF
1. Vá para `http://localhost:5173/login`
2. Campo "CPF ou E-mail": `12345678901`
3. Campo "Senha": `admin123`
4. Clique em "Entrar"

---

## Criar Novo Usuário

Se preferir criar um novo usuário:

1. Vá para `http://localhost:5173/register`
2. Preencha:
   - **Nome Completo:** Seu nome
   - **E-mail:** seu@email.com
   - **Senha:** Sua senha (mínimo 6 caracteres)
   - **Confirmar Senha:** Repita a senha
3. Clique em "Cadastrar"
4. Você será redirecionado para o login

---

## Notas

- Os usuários pré-configurados foram criados durante o seed do banco de dados
- Você pode logar com **e-mail OU CPF** (ambos funcionam)
- As senhas são armazenadas com hash bcrypt (seguro)
- Para resetar os dados, delete o arquivo `wr_cursos.db` (SQLite) ou limpe o banco PostgreSQL

---

## Troubleshooting

### "CPF/E-mail ou senha inválidos"
- Verifique se o e-mail ou CPF está correto
- Verifique se a senha está correta
- Tente com um dos usuários pré-configurados acima

### "Usuário não encontrado"
- Se criou um novo usuário, aguarde alguns segundos e tente novamente
- Verifique se o e-mail foi digitado corretamente durante o cadastro

### Esqueci a senha
- Por enquanto, não há função de "Recuperar senha"
- Crie um novo usuário com outro e-mail
- Ou contato suporte via WhatsApp: (21) 97462-3559

---

**Última atualização:** 12 de Agosto de 2026
