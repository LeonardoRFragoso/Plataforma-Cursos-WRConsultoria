# WR Course Catalog Reconciliation

> Gerado a partir de `wr_course_content_manifest.json` v1.0.0 (2026-08-26)
> Tenant: `wr`
> Diretório fonte: `/home/leonardo/Documentos/Apostilas-WR-Cursos`

---

## 1. Resumo Executivo

| Métrica | Valor |
|---|---|
| PDFs encontrados | 55 |
| Duplicados exatos | 8 |
| PDFs únicos | 47 |
| Cursos identificados | 47 |
| NRs distintas | 22 (NR 1, 5, 6, 10, 11, 12, 17, 18, 20, 22, 23, 26, 29, 31, 32, 33, 34, 35, 36 + 6 non-NR) |
| Cursos a criar | 27 |
| Cursos a atualizar | 20 |
| Cursos a desativar | 31 |

---

## 2. Inventário de PDFs

Inventário completo dos 55 arquivos PDF encontrados no diretório fonte, incluindo duplicatas exatas.

| Arquivo | SHA-256 (primeiros 16 chars) | Páginas | Tamanho | Status |
|---|---|---|---|---|
| brigadavoluntaria.pdf | `6d8652fc87d4e2c4` | 43 | 4.9 MB | UNIQUE |
| direcaodefensiva.pdf | `b869d409ed9ed12f` | 25 | 6.6 MB | UNIQUE |
| ginasticalaboral.pdf | `0ee8e63249ef760f` | 13 | 2.9 MB | UNIQUE |
| nr1.pdf | `0400c3cdab93282f` | 39 | 9.5 MB | UNIQUE |
| nr10basico (1).pdf | `403c7fd382084663` | 90 | 15.7 MB | EXACT_DUPLICATE |
| nr10basico.pdf | `403c7fd382084663` | 90 | 15.7 MB | UNIQUE |
| nr10sep (1).pdf | `69318e55ede17a60` | 145 | 10.1 MB | EXACT_DUPLICATE |
| nr10sep.pdf | `69318e55ede17a60` | 145 | 10.1 MB | UNIQUE |
| nr11empilhadeira.pdf | `ddf7bb8381750256` | 78 | 8.2 MB | UNIQUE |
| nr11guindauto.pdf | `4e8d2efd15a194eb` | 83 | 8.1 MB | UNIQUE |
| nr11minicarregadeira.pdf | `e328110b0efc3f75` | 59 | 6.0 MB | UNIQUE |
| nr11plataforma.pdf | `c869516b9536ddaf` | 65 | 6.8 MB | UNIQUE |
| nr11ponte.pdf | `a95cfd7806e4f242` | 69 | 6.6 MB | UNIQUE |
| nr11retroescavadeira.pdf | `23dd951fa05d5a1f` | 66 | 7.4 MB | UNIQUE |
| nr12.pdf | `ebba3c717ad2c53e` | 13 | 3.8 MB | UNIQUE |
| nr17administrativas.pdf | `91d8b946f87378d1` | 25 | 3.3 MB | UNIQUE |
| nr17checkout.pdf | `c3071a1aead1986b` | 13 | 3.3 MB | UNIQUE |
| nr17telemarketing.pdf | `6904ff45c6e16d19` | 19 | 2.9 MB | UNIQUE |
| nr17transporte.pdf | `0b0d2eacf215a6b4` | 14 | 2.6 MB | UNIQUE |
| nr18.pdf | `6a4769e0da7b3fdb` | 67 | 7.8 MB | UNIQUE |
| nr20.pdf | `d4ea97b38bd06c48` | 53 | 4.9 MB | UNIQUE |
| nr20avancadoi.pdf | `161ea52b9f0706d9` | 70 | 5.7 MB | UNIQUE |
| nr20avancadoii.pdf | `83fa4d5ebe7e3367` | 72 | 5.8 MB | UNIQUE |
| nr20basico.pdf | `90423ee5b51cf107` | 54 | 5.0 MB | UNIQUE |
| nr20especifico.pdf | `a16d054b9cfa830a` | 19 | 2.4 MB | UNIQUE |
| nr20intermediario.pdf | `11f2f692e5f13207` | 68 | 5.6 MB | UNIQUE |
| nr22.pdf | `f5373d06c3894724` | 87 | 17.9 MB | UNIQUE |
| nr23.pdf | `e87f7f3c8f0069fc` | 43 | 5.4 MB | UNIQUE |
| nr26.pdf | `59d2dc4d7589c1f8` | 38 | 4.9 MB | UNIQUE |
| nr26laboratorio.pdf | `863d64625bccc0ff` | 47 | 5.3 MB | UNIQUE |
| nr29cpatp.pdf | `050c47d5277268e2` | 87 | 14.8 MB | UNIQUE |
| nr29portuario.pdf | `495680411a805512` | 59 | 7.6 MB | UNIQUE |
| nr29sinaleiro.pdf | `66a16c9b87453773` | 62 | 5.9 MB | UNIQUE |
| nr31agrotoxicos.pdf | `8eeb71a28c1a053f` | 66 | 7.1 MB | UNIQUE |
| nr31cipatr.pdf | `a4f484ce9f5f78fa` | 88 | 15.4 MB | UNIQUE |
| nr31inicial.pdf | `08ffbe2f4ab45da3` | 64 | 6.8 MB | UNIQUE |
| nr31periodico.pdf | `5eede8b2f2e739fc` | 64 | 7.0 MB | UNIQUE |
| nr32.pdf | `a973b758384e57a0` | 30 | 3.4 MB | UNIQUE |
| nr33autorizado (1).pdf | `7661f18d78899cf4` | 25 | 4.6 MB | EXACT_DUPLICATE |
| nr33autorizado.pdf | `7661f18d78899cf4` | 25 | 4.6 MB | UNIQUE |
| nr33supervisor (1).pdf | `d8bad6104d51ba3d` | 33 | 4.0 MB | EXACT_DUPLICATE |
| nr33supervisor.pdf | `d8bad6104d51ba3d` | 33 | 4.0 MB | UNIQUE |
| nr34admissional.pdf | `1b1623f5dfeae826` | 53 | 6.1 MB | UNIQUE |
| nr34periodico.pdf | `6e66318ea318aea7` | 53 | 5.9 MB | UNIQUE |
| nr35 (1).pdf | `4a1e5464223b3ef0` | 70 | 6.7 MB | EXACT_DUPLICATE |
| nr35.pdf | `4a1e5464223b3ef0` | 70 | 6.7 MB | UNIQUE |
| nr36.pdf | `d9de7efbb9f86a5f` | 53 | 6.0 MB | UNIQUE |
| nr5 (1).pdf | `468d56b9ca4c4045` | 91 | 19.2 MB | EXACT_DUPLICATE |
| nr5 (2).pdf | `468d56b9ca4c4045` | 91 | 19.2 MB | EXACT_DUPLICATE |
| nr5 (3).pdf | `468d56b9ca4c4045` | 91 | 19.2 MB | EXACT_DUPLICATE |
| nr5.pdf | `468d56b9ca4c4045` | 91 | 19.2 MB | UNIQUE |
| nr6.pdf | `7ce74f09bfd50d15` | 34 | 8.5 MB | UNIQUE |
| pca.pdf | `602fc7203b88faea` | 19 | 3.4 MB | UNIQUE |
| ppr.pdf | `c92036bf74d1b61d` | 18 | 3.3 MB | UNIQUE |
| primeirossocorros.pdf | `d37933823c4e0247` | 35 | 4.7 MB | UNIQUE |

---

## 3. Duplicidades Detectadas

Foram encontradas 8 duplicidades exatas (mesmo conteúdo, mesmo SHA-256). O arquivo mantido é a versão sem sufixo de cópia.

| Arquivo duplicado | SHA-256 | Arquivo mantido |
|---|---|---|
| nr10basico (1).pdf | `403c7fd382084663c5e9154ec7ad1a664760edf44657b66d19a152b8acaad997` | nr10basico.pdf |
| nr10sep (1).pdf | `69318e55ede17a60971e8536f814c06ed5ccb153ba765cf4b033e7c54a494d13` | nr10sep.pdf |
| nr33autorizado (1).pdf | `7661f18d78899cf4fa6e675a8d7efd2c4fb4f4c9fefbe8b62ac57f136e64de26` | nr33autorizado.pdf |
| nr33supervisor (1).pdf | `d8bad6104d51ba3d217896f720b02021cf4bf8d98e0cf52af9a1f35eb55ef2be` | nr33supervisor.pdf |
| nr35 (1).pdf | `4a1e5464223b3ef0698012f986263488136166c4093d1cb64a5fd8f3ceb77e46` | nr35.pdf |
| nr5 (1).pdf | `468d56b9ca4c4045f2630d835734cf49ed6a4582ef65667ca7830a294821ca1f` | nr5.pdf |
| nr5 (2).pdf | `468d56b9ca4c4045f2630d835734cf49ed6a4582ef65667ca7830a294821ca1f` | nr5.pdf |
| nr5 (3).pdf | `468d56b9ca4c4045f2630d835734cf49ed6a4582ef65667ca7830a294821ca1f` | nr5.pdf |

---

## 4. Tabela de Reconciliação

Mapeamento de cada PDF único para o curso correspondente no catálogo final.

| PDF | NR | Curso identificado | Variante | Código atual | Código final | Ação |
|---|---|---|---|---|---|---|
| brigadavoluntaria.pdf | BV | Brigada Voluntária | Formação | BV-F | BV-F | UPDATE |
| direcaodefensiva.pdf | DD | Direção Defensiva | Formação | DD-F | DD-F | UPDATE |
| ginasticalaboral.pdf | GL | Ginástica Laboral | Formação | GL-F | GL-F | UPDATE |
| nr1.pdf | NR-01 | NR 1 - Disposições Gerais e Gerenciamento de Riscos Ocupacionais | Formação | NR-01-F | NR-01-F | UPDATE |
| nr10basico.pdf | NR-10 | NR 10 - Segurança em Instalações e Serviços em Eletricidade - Básico | Básico | NR-10-B | NR-10-B | UPDATE |
| nr10sep.pdf | NR-10 | NR 10 - Segurança no Sistema Elétrico de Potência - SEP | SEP | NR-10-S | NR-10-S | UPDATE |
| nr11empilhadeira.pdf | NR-11 | NR 11 - Operador de Empilhadeira | Empilhadeira | — | NR-11-EMP | CREATE |
| nr11guindauto.pdf | NR-11 | NR 11 - Operador de Guindauto | Guindauto | — | NR-11-GUI | CREATE |
| nr11minicarregadeira.pdf | NR-11 | NR 11 - Operador de Mini Carregadeira | Mini Carregadeira | — | NR-11-MIN | CREATE |
| nr11plataforma.pdf | NR-11 | NR 11 - Operador de Plataforma Elevatória | Plataforma Elevatória | — | NR-11-PLA | CREATE |
| nr11ponte.pdf | NR-11 | NR 11 - Operador de Ponte Rolante | Ponte Rolante | — | NR-11-PON | CREATE |
| nr11retroescavadeira.pdf | NR-11 | NR 11 - Operador de Retroescavadeira | Retroescavadeira | — | NR-11-RET | CREATE |
| nr12.pdf | NR-12 | NR 12 - Máquinas e Equipamentos - Geral | Formação | NR-12-F | NR-12-F | UPDATE |
| nr17administrativas.pdf | NR-17 | NR 17 - Ergonomia para Atividades Administrativas | Administrativas | — | NR-17-ADM | CREATE |
| nr17checkout.pdf | NR-17 | NR 17 - Ergonomia para Operador de Checkout | Checkout | — | NR-17-CHK | CREATE |
| nr17telemarketing.pdf | NR-17 | NR 17 - Ergonomia para Operador de Telemarketing/Teleatendimento | Telemarketing | — | NR-17-TEL | CREATE |
| nr17transporte.pdf | NR-17 | NR 17 - Levantamento e Transporte Manual de Peso | Transporte Manual | — | NR-17-TRA | CREATE |
| nr18.pdf | NR-18 | NR 18 - Condições e Meio Ambiente na Indústria da Construção | Formação | NR-18-F | NR-18-F | UPDATE |
| nr20.pdf | NR-20 | NR 20 - Inflamáveis e Combustíveis - Inicial | Inicial | — | NR-20-INI | CREATE |
| nr20avancadoi.pdf | NR-20 | NR 20 - Inflamáveis e Combustíveis - Avançado I | Avançado I | — | NR-20-AI | CREATE |
| nr20avancadoii.pdf | NR-20 | NR 20 - Inflamáveis e Combustíveis - Avançado II | Avançado II | — | NR-20-AII | CREATE |
| nr20basico.pdf | NR-20 | NR 20 - Inflamáveis e Combustíveis - Básico | Básico | — | NR-20-BAS | CREATE |
| nr20especifico.pdf | NR-20 | NR 20 - Inflamáveis e Combustíveis - Específico | Específico | — | NR-20-ESP | CREATE |
| nr20intermediario.pdf | NR-20 | NR 20 - Inflamáveis e Combustíveis - Intermediário | Intermediário | — | NR-20-INT | CREATE |
| nr22.pdf | NR-22 | NR 22 - CIPAMIN - Segurança e Saúde na Mineração | Formação | NR-22-F | NR-22-F | UPDATE |
| nr23.pdf | NR-23 | NR 23 - Proteção Contra Incêndios | Formação | NR-23-F | NR-23-F | UPDATE |
| nr26.pdf | NR-26 | NR 26 - Sinalização de Segurança - Geral | Formação | NR-26-F | NR-26-F | UPDATE |
| nr26laboratorio.pdf | NR-26 | NR 26 - Sinalização de Segurança para Laboratório | Laboratório | — | NR-26-LAB | CREATE |
| nr29cpatp.pdf | NR-29 | NR 29 - CPATP - Comissão de Prevenção de Acidentes no Trabalho Portuário | CPATP | — | NR-29-CPATP | CREATE |
| nr29portuario.pdf | NR-29 | NR 29 - Saúde e Segurança no Trabalho Portuário | Portuário | — | NR-29-POR | CREATE |
| nr29sinaleiro.pdf | NR-29 | NR 29 - Sinaleiro - Sinalização Manual no Trabalho Portuário | Sinaleiro | — | NR-29-SIN | CREATE |
| nr31agrotoxicos.pdf | NR-31 | NR 31 - Saúde e Segurança com Produtos Agrotóxicos | Agrotóxicos | — | NR-31-AGR | CREATE |
| nr31cipatr.pdf | NR-31 | NR 31 - CIPATR - Comissão Interna de Prevenção de Acidentes no Trabalho Rural | CIPATR | — | NR-31-CIPATR | CREATE |
| nr31inicial.pdf | NR-31 | NR 31 - Saúde e Segurança no Trabalho Rural - Admissional | Admissional | NR-31-I | NR-31-I | UPDATE |
| nr31periodico.pdf | NR-31 | NR 31 - Saúde e Segurança no Trabalho Rural - Periódico | Periódico | — | NR-31-P | CREATE |
| nr32.pdf | NR-32 | NR 32 - Segurança e Saúde no Serviço de Saúde / Biossegurança | Formação | NR-32-F | NR-32-F | UPDATE |
| nr33autorizado.pdf | NR-33 | NR 33 - Espaços Confinados - Trabalhador Autorizado | Autorizado | — | NR-33-AUT | CREATE |
| nr33supervisor.pdf | NR-33 | NR 33 - Espaços Confinados - Supervisor | Supervisor | — | NR-33-SUP | CREATE |
| nr34admissional.pdf | NR-34 | NR 34 - Segurança e Saúde no Trabalho Naval - Admissional | Admissional | — | NR-34-ADM | CREATE |
| nr34periodico.pdf | NR-34 | NR 34 - Segurança e Saúde no Trabalho Naval - Periódico | Periódico | — | NR-34-PER | CREATE |
| nr35.pdf | NR-35 | NR 35 - Trabalho em Altura | Formação | NR-35-F | NR-35-F | UPDATE |
| nr36.pdf | NR-36 | NR 36 - Segurança e Saúde em Frigoríficos / Abate e Processamento de Carnes | Formação | NR-36-F | NR-36-F | UPDATE |
| nr5.pdf | NR-05 | NR 5 - CIPA - Comissão Interna de Prevenção de Acidentes | Formação | NR-05-F | NR-05-F | UPDATE |
| nr6.pdf | NR-06 | NR 6 - Equipamento de Proteção Individual - EPI | Formação | NR-06-F | NR-06-F | UPDATE |
| pca.pdf | PCA | Programa de Conservação Auditiva - PCA | Formação | PCA-F | PCA-F | UPDATE |
| ppr.pdf | PPR | Programa de Proteção Respiratória - PPR | Formação | PPR-F | PPR-F | UPDATE |
| primeirossocorros.pdf | PS | Primeiros Socorros | Formação | PS-F | PS-F | UPDATE |

---

## 5. Catálogo Final Proposto (agrupado por NR)

Catálogo final de 47 cursos agrupado por família NR.

### NR-01

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-01-F | NR 1 - Disposições Gerais e Gerenciamento de Riscos Ocupacionais | Formação | UPDATE |

### NR-05

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-05-F | NR 5 - CIPA - Comissão Interna de Prevenção de Acidentes | Formação | UPDATE |

### NR-06

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-06-F | NR 6 - Equipamento de Proteção Individual - EPI | Formação | UPDATE |

### NR-10

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-10-B | NR 10 - Segurança em Instalações e Serviços em Eletricidade - Básico | Básico | UPDATE |
| NR-10-S | NR 10 - Segurança no Sistema Elétrico de Potência - SEP | SEP | UPDATE |

### NR-11

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-11-EMP | NR 11 - Operador de Empilhadeira | Empilhadeira | CREATE |
| NR-11-GUI | NR 11 - Operador de Guindauto | Guindauto | CREATE |
| NR-11-MIN | NR 11 - Operador de Mini Carregadeira | Mini Carregadeira | CREATE |
| NR-11-PLA | NR 11 - Operador de Plataforma Elevatória | Plataforma Elevatória | CREATE |
| NR-11-PON | NR 11 - Operador de Ponte Rolante | Ponte Rolante | CREATE |
| NR-11-RET | NR 11 - Operador de Retroescavadeira | Retroescavadeira | CREATE |

### NR-12

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-12-F | NR 12 - Máquinas e Equipamentos - Geral | Formação | UPDATE |

### NR-17

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-17-ADM | NR 17 - Ergonomia para Atividades Administrativas | Administrativas | CREATE |
| NR-17-CHK | NR 17 - Ergonomia para Operador de Checkout | Checkout | CREATE |
| NR-17-TEL | NR 17 - Ergonomia para Operador de Telemarketing/Teleatendimento | Telemarketing | CREATE |
| NR-17-TRA | NR 17 - Levantamento e Transporte Manual de Peso | Transporte Manual | CREATE |

### NR-18

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-18-F | NR 18 - Condições e Meio Ambiente na Indústria da Construção | Formação | UPDATE |

### NR-20

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-20-INI | NR 20 - Inflamáveis e Combustíveis - Inicial | Inicial | CREATE |
| NR-20-AI | NR 20 - Inflamáveis e Combustíveis - Avançado I | Avançado I | CREATE |
| NR-20-AII | NR 20 - Inflamáveis e Combustíveis - Avançado II | Avançado II | CREATE |
| NR-20-BAS | NR 20 - Inflamáveis e Combustíveis - Básico | Básico | CREATE |
| NR-20-ESP | NR 20 - Inflamáveis e Combustíveis - Específico | Específico | CREATE |
| NR-20-INT | NR 20 - Inflamáveis e Combustíveis - Intermediário | Intermediário | CREATE |

### NR-22

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-22-F | NR 22 - CIPAMIN - Segurança e Saúde na Mineração | Formação | UPDATE |

### NR-23

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-23-F | NR 23 - Proteção Contra Incêndios | Formação | UPDATE |

### NR-26

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-26-F | NR 26 - Sinalização de Segurança - Geral | Formação | UPDATE |
| NR-26-LAB | NR 26 - Sinalização de Segurança para Laboratório | Laboratório | CREATE |

### NR-29

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-29-CPATP | NR 29 - CPATP - Comissão de Prevenção de Acidentes no Trabalho Portuário | CPATP | CREATE |
| NR-29-POR | NR 29 - Saúde e Segurança no Trabalho Portuário | Portuário | CREATE |
| NR-29-SIN | NR 29 - Sinaleiro - Sinalização Manual no Trabalho Portuário | Sinaleiro | CREATE |

### NR-31

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-31-AGR | NR 31 - Saúde e Segurança com Produtos Agrotóxicos | Agrotóxicos | CREATE |
| NR-31-CIPATR | NR 31 - CIPATR - Comissão Interna de Prevenção de Acidentes no Trabalho Rural | CIPATR | CREATE |
| NR-31-I | NR 31 - Saúde e Segurança no Trabalho Rural - Admissional | Admissional | UPDATE |
| NR-31-P | NR 31 - Saúde e Segurança no Trabalho Rural - Periódico | Periódico | CREATE |

### NR-32

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-32-F | NR 32 - Segurança e Saúde no Serviço de Saúde / Biossegurança | Formação | UPDATE |

### NR-33

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-33-AUT | NR 33 - Espaços Confinados - Trabalhador Autorizado | Autorizado | CREATE |
| NR-33-SUP | NR 33 - Espaços Confinados - Supervisor | Supervisor | CREATE |

### NR-34

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-34-ADM | NR 34 - Segurança e Saúde no Trabalho Naval - Admissional | Admissional | CREATE |
| NR-34-PER | NR 34 - Segurança e Saúde no Trabalho Naval - Periódico | Periódico | CREATE |

### NR-35

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-35-F | NR 35 - Trabalho em Altura | Formação | UPDATE |

### NR-36

| Código | Nome | Variante | Ação |
|---|---|---|---|
| NR-36-F | NR 36 - Segurança e Saúde em Frigoríficos / Abate e Processamento de Carnes | Formação | UPDATE |

### BV

| Código | Nome | Variante | Ação |
|---|---|---|---|
| BV-F | Brigada Voluntária | Formação | UPDATE |

### DD

| Código | Nome | Variante | Ação |
|---|---|---|---|
| DD-F | Direção Defensiva | Formação | UPDATE |

### GL

| Código | Nome | Variante | Ação |
|---|---|---|---|
| GL-F | Ginástica Laboral | Formação | UPDATE |

### PCA

| Código | Nome | Variante | Ação |
|---|---|---|---|
| PCA-F | Programa de Conservação Auditiva - PCA | Formação | UPDATE |

### PPR

| Código | Nome | Variante | Ação |
|---|---|---|---|
| PPR-F | Programa de Proteção Respiratória - PPR | Formação | UPDATE |

### PS

| Código | Nome | Variante | Ação |
|---|---|---|---|
| PS-F | Primeiros Socorros | Formação | UPDATE |

---

## 6. Códigos a Desativar

Total de 31 códigos a serem desativados no catálogo atual.

| Código | Motivo |
|---|---|
| NR-01-R | Substituído por NR-01-F (Formação) |
| NR-05-R | Substituído por NR-05-F (Formação) |
| NR-06-R | Substituído por NR-06-F (Formação) |
| NR-10-AE | Substituído por NR-10-B (Básico) e NR-10-S (SEP) |
| NR-10-R | Substituído por NR-10-B (Básico) e NR-10-S (SEP) |
| NR-11-F | Substituído por variantes específicas: NR-11-EMP, NR-11-GUI, NR-11-MIN, NR-11-PLA, NR-11-PON, NR-11-RET |
| NR-11-R | Substituído por variantes específicas: NR-11-EMP, NR-11-GUI, NR-11-MIN, NR-11-PLA, NR-11-PON, NR-11-RET |
| NR-12-R | Substituído por NR-12-F (Formação) |
| NR-17-F | Substituído por variantes específicas: NR-17-ADM, NR-17-CHK, NR-17-TEL, NR-17-TRA |
| NR-17-R | Substituído por variantes específicas: NR-17-ADM, NR-17-CHK, NR-17-TEL, NR-17-TRA |
| NR-18-R | Substituído por NR-18-F (Formação) |
| NR-20-F | Substituído por variantes: NR-20-INI, NR-20-BAS, NR-20-INT, NR-20-AI, NR-20-AII, NR-20-ESP |
| NR-20-R | Substituído por variantes: NR-20-INI, NR-20-BAS, NR-20-INT, NR-20-AI, NR-20-AII, NR-20-ESP |
| NR-22-R | Substituído por NR-22-F (Formação) |
| NR-23-R | Substituído por NR-23-F (Formação) |
| NR-26-R | Substituído por NR-26-F (Formação) e NR-26-LAB (Laboratório) |
| NR-29-F | Substituído por variantes: NR-29-CPATP, NR-29-POR, NR-29-SIN |
| NR-29-R | Substituído por variantes: NR-29-CPATP, NR-29-POR, NR-29-SIN |
| NR-31-R | Substituído por variantes: NR-31-AGR, NR-31-CIPATR, NR-31-I, NR-31-P |
| NR-32-R | Substituído por NR-32-F (Formação) |
| NR-33-F | Substituído por NR-33-AUT (Autorizado) e NR-33-SUP (Supervisor) |
| NR-33-R | Substituído por NR-33-AUT (Autorizado) e NR-33-SUP (Supervisor) |
| NR-34-F | Substituído por NR-34-ADM (Admissional) e NR-34-PER (Periódico) |
| NR-34-P | Substituído por NR-34-ADM (Admissional) e NR-34-PER (Periódico) |
| NR-35-R | Substituído por NR-35-F (Formação) |
| NR-36-R | Substituído por NR-36-F (Formação) |
| DP-F | Sem apostila correspondente no diretório fonte |
| LE-F | Sem apostila correspondente no diretório fonte |
| NEG-F | Sem apostila correspondente no diretório fonte |
| QP-F | Sem apostila correspondente no diretório fonte |
| SAU-F | Sem apostila correspondente no diretório fonte |

---

## 7. Mapeamento OLD_CODE → FINAL_CODE

Mapeamento de códigos antigos para códigos finais. Cursos com ação CREATE não possuem código anterior (indicado por `—`).

| Código Anterior (OLD_CODE) | Código Final (FINAL_CODE) | Curso | Ação |
|---|---|---|---|
| BV-F | BV-F | Brigada Voluntária | UPDATE |
| DD-F | DD-F | Direção Defensiva | UPDATE |
| GL-F | GL-F | Ginástica Laboral | UPDATE |
| NR-01-F | NR-01-F | NR 1 - Disposições Gerais e Gerenciamento de Riscos Ocupacionais | UPDATE |
| NR-10-B | NR-10-B | NR 10 - Segurança em Instalações e Serviços em Eletricidade - Básico | UPDATE |
| NR-10-S | NR-10-S | NR 10 - Segurança no Sistema Elétrico de Potência - SEP | UPDATE |
| — | NR-11-EMP | NR 11 - Operador de Empilhadeira | CREATE |
| — | NR-11-GUI | NR 11 - Operador de Guindauto | CREATE |
| — | NR-11-MIN | NR 11 - Operador de Mini Carregadeira | CREATE |
| — | NR-11-PLA | NR 11 - Operador de Plataforma Elevatória | CREATE |
| — | NR-11-PON | NR 11 - Operador de Ponte Rolante | CREATE |
| — | NR-11-RET | NR 11 - Operador de Retroescavadeira | CREATE |
| NR-12-F | NR-12-F | NR 12 - Máquinas e Equipamentos - Geral | UPDATE |
| — | NR-17-ADM | NR 17 - Ergonomia para Atividades Administrativas | CREATE |
| — | NR-17-CHK | NR 17 - Ergonomia para Operador de Checkout | CREATE |
| — | NR-17-TEL | NR 17 - Ergonomia para Operador de Telemarketing/Teleatendimento | CREATE |
| — | NR-17-TRA | NR 17 - Levantamento e Transporte Manual de Peso | CREATE |
| NR-18-F | NR-18-F | NR 18 - Condições e Meio Ambiente na Indústria da Construção | UPDATE |
| — | NR-20-INI | NR 20 - Inflamáveis e Combustíveis - Inicial | CREATE |
| — | NR-20-AI | NR 20 - Inflamáveis e Combustíveis - Avançado I | CREATE |
| — | NR-20-AII | NR 20 - Inflamáveis e Combustíveis - Avançado II | CREATE |
| — | NR-20-BAS | NR 20 - Inflamáveis e Combustíveis - Básico | CREATE |
| — | NR-20-ESP | NR 20 - Inflamáveis e Combustíveis - Específico | CREATE |
| — | NR-20-INT | NR 20 - Inflamáveis e Combustíveis - Intermediário | CREATE |
| NR-22-F | NR-22-F | NR 22 - CIPAMIN - Segurança e Saúde na Mineração | UPDATE |
| NR-23-F | NR-23-F | NR 23 - Proteção Contra Incêndios | UPDATE |
| NR-26-F | NR-26-F | NR 26 - Sinalização de Segurança - Geral | UPDATE |
| — | NR-26-LAB | NR 26 - Sinalização de Segurança para Laboratório | CREATE |
| — | NR-29-CPATP | NR 29 - CPATP - Comissão de Prevenção de Acidentes no Trabalho Portuário | CREATE |
| — | NR-29-POR | NR 29 - Saúde e Segurança no Trabalho Portuário | CREATE |
| — | NR-29-SIN | NR 29 - Sinaleiro - Sinalização Manual no Trabalho Portuário | CREATE |
| — | NR-31-AGR | NR 31 - Saúde e Segurança com Produtos Agrotóxicos | CREATE |
| — | NR-31-CIPATR | NR 31 - CIPATR - Comissão Interna de Prevenção de Acidentes no Trabalho Rural | CREATE |
| NR-31-I | NR-31-I | NR 31 - Saúde e Segurança no Trabalho Rural - Admissional | UPDATE |
| — | NR-31-P | NR 31 - Saúde e Segurança no Trabalho Rural - Periódico | CREATE |
| NR-32-F | NR-32-F | NR 32 - Segurança e Saúde no Serviço de Saúde / Biossegurança | UPDATE |
| — | NR-33-AUT | NR 33 - Espaços Confinados - Trabalhador Autorizado | CREATE |
| — | NR-33-SUP | NR 33 - Espaços Confinados - Supervisor | CREATE |
| — | NR-34-ADM | NR 34 - Segurança e Saúde no Trabalho Naval - Admissional | CREATE |
| — | NR-34-PER | NR 34 - Segurança e Saúde no Trabalho Naval - Periódico | CREATE |
| NR-35-F | NR-35-F | NR 35 - Trabalho em Altura | UPDATE |
| NR-36-F | NR-36-F | NR 36 - Segurança e Saúde em Frigoríficos / Abate e Processamento de Carnes | UPDATE |
| NR-05-F | NR-05-F | NR 5 - CIPA - Comissão Interna de Prevenção de Acidentes | UPDATE |
| NR-06-F | NR-06-F | NR 6 - Equipamento de Proteção Individual - EPI | UPDATE |
| PCA-F | PCA-F | Programa de Conservação Auditiva - PCA | UPDATE |
| PPR-F | PPR-F | Programa de Proteção Respiratória - PPR | UPDATE |
| PS-F | PS-F | Primeiros Socorros | UPDATE |
