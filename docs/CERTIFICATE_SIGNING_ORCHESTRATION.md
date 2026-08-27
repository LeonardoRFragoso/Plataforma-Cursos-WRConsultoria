# Certificate Signing Orchestration

## Scope

This phase connects the trusted certificate document pipeline to a safe signing orchestration layer without activating real production credentials.

The application never stores a private key, PFX/PKCS#12 payload, certificate password or HSM secret in certificate tables, profile JSON or frontend state.

## Domain separation

### CertificateSigningProfile

Tenant-level operational policy and **public** signer/certificate metadata:

- provider;
- enabled flag;
- signer display name/identifier;
- public SHA-256 certificate fingerprint;
- serial/subject/issuer;
- validity window;
- external HSM/provider key reference;
- non-secret provider metadata.

Credentials are kept in encrypted `TenantSecret` entries:

- `certificate_signing_api_token`;
- `certificate_signing_webhook_secret`.

`provider_metadata` rejects credential/private-key-like keys.

### CertificateSigningJob

One job per immutable `CertificateDocument`.

States:

- `QUEUED`;
- `SUBMITTING`;
- `WAITING_PROVIDER`;
- `RETRY_SCHEDULED`;
- `SIGNED`;
- `FAILED`;
- `CANCELLED`.

The job freezes a `profile_snapshot` so a retry/poll remains tied to the signer/provider configuration used for that document.

### CertificateSigningEvent

Append-only operational ledger. PostgreSQL rejects UPDATE/DELETE.

## Providers

### DISABLED

Default/safe state. Nothing is submitted.

### MOCK

Non-cryptographic test/demo adapter.

- forbidden when `ENVIRONMENT=production`;
- appends an explicit `MOCK-PADES-SIGNATURE — SEM VALIDADE ICP-BRASIL` marker;
- reports `chain_trusted=false` and `is_mock=true`;
- exists only to exercise the complete domain workflow.

### EXTERNAL_PADES_GATEWAY

Vendor-neutral contract for an external PAdES/HSM/ICP-Brasil gateway.

The platform sends the immutable original PDF over HTTPS with:

- `X-Certificate-Id`;
- `X-Original-SHA256`;
- stable `Idempotency-Key`;
- optional callback URL;
- bearer credential from encrypted TenantSecret.

The gateway owns private-key/HSM access and ICP-Brasil trust-chain validation.

A signed result is accepted only when the gateway verification evidence says:

- `signature_valid=true`;
- `chain_trusted=true`;
- `standard` starts with `PAdES`;
- returned certificate fingerprint matches the frozen configured fingerprint when one was configured;
- returned PDF differs from the original and is structurally a PDF.

Only then does the orchestrator call the internal `CertificateDocumentService.finalize_signed_document()` boundary.

## Webhook

`POST /api/v1/integrations/certificate-signing/webhook/{tenant_slug}/{provider}`

Authentication:

- `X-Signature-Timestamp`;
- `X-Signature-Hmac` = HMAC-SHA256(secret, `timestamp + '.' + raw_body`);
- 5 minute replay window;
- tenant webhook secret is encrypted in TenantSecret.

The callback **never** receives a PDF and **never** marks a certificate signed. It only wakes the trusted poll/verification worker.

This keeps the signed artifact retrieval and trust decision inside the configured adapter.

## Retries and crash safety

- exponential retry: 30 seconds up to 1 hour;
- per-job `max_attempts`, bounded to 1..20;
- non-retryable trust/fingerprint/configuration failures end in `FAILED`;
- provider/network failures can move to `RETRY_SCHEDULED`;
- provider job IDs are preserved on retries so the system polls rather than resubmits;
- external submit uses a certificate-version stable idempotency key;
- stale `SUBMITTING` jobs become eligible after five minutes;
- if the document was successfully finalized but the job status update was interrupted, the worker reconciles it to `SIGNED`.

## Worker

Scheduler-safe command:

```bash
python -m app.scripts.process_certificate_signing
```

The command scans active tenants with privileged RLS bypass only to enumerate tenants, then processes each tenant under that tenant's own RLS context.

No scheduler is activated by this phase.

## Admin API

- `GET /api/v1/certificate-signing/status`
- `GET /api/v1/certificate-signing/profile`
- `PUT /api/v1/certificate-signing/profile`
- `POST /api/v1/certificate-signing/certificates/{certificate_id}/enqueue`
- `GET /api/v1/certificate-signing/jobs`
- `GET /api/v1/certificate-signing/jobs/{job_id}`
- `GET /api/v1/certificate-signing/jobs/{job_id}/events`
- `POST /api/v1/certificate-signing/jobs/{job_id}/process`
- `POST /api/v1/certificate-signing/jobs/{job_id}/retry`
- `POST /api/v1/certificate-signing/jobs/{job_id}/cancel`
- `GET /api/v1/certificate-signing/queue/summary`

`process` runs the configured adapter. It does not allow an admin to upload/inject arbitrary signed bytes.

## Production activation gates

Before using `EXTERNAL_PADES_GATEWAY` in production, all of the following remain external/operational gates:

1. select the actual qualified signing/HSM provider;
2. validate its API contract against this adapter or implement a vendor-specific adapter;
3. establish the ICP-Brasil trust-validation policy;
4. provision API/webhook secrets in TenantSecret/secret management;
5. register the real public certificate fingerprint and validity metadata;
6. run sandbox/homologation signatures and independently validate produced PAdES PDFs;
7. activate the scheduler/worker;
8. approve legal/regulatory responsibility for signer/issuer roles.

Until then, no code in this phase claims a production certificate has an ICP-Brasil signature.
