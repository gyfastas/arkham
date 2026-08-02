<script setup lang="ts">
import { computed } from 'vue'
import type { CardDisplay } from '../state/types'
import Card from './Card.vue'

const props = defineProps<{ hand: CardDisplay[]; resources: number }>()

const emit = defineEmits<{
  playCard: [cardId: string]
}>()

const handGridStyle = computed(() => ({
  // Keep eight narrow slots on desktop. Extra cards naturally flow to row 2;
  // fewer cards must not stretch back into oversized cards.
  '--hand-columns': props.hand.length ? 8 : 1,
}))

function canPlay(card: CardDisplay): boolean {
  return card.allowed !== false && (card.cost === null || card.cost <= props.resources)
}
</script>

<template>
  <div class="hand-area">
    <div class="hand-label">手牌 ({{ hand.length }})</div>
    <div class="hand-cards" :style="handGridStyle">
      <div
        v-for="(card, index) in hand"
        :key="`${card.id}-${index}`"
        class="hand-card-wrapper"
        :class="{ disallowed: !canPlay(card), 'insufficient-cost': card.cost !== null && card.cost > resources }"
        @click="canPlay(card) && emit('playCard', card.id)"
      >
        <Card :card="card" show-tooltip />
        <span v-if="card.cost !== null && card.cost > resources" class="hand-cost-warning">费用不足</span>
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
  display: grid;
  grid-template-columns: repeat(var(--hand-columns), minmax(0, 1fr));
  gap: 8px;
  overflow-x: hidden;
  justify-content: start;
  padding: 4px;
}
.hand-card-wrapper {
  position: relative;
  min-width: 0;
}
.hand-card-wrapper.disallowed {
  opacity: 0.68;
  cursor: not-allowed;
}
.hand-card-wrapper :deep(.card) {
  width: 100%;
  min-height: 95px;
}
.hand-cost-warning {
  position: absolute;
  right: 7px;
  bottom: 7px;
  z-index: 2;
  padding: 2px 0;
  background: transparent;
  color: #ffd0d0;
  font-size: 10px;
  font-weight: bold;
  pointer-events: none;
}
.hand-empty {
  color: #555;
  font-style: italic;
  font-size: 12px;
  padding: 16px;
}

@media (max-width: 560px) {
  .hand-cards { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
</style>
