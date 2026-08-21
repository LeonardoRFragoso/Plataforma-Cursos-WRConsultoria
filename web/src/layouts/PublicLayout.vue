<template>
  <div data-testid="public-layout" class="public-layout">
    <slot />
  </div>
</template>

<script setup>
/**
 * PublicLayout — centered, marketing-friendly shell for unauthenticated pages.
 *
 * Public pages (Home, Catalog, CourseDetail, Login, Register, Forgot/Reset
 * Password, Partner, ValidateCertificate, 403/404) keep their own bespoke
 * centered layouts. This component is a thin, non-imposing wrapper that acts
 * as the explicit layout marker for the public route contract and guarantees
 * NO authenticated application shell (sidebar/topbar) is rendered.
 */
</script>
