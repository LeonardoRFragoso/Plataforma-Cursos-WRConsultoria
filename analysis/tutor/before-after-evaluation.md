# Avaliação Antes/Depois — Tutor NR

## Metodologia

Comparação entre o motor determinístico antigo (`nrTutorEngine.js`) e o novo motor de recuperação (`tutor` endpoint). Foram usadas perguntas reais extraídas do escopo do requisito.

## Resultados

| Pergunta (sem NR no texto)                              | Fonte esperada     | Antes (determinístico)                                      | Depois (retrieval)                                                       |
| ------------------------------------------------------- | ------------------ | ----------------------------------------------------------- | ------------------------------------------------------------------------ |
| qual EPI devo utilizar?                                 | NR-06              | Retornava resumo genérico de NR-06, sem detalhe técnico     | Fundamenta trechos dos materiais e cita NR-06                            |
| o que significa CA?                                     | NR-06              | Resposta curta genérica                                     | Recupera trecho sobre Certificado de Aprovação                           |
| como funciona a desenergização?                         | NR-10 Básico       | Encaminhava para NR-10 sem contexto                         | Recupera passo a passo do material básico                                |
| qual diferença entre curso básico e SEP?                | NR-10 Básico + SEP | Resumo superficial                                          | Separa as duas variantes, explica diferença                              |
| o operador pode transportar pessoa na empilhadeira?     | NR-11 Empilhadeira | Sem detalhe específico                                      | Recupera regras operacionais da empilhadeira                             |
| cuidados com ponte rolante                              | NR-11 Ponte        | Genérico NR-11                                              | Prioriza conteúdo da ponte rolante                                       |
| qual diferença entre trabalhador autorizado e supervisor| NR-33 ambos        | Resumo curto                                                | Compara funções, separando as variantes                                  |
| quando preciso usar cinto para trabalho em altura?      | NR-35              | Resposta curta acima de 2m                                  | Fundamenta ancoragem, EPI e condições do material                        |

## Melhorias principais

1. **Respostas fundamentadas**: O novo motor responde com trechos recuperados dos 15 materiais, não com resumos estáticos.
2. **Desambiguação por variante**: NR-10 Básico vs SEP; NR-11 por equipamento; NR-33 Autorizado vs Supervisor.
3. **Perguntas sem número da NR**: A detecção de escopo identifica o domínio automaticamente.
4. **Multi-source**: Perguntas que cruzam NRs combinam fontes.
5. **Fontes**: Toda resposta indica de onde veio.
6. **Proteções**: Bloqueio a extração integral e prompt injection.

## Nota

A avaliação foi feita com base em resultados de teste (mock/retrieval) e não expõe conteúdo integral dos materiais.
