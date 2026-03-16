<script setup lang="ts">
import type { CardDisplay } from '../state/types'
import Card from './Card.vue'

defineProps<{ hand: CardDisplay[] }>()

const emit = defineEmits<{
  playCard: [cardId: string]
}>()
</script>

<template>
  <div class="hand-area">
    <div class="hand-label">手牌 ({{ hand.length }})</div>
    <div class="hand-cards">
      <div
        v-for="card in hand"
        :key="card.id"
        class="hand-card-wrapper"
        :class="{ disallowed: card.allowed === false }"
        @click="card.allowed !== false && emit('playCard', card.id)"
      >
        <Card :card="card" />
      </div>
      <div v-if="!hand.length" class="hand-empty">手牌为空</div>
    </div>
  </div>
</template>

<style scoped>
.hand-area {
  display: flex;
  flex-direction: column;
}
.hand-label {
  font-size: 12px;
  color: #c0a060;
  font-weight: bold;
  margin-bottom: 6px;
  padding-left: 4px;
}
.hand-cards {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px;
}
.hand-card-wrapper {
  flex-shrink: 0;
}
.hand-card-wrapper.disallowed {
  opacity: 0.4;
  pointer-events: none;
}
.hand-empty {
  color: #555;
  font-style: italic;
  font-size: 12px;
  padding: 16px;
}
</style>
