<template>
  <svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8" aria-hidden="true">
    <path stroke-linecap="round" stroke-linejoin="round" :d="path" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ name: { type: String, required: true } })
const ICONS = {
  home: 'M3 11.5 12 4l9 7.5M5.5 10v9.5h5v-5h3v5h5V10',
  catalog: 'M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21V5.5Zm16 0A2.5 2.5 0 0 0 17.5 3H13v16h4.5A2.5 2.5 0 0 1 20 21V5.5Z',
  cert: 'm8.5 12.5 2.2 2.2 4.8-5M12 2.8l2.1 1.5 2.6-.1.7 2.5 2.1 1.5-.9 2.4.9 2.4-2.1 1.5-.7 2.5-2.6-.1L12 18.4l-2.1-1.5-2.6.1-.7-2.5L4.5 13l.9-2.4-.9-2.4 2.1-1.5.7-2.5 2.6.1L12 2.8ZM9 18.2 8 22l4-2 4 2-1-3.8',
  pulse: 'M3 12h4l2.2-5.5 4.2 11 2.2-5.5H21',
  layers: 'm12 3 9 5-9 5-9-5 9-5Zm-7.5 9.5L12 17l7.5-4.5M4.5 17 12 21l7.5-4',
  calendar: 'M6 2v3m12-3v3M3.5 8h17M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  building: 'M4 21V5l8-3v19M4 9h8m-8 4h8m-8 4h8m3-9h5v13m-5-9h5m-5 4h5',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m7-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8-1a4 4 0 0 1 4 4v2m-4-13a4 4 0 0 1 0 7',
  clipboard: 'M9 5h6M9 3h6a1 1 0 0 1 1 1v2H8V4a1 1 0 0 1 1-1ZM6 5H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1M8 12h8m-8 4h5',
  card: 'M3 7h18M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm2 11h4',
  briefcase: 'M9 6V4h6v2m-11 0h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Zm-2 6c5 2 15 2 20 0m-11 0v2h2v-2',
  chart: 'M4 20V10m6 10V4m6 16v-7m5 7H2',
  shield: 'M12 2 20 5v6c0 5-3.2 8.5-8 11-4.8-2.5-8-6-8-11V5l8-3Zm-3 9 2 2 4-4',
  settings: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7.4-3.5 2-1.2-2-3.5-2.3.7a7 7 0 0 0-1.6-.9L15 4.7h-4L10.5 7a7 7 0 0 0-1.6.9l-2.3-.7-2 3.5 2 1.2v1.9l-2 1.2 2 3.5 2.3-.7a7 7 0 0 0 1.6.9l.5 2.3h4l.5-2.3a7 7 0 0 0 1.6-.9l2.3.7 2-3.5-2-1.2V12Z',
  palette: 'M12 3a9 9 0 0 0 0 18h1.5a1.5 1.5 0 0 0 0-3H12a2 2 0 0 1 0-4h2.5A6.5 6.5 0 0 0 21 7.5C21 5 17 3 12 3ZM7 9h.01M10 6h.01M15 6h.01M18 9h.01',
  globe: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0 0c2.5-2.7 3.8-6 3.8-10S14.5 4.7 12 2c-2.5 2.7-3.8 6-3.8 10S9.5 19.3 12 22ZM2.5 9h19m-19 6h19',
  search: 'm21 21-4.4-4.4m2.4-5.1a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z',
  bell: 'M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 12h4',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  logout: 'M10 17l5-5-5-5m5 5H3m12-8h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4',
}
const path = computed(() => ICONS[props.name] || ICONS.home)
</script>
