# Business Journey Matrix

> Living contract for business behavior across WR Plataforma de Cursos.
>
> This document is the authoritative matrix of business journeys, their expected
> behavior, and implementation coverage. It is updated as journeys are implemented
> and hardened.
>
> Environment: PRE-LAUNCH / HOMOLOGAÇÃO (see `docs/PRE_LAUNCH_STRATEGY.md`).
> No real Asaas credentials or monetary transactions are used during PRE-LAUNCH.

---

## Matrix columns

| Column | Description |
|--------|-------------|
| ID | Unique journey identifier |
| Priority | P0 (blocker) / P1 (high) / P2 (evolution) / P3 (future) |
| Journey | Short description of the journey |
| Actor | Who initiates the journey |
| Tenant | WR / Alfa / Partner / Any |
| Preconditions | What must be true before the journey starts |
| Steps | Sequential steps of the journey |
| Expected result | What the user/system should observe |
| Backend coverage | Test coverage status on the backend |
| Frontend coverage | Test coverage status on the frontend |
| E2E coverage | Playwright E2E coverage status |
| Status | NOT STARTED / IN PROGRESS / IMPLEMENTED / DEFERRED |
| Notes | Additional context or caveats |

---

## B2C — Pessoa física

### B2C-ENTRY-001 — Anonymous visitor registers and returns to course

| Field | Value |
|-------|-------|
| ID | B2C-ENTRY-001 |
| Priority | P0 |
| Journey | Anonymous visitor → public course → register → auto-login → return to same course |
| Actor | Anonymous visitor (prospective student) |
| Tenant | Any (WR or partner) |
| Preconditions | A public course exists in the catalog |
| Steps | 1. Visitor opens `/cursos/:id`; 2. Clicks "Entrar para comprar"; 3. Redirected to `/login?redirect=/cursos/:id`; 4. Clicks "Cadastre-se"; 5. Redirected to `/register?redirect=/cursos/:id`; 6. Fills name, email, CPF, password; 7. Submits registration; 8. Auto-login succeeds; 9. Redirected back to `/cursos/:id` |
| Expected result | User is authenticated and sees the same course detail page, now with purchase options for an authenticated student |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — register + login tenant-scoped |
| Frontend coverage | ✅ `Register.spec.js` — auto-login + redirect; `Login.spec.js` — redirect preservation; `CourseDetail.spec.js` — CTA redirect |
| E2E coverage | 🟠 IN PROGRESS — Playwright B2C entry flow |
| Status | IN PROGRESS |
| Notes | Auto-login uses the normal auth store login path. No password is emailed. If auto-login fails, manual login link is shown. |

### B2C-ENTRY-002 — Existing user logs in and returns to course

| Field | Value |
|-------|-------|
| ID | B2C-ENTRY-002 |
| Priority | P0 |
| Journey | Anonymous visitor → public course → login with existing account → return to same course |
| Actor | Returning student |
| Tenant | Any |
| Preconditions | User has an existing account in the resolved tenant |
| Steps | 1. Visitor opens `/cursos/:id`; 2. Clicks "Entrar para comprar"; 3. Login page preserves `?redirect=/cursos/:id`; 4. User logs in; 5. Redirected back to `/cursos/:id` |
| Expected result | User is authenticated and sees the course detail page |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — login tenant-scoped |
| Frontend coverage | ✅ `Login.spec.js` — valid redirect after login |
| E2E coverage | 🟠 IN PROGRESS |
| Status | IN PROGRESS |

### B2C-PURCHASE-001 — Purchase a paid course

| Field | Value |
|-------|-------|
| ID | B2C-PURCHASE-001 |
| Priority | P0 |
| Journey | Authenticated student → course detail → purchase → payment → enrollment confirmed → access |
| Actor | Authenticated student |
| Tenant | Any |
| Preconditions | Course has price > 0, user is authenticated |
| Steps | 1. Click "Comprar agora"; 2. Redirected to payment gateway (mocked in PRE-LAUNCH); 3. Payment confirmed; 4. Enrollment created; 5. Course access unlocked |
| Expected result | Student can access the course content |
| Backend coverage | 🟠 Existing payment tests use mocks |
| Frontend coverage | 🟠 Existing CourseDetail tests |
| E2E coverage | 🟠 DEFERRED to payment lifecycle slice |
| Status | DEFERRED |
| Notes | Payment lifecycle (retry, declined, abandoned checkout) is a subsequent slice. No real Asaas during PRE-LAUNCH. |

### B2C-FREE-001 — Enroll in a free course

| Field | Value |
|-------|-------|
| ID | B2C-FREE-001 |
| Priority | P0 |
| Journey | Authenticated student → free course → direct enrollment → access |
| Actor | Authenticated student |
| Tenant | Any |
| Preconditions | Course price == 0, user is authenticated |
| Steps | 1. Click "Comprar/Entrar"; 2. No gateway needed; 3. Enrollment confirmed; 4. Course access unlocked |
| Expected result | Student can access the course without payment |
| Backend coverage | 🟠 DEFERRED |
| Frontend coverage | 🟠 DEFERRED |
| E2E coverage | 🟠 DEFERRED |
| Status | DEFERRED |
| Notes | Free-course checkout without gateway is a subsequent slice. |

---

## B2B CUSTOMER COMPANY — Empresa cliente de treinamento

### B2B-LEAD-001 — Company expresses interest in training

| Field | Value |
|-------|-------|
| ID | B2B-LEAD-001 |
| Priority | P1 |
| Journey | Company representative → public B2B form → lead captured → admin follow-up |
| Actor | Company representative |
| Tenant | WR |
| Preconditions | Public B2B form exists |
| Steps | 1. Company rep fills form with CNPJ, contact, number of employees, desired courses; 2. Lead created; 3. Admin reviews; 4. Lead converted to Company/contract |
| Expected result | Lead is captured and can be converted without rework |
| Backend coverage | 🟠 DEFERRED |
| Frontend coverage | 🟠 DEFERRED |
| E2E coverage | 🟠 DEFERRED |
| Status | DEFERRED |
| Notes | B2B lead funnel is a subsequent slice. Distinct from white-label PartnerLead. |

### B2B-ONBOARD-001 — Corporate employee activation

| Field | Value |
|-------|-------|
| ID | B2B-ONBOARD-001 |
| Priority | P1 |
| Journey | Admin creates company → adds employees → employees activate accounts → training |
| Actor | Admin + corporate employees |
| Tenant | Any |
| Preconditions | Company exists, employees created by admin |
| Steps | 1. Admin creates employees (with or without password); 2. Activation token generated; 3. Employee receives activation link; 4. Employee sets password; 5. Account activated |
| Expected result | Employee can log in and access assigned courses |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — activation tenant-bound |
| Frontend coverage | 🟠 Existing |
| E2E coverage | 🟠 DEFERRED |
| Status | IN PROGRESS (tenant scope hardened) |

---

## WHITE-LABEL PARTNER — Parceiro white-label

### WL-PARTNER-001 — Partner lead to tenant creation

| Field | Value |
|-------|-------|
| ID | WL-PARTNER-001 |
| Priority | P1 |
| Journey | Prospective partner → "Seja parceiro" form → WR approval → tenant created → partner admin activated |
| Actor | Prospective partner + WR SUPER_ADMIN |
| Tenant | WR (approval) → new partner tenant |
| Preconditions | Partner lead form exists |
| Steps | 1. Partner fills form; 2. SUPER_ADMIN reviews; 3. Approved → tenant + admin user created; 4. Partner admin activates account; 5. Partner onboards |
| Expected result | Partner has their own tenant and can operate their academy |
| Backend coverage | 🟠 Existing partner lead tests |
| Frontend coverage | 🟠 Existing |
| E2E coverage | 🟠 Existing white-label regression |
| Status | IMPLEMENTED (existing) |

---

## MULTI-TENANT IDENTITY — Identidade multi-tenant

### MULTITENANT-ID-001 — Same person exists in WR and Alfa

| Field | Value |
|-------|-------|
| ID | MULTITENANT-ID-001 |
| Priority | P0 |
| Journey | Same email/CPF registered in WR and Alfa → each tenant authenticates its own user |
| Actor | Same person in two tenants |
| Tenant | WR + Alfa |
| Preconditions | Both tenants exist |
| Steps | 1. Person registers in WR with email X; 2. Same person registers in Alfa with email X; 3. WR login authenticates WR user; 4. Alfa login authenticates Alfa user; 5. Cross-tenant password rejected |
| Expected result | No ambiguity. Each tenant authenticates only its own user. |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — same email/CPF cross-tenant login + register |
| Frontend coverage | N/A (backend behavior) |
| E2E coverage | 🟠 IN PROGRESS — Playwright multi-tenant identity |
| Status | IN PROGRESS |
| Notes | Login query is tenant-scoped from the database level. No global lookup. |

### MULTITENANT-ID-002 — Password recovery tenant-scoped

| Field | Value |
|-------|-------|
| ID | MULTITENANT-ID-002 |
| Priority | P0 |
| Journey | Same email in WR + Alfa → reset request from WR targets WR user only |
| Actor | Same person in two tenants |
| Tenant | WR + Alfa |
| Preconditions | Same email exists in both tenants |
| Steps | 1. Request reset from WR context; 2. Only WR user gets reset token; 3. Alfa user unaffected; 4. Reset token cannot be used cross-tenant |
| Expected result | Password recovery is tenant-scoped end-to-end |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — cross-tenant reset |
| Frontend coverage | N/A |
| E2E coverage | 🟠 DEFERRED |
| Status | IN PROGRESS |
| Notes | Anti-enumeration: generic response regardless of email existence. |

### MULTITENANT-ID-003 — Activation tenant-scoped

| Field | Value |
|-------|-------|
| ID | MULTITENANT-ID-003 |
| Priority | P0 |
| Journey | Activation token is bound to the correct tenant |
| Actor | Corporate employee / partner admin |
| Tenant | Any |
| Preconditions | Activation token exists for a user in tenant T |
| Steps | 1. Activation token used in tenant T context → succeeds; 2. Same token used in different tenant context → rejected |
| Expected result | Cross-tenant activation is impossible |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — activation cross-tenant rejected |
| Frontend coverage | N/A |
| E2E coverage | 🟠 DEFERRED |
| Status | IN PROGRESS |

---

## PAYMENT LIFECYCLE — Lifecycle de pagamento

> All payment lifecycle journeys are DEFERRED to subsequent slices.
> No real Asaas credentials or monetary transactions during PRE-LAUNCH.

| ID | Priority | Journey | Status |
|----|----------|---------|--------|
| PAY-RETRY-001 | P0 | Declined payment → new attempt | DEFERRED |
| PAY-ABANDON-001 | P0 | Abandoned checkout → resume without duplicate charge | DEFERRED |
| PAY-DUP-001 | P0 | Double-click / two tabs → no duplicate enrollment/charge | DEFERRED |
| PAY-FREE-001 | P0 | Free course → direct enrollment without gateway | DEFERRED |
| PAY-REFUND-001 | P1 | Refund → access policy | DEFERRED |
| PAY-CHARGEBACK-001 | P1 | Chargeback → access/certificate policy | DEFERRED |
| PAY-EXPIRED-001 | P1 | Expired payment → resume or recreate | DEFERRED |

---

## ACCOUNT RECOVERY — Recuperação de conta

### ACC-RESET-001 — Password reset via email

| Field | Value |
|-------|-------|
| ID | ACC-RESET-001 |
| Priority | P0 |
| Journey | User forgot password → request reset → receive token → set new password |
| Actor | Any user |
| Tenant | Any |
| Preconditions | User exists in the resolved tenant |
| Steps | 1. User enters email on `/recuperar-senha`; 2. System generates one-time token; 3. In dev/test, token returned; in staging/prod, emailed; 4. User uses token on `/redefinir-senha`; 5. Password updated |
| Expected result | User can log in with the new password |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` + `test_auth_security_hardening.py` |
| Frontend coverage | 🟠 Existing ForgotPassword/ResetPassword tests |
| E2E coverage | 🟠 DEFERRED |
| Status | IN PROGRESS (tenant scope hardened) |
| Notes | Token is one-time, expiring, secure. Anti-enumeration: generic response. |

### ACC-ACTIVATE-001 — Account activation via token

| Field | Value |
|-------|-------|
| ID | ACC-ACTIVATE-001 |
| Priority | P0 |
| Journey | Inactive user → activation link → set password → account active |
| Actor | Corporate employee / partner admin |
| Tenant | Any |
| Preconditions | User was created without a password (admin-created) |
| Steps | 1. User receives activation link; 2. Sets password on `/ativar-conta`; 3. Account activated |
| Expected result | User can log in |
| Backend coverage | ✅ `test_b2c_identity_journeys.py` — activation tenant-bound |
| Frontend coverage | 🟠 Existing ActivateAccount tests |
| E2E coverage | 🟠 DEFERRED |
| Status | IN PROGRESS (tenant scope hardened) |

---

## CERTIFICATION — Certificação

| ID | Priority | Journey | Status |
|----|----------|---------|--------|
| CERT-ISSUE-001 | P1 | Complete course → certificate issued | IMPLEMENTED (existing) |
| CERT-VALIDATE-001 | P1 | Public certificate validation | IMPLEMENTED (existing) |
| CERT-TEMPLATE-001 | P2 | Certificate Studio templates | DEFERRED (UX slice) |

---

## CPF/CNPJ Validation

| ID | Priority | Journey | Status |
|----|----------|---------|--------|
| CPF-VAL-001 | P0 | Mathematical CPF validation on registration | ✅ IMPLEMENTED |
| CPF-VAL-002 | P0 | Invalid CPF never sent to payment provider | ✅ IMPLEMENTED |
| CNPJ-VAL-001 | P1 | Mathematical CNPJ validation | DEFERRED (B2B slice) |

---

## Legend

| Status | Meaning |
|--------|---------|
| NOT STARTED | Not yet begun |
| IN PROGRESS | Currently being implemented/hardened |
| IMPLEMENTED | Code implemented, tested, merged |
| DEFERRED | Planned for a subsequent slice/PR |
