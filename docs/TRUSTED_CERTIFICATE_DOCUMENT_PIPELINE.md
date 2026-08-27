# Trusted Certificate Document Pipeline

Status técnico: implementado na branch `feat/trusted-certificate-document-pipeline`.

Este documento descreve a etapa entre a conclusão regulatória da matrícula e a futura integração de assinatura digital PAdES/ICP-Brasil.

## Objetivo

Um certificado regulatório não pode ser tratado como confiável se o PDF for reconstruído a cada download. A pipeline passa a preservar os bytes exatos do documento preparado para assinatura e, posteriormente, os bytes exatos devolvidos pelo provedor de assinatura.

O hash `Certificate.content_hash` continua sendo o hash SHA-256 do registro estruturado de emissão. Ele não é reutilizado como hash do PDF.

## Estados

O registro acadêmico `Certificate` e o artefato `CertificateDocument` possuem responsabilidades separadas.

### Certificate

- `PENDING_SIGNATURE`: registro reservado, ainda não é uma credencial pública válida.
- `ACTIVE`: documento assinado foi persistido e ativado.
- `REVOKED`: certificado revogado.
- `SUPERSEDED`: certificado substituído por nova versão.

### CertificateDocument

- `PENDING_SIGNATURE`: snapshot e PDF original foram congelados e persistidos.
- `SIGNED`: artefato assinado foi persistido e o certificado correspondente foi ativado.

Não existe endpoint HTTP que altere manualmente um documento para `SIGNED`.

## Snapshot imutável

Antes da renderização, a plataforma congela os fatos que sustentam o certificado:

- identificadores e versão do certificado;
- emissor/tenant;
- aluno, minimizando CPF quando ele não é um campo obrigatório do certificado;
- curso, carga horária, modalidade e tipo;
- turma e período;
- versão do projeto pedagógico fixada na turma;
- referência regulatória e configuração de compliance;
- responsável técnico;
- instrutores cadastrados para o curso;
- tentativa de avaliação satisfatória, quando exigida;
- registro prático satisfatório, quando exigido;
- evidência de confirmação eletrônica do participante;
- digest SHA-256 determinístico do ledger de evidências da matrícula.

O snapshot recebe seu próprio `snapshot_sha256` calculado sobre JSON canônico.

Campos listados em `certificate_required_fields` são fail-closed: a preparação é recusada quando um campo obrigatório não existe ou não é suportado. A aplicação não cria dados regulatórios fictícios para completar o PDF.

## PDF original

A plataforma renderiza um PDF regulatório fixo desta fase e calcula `original_pdf_sha256` sobre os bytes finais.

Em seguida, esses mesmos bytes são armazenados em storage privado usando chave tenant-aware e content-addressed:

`tenants/{tenant_id}/certificates/{certificate_id}/original/{sha256}.pdf`

O PDF original é acessível somente para administração/auditoria.

O Certificate Studio, com templates visuais configuráveis, é uma etapa posterior e não altera o requisito de congelar bytes antes da assinatura.

## Assinatura

`CertificateDocumentService.finalize_signed_document()` é uma fronteira interna destinada ao futuro adaptador do provedor PAdES/ICP-Brasil.

Ela não valida por conta própria uma assinatura ICP-Brasil e não deve ser tratada como um verificador criptográfico.

O adaptador futuro deverá:

1. enviar exatamente o PDF original persistido ao provedor;
2. validar a identidade/resposta do provedor;
3. validar o perfil e a assinatura PAdES/ICP-Brasil de acordo com a integração escolhida;
4. entregar os bytes assinados ao domínio;
5. somente então chamar `finalize_signed_document()`.

Na finalização, a plataforma:

- persiste os bytes assinados;
- calcula `signed_pdf_sha256`;
- grava provedor e metadados de assinatura;
- move o documento de `PENDING_SIGNATURE` para `SIGNED`;
- move o certificado para `ACTIVE`;
- registra eventos de certificado e treinamento;
- move a matrícula regulatória para `CERTIFIED`.

## Imutabilidade no PostgreSQL

A migration `f4a5b6c7d8e9` cria proteção no próprio banco.

Para `certificate_documents`:

- DELETE é proibido;
- snapshot e metadados do PDF original não podem ser alterados;
- a única atualização permitida é `PENDING_SIGNATURE -> SIGNED`, preenchendo os dados do artefato assinado;
- depois de `SIGNED`, a linha inteira é imutável.

Também existe índice parcial único impedindo duas emissões simultâneas em `PENDING_SIGNATURE` para a mesma matrícula.

## Integridade e download

Todo download confiável recalcula SHA-256 antes de devolver o arquivo.

Em caso de divergência:

- o download é bloqueado;
- um evento `INTEGRITY_FAILED` é registrado;
- os bytes corrompidos não são entregues ao usuário.

Depois da assinatura, o endpoint legado de download também usa o artefato persistido. Ele não regenera o certificado com ReportLab.

A validação pública expõe o SHA-256 do PDF apenas quando o documento está `SIGNED`. Enquanto `PENDING_SIGNATURE`, não são expostos hash do original, aluno ou curso.

## Compatibilidade

Certificados não regulatórios continuam usando o fluxo anterior.

Certificados regulatórios:

- não podem ser emitidos diretamente pela rota administrativa antiga;
- não são considerados válidos em `PENDING_SIGNATURE`;
- reemissões voltam para `PENDING_SIGNATURE`;
- versões anteriores permanecem preservadas como histórico.

## Gate externo ainda necessário

A pipeline de documento está preparada para receber uma assinatura real, mas a conformidade criptográfica final depende de fatores externos ao código desta fase:

- definição do provedor de assinatura;
- certificado/credencial real autorizado;
- política de assinatura da organização;
- integração PAdES escolhida;
- validação técnica e jurídica do uso de ICP-Brasil no processo real.

Nenhuma dessas credenciais deve ser simulada ou ativada no pre-launch.
