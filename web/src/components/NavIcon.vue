<template>
  <svg
    class="h-5 w-5 shrink-0"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    stroke-width="1.8"
    aria-hidden="true"
  >
    <path stroke-linecap="round" stroke-linejoin="round" :d="path" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
})

const ICONS = {
  home: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  catalog: 'M12 6.253v13m0-13C10.02 5.293 7.731 4.5 5.25 4.5c-1.496 0-2.906.27-4.198.75v13m0 0A8.965 8.965 0 015.25 18c2.481 0 4.77.793 6.75 2.253m0-13C14.98 5.293 17.269 4.5 19.75 4.5c1.496 0 2.906.27 4.198.75v13m0 0A8.965 8.965 0 0019.75 18c-2.481 0-4.77.793-6.75 2.253',
  cert: 'M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z',
}

const path = computed(() => ICONS[props.name] || ICONS.home)
</script>
