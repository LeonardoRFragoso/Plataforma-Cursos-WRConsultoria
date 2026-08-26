# Business Journey Matrix

> Living contract for business behavior across WR Plataforma de Cursos.
>
> Environment: **PRE-LAUNCH / HOMOLOGAÇÃO** (see `docs/PRE_LAUNCH_STRATEGY.md`).
> No real Asaas credentials or monetary transactions are used during PRE-LAUNCH.
>
> `IMPLEMENTED` means merged into `main`. Work that exists only in an open PR is
> intentionally marked `IN PROGRESS` until validation and merge are complete.

---

## Status legend

| Status | Meaning |
|---|---|
| NOT STARTED | Not yet begun |
| IN PROGRESS | Implemented/hardened in an open slice or still awaiting validation |
| IMPLEMENTED | Code implemented, validated and merged |
| DEFERRED | Planned for a subsequent slice/PR |

---

## B2C — Pessoa física

| ID | Priority | Journey | Backend | Frontend | E2E | Status | Notes |
|---|---|---|---|---|---|---|---|
| B2C-ENTRY-001 | P0 | Anonymous visitor → course → register → auto-login → same course | ✅ tenant-scoped register/login | ✅ redirect + auto-login | ✅ `b2c-entry.spec.js` exists; execution gate pending | IN PROGRESS | Entry/identity hardening came from PR #21; final gate still required |
| B2C-ENTRY-002 | P0 | Existing user → course → login → same course | ✅ tenant-scoped login | ✅ redirect preservation | ✅ `b2c-entry.spec.js` exists; execution gate pending | IN PROGRESS | Safe internal redirect only |
| B2C-ENTRY-003 | P0 | Logout → login → intended destination preserved | ✅ | ✅ | ✅ `b2c-entry.spec.js` exists; execution gate pending | IN PROGRESS | Regression coverage for returning users |
| B2C-PURCHASE-001 | P0 | Authenticated student → paid course → checkout → payment confirmation → access | ✅ focused purchase/payment/reconciliation tests in PR #22 | ✅ CourseDetail + PaymentReturn | ✅ `b2c-purchase.spec.js` added; execution gate pending | IN PROGRESS (PR #22) | No real gateway transactions in PRE-LAUNCH |
| B2C-FREE-001 | P0 | Authenticated student → free course → direct enrollment → access | ✅ confirms enrollment with no Payment | ✅ goes directly to `/courses/:id/learn` | ✅ `b2c-purchase.spec.js` added; execution gate pending | IN PROGRESS (PR #22) | Gateway is never called for `price <= 0` |
| B2C-NOTIFY-001 | P1 | Public registration → welcome email | ✅ post-commit, best effort, tenant-aware | N/A | Backend/template coverage | IN PROGRESS (PR #22) | Password is never sent; SMTP failure cannot roll back account creation |
| B2C-NOTIFY-002 | P1 | Payment confirmation → course-access email | ✅ Mercado Pago, Asaas and demo reconciliation hooks | N/A | Backend/template coverage | IN PROGRESS (PR #22) | Triggered only when enrollment is newly confirmed; duplicate webhooks do not resend |

---

## Payment lifecycle

| ID | Priority | Journey | Status | Contract / coverage |
|---|---|---|---|---|
| PAY-RETRY-001 | P0 | Declined/refunded attempt → new payment attempt | IN PROGRESS (PR #22) | Closed attempts remain immutable; a new `Payment` row preserves financial history |
| PAY-ABANDON-001 | P0 | User returns with an active pending/processing attempt | IN PROGRESS (PR #22) | Active attempt and provider checkout are reused; long-lived expiration policy remains deferred |
| PAY-DUP-001 | P0 | Double-click / two tabs → no duplicate enrollment/charge | IN PROGRESS (PR #22) | Student/class row locking + course-level idempotency + checkout reuse; focused backend tests |
| PAY-FREE-001 | P0 | Free course → direct enrollment without gateway | IN PROGRESS (PR #22) | `Payment` is `null`; no provider call |
| PAY-RETURN-001 | P0 | Approved payment return → access CTA resolves correct course | IN PROGRESS (PR #22) | `GET /payments/{id}` enriches individual payment with `course_id` and `enrollment_status` |
| PAY-REFUND-001 | P1 | Full refund → formal access policy | DEFERRED | Current reconciliation preserves existing access; revocation policy must be explicitly defined |
| PAY-CHARGEBACK-001 | P1 | Chargeback → access/certificate policy | DEFERRED | Must define content access, certificate retention/revocation and audit behavior |
| PAY-EXPIRED-001 | P1 | Expired/long-abandoned payment → resume or recreate | DEFERRED | Must be implemented as a separate migration + lifecycle slice; provider charge remains authoritative |

### Payment invariants in PR #22

- `CONFIRMADA` / `CONCLUIDA` enrollment never creates another purchase charge.
- `PENDENTE` / `PROCESSANDO` active attempts are reused.
- `RECUSADO` / `REEMBOLSADO` attempts are preserved and cannot be checked out again.
- An approved payment record is immutable for checkout purposes.
- A free course never creates a payment record.
- Payment/enrollment state is committed before transactional email delivery is attempted.
- Provider webhooks remain authoritative after an external charge exists.

---

## B2B CUSTOMER COMPANY — Empresa cliente de treinamento

| ID | Priority | Journey | Status | Notes |
|---|---|---|---|---|
| B2B-LEAD-001 | P1 | Company representative → public B2B lead → admin follow-up | DEFERRED | Distinct from white-label PartnerLead |
| B2B-ONBOARD-001 | P1 | Admin creates company/employees → activation → assigned training | IN PROGRESS | Tenant-bound activation exists; broader E2E remains deferred |
| B2B-PAY-001 | P1 | Consolidated company payment | IN PROGRESS | Existing corporate flow permits `Payment.enrollment_id = null`; PR #22 aligns response schema |

---

## WHITE-LABEL PARTNER

| ID | Priority | Journey | Status | Notes |
|---|---|---|---|---|
| WL-PARTNER-001 | P1 | Partner lead → WR approval → tenant + partner admin | IMPLEMENTED | Existing flow; activation remains tenant-bound |
| WL-BRANDING-001 | P1 | Tenant branding/custom domain used across academy | IMPLEMENTED / EVOLVING | Transactional email links only trust verified/active custom domains or safe configured HTTP(S) frontend URLs |

---

## MULTI-TENANT IDENTITY

| ID | Priority | Journey | Status | Coverage |
|---|---|---|---|---|
| MULTITENANT-ID-001 | P0 | Same email/CPF in WR and Alfa authenticates the correct tenant user | IN PROGRESS | Backend regression suite + `b2c-entry.spec.js` |
| MULTITENANT-ID-002 | P0 | Password recovery is tenant-scoped | IN PROGRESS | Backend cross-tenant reset tests |
| MULTITENANT-ID-003 | P0 | Activation token is tenant-bound | IN PROGRESS | Backend cross-tenant activation tests |

---

## ACCOUNT RECOVERY

| ID | Priority | Journey | Status | Notes |
|---|---|---|---|---|
| ACC-RESET-001 | P0 | Forgot password → one-time reset token → new password | IN PROGRESS | Anti-enumeration; production/staging do not expose raw token |
| ACC-ACTIVATE-001 | P0 | Inactive account → activation link → set password → active | IN PROGRESS | Cross-tenant token use rejected |

---

## CERTIFICATION

| ID | Priority | Journey | Status |
|---|---|---|---|
| CERT-ISSUE-001 | P1 | Complete course → certificate issued | IMPLEMENTED |
| CERT-VALIDATE-001 | P1 | Public certificate validation | IMPLEMENTED |
| CERT-TEMPLATE-001 | P2 | Certificate Studio templates | DEFERRED |

> Refund/chargeback effects on already-issued certificates are **not** implied by
> the existing certification status. That policy belongs to `PAY-REFUND-001` /
> `PAY-CHARGEBACK-001` and remains deferred.

---

## CPF/CNPJ validation

| ID | Priority | Journey | Status |
|---|---|---|---|
| CPF-VAL-001 | P0 | Mathematical CPF validation on registration | IMPLEMENTED |
| CPF-VAL-002 | P0 | Invalid CPF never reaches payment provider | IMPLEMENTED |
| CNPJ-VAL-001 | P1 | Mathematical CNPJ validation | DEFERRED |

---

## Validation gate for PR #22

Run from the repository root:

```bash
bash scripts/validate-b2c-purchase.sh
```

Optional broader gates:

```bash
FULL_BACKEND=1 FULL_FRONTEND=1 E2E=1 bash scripts/validate-b2c-purchase.sh
```

The PR must remain in draft until the focused gate passes in an environment with
PostgreSQL/backend dependencies and Node/Playwright available. Vercel
`build-rate-limit` statuses are infrastructure quota failures and do not replace
these application validation gates.
