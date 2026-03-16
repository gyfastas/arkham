<template>
  <router-view />
</template>

<script setup lang="ts">
// Root component — just renders the current route
</script>

<style>
:root {
  --color-bg: #0a0a1a;
  --color-panel: #1a1a2e;
  --color-border: #333344;
  --color-text: #e0e0e0;
  --color-text-muted: #888888;
  --color-accent: #c0a060;
  --color-guardian: #2980b9;
  --color-seeker: #d4a017;
  --color-rogue: #27ae60;
  --color-mystic: #8e44ad;
  --color-survivor: #c0392b;
  --color-neutral: #666666;
  --color-danger: #e74c3c;
  --color-success: #2e7d32;
}

body {
  background: var(--color-bg);
  color: var(--color-text);
}

button {
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: var(--color-panel);
  color: var(--color-text);
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 13px;
  transition: background 0.15s;
}
button:hover {
  background: #2a2a4e;
}
button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
