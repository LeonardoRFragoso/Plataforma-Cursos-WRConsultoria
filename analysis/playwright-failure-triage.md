# Playwright failure triage

## Runs

- Initial run: 86 tests could not launch because the Playwright Chromium headless executable was not installed. This was an `ENVIRONMENT` prerequisite failure, not an application failure. Chromium was installed with `npx playwright install chromium`.
- Reproduced application run: 29 failed, 57 passed.
- Final run after fixture correction: **86 passed, 0 failed**.

## Root-cause groups

| TEST | FEATURE | FAILURE | ROOT_CAUSE | CLASSIFICATION | ACTION |
|---|---|---|---|---|---|
| `b2c-entry.spec.js` B2C-ENTRY-001, 002, 003 | B2C entry, registration, login redirect | Course detail never rendered | Mock routes targeted `localhost:8000`, while Vite loaded `VITE_API_URL=http://localhost:8001` from the repository `.env`; requests were not intercepted | MOCK_CONTRACT_DRIFT | Changed the fixture API base to the configured local LMS port `8001` |
| `b2c-entry.spec.js` MULTITENANT-ID-001 | Tenant-scoped authentication | Login remained on `/login` | Same unmatched authentication mock caused the real request to be attempted | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001`; kept both tenant login assertions enabled |
| `b2c-purchase.spec.js` B2C-FREE-001, B2C-PURCHASE-001, PAY-ABANDON-001 | Free purchase, paid purchase, abandoned payment | Expected CTA was absent | Course/enrollment/payment mocks were on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001`; no tests skipped or deleted |
| `certificate-qr-validation.spec.js` CERT-QR-001–004 | QR/public certificate validation | Validation state/test IDs never appeared | Validation endpoint mock was on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001`; retained valid, compatibility, not-found, and revoked cases |
| `compliance-operations.spec.js` admin dashboard test | Compliance operations | Login stayed on `/login` | Auth/branding mocks were on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001` |
| `home.spec.js` flows 2–4 | Student login, enrolled course, certificate validation | Redirect/detail assertions timed out | Home fixture endpoints were on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001` |
| `premium-ui.spec.js` PREMIUM-UI-003 | Authenticated admin shell | Admin login did not complete | Auth mock was on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001` |
| `tutor-nr.spec.js` four tutor tests | NR tutor and conversation context | Tutor response/source chips did not appear | Tutor endpoint mock was on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001`; retained all source and follow-up assertions |
| `ui-ux-hardening.spec.js` reset-password test and CourseDetail/dashboard/admin thumbnail tests | Password recovery and visual media | Expected form/media was absent | Relevant API fixtures were on the stale port | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001`; retained responsive and thumbnail coverage |
| `white-label-demo.spec.js` WR, Alfa, favicon, header, footer tests | White-label branding and tenant isolation | Branding fell back to WR/default values; Alfa favicon/header assertions failed | Branding mocks were on the stale port, so the application correctly used its fallback branding; this was a fixture mismatch, not cross-tenant leakage | MOCK_CONTRACT_DRIFT | Updated fixture API base to `8001`; verified WR and Alfa cases pass independently and no WR text leaks into Alfa assertions |

## Validation

The correction was limited to the UI-mocked test contract: all ten UI-mocked suites now intercept the same `8001` API origin used by the built frontend. The final run was:

```text
86 passed (39.6s)
```

No `.skip` markers, test deletions, or application changes were used to hide failures.
