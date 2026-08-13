"""
Seed data para cursos WR Consultoria.
Baseado no catálogo da plataforma atual (wrsst-treinamentos.com.br).
"""

COURSES_DATA = [
    # NR 1 - Disposições Gerais
    {"code": "NR-01-F", "name": "NR 1 - Disposições Gerais - Formação", "category": "NR 1", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 79.90},
    {"code": "NR-01-R", "name": "NR 1 - Disposições Gerais - Reciclagem", "category": "NR 1", "carga_horaria": 2, "modality": "EAD", "tipo_curso": "RECICLAGEM", "price": 39.90},
    
    # NR 5 - CIPA
    {"code": "NR-05-F", "name": "NR 5 - CIPA - Formação", "category": "NR 5", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-05-R", "name": "NR 5 - CIPA - Reciclagem", "category": "NR 5", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 6 - EPI
    {"code": "NR-06-F", "name": "NR 6 - EPI - Formação", "category": "NR 6", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 79.90},
    {"code": "NR-06-R", "name": "NR 6 - EPI - Reciclagem", "category": "NR 6", "carga_horaria": 2, "modality": "EAD", "tipo_curso": "RECICLAGEM", "price": 39.90},
    
    # NR 10 - Segurança em Instalações e Serviços com Eletricidade
    {"code": "NR-10-B", "name": "NR 10 - Básico", "category": "NR 10", "carga_horaria": 40, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 299.90},
    {"code": "NR-10-S", "name": "NR 10 - SEP (Sistema Elétrico de Potência)", "category": "NR 10", "carga_horaria": 40, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 299.90},
    {"code": "NR-10-AE", "name": "NR 10 - Atmosfera Explosiva", "category": "NR 10", "carga_horaria": 20, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 199.90},
    {"code": "NR-10-R", "name": "NR 10 - Reciclagem", "category": "NR 10", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 99.90},
    
    # NR 11 - Transporte, Movimentação, Armazenagem e Manuseio de Materiais
    {"code": "NR-11-F", "name": "NR 11 - Formação", "category": "NR 11", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-11-R", "name": "NR 11 - Reciclagem", "category": "NR 11", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 12 - Segurança do Trabalho em Máquinas e Equipamentos
    {"code": "NR-12-F", "name": "NR 12 - Formação", "category": "NR 12", "carga_horaria": 12, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 199.90},
    {"code": "NR-12-R", "name": "NR 12 - Reciclagem", "category": "NR 12", "carga_horaria": 6, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 99.90},
    
    # NR 17 - Ergonomia
    {"code": "NR-17-F", "name": "NR 17 - Ergonomia - Formação", "category": "NR 17", "carga_horaria": 8, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-17-R", "name": "NR 17 - Ergonomia - Reciclagem", "category": "NR 17", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 18 - Condições e Meio Ambiente de Trabalho na Indústria da Construção
    {"code": "NR-18-F", "name": "NR 18 - Formação", "category": "NR 18", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-18-R", "name": "NR 18 - Reciclagem", "category": "NR 18", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 20 - Segurança e Saúde no Trabalho com Inflamáveis e Combustíveis
    {"code": "NR-20-F", "name": "NR 20 - Formação", "category": "NR 20", "carga_horaria": 12, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 199.90},
    {"code": "NR-20-R", "name": "NR 20 - Reciclagem", "category": "NR 20", "carga_horaria": 6, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 99.90},
    
    # NR 22 - Segurança e Saúde Ocupacional na Mineração (CIPAMIN)
    {"code": "NR-22-F", "name": "NR 22 - CIPAMIN - Formação", "category": "NR 22", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-22-R", "name": "NR 22 - CIPAMIN - Reciclagem", "category": "NR 22", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 23 - Proteção Contra Incêndios
    {"code": "NR-23-F", "name": "NR 23 - Proteção Contra Incêndios - Formação", "category": "NR 23", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-23-R", "name": "NR 23 - Proteção Contra Incêndios - Reciclagem", "category": "NR 23", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 26 - Sinalização de Segurança
    {"code": "NR-26-F", "name": "NR 26 - Sinalização de Segurança - Formação", "category": "NR 26", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 79.90},
    {"code": "NR-26-R", "name": "NR 26 - Sinalização de Segurança - Reciclagem", "category": "NR 26", "carga_horaria": 2, "modality": "EAD", "tipo_curso": "RECICLAGEM", "price": 39.90},
    
    # NR 29 - Segurança e Saúde no Trabalho Portuário
    {"code": "NR-29-F", "name": "NR 29 - Trabalho Portuário - Formação", "category": "NR 29", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-29-R", "name": "NR 29 - Trabalho Portuário - Reciclagem", "category": "NR 29", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 31 - Segurança e Saúde no Trabalho na Agricultura, Pecuária, Silvicultura, Exploração Florestal e Aquicultura
    {"code": "NR-31-I", "name": "NR 31 - Trabalho Rural - Inicial", "category": "NR 31", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "INICIAL", "price": 149.90},
    {"code": "NR-31-R", "name": "NR 31 - Trabalho Rural - Reciclagem", "category": "NR 31", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 32 - Segurança e Saúde no Trabalho em Serviços de Saúde
    {"code": "NR-32-F", "name": "NR 32 - Serviços de Saúde - Formação", "category": "NR 32", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-32-R", "name": "NR 32 - Serviços de Saúde - Reciclagem", "category": "NR 32", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 33 - Segurança e Saúde no Trabalho em Espaços Confinados
    {"code": "NR-33-F", "name": "NR 33 - Espaços Confinados - Formação", "category": "NR 33", "carga_horaria": 16, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 249.90},
    {"code": "NR-33-R", "name": "NR 33 - Espaços Confinados - Reciclagem", "category": "NR 33", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 149.90},
    
    # NR 34 - Condições e Meio Ambiente de Trabalho na Indústria da Construção, Reparação, Manutenção, Alteração e Desmontagem de Embarcações
    {"code": "NR-34-F", "name": "NR 34 - Trabalho Naval - Formação", "category": "NR 34", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-34-P", "name": "NR 34 - Trabalho Naval - Periódico", "category": "NR 34", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "PERIODICO", "price": 79.90},
    
    # NR 35 - Trabalho em Altura
    {"code": "NR-35-F", "name": "NR 35 - Trabalho em Altura - Formação", "category": "NR 35", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-35-R", "name": "NR 35 - Trabalho em Altura - Reciclagem", "category": "NR 35", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # NR 36 - Segurança e Saúde do Trabalho em Empresas de Abate e Processamento de Carnes e Derivados
    {"code": "NR-36-F", "name": "NR 36 - Frigoríficos - Formação", "category": "NR 36", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "NR-36-R", "name": "NR 36 - Frigoríficos - Reciclagem", "category": "NR 36", "carga_horaria": 4, "modality": "SEMIPRESENCIAL", "tipo_curso": "RECICLAGEM", "price": 79.90},
    
    # Programas Complementares
    {"code": "PCA-F", "name": "Programa de Conservação Auditiva (PCA) - Formação", "category": "Programas", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 79.90},
    {"code": "PPR-F", "name": "Programa de Proteção Respiratória (PPR) - Formação", "category": "Programas", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 79.90},
    {"code": "PS-F", "name": "Primeiros Socorros - Formação", "category": "Programas", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    
    # Cursos Complementares
    {"code": "DD-F", "name": "Direção Defensiva - Formação", "category": "Complementares", "carga_horaria": 8, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 149.90},
    {"code": "GL-F", "name": "Ginástica Laboral - Formação", "category": "Complementares", "carga_horaria": 4, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 79.90},
    {"code": "DP-F", "name": "Desenvolvimento Pessoal - Formação", "category": "Complementares", "carga_horaria": 8, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 99.90},
    {"code": "LE-F", "name": "Língua Estrangeira (Inglês) - Formação", "category": "Complementares", "carga_horaria": 20, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 199.90},
    {"code": "NEG-F", "name": "Negócios - Formação", "category": "Complementares", "carga_horaria": 8, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 99.90},
    {"code": "QP-F", "name": "Qualificação Profissional - Formação", "category": "Complementares", "carga_horaria": 20, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 299.90},
    {"code": "SAU-F", "name": "Saúde - Formação", "category": "Complementares", "carga_horaria": 8, "modality": "EAD", "tipo_curso": "FORMACAO", "price": 99.90},
    {"code": "BV-F", "name": "Brigada Voluntária - Formação", "category": "Complementares", "carga_horaria": 16, "modality": "SEMIPRESENCIAL", "tipo_curso": "FORMACAO", "price": 249.90},
]
