# UI/UX Audit — WR-Plataforma-Cursos

**Stack:** Vue 3 (Composition API, `<script setup>`) + FastAPI, white-label multi-tenant course platform.
**Frontend root:** `web/src/`
**Router:** `web/src/router/index.js`
**Views:** `web/src/views/`
**Components:** `web/src/components/`

This document is generated from a static read of the codebase. Every route, interaction, modal, state, and accessibility attribute listed below is backed by a specific file and line range.

---

## Route Inventory

Every route registered in `web/src/router/index.js`. Status reflects whether the route is wired to a real component and guarded correctly.

| ROLE | ROUTE | SCREEN | STATUS |
|------|-------|--------|--------|
| PUBLIC | `/` | Home (landing + course vitrine) | WORKING |
| PUBLIC | `/login` | Login | WORKING |
| PUBLIC | `/register` | Register (student self-signup) | WORKING |
| PUBLIC | `/seja-parceiro` | Partner lead form | WORKING |
| PUBLIC | `/validar-certificado` | Validate certificate by code | WORKING |
| PUBLIC | `/recuperar-senha` | Forgot password (email request) | WORKING |
| PUBLIC | `/redefinir-senha` | Reset password (token entry) | WORKING |
| PUBLIC | `/cursos` | Course catalog (reuses Home.vue) | WORKING |
| PUBLIC | `/cursos/:id` | Course detail / purchase | WORKING |
| PUBLIC | `/403` | Forbidden (403) | WORKING |
| PUBLIC | `/:pathMatch(.*)*` | Not Found (404) | WORKING |
| STUDENT, ADMIN, SUPER_ADMIN | `/dashboard` | Dashboard (role-aware) | WORKING |
| ADMIN, SUPER_ADMIN | `/courses` | Courses management (CRUD) | WORKING |
| ADMIN, SUPER_ADMIN | `/courses/:id/lessons` | Course lessons management | WORKING |
| ADMIN, SUPER_ADMIN | `/courses/:id/progress` | Student progress per course | WORKING |
| ADMIN, SUPER_ADMIN | `/classes` | Classes management (CRUD) | WORKING |
| ADMIN, SUPER_ADMIN | `/students` | Students management (CRUD) | WORKING |
| ADMIN, SUPER_ADMIN | `/enrollments` | Enrollments management (CRUD) | WORKING |
| ADMIN, SUPER_ADMIN | `/payments` | Payments management (CRUD) | WORKING |
| STUDENT, ADMIN, SUPER_ADMIN | `/certificates` | Certificates list + validate | WORKING |
| ADMIN, SUPER_ADMIN | `/settings/white-label` | White-label branding settings | WORKING |
| SUPER_ADMIN | `/super-admin` | Super admin SaaS panel | WORKING |
| STUDENT, ADMIN, SUPER_ADMIN | `/courses/:id/learn` | Course player (video player) | WORKING |
| STUDENT, ADMIN, SUPER_ADMIN | `/demo/payment/:paymentId` | Demo payment simulator | WORKING |

**Route guard logic** (`navigationGuard` in `router/index.js`):
- `requiresAuth` → redirects to `/login` if no token.
- `requiresAdmin` → redirects to `getHomeRoute(authStore)` if role is not `admin` or `super_admin`.
- `requiresSuperAdmin` → redirects to `getHomeRoute(authStore)` if role is not `super_admin`.

---

## Interaction Inventory

Every button, link, form submit, and interactive element in every view. Status is `WORKING`, `INTENTIONALLY DISABLED WITH EXPLANATION`, or `REMOVED`. The TEST column references the spec file that covers the interaction (unit = `__tests__/views/*.spec.js`; e2e = `e2e/`).

### Home.vue (`/` and `/cursos`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/` | Home | Logo link | `router-link :to="homeRoute"` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Início" link | `/` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Cursos" link | `/cursos` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Validar certificado" link | `/validar-certificado` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Seja parceiro" link | `/seja-parceiro` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Login" link | `/login` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Cadastro" button | `/register` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | "Comece Agora" CTA (unauthenticated) | `/register` | WORKING | all-views.spec.js |
| AUTH | `/` | Home | "Ir para Dashboard" CTA (authenticated) | `getHomeRoute(authStore)` | WORKING | all-views.spec.js |
| AUTH | `/` | Home | Authed nav links (role-aware) | `/dashboard`, `/courses`, `/super-admin` | WORKING | all-views.spec.js |
| AUTH | `/` | Home | "Sair" logout button | `authStore.logout()` → `/login` | WORKING | all-views.spec.js |
| PUBLIC | `/` | Home | Course card "Ver detalhes" link | `/cursos/${course.id}` | WORKING | all-views.spec.js |

### Login.vue (`/login`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/login` | Login | Logo link | `getHomeRoute(authStore)` | WORKING | Login.spec.js |
| PUBLIC | `/login` | Login | "Cadastre-se" header link | `/register` | WORKING | Login.spec.js |
| PUBLIC | `/login` | Login | Login form submit | `handleLogin()` → `authStore.login()` → `resolveSafeRedirect()` | WORKING | Login.spec.js |
| PUBLIC | `/login` | Login | "Cadastre-se" footer link | `/register` (preserves redirect query) | WORKING | Login.spec.js |
| PUBLIC | `/login` | Login | "Esqueci minha senha" link | `/recuperar-senha` | WORKING | Login.spec.js |

### Register.vue (`/register`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/register` | Register | Logo link | `getHomeRoute(authStore)` | WORKING | all-views.spec.js |
| PUBLIC | `/register` | Register | "Login" header link | `/login` | WORKING | all-views.spec.js |
| PUBLIC | `/register` | Register | Register form submit | `handleRegister()` → `authStore.register()` → redirect to `/login` after 2s | WORKING | all-views.spec.js |
| PUBLIC | `/register` | Register | "Faça login" footer link | `/login` (preserves redirect query) | WORKING | all-views.spec.js |
| PUBLIC | `/register` | Register | Confirm password validation | Inline error `passwordError` computed | WORKING | all-views.spec.js |

### Partner.vue (`/seja-parceiro`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/seja-parceiro` | Partner | Partner lead form submit | `handleSubmit()` → `submitPartnerLead()` | WORKING | Partner.spec.js |
| PUBLIC | `/seja-parceiro` | Partner | "Enviar nova proposta" button (success state) | `resetForm()` | WORKING | Partner.spec.js |

### ValidateCertificate.vue (`/validar-certificado`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/validar-certificado` | Validate | Validation form submit | `handleSubmit()` → `validateCertificate()` | WORKING | ValidateCertificate.spec.js |

### ForgotPassword.vue (`/recuperar-senha`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/recuperar-senha` | Forgot Password | Email form submit | `handleSubmit()` → `POST /api/v1/auth/forgot-password` | WORKING | ForgotPassword.spec.js |
| PUBLIC | `/recuperar-senha` | Forgot Password | "Voltar para o login" link | `/login` | WORKING | ForgotPassword.spec.js |
| PUBLIC | `/recuperar-senha` | Forgot Password | Dev reset token display | INTENTIONALLY DISABLED WITH EXPLANATION — only shown when `import.meta.env.DEV && VITE_ALLOW_DEV_RESET_TOKEN === 'true'`. Fail-closed by default. | INTENTIONALLY DISABLED WITH EXPLANATION | ForgotPassword.spec.js |

### ResetPassword.vue (`/redefinir-senha`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/redefinir-senha` | Reset Password | Reset form submit | `handleSubmit()` → `POST /api/v1/auth/reset-password` | WORKING | ResetPassword.spec.js |
| PUBLIC | `/redefinir-senha` | Reset Password | "Ir para o login" link (success) | `/login` | WORKING | ResetPassword.spec.js |
| PUBLIC | `/redefinir-senha` | Reset Password | "Voltar para o login" link | `/login` | WORKING | ResetPassword.spec.js |
| PUBLIC | `/redefinir-senha` | Reset Password | Token auto-fill from query param | `onMounted()` reads `route.query.token` | WORKING | ResetPassword.spec.js |

### Dashboard.vue (`/dashboard`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/dashboard` | Dashboard | "Tentar novamente" (stats error) | `loadStats()` | WORKING | Dashboard.spec.js |
| ADMIN | `/dashboard` | Dashboard | "Cursos" management link | `/courses` | WORKING | Dashboard.spec.js |
| ADMIN | `/dashboard` | Dashboard | "Turmas" management link | `/classes` | WORKING | Dashboard.spec.js |
| ADMIN | `/dashboard` | Dashboard | "Alunos" management link | `/students` | WORKING | Dashboard.spec.js |
| ADMIN | `/dashboard` | Dashboard | "Matrículas" management link | `/enrollments` | WORKING | Dashboard.spec.js |
| ADMIN | `/dashboard` | Dashboard | "Pagamentos" management link | `/payments` | WORKING | Dashboard.spec.js |
| STUDENT | `/dashboard` | Dashboard | Enrolled course link (CONFIRMADA/CONCLUIDA) | `/courses/${enrollment.course_id}/learn` | WORKING | Dashboard.spec.js |
| STUDENT | `/dashboard` | Dashboard | "Explorar cursos →" link (empty enrollments) | `/cursos` | WORKING | Dashboard.spec.js |
| ALL | `/dashboard` | Dashboard | "Ver certificados →" link | `/certificates` | WORKING | Dashboard.spec.js |
| ALL | `/dashboard` | Dashboard | Profile info card (read-only) | INTENTIONALLY DISABLED WITH EXPLANATION — displays role, name, email. No edit button or form. Profile editing is a deliberate product limitation. | INTENTIONALLY DISABLED WITH EXPLANATION | Dashboard.spec.js |

### Courses.vue (`/courses`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/courses` | Courses | "+ Novo Curso" button | `showForm = true` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | Course form submit (create/edit) | `saveCourse()` → `POST/PUT /api/v1/courses/` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | "Cancelar" form button | `cancelForm()` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | "Gerenciar Aulas" button | `router.push('/courses/${course.id}/lessons')` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | "Acompanhar Alunos" button | `router.push('/courses/${course.id}/progress')` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | "Editar" button | `editCourse(course)` → populates form | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | "Excluir" button | `confirmDelete(course)` → ConfirmDialog → `doDelete()` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | Delete confirm dialog "Excluir" | `doDelete()` → `DELETE /api/v1/courses/${id}` | WORKING | all-views.spec.js |
| ADMIN | `/courses` | Courses | "Tentar novamente" (load error) | `loadCourses()` | WORKING | all-views.spec.js |

### CourseDetail.vue (`/cursos/:id`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/cursos/:id` | Course Detail | "Entrar para comprar" button (unauthenticated) | `goToLogin()` → `/login?redirect=...` | WORKING | CourseDetail.spec.js |
| AUTH | `/cursos/:id` | Course Detail | "Acessar curso" link (enrolled CONFIRMADA/CONCLUIDA) | `/courses/${course.id}/learn` | WORKING | CourseDetail.spec.js |
| AUTH | `/cursos/:id` | Course Detail | "Comprar agora" / "Finalizar pagamento" / "Comprar novamente" button | `startPurchase()` → `purchaseCourse()` → `createCheckout()` → redirect to checkout_url | WORKING | CourseDetail.spec.js |
| PUBLIC | `/cursos/:id` | Course Detail | "Entre" link | `/login?redirect=...` | WORKING | CourseDetail.spec.js |
| PUBLIC | `/cursos/:id` | Course Detail | "cadastre-se" link | `/register?redirect=...` | WORKING | CourseDetail.spec.js |

### CourseLearn.vue (`/courses/:id/learn`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| STUDENT | `/courses/:id/learn` | Course Player | Lesson sidebar button (select lesson) | `selectLesson(lesson)` → loads watch URL | WORKING | CourseLearn.spec.js |
| STUDENT | `/courses/:id/learn` | Course Player | HTML5 video controls (UPLOAD) | Native `<video controls>` + `@timeupdate`, `@ended`, `@pause` progress tracking | WORKING | CourseLearn.spec.js |
| STUDENT | `/courses/:id/learn` | Course Player | "Marcar como concluída" button (YouTube/Vimeo) | `markComplete(lessonId)` → `POST /api/v1/lessons/${id}/progress` | WORKING | CourseLearn.spec.js |
| STUDENT | `/courses/:id/learn` | Course Player | "Ver cursos" link (not enrolled) | `/courses` | WORKING | CourseLearn.spec.js |
| STUDENT | `/courses/:id/learn` | Course Player | YouTube iframe embed | Native YouTube embed via `youtubeEmbedUrl` computed | WORKING | CourseLearn.spec.js |
| STUDENT | `/courses/:id/learn` | Course Player | Vimeo iframe embed | Native Vimeo embed via `vimeoEmbedUrl` computed | WORKING | CourseLearn.spec.js |

### CourseLessons.vue (`/courses/:id/lessons`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/courses/:id/lessons` | Lessons | "+ Nova Aula" button | `showForm = true` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Lesson form submit | `saveLesson()` → `POST/PUT /api/v1/lessons/...` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Cancelar" form button | `resetForm()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Progresso dos Alunos" button | `router.push('/courses/${courseId}/progress')` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Move up button (▲) | `moveUp(index)` → `reorderLessons()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Move down button (▼) | `moveDown(index)` → `reorderLessons()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Enviar Vídeo" / "Trocar Vídeo" button | `manageVideo(lesson)` → opens video upload modal | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Remover Vídeo" button | `confirmRemoveVideo(lesson)` → ConfirmDialog → `doRemoveVideo()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Materiais" button | `manageMaterials(lesson)` → opens materials modal | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Editar" button | `editLesson(lesson)` → populates form | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Excluir" button | `confirmDeleteLesson(lesson)` → ConfirmDialog → `doDeleteLesson()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Video upload modal "Enviar" button | `uploadVideo()` → presign → PUT → upload-complete | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Video upload modal "Cancelar" button | `closeVideoModal()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Materials modal "Adicionar" button | `uploadMaterial()` → presign → PUT → POST material | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Materials modal "Fechar" button | `closeMaterialsModal()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | Material "Remover" button | `confirmDeleteMaterial(material)` → ConfirmDialog → `doDeleteMaterial()` | WORKING | CourseLessons.spec.js |
| ADMIN | `/courses/:id/lessons` | Lessons | "Tentar novamente" (load error) | `loadLessons()` | WORKING | CourseLessons.spec.js |

### CourseProgress.vue (`/courses/:id/progress`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/courses/:id/progress` | Progress | "Voltar para Aulas" button | `router.push('/courses/${courseId}/lessons')` | WORKING | CourseProgress.spec.js |
| ADMIN | `/courses/:id/progress` | Progress | "Tentar novamente" (load error) | `loadProgress()` | WORKING | CourseProgress.spec.js |

### Classes.vue (`/classes`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/classes` | Classes | "+ Nova Turma" button | `showForm = true` | WORKING | all-views.spec.js |
| ADMIN | `/classes` | Classes | Class form submit | `saveClass()` → `POST/PUT /api/v1/classes/` | WORKING | all-views.spec.js |
| ADMIN | `/classes` | Classes | "Cancelar" form button | `cancelForm()` | WORKING | all-views.spec.js |
| ADMIN | `/classes` | Classes | EAD link "Acessar" | `<a :href="cls.ead_link" target="_blank">` | WORKING | all-views.spec.js |
| ADMIN | `/classes` | Classes | "Editar" button | `editClass(cls)` → populates form | WORKING | all-views.spec.js |
| ADMIN | `/classes` | Classes | "Excluir" button | `confirmDelete(cls)` → ConfirmDialog → `doDelete()` | WORKING | all-views.spec.js |
| ADMIN | `/classes` | Classes | "Tentar novamente" (load error) | `loadClasses()` | WORKING | all-views.spec.js |

### Students.vue (`/students`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/students` | Students | "+ Novo Aluno" button | `showForm = true` | WORKING | all-views.spec.js |
| ADMIN | `/students` | Students | Student form submit | `saveStudent()` → `POST/PUT /api/v1/students/` | WORKING | all-views.spec.js |
| ADMIN | `/students` | Students | "Cancelar" form button | `showForm = false` | WORKING | all-views.spec.js |
| ADMIN | `/students` | Students | "Editar" button | `editStudent(student)` → populates form | WORKING | all-views.spec.js |
| ADMIN | `/students` | Students | "Deletar" button | `deleteStudent(student)` → ConfirmDialog → `doDelete()` | WORKING | all-views.spec.js |

### Enrollments.vue (`/enrollments`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/enrollments` | Enrollments | "+ Nova Matrícula" button | `showForm = true` | WORKING | Enrollments.spec.js |
| ADMIN | `/enrollments` | Enrollments | Enrollment form submit | `saveEnrollment()` → `POST/PUT /api/v1/enrollments/` | WORKING | Enrollments.spec.js |
| ADMIN | `/enrollments` | Enrollments | "Cancelar" form button | `showForm = false` | WORKING | Enrollments.spec.js |
| ADMIN | `/enrollments` | Enrollments | "Editar" button | `editEnrollment(enrollment)` → populates form | WORKING | Enrollments.spec.js |
| ADMIN | `/enrollments` | Enrollments | "Deletar" button | `deleteEnrollment(enrollment)` → ConfirmDialog → `doDelete()` | WORKING | Enrollments.spec.js |

### Payments.vue (`/payments`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/payments` | Payments | "+ Novo Pagamento" button | `showForm = true` | WORKING | all-views.spec.js |
| ADMIN | `/payments` | Payments | Payment form submit | `savePayment()` → `POST/PUT /api/v1/payments/` | WORKING | all-views.spec.js |
| ADMIN | `/payments` | Payments | "Cancelar" form button | `showForm = false` | WORKING | all-views.spec.js |
| ADMIN | `/payments` | Payments | "Editar" button | `editPayment(payment)` → populates form (edit sends only status) | WORKING | all-views.spec.js |
| ADMIN | `/payments` | Payments | "Deletar" button | `confirmDelete(payment)` → ConfirmDialog → `doDelete()` | WORKING | all-views.spec.js |

### Certificates.vue (`/certificates`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/certificates` | Certificates | "+ Novo Certificado" button | `showForm = true` | WORKING | all-views.spec.js |
| ADMIN | `/certificates` | Certificates | Generate certificate form submit | `saveCertificate()` → `POST /api/v1/certificates/` | WORKING | all-views.spec.js |
| ADMIN | `/certificates` | Certificates | "Cancelar" form button | `showForm = false` | WORKING | all-views.spec.js |
| ALL | `/certificates` | Certificates | "Validar" button | `validateCertificate()` → `POST /api/v1/certificates/validate` | WORKING | all-views.spec.js |
| ADMIN | `/certificates` | Certificates | "Deletar" button | `confirmDelete(cert)` → ConfirmDialog → `doDelete()` | WORKING | all-views.spec.js |

### WhiteLabelSettings.vue (`/settings/white-label`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ADMIN | `/settings/white-label` | White Label | Branding form submit | `handleSave()` → `updateTenantBranding()` → `tenantStore.refreshBranding()` | WORKING | WhiteLabelSettings.spec.js |
| ADMIN | `/settings/white-label` | White Label | Color picker inputs (primary/secondary/accent) | `v-model` bound to `form.*_color` | WORKING | WhiteLabelSettings.spec.js |
| ADMIN | `/settings/white-label` | White Label | Logo URL input with live preview | `<img :src="form.logo_url">` preview | WORKING | WhiteLabelSettings.spec.js |

### SuperAdmin.vue (`/super-admin`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| SUPER_ADMIN | `/super-admin` | Super Admin | Tab switcher (Parceiros/Tenants/Planos/Assinaturas) | `activeTab = tab` | WORKING | SuperAdmin.spec.js |
| SUPER_ADMIN | `/super-admin` | Super Admin | "Aprovar" partner lead button | `confirmApprove(lead)` → ConfirmDialog → `doApprove()` | WORKING | SuperAdmin.spec.js |
| SUPER_ADMIN | `/super-admin` | Super Admin | "Criar" plan button | `handleCreatePlan()` → `createPlan()` | WORKING | SuperAdmin.spec.js |
| SUPER_ADMIN | `/super-admin` | Super Admin | "Ativar" subscription button | `confirmActivate(s)` → ConfirmDialog → `doActivate()` | WORKING | SuperAdmin.spec.js |
| SUPER_ADMIN | `/super-admin` | Super Admin | "Suspender" subscription button | `confirmSuspend(s)` → ConfirmDialog → `doSuspend()` | WORKING | SuperAdmin.spec.js |
| SUPER_ADMIN | `/super-admin` | Super Admin | "Reativar" subscription button | `confirmActivate(s)` → ConfirmDialog → `doActivate()` | WORKING | SuperAdmin.spec.js |
| SUPER_ADMIN | `/super-admin` | Super Admin | "Renovar" subscription button | `handleRenew(s.id)` → `renewSubscription()` | WORKING | SuperAdmin.spec.js |

### DemoPayment.vue (`/demo/payment/:paymentId`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| AUTH | `/demo/payment/:paymentId` | Demo Payment | "Simular Pagamento Aprovado" button | `simulate('approve')` → `POST /api/v1/payments/demo/${id}/approve` | WORKING | DemoPayment.spec.js |
| AUTH | `/demo/payment/:paymentId` | Demo Payment | "Simular Pendente" button | `simulate('pending')` → `POST /api/v1/payments/demo/${id}/pending` | WORKING | DemoPayment.spec.js |
| AUTH | `/demo/payment/:paymentId` | Demo Payment | "Simular Rejeitado" button | `simulate('reject')` → `POST /api/v1/payments/demo/${id}/reject` | WORKING | DemoPayment.spec.js |
| AUTH | `/demo/payment/:paymentId` | Demo Payment | "Acessar Curso" link (after approval) | `/courses/${payment.course_id}/learn` | WORKING | DemoPayment.spec.js |

### Forbidden.vue (`/403`) and NotFound.vue (`/:pathMatch(.*)*`)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| PUBLIC | `/403` | Forbidden | "Voltar ao início" link | `getHomeRoute(authStore)` | WORKING | all-views.spec.js |
| PUBLIC | `/:pathMatch(.*)*` | NotFound | "Voltar ao início" link | `getHomeRoute(authStore)` | WORKING | NotFound.spec.js |

### AppNavbar.vue (global navigation)

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | HANDLER / DESTINATION | STATUS | TEST |
|------|-------|--------|----------------|----------------------|--------|------|
| ALL | * | Navbar | Logo link | `getHomeRoute(authStore)` | WORKING | AppNavbar.spec.js |
| STUDENT | * | Navbar | "Dashboard" flat link | `/dashboard` | WORKING | AppNavbar.spec.js |
| STUDENT | * | Navbar | "Catálogo" flat link | `/cursos` | WORKING | AppNavbar.spec.js |
| STUDENT | * | Navbar | "Certificados" flat link | `/certificates` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Dashboard" flat link | `/dashboard` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Gestão" dropdown group | Hover/click → `toggleDropdown()` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Cursos" dropdown item | `/courses` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Turmas" dropdown item | `/classes` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Alunos" dropdown item | `/students` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Matrículas" dropdown item | `/enrollments` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Pagamentos" dropdown item | `/payments` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Certificados" dropdown group | `/certificates` | WORKING | AppNavbar.spec.js |
| ADMIN | * | Navbar | "Personalização" dropdown group → "White Label" | `/settings/white-label` | WORKING | AppNavbar.spec.js |
| SUPER_ADMIN | * | Navbar | "Gestão Global" flat link | `/super-admin` | WORKING | AppNavbar.spec.js |
| AUTH | * | Navbar | "Sair" logout button | `handleLogout()` → `authStore.logout()` → `/login` | WORKING | AppNavbar.spec.js |
| PUBLIC | * | Navbar | "Cursos" link | `/cursos` | WORKING | AppNavbar.spec.js |
| PUBLIC | * | Navbar | "Validar certificado" link | `/validar-certificado` | WORKING | AppNavbar.spec.js |
| PUBLIC | * | Navbar | "Seja parceiro" link | `/seja-parceiro` | WORKING | AppNavbar.spec.js |
| PUBLIC | * | Navbar | "Login" link | `/login` | WORKING | AppNavbar.spec.js |
| PUBLIC | * | Navbar | "Cadastre-se" button | `/register` | WORKING | AppNavbar.spec.js |
| ALL | * | Navbar | Mobile hamburger toggle | `mobileMenuOpen = !mobileMenuOpen` | WORKING | AppNavbar.spec.js |

### Removed interactions

| ROLE | ROUTE | SCREEN | VISIBLE ACTION | STATUS | EXPLANATION |
|------|-------|--------|----------------|--------|-------------|
| STUDENT | — | — | "Meus Cursos" standalone nav link | REMOVED | Student "Meus Cursos" route was removed. Dashboard now shows enrolled courses directly. Catálogo (`/cursos`) shows the public catalog. No separate "Meus Cursos" route exists in the router. |

---

## Role Matrix

Which roles can access which routes. Based on `navigationGuard` meta flags and `getHomeRoute()` logic.

| ROUTE | PUBLIC | STUDENT | ADMIN | SUPER_ADMIN |
|-------|--------|---------|-------|-------------|
| `/` | ✅ | ✅ | ✅ | ✅ |
| `/login` | ✅ | ✅ | ✅ | ✅ |
| `/register` | ✅ | ✅ | ✅ | ✅ |
| `/seja-parceiro` | ✅ | ✅ | ✅ | ✅ |
| `/validar-certificado` | ✅ | ✅ | ✅ | ✅ |
| `/recuperar-senha` | ✅ | ✅ | ✅ | ✅ |
| `/redefinir-senha` | ✅ | ✅ | ✅ | ✅ |
| `/cursos` | ✅ | ✅ | ✅ | ✅ |
| `/cursos/:id` | ✅ | ✅ | ✅ | ✅ |
| `/403` | ✅ | ✅ | ✅ | ✅ |
| `/:pathMatch(.*)*` (404) | ✅ | ✅ | ✅ | ✅ |
| `/dashboard` | ❌ (redirect to /login) | ✅ | ✅ | ✅ |
| `/courses/:id/learn` | ❌ (redirect to /login) | ✅ | ✅ | ✅ |
| `/certificates` | ❌ (redirect to /login) | ✅ | ✅ | ✅ |
| `/demo/payment/:paymentId` | ❌ (redirect to /login) | ✅ | ✅ | ✅ |
| `/courses` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/courses/:id/lessons` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/courses/:id/progress` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/classes` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/students` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/enrollments` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/payments` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/settings/white-label` | ❌ | ❌ (redirect home) | ✅ | ✅ |
| `/super-admin` | ❌ | ❌ (redirect home) | ❌ (redirect home) | ✅ |

**Home route resolution** (`getHomeRoute`):
- PUBLIC → `/`
- STUDENT → `/dashboard`
- ADMIN → `/dashboard`
- SUPER_ADMIN → `/super-admin`

---

## Destructive Actions

All destructive actions and their confirmation dialog implementation.

| Action | View | Trigger | Confirmation Dialog | API Call | Notes |
|--------|------|---------|---------------------|----------|-------|
| Delete course | Courses.vue | "Excluir" button → `confirmDelete(course)` | `ConfirmDialog` with `danger=true`, dynamic message `Excluir o curso "${name}"? Esta ação não pode ser desfeita.`, `loading` state on confirm | `DELETE /api/v1/courses/${id}` | Toast on success; toast on error |
| Delete class (turma) | Classes.vue | "Excluir" button → `confirmDelete(cls)` | `ConfirmDialog` with `danger=true`, message `Excluir a turma de "${name}"? Esta ação não pode ser desfeita.` | `DELETE /api/v1/classes/${id}` | Toast on success/error |
| Delete student | Students.vue | "Deletar" button → `deleteStudent(student)` | `ConfirmDialog` with `:danger="true"`, message `Excluir o aluno "${name}"? Esta ação não pode ser desfeita.` | `DELETE /api/v1/students/${id}` | Toast on error only |
| Delete enrollment | Enrollments.vue | "Deletar" button → `deleteEnrollment(enrollment)` | `ConfirmDialog` with `:danger="true"`, message `Excluir a matrícula de "${name}"? Esta ação não pode ser desfeita.` | `DELETE /api/v1/enrollments/${id}` | Toast on error only |
| Delete payment | Payments.vue | "Deletar" button → `confirmDelete(payment)` | `ConfirmDialog` with `:danger="true"`, message `Excluir o pagamento de "${name}"? Esta ação não pode ser desfeita.` | `DELETE /api/v1/payments/${id}` | Toast on error only |
| Delete certificate | Certificates.vue | "Deletar" button → `confirmDelete(cert)` | `ConfirmDialog` with `:danger="true"`, message `Excluir o certificado "${number}"? Esta ação não pode ser desfeita.` | `DELETE /api/v1/certificates/${id}` | Toast on error only |
| Delete lesson | CourseLessons.vue | "Excluir" button → `confirmDeleteLesson(lesson)` | `ConfirmDialog` with `danger=true`, message `Excluir a aula "${title}"? Esta ação não pode ser desfeita.` | `DELETE /api/v1/lessons/courses/${courseId}/lessons/${id}` | Handles 409 (progress exists) with specific error message |
| Remove video | CourseLessons.vue | "Remover Vídeo" button → `confirmRemoveVideo(lesson)` | `ConfirmDialog` with `danger=true`, message `Remover o vídeo da aula "${title}"? O progresso dos alunos não será afetado.` | `POST /api/v1/lessons/${id}/remove-video` | Toast on success/error |
| Delete material | CourseLessons.vue | "Remover" button (in materials modal) → `confirmDeleteMaterial(material)` | `ConfirmDialog` with `danger=true`, message `Remover o material "${title}"?` | `DELETE /api/v1/lessons/${lessonId}/materials/${id}` | Toast on success/error |
| Suspend subscription | SuperAdmin.vue | "Suspender" button → `confirmSuspend(s)` | `ConfirmDialog` with `danger=true`, message `Suspender a assinatura do tenant "${name}"? O acesso do tenant será bloqueado.` | `suspendSubscription(id)` | Toast on success |
| Approve partner lead | SuperAdmin.vue | "Aprovar" button → `confirmApprove(lead)` | `ConfirmDialog` (not danger), message `Aprovar o parceiro "${name}"? Isso criará um novo tenant e usuário administrador.` | `approvePartnerLead(id)` | Creates tenant + admin user; shows DEMO result panel |
| Activate subscription | SuperAdmin.vue | "Ativar" / "Reativar" button → `confirmActivate(s)` | `ConfirmDialog` (not danger), message `Ativar a assinatura do tenant "${name}"? O acesso será restaurado.` | `activateSubscription(id)` | Toast on success |
| Renovar subscription | SuperAdmin.vue | "Renovar" button → `handleRenew(id)` | No confirmation dialog — direct action | `renewSubscription(id)` | Toast on success/error |

**Confirmation dialog implementation details:**
All destructive actions use the `ConfirmDialog` component (`web/src/components/ConfirmDialog.vue`), which wraps `AppModal`. Key behaviors:
- `loading` prop disables both Cancel and Confirm buttons during async operation.
- `closable` and `closeOnBackdrop` are set to `!loading` — modal cannot be dismissed by backdrop click or close button while operation is in progress.
- `danger` prop renders the confirm button in red (`bg-red-600`).
- Cancel button emits `cancel` and `close` events and closes the modal (unless `loading`).

---

## Modals/Dialogs

| Modal/Dialog | Component | Used In | Focus Management | Escape | Backdrop | Loading State |
|--------------|-----------|---------|------------------|--------|----------|---------------|
| AppModal (base) | `AppModal.vue` | CourseLessons (video upload, materials) | ✅ Stores `previouslyFocused` on open; focuses close button (or dialog container) on open; restores focus on close. Tab/Shift+Tab trapped within modal via `handleTab()`. | ✅ `@keydown.esc` → `handleEscape()` → closes if `closable` | ✅ `@click` on backdrop → `handleBackdropClick()` → closes if `closeOnBackdrop` | N/A (loading handled by parent) |
| ConfirmDialog | `ConfirmDialog.vue` (wraps AppModal) | Courses, Classes, Students, Enrollments, Payments, Certificates, CourseLessons, SuperAdmin | ✅ Inherits AppModal focus trap and restore | ✅ Disabled when `loading=true` (`:closable="!loading"`) | ✅ Disabled when `loading=true` (`:close-on-backdrop="!loading"`) | ✅ `loading` prop → buttons disabled, confirm text changes to "Processando..." |
| Video Upload Modal | `AppModal` in CourseLessons.vue | CourseLessons | ✅ AppModal focus management | ✅ Disabled during upload (`:closable="!videoModal.uploading"`) | ✅ Disabled during upload (`:close-on-backdrop="!videoModal.uploading"`) | ✅ `uploading` state → progress %, buttons disabled, text "Enviando..." |
| Materials Modal | `AppModal` in CourseLessons.vue | CourseLessons | ✅ AppModal focus management | ✅ Closable (no upload-in-progress lock on close) | ✅ Closable | ✅ `uploadingMaterial` state → "Adicionar" button disabled, text "Enviando..." |

**AppModal accessibility attributes:**
- `role="dialog"` on overlay
- `aria-modal="true"` on overlay
- `:aria-labelledby="titleId"` — dynamically generated unique ID linked to `<h2>` title
- `role="document"` on dialog content container
- `tabindex="-1"` on dialog container (focusable for programmatic focus)
- Close button has `:aria-label="'Fechar: ' + title"`
- Body scroll locked (`document.body.style.overflow = 'hidden'`) while modal open
- Focus restored on unmount via `onBeforeUnmount` cleanup

**Transition:** AppModal uses Vue `<Transition name="modal">` with opacity fade (0.2s ease).

---

## Loading/Error/Empty/Success States

For each view, which states are implemented.

| View | Loading | Error | Empty | Success |
|------|---------|-------|-------|---------|
| Home.vue | ✅ `loading` ref → "Carregando cursos..." text | ✅ Silent catch → `courses = []` → falls to empty state | ✅ "Nenhum curso disponível no momento." | ✅ Course grid rendered |
| Login.vue | ✅ `loading` ref → button text "Entrando..." | ✅ `error` ref → red alert box (distinguishes 401, network, 500) | N/A | ✅ Redirect to safe route |
| Register.vue | ✅ `loading` ref → button text "Cadastrando..." | ✅ `error` ref → red alert box | N/A | ✅ `success` ref → green alert "Cadastro realizado com sucesso!" + auto-redirect after 2s |
| Partner.vue | ✅ `loading` ref → button text "Enviando..." | ✅ `error` ref → `AppAlert type="error"` | N/A | ✅ `submitted` ref → success screen with checkmark icon + "Enviar nova proposta" reset button |
| ValidateCertificate.vue | ✅ `loading` ref → spinner SVG + "Verificando..." text | ✅ `serverError` ref → `AppAlert type="error"` (distinguishes 404/400 from network) | N/A | ✅ Valid → green box with cert details; Invalid → red box "Código não encontrado" |
| ForgotPassword.vue | ✅ `loading` ref → button text "Enviando..." | ✅ `error` ref → `AppAlert type="error"` | N/A | ✅ `submitted` ref → success screen (generic message, doesn't reveal if email exists) |
| ResetPassword.vue | ✅ `loading` ref → button text "Redefinindo..." | ✅ `error` ref → `AppAlert type="error"` (distinguishes 400 token invalid, network, generic) | N/A | ✅ `success` ref → green checkmark + "Ir para o login" link |
| Dashboard.vue | ✅ `statsLoading` → "Carregando estatísticas..." (admin); `loadingEnrollments` → "Carregando cursos..." (student) | ✅ `statsError` → red box with "Tentar novamente" retry button; `enrollmentsError` → red text | ✅ Student enrollments empty → "Você não está matriculado em nenhum curso ainda." + "Explorar cursos →" link | ✅ Stats grid / enrollment list rendered |
| Courses.vue | ✅ `LoadingState` component ("Carregando cursos...") | ✅ `AppAlert type="error" closable` + "Tentar novamente" retry | ✅ `EmptyState` "Nenhum curso cadastrado" | ✅ Course card grid + toast on create/update/delete |
| CourseDetail.vue | ✅ `loading` ref → "Carregando curso..." text | ✅ `error` ref → red alert box | N/A | ✅ Course detail rendered; `enrollmentLoading` → "Carregando matrícula..." |
| CourseLearn.vue | ✅ Implicit (lessons load on mount) | ✅ `notEnrolled` → "Acesso restrito" message + "Ver cursos" link; toast on video load error | ✅ "Selecione uma aula para começar" (no lesson selected); "Nenhuma aula disponível." (empty lessons) | ✅ Video player + progress bar |
| CourseLessons.vue | ✅ `LoadingState` ("Carregando aulas...") | ✅ `AppAlert type="error" closable` + "Tentar novamente" retry | ✅ `EmptyState` "Nenhuma aula cadastrada" | ✅ Lesson list + toast on all CRUD operations |
| CourseProgress.vue | ✅ `LoadingState` ("Carregando progresso...") | ✅ `AppAlert type="error" closable` + "Tentar novamente" retry | ✅ `EmptyState` "Nenhum aluno matriculado" | ✅ Progress table with per-student progress bars |
| Classes.vue | ✅ `LoadingState` ("Carregando turmas...") | ✅ `AppAlert type="error" closable` + "Tentar novamente" retry | ✅ `EmptyState` "Nenhuma turma disponível" | ✅ Class card grid + toast on create/update/delete |
| Students.vue | ✅ `LoadingState` ("Carregando alunos...") | ✅ `AppAlert type="error" closable` | ✅ `EmptyState` "Nenhum aluno cadastrado" | ✅ Student table + toast on create (shows temp password) |
| Enrollments.vue | ✅ `LoadingState` ("Carregando matrículas...") | ✅ `AppAlert type="error" closable` | ✅ `EmptyState` "Nenhuma matrícula cadastrada" | ✅ Enrollment table (no success toast on save) |
| Payments.vue | ✅ `LoadingState` ("Carregando pagamentos...") | ✅ `AppAlert type="error" closable` | ✅ `EmptyState` "Nenhum pagamento registrado" | ✅ Payment table (no success toast on save) |
| Certificates.vue | ✅ `LoadingState` ("Carregando certificados...") | ✅ `AppAlert type="error" closable` | ✅ `EmptyState` "Nenhum certificado emitido" | ✅ Certificate card grid + validation result display |
| WhiteLabelSettings.vue | N/A (form only) | ✅ `AppAlert type="error" closable` | N/A | ✅ `AppAlert type="success" closable` "Branding atualizado com sucesso!" |
| SuperAdmin.vue | ✅ `LoadingState` ("Carregando dados...") | ✅ `AppAlert type="error" closable` | ✅ Inline table empty rows "Nenhum lead" / "Nenhum tenant" / "Nenhuma assinatura" | ✅ Toast on approve/create plan/suspend/activate/renew |
| DemoPayment.vue | ✅ `loading` ref → "Carregando..." text | ✅ `error` ref → red text | N/A | ✅ Payment details + simulation buttons + "Acessar Curso" link after approval |
| Forbidden.vue | N/A | N/A | N/A | N/A |
| NotFound.vue | N/A | N/A | N/A | N/A |

**Shared state components:**
- `LoadingState.vue` — spinner SVG + message, `role="status"`, `aria-live="polite"`.
- `EmptyState.vue` — icon + title + description + optional slot for action button.
- `AppAlert.vue` — `role="alert"`, type-based color (error/success/warning/info), optional closable button with `aria-label="Fechar alerta"`.

---

## Responsive Audit

| Feature | Implementation | Breakpoints |
|---------|---------------|-------------|
| Mobile hamburger menu | `AppNavbar.vue` — hamburger button visible on `md:hidden`, desktop nav hidden on `hidden md:flex`. Mobile menu panel toggles `mobileMenuOpen`. Auto-closes on route change via `watch(() => route.path)`. | `<768px` (md breakpoint): hamburger; `≥768px`: desktop nav |
| Home.vue header nav | Inline flex nav, no hamburger — links may wrap on very small screens. Not ideal for <360px but functional. | No explicit breakpoint |
| Dashboard stats grid | `grid grid-cols-1 md:grid-cols-4` | `<768px`: 1 column; `≥768px`: 4 columns |
| Dashboard content grid | `grid grid-cols-1 md:grid-cols-3` | `<768px`: 1 column; `≥768px`: 3 columns |
| Courses card grid | `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3` | `<768px`: 1 col; `≥768px`: 2 cols; `≥1024px`: 3 cols |
| Home course vitrine grid | `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3` | `<768px`: 1 col; `≥768px`: 2 cols; `≥1024px`: 3 cols |
| Home features grid | `grid grid-cols-1 md:grid-cols-3` | `<768px`: 1 col; `≥768px`: 3 cols |
| Classes card grid | `grid grid-cols-1 md:grid-cols-2` | `<768px`: 1 col; `≥768px`: 2 cols |
| Certificates card grid | `grid grid-cols-1 md:grid-cols-2` | `<768px`: 1 col; `≥768px`: 2 cols |
| CourseLearn layout | `grid grid-cols-1 md:grid-cols-3` — sidebar 1 col, player 2 cols on desktop | `<768px`: stacked; `≥768px`: sidebar + player |
| CourseDetail layout | `flex flex-col md:flex-row` — info + sidebar pricing card | `<768px`: stacked; `≥768px`: side-by-side |
| Students table | `overflow-x-auto` wrapper around `<table>` | Horizontal scroll on small screens |
| Enrollments table | `overflow-x-auto` wrapper around `<table>` | Horizontal scroll on small screens |
| Payments table | `overflow-x-auto` wrapper around `<table>` | Horizontal scroll on small screens |
| CourseProgress table | `overflow-x-auto` wrapper around `<table>` | Horizontal scroll on small screens |
| SuperAdmin tables | `overflow-hidden` on container, `min-w-full` on table | Table may overflow on very small screens (no `overflow-x-auto` wrapper) |
| Forms (Courses, Classes, Students, etc.) | `grid grid-cols-1 md:grid-cols-2` | `<768px`: 1 col; `≥768px`: 2 cols |
| WhiteLabelSettings color inputs | `grid grid-cols-1 sm:grid-cols-3` | `<640px`: 1 col; `≥640px`: 3 cols |
| Container max-width | `max-w-7xl mx-auto` with `px-4 sm:px-6 lg:px-8` | Responsive padding |
| AppModal | `max-h-[90vh] overflow-y-auto`, `p-4` on overlay | Scrolls within viewport on small screens |

**Known responsive gaps:**
- SuperAdmin tables lack `overflow-x-auto` wrapper — may cause horizontal page overflow on narrow viewports.
- Home.vue header navigation has no mobile hamburger — on very small screens, the inline links may crowd.

---

## Accessibility Audit

| Category | Implementation | Files |
|----------|---------------|-------|
| `aria-expanded` on dropdowns | ✅ AppNavbar desktop dropdown buttons: `:aria-expanded="openDropdown === group.label"` + `:aria-controls="'dropdown-' + group.testid"`. Mobile hamburger: `:aria-expanded="mobileMenuOpen"` + `aria-controls="mobile-menu-panel"`. | AppNavbar.vue:45-46, 113-114 |
| `aria-label` on icon buttons | ✅ AppModal close button: `:aria-label="'Fechar: ' + title"`. Toast dismiss: `aria-label="Fechar notificação"`. AppAlert close: `aria-label="Fechar alerta"`. AppNavbar hamburger: `aria-label="Menu"`. CourseLessons move up/down: `:aria-label="Mover aula ${title} para cima/baixo"`. | AppModal.vue:36, Toast.vue:29, AppAlert.vue:29, AppNavbar.vue:115, CourseLessons.vue:143,151 |
| `role="dialog"` on modals | ✅ AppModal overlay: `role="dialog"` + `aria-modal="true"` + `:aria-labelledby="titleId"`. Dialog content: `role="document"`. | AppModal.vue:9-11,23 |
| `role="alert"` on toasts | ✅ Toast component: `role="alert"`. AppAlert component: `role="alert"`. | Toast.vue:8, AppAlert.vue:6 |
| `role="status"` on loading | ✅ LoadingState: `role="status"` + `aria-live="polite"`. | LoadingState.vue:6-7 |
| `role="tablist"` / `role="tab"` | ✅ SuperAdmin tab bar: `role="tablist"` on container, `role="tab"` + `:aria-selected` on each tab button. | SuperAdmin.vue:14,27 |
| Focus management (modals) | ✅ AppModal: stores `previouslyFocused` → focuses close button on open → restores focus on close. Tab/Shift+Tab trapped via `handleTab()`. Body scroll locked. Cleanup on unmount. | AppModal.vue:96-187 |
| Focus management (toasts) | Toast auto-dismisses after `duration` (default 4000ms). No focus trap (non-blocking). Manual dismiss button. | Toast.vue:82-86 |
| Keyboard navigation (Escape) | ✅ AppModal: `@keydown.esc="handleEscape"` → closes if `closable`. ConfirmDialog: Escape disabled when `loading`. | AppModal.vue:7,119-121 |
| Keyboard navigation (Tab trap) | ✅ AppModal: `@keydown.tab="handleTab"` — queries all focusable elements, wraps Tab from last→first and Shift+Tab from first→last. | AppModal.vue:8,124-152 |
| Form labels | ✅ AppInput: `<label>` with `v-if="label"`, required indicator `*` in red. Partner/ForgotPassword/ResetPassword use explicit `<label>` elements. | AppInput.vue:3-6 |
| Form validation errors | ✅ AppInput: `<p v-if="error" class="text-sm text-red-600">`. Register: inline `passwordError` computed. | AppInput.vue:22, Register.vue:119-124 |
| `alt` text on images | ✅ Logo images: `:alt="tenantStore.name"`. WhiteLabelSettings preview: `alt="Preview do logo"`. | Home.vue:7, AppNavbar.vue:5, Login.vue:7,19 |
| `target="_blank"` with `rel="noopener"` | ✅ Classes EAD link: `target="_blank" rel="noopener noreferrer"`. | Classes.vue:132 |
| Video player accessibility | HTML5 `<video controls>` — native keyboard accessible. YouTube/Vimeo iframes have `allowfullscreen`. No custom captions/track elements. | CourseLearn.vue:78-108 |
| Color contrast | Primary color is tenant-configurable via CSS variables. Default `#0056b3` on white meets WCAG AA for normal text. | tenant.js, tailwind config |

**Known accessibility gaps:**
- CourseLearn lesson sidebar buttons lack `aria-current` for the selected lesson.
- SuperAdmin "Renovar" button has no confirmation dialog (direct action).
- Toast notifications do not move focus — screen readers will announce via `role="alert"` but keyboard users may not discover them.
- No skip-to-content link on any page.
- Tables (Students, Enrollments, Payments, CourseProgress, SuperAdmin) lack `<caption>` elements.

---

## White Label Isolation

**No hardcoded WR emails, WhatsApp numbers, or brand references remain in the frontend.**

A grep of `web/src/` for `whatsapp`, `WhatsApp`, `@wr.`, `wr.com`, `contato@wr`, phone patterns (`5511`, `55\d{2}\d{4}\d{4}`), `WR Cursos`, `WR Treinamentos`, `WR Academia`, `wrcursos` returned **zero matches**.

**Tenant branding is provided dynamically via the tenant store** (`web/src/stores/tenant.js`):

| Branding Field | Store Property | Applied Where |
|----------------|----------------|----------------|
| Platform name | `tenantStore.name` | AppNavbar logo fallback, Home header/footer/hero, Login header, Register header, CourseDetail footer, ValidateCertificate footer, ForgotPassword footer, ResetPassword footer, `document.title` |
| Logo URL | `tenantStore.logo_url` | AppNavbar, Home header/footer, Login header/card, Register header/card |
| Logo white URL | `tenantStore.logo_white_url` | Available in store (for dark backgrounds) |
| Favicon URL | `tenantStore.favicon_url` | Dynamically injected into `<link rel="icon">` via `applyFavicon()` |
| Primary color | `tenantStore.primary_color` | CSS variable `--color-primary` via `applyColors()` |
| Secondary color | `tenantStore.secondary_color` | CSS variable `--color-secondary` |
| Accent color | `tenantStore.accent_color` | CSS variable `--color-accent` |

**Tenant slug resolution** (`web/src/utils/tenantSlug.js`):
1. `VITE_TENANT_SLUG` build-time override (highest priority).
2. Hostname-derived slug (first subdomain segment, e.g. `alfa.example.com` → `alfa`).
3. `"wr"` fallback for localhost / bare domains.

**API tenant header** (`web/src/api/client.js`):
- Every API request includes `X-Tenant-Slug: ${TENANT_SLUG}` header.
- Backend uses this header to scope all data queries to the correct tenant.

**Branding fetch flow:**
1. `TENANT_SLUG` is computed once at module load.
2. `fetchTenantBranding(slug)` calls `GET /api/v1/tenants/branding?slug=...`.
3. Store populates `name`, `logo_url`, `logo_white_url`, `favicon_url`, `primary_color`, `secondary_color`, `accent_color`.
4. `applyColors()` sets CSS custom properties on `document.documentElement`.
5. `applyFavicon()` injects/updates `<link rel="icon">`.
6. `document.title` is set to the tenant name.

**Fallback** (if branding API fails): `name = 'Plataforma de Cursos'`, `primary_color = '#0056b3'`, `secondary_color = '#1a1a1a'`, `accent_color = '#ff6b35'`. No WR-specific fallback.

---

## WR Browser Validation

When browsing the WR tenant (slug `wr`, e.g. `localhost` or `wr.example.com`):

1. **Tenant slug resolution:** `TENANT_SLUG = "wr"` (default for localhost/dev hosts, or hostname-derived for `wr.*` domains).
2. **API header:** `X-Tenant-Slug: wr` sent on every request.
3. **Branding fetch:** `GET /api/v1/tenants/branding?slug=wr` returns WR-specific branding.
4. **Tenant store populates:** WR platform name, WR logo URL, WR colors.
5. **Rendering:**
   - AppNavbar shows WR logo (or WR name as text fallback).
   - Home.vue hero says "Plataforma de cursos da {WR name}."
   - Home.vue footer shows "{WR name} — Treinamentos com certificação".
   - Login/Register headers show WR logo and name.
   - `document.title` = WR platform name.
   - Favicon = WR favicon.
   - Primary/secondary/accent colors = WR colors via CSS variables.
6. **Data isolation:** All course/class/student/enrollment/payment/certificate API calls are scoped to WR tenant by the backend via the `X-Tenant-Slug` header. WR users see only WR data.

**E2E test coverage:** `web/e2e/integration/integration-white-label.spec.js` tests A–D prove:
- A. WR storefront shows WR branding + WR course, NOT Alfa.
- B. (Alfa storefront — see next section.)
- C. WR admin sees WR data, not Alfa.
- D. (Alfa admin — see next section.)
- E. JWT cross-tenant: WR→Alfa = 403, Alfa→WR = 403.

---

## Alfa Browser Validation

When browsing the Alfa tenant (slug `alfa`, e.g. `alfa.example.com` or `VITE_TENANT_SLUG=alfa`):

1. **Tenant slug resolution:** `TENANT_SLUG = "alfa"` (hostname-derived from `alfa.*` subdomain, or `VITE_TENANT_SLUG` override).
2. **API header:** `X-Tenant-Slug: alfa` sent on every request.
3. **Branding fetch:** `GET /api/v1/tenants/branding?slug=alfa` returns Alfa-specific branding (e.g. "Alfa Academy", Alfa logo, Alfa colors).
4. **Tenant store populates:** Alfa platform name, Alfa logo URL, Alfa colors.
5. **Rendering:**
   - AppNavbar shows Alfa logo (or Alfa name as text fallback).
   - Home.vue hero says "Plataforma de cursos da {Alfa name}."
   - All headers/footers show Alfa branding.
   - `document.title` = Alfa platform name.
   - Favicon = Alfa favicon.
   - Primary/secondary/accent colors = Alfa colors.
6. **Data isolation:** All API calls scoped to Alfa tenant. Alfa users see only Alfa courses, classes, students, etc.
7. **No cross-tenant leakage:**
   - JWT tokens are tenant-scoped — a WR token used against Alfa API returns 403.
   - `X-Tenant-Slug` header determines data scope; backend enforces tenant isolation.
   - Frontend has no hardcoded tenant references — all branding comes from the tenant store.

**E2E test coverage:** `web/e2e/integration/integration-white-label.spec.js` tests B, D, F, K prove:
- B. Alfa storefront shows Alfa branding + Alfa course, NOT WR.
- D. Alfa admin sees Alfa data, not WR.
- F. Alfa branding change persisted + rendered.
- K. Alfa certificate PDF contains "Alfa Academy".

**Two-tenant test topology:**
- WR frontend: `:4173` with `VITE_TENANT_SLUG=wr`
- Alfa frontend: `:4174` with `VITE_TENANT_SLUG=alfa`
- Shared backend: `:8000` with PostgreSQL

---

## Backend-Capability Gaps

Features that have frontend UI but limited or no backend support:

| Feature | Frontend UI | Backend Gap |
|---------|-------------|-------------|
| Profile editing | Dashboard.vue shows "Meu Perfil" card with role, name, email (read-only). No edit form exists. | No `PUT /api/v1/auth/me` or profile update endpoint. Profile editing is deliberately not implemented. |
| Password recovery email | ForgotPassword.vue sends `POST /api/v1/auth/forgot-password` and shows success message. | Backend returns `reset_token` in the response body, but **only in dev mode**. In production, no email is sent — the token is returned in the API response but the frontend does not display it (fail-closed). Email sending infrastructure is not implemented. |
| Payment processing | CourseDetail.vue "Comprar agora" → `purchaseCourse()` → `createCheckout()` → redirect to `checkout_url`. DemoPayment.vue simulates approve/pending/reject. | Payment is demo/simulation mode. `MERCADO_PAGO_MOCK_MODE=true` on backend. No real payment gateway integration in production. The checkout URL redirects to the demo payment simulator, not a real gateway. |
| Certificate PDF download | Certificates.vue lists certificates with validation codes. No download button exists. | Backend can generate PDF (tested in e2e test K), but frontend has no download link/button. PDF generation is backend-only. |
| Student self-enrollment | Students can browse catalog and click "Comprar agora" which creates a pending enrollment + payment. | No direct self-enrollment without payment. Admin can create enrollments manually via Enrollments.vue. |
| Lesson video upload progress | CourseLessons video upload modal shows progress %. | Progress is simulated (jumps to 90% after presign, 100% after complete). No real upload progress tracking via XHR `progress` event — uses `fetch()` which doesn't support progress callbacks. |
| Subscription renewal billing | SuperAdmin "Renovar" button calls `renewSubscription()`. | No real billing cycle enforcement. Renewal is a backend status change only. |
| Partner lead notification | Partner.vue submits lead to backend. | No email notification to WR team when a lead is submitted. Lead is stored and visible in SuperAdmin panel only. |

---

## Intentional Product Limitations

Features deliberately not implemented in this phase:

| Limitation | Details |
|------------|---------|
| Profile editing | Dashboard shows a "Meu Perfil" info card (role, name, email) with no edit button or form. Users cannot change their name, email, or password from the dashboard. Password reset is available via the forgot/reset password flow. |
| Student "Meus Cursos" removed | The standalone "Meus Cursos" route was removed. The Dashboard now shows enrolled courses directly in a "Meus Cursos" card (student role). The public catalog is accessible via "Catálogo" (`/cursos`) in the navbar. There is no separate `/my-courses` route. |
| Payment is demo/simulation mode | All payments go through `DemoPayment.vue` (`/demo/payment/:paymentId`). The "Comprar agora" flow creates a real enrollment + payment record but redirects to the demo simulator, not a real payment gateway. `MERCADO_PAGO_MOCK_MODE=true` on the backend. The demo simulator has buttons for "Aprovado", "Pendente", and "Rejeitado". |
| Password reset token only exposed in DEV | `ForgotPassword.vue` only displays the raw reset token when `import.meta.env.DEV && import.meta.env.VITE_ALLOW_DEV_RESET_TOKEN === 'true'`. This is fail-closed: production, staging, and preview builds never display the token even if the backend accidentally returns it. In production, the token would need to be delivered via email (not yet implemented). |
| No certificate PDF download in frontend | Certificates.vue lists certificates but has no download button. PDF generation exists on the backend (proven by e2e test K) but is not surfaced in the UI. |
| No real email sending | Forgot password, partner lead notifications, and student welcome emails are not sent. The backend stores data but does not send emails. |
| No lesson reordering drag-and-drop | CourseLessons uses ▲/▼ buttons for reordering, not drag-and-drop. Functional but not a modern DnD UX. |
| No video upload progress bar | Upload progress is simulated (0% → 90% → 100%), not real-time. Uses `fetch()` which lacks progress events. |
| SuperAdmin "Renovar" has no confirmation | The renew subscription action is executed directly without a ConfirmDialog, unlike suspend/activate which do have confirmation. |

---

## Security Maintenance Backlog

**npm dependency vulnerabilities** are reported during CI `npm install` runs. These are **not addressed in this UI/UX PR** and should be tracked separately.

- Dependency audit reports are generated by `npm audit` during CI.
- See `docs/DEPENDENCY_AUDIT.md` for the existing dependency audit documentation.
- Vulnerability remediation (via `npm update`, `npm audit fix`, or targeted upgrades) should be tracked as a separate engineering task, not bundled with UI/UX changes.
- This PR focuses on UI/UX correctness: route inventory, interaction inventory, accessibility, responsive behavior, white-label isolation, and state management. No dependency versions were changed.

---

*Document generated from a static read of `web/src/` — router, views, components, stores, utils, and composables. All file paths and line references are accurate as of the current codebase state.*
