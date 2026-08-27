# Cobertura da Base de Conhecimento do Tutor NR

**Gerado em:** 2026-08-27

**Fontes:** 15/15 processadas
**Chunks gerados:** 237

| Fonte                 | Documento                                           | Caracteres | Headings | Chunks | Status |
| --------------------- | --------------------------------------------------- | ---------: | -------: | -----: | ------ |
| nr01                  | NR-01 — Disposições Gerais e GRO/PGR                |     52.797 |       40 |     13 | PASS   |
| nr06                  | NR-06 — EPI                                         |     33.348 |       35 |      8 | PASS   |
| nr10-basico           | NR-10 Básico                                        |    109.647 |       91 |     27 | PASS   |
| nr10-sep              | NR-10 SEP                                           |    148.596 |      146 |     35 | PASS   |
| nr11-empilhadeira     | NR-11 — Empilhadeira                                |     80.682 |       79 |     19 | PASS   |
| nr11-guindauto        | NR-11 — Guindauto                                   |     86.910 |       84 |     20 | PASS   |
| nr11-minicarregadeira | NR-11 — Minicarregadeira                            |     61.515 |       60 |     15 | PASS   |
| nr11-plataforma       | NR-11 — Plataforma Elevatória                       |     63.368 |       66 |     16 | PASS   |
| nr11-ponte            | NR-11 — Ponte Rolante                               |     70.764 |       70 |     17 | PASS   |
| nr11-retroescavadeira | NR-11 — Retroescavadeira                            |     66.859 |       67 |     16 | PASS   |
| nr12                  | NR-12 — Segurança em Máquinas                       |     13.026 |       14 |      3 | PASS   |
| nr18                  | NR-18 — Construção Civil                            |     70.912 |       68 |     17 | PASS   |
| nr33-autorizado       | NR-33 — Trabalhador Autorizado                      |     22.189 |       26 |      5 | PASS   |
| nr33-supervisor       | NR-33 — Supervisor de Entrada                       |     28.373 |       34 |      7 | PASS   |
| nr35                  | NR-35 — Trabalho em Altura                          |     74.442 |       71 |     19 | PASS   |

## Resumo

Todos os 15 materiais obrigatórios foram lidos, fragmentados e estão prontos para indexação.

- Tecnologia: PostgreSQL full-text search (`tsvector` português) com GIN index.
- Top-K: 6 (configurável via `retrieve`)
- Ranking: lexical (TS rank) + scope boost por NR/variante
- Armazenamento: S3/Tebi privado por tenant (`tenants/{tenant_id}/tutor-knowledge/sources/{slug}/extracted-text.md`)
- Nenhum conteúdo integral foi commitado no repositório Git.
