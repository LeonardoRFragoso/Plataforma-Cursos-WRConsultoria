# Payment Lifecycle Policy

> Status: **PRE-LAUNCH / IN PROGRESS** — implemented in PR #23, dependent on PR #22.
>
> This document describes the business behavior expected from payment attempts,
> expiration, refunds and chargebacks. It is not a provider-specific API manual.

## Principles

1. **Never double-charge a student.**
2. **Provider state wins once an external charge exists.**
3. **Terminal financial attempts are immutable history.**
4. **Learning/certificate history is not silently destroyed by finance events.**
5. **Ambiguous financial states require human review instead of guessing.**
6. **Tenant boundaries apply to every lookup, webhook and payment mutation.**

## Payment statuses

| Status | Meaning | Can create checkout? | Can be reused for a new purchase action? |
|---|---|---:|---:|
| `PENDENTE` | Internal attempt created, provider may not have been contacted yet | Yes | Yes while active |
| `PROCESSANDO` | External charge/checkout is active or provider is still processing | Reuse existing checkout | Yes, same attempt |
| `APROVADO` | Provider confirmed payment | No | No new charge |
| `RECUSADO` | Attempt was rejected/closed | No | No; create a new Payment row |
| `REEMBOLSADO` | Payment was fully refunded / final adverse chargeback outcome | No | No; historical record |
| `EXPIRADO` | Attempt/charge was explicitly closed by expiry/cancellation policy | No | No; create a new Payment row |

## Active-attempt invariant

For an individual enrollment, there may be at most one active payment attempt in
`PENDENTE`, `PROCESSANDO` or `APROVADO`.

The rule is enforced twice:

- application layer: enrollment row locks + active-attempt lookup;
- database layer: partial unique index
  `uq_payment_active_attempt_per_enrollment`.

The migration refuses to proceed if legacy data already violates the invariant.
Those rows must be reconciled manually rather than arbitrarily deleting history.

## Abandoned internal attempts

A `PENDENTE` payment may be expired locally only when **all** are true:

- it is older than `PAYMENT_PENDING_ATTEMPT_TTL_MINUTES`;
- it has no `provider_payment_id`;
- it has no `checkout_url`;
- it has no legacy Mercado Pago preference id.

When those conditions are met:

1. old payment becomes `EXPIRADO`;
2. enrollment remains `PENDENTE`;
3. a new purchase action creates a new `Payment`;
4. old attempt remains stored for audit/history.

### External charge exception

Once the platform has evidence that the provider created a charge, local time
must **not** expire it. This is important for boleto/PIX/card states that may
remain payable or settle after the browser was closed.

The provider webhook/reconciliation is the source of truth for those attempts.

## Asaas lifecycle

### Overdue

`PAYMENT_OVERDUE` remains `PROCESSANDO`.

Overdue is not treated as an expired/cancelled payment because a boleto/PIX can
still settle later. The platform keeps the existing external attempt instead of
creating a second charge.

### Bank slip cancelled

`PAYMENT_BANK_SLIP_CANCELLED` closes the attempt as `EXPIRADO`.

The enrollment remains pending and the student can start a new purchase attempt.

### Refund

- `PAYMENT_REFUNDED`: full refund policy.
- `PAYMENT_PARTIALLY_REFUNDED`: manual review.
- `PAYMENT_REFUND_IN_PROGRESS`: manual review.
- `PAYMENT_REFUND_DENIED`: clears the refund review flag.

### Chargeback

The request/dispute phases are **not** equivalent to a rejected payment:

- `PAYMENT_CHARGEBACK_REQUESTED` → review required;
- `PAYMENT_CHARGEBACK_DISPUTE` → review required;
- `PAYMENT_AWAITING_CHARGEBACK_REVERSAL` → review required.

Access and historical learning data are not automatically revoked during the
dispute. A later final refund event applies the full-refund policy.

## Mercado Pago lifecycle

Provider status is reconciled conservatively:

- `approved` → `APROVADO`;
- `pending`, `in_process`, `in_mediation` → `PROCESSANDO`;
- `rejected` → `RECUSADO`;
- `cancelled` / `canceled` / `expired` → `EXPIRADO` policy;
- `refunded` → full-refund policy;
- `charged_back` + dispute in progress → review required;
- `charged_back` + adverse settlement → full-refund policy;
- `charged_back` + seller reimbursed → `APROVADO`, review cleared.

Unknown provider statuses are acknowledged without changing payment or access.
This is fail-safe behavior: an unknown future provider state must never unlock a
course or silently revoke it.

## Full refund policy

### Before course completion / certificate

When the student has not completed the course and has no certificate:

1. payment becomes `REEMBOLSADO`;
2. enrollment becomes `CANCELADA`;
3. access is revoked;
4. payment history remains stored.

### After completion or certificate issuance

The platform does **not** silently delete or rewrite training evidence:

1. payment becomes `REEMBOLSADO`;
2. completed enrollment remains preserved;
3. certificate record remains preserved;
4. `review_required = true`;
5. `review_reason = refund_after_completion_or_certificate`.

Certificate revocation/reissue is a separate Trusted Certificate lifecycle and
must be an explicit, auditable decision.

## Partial refund policy

Partial or in-progress refund does not automatically decide access.

The payment receives:

- `review_required = true`;
- a provider/event-specific `review_reason`.

This intentionally leaves commercial policy to an explicit operator decision
until configurable tenant refund rules exist.

## Financial review state

`payments.review_required` and `payments.review_reason` indicate that the
financial state requires human reconciliation.

Examples:

- chargeback dispute in progress;
- partial refund;
- refund after certificate issuance;
- unexpected expiration event after an already approved/refunded state.

These fields are exposed in `PaymentResponse` and are intended to support a
future administrative review queue.

## Idempotency

Webhook processing must remain idempotent.

Repeated provider events must not:

- create a second Payment;
- send duplicate course-unlocked email;
- recreate a checkout;
- cancel the same enrollment repeatedly;
- delete historical financial or certificate records.

## Deployment gate

Before merging/releasing this lifecycle:

```bash
FULL_BACKEND=1 FULL_FRONTEND=1 E2E=1 bash scripts/validate-b2c-purchase.sh
```

Additionally validate on a migrated PostgreSQL database:

```bash
cd api
alembic heads
alembic upgrade head
```

If the migration reports duplicate active payments, stop the release and
reconcile those records manually before retrying the migration.
