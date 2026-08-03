<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CardDisplay } from '../state/types'
import { useGameStore } from '../stores/game'
import { localizeDisplayText } from '../utils/displayText'
import { CLASS_COLORS } from '../utils/labels'

const props = defineProps<{
  deck: CardDisplay[]
  discard: CardDisplay[]
}>()

const store = useGameStore()

const TYPE_LABELS: Record<string, string> = {
  asset: '支援', event: '事件', skill: '技能', treachery: '诡计', enemy: '敌人',
}

const open = ref<'deck' | 'discard' | null>(null)

const shown = computed(() => {
  if (open.value === 'deck') return props.deck
  if (open.value === 'discard') return [...props.discard].reverse() // 最近弃置在前
  return []
})

const title = computed(() =>
  open.value === 'deck' ? `抽牌堆（${props.deck.length} 张）` : `弃牌堆（${props.discard.length} 张）`,
)

const note = computed(() =>
  open.value === 'deck'
    ? '顺序已打乱，仅供查看牌库构成（官方规则不允许查看顺序）'
    : '靠上的为最近弃置的牌',
)

function cardName(card: CardDisplay): string {
  return localizeDisplayText(card.name_cn || card.name, store.language)
}
</script>

<template>
  <div class="deck-panel">
    <button class="pile-btn" @click="open = 'deck'">
      <span class="pile-icon">🂠</span> 抽牌堆 <span class="pile-count">{{ deck.length }}</span>
    </button>
    <button class="pile-btn" @click="open = 'discard'">
      <span class="pile-icon">🗑</span> 弃牌堆 <span class="pile-count">{{ discard.length }}</span>
    </button>
  </div>

  <Teleport to="body">
    <div v-if="open" class="pile-overlay" @click.self="open = null">
      <div class="pile-modal">
        <div class="pile-header">
          <span class="pile-title">{{ title }}</span>
          <button class="pile-close" @click="open = null">✕</button>
        </div>
        <div class="pile-note">{{ note }}</div>
        <div class="pile-grid">
          <div
            v-for="(card, i) in shown"
            :key="card.id + '_' + i"
            class="pile-card"
            :style="{ borderLeftColor: CLASS_COLORS[card.class] || '#333' }"
          >
            <span class="pc-name">{{ cardName(card) }}</span>
            <span class="pc-meta">
              {{ TYPE_LABELS[card.type] || card.type }}
              <template v-if="card.cost !== null && card.cost !== undefined"> · {{ card.cost }}费</template>
              <template v-if="card.level"> · Lv.{{ card.level }}</template>
            </span>
          </div>
          <div v-if="shown.length === 0" class="pile-empty">空</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.deck-panel {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
}

.pile-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #12122a;
  border: 1px solid #2a2a4e;
  color: #bbb;
  padding: 8px 6px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.pile-btn:hover {
  border-color: #c0a060;
  color: #eee;
}

.pile-icon {
  font-size: 15px;
}

.pile-count {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 1px 8px;
  font-size: 12px;
  color: #c0a060;
}

.pile-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1500;
}

.pile-modal {
  background: #12122a;
  border: 1px solid #333355;
  border-radius: 10px;
  width: 640px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
}

.pile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 8px;
}

.pile-title {
  font-size: 16px;
  font-weight: 600;
  color: #e0d0a0;
}

.pile-close {
  background: none;
  border: none;
  color: #888;
  font-size: 16px;
  cursor: pointer;
}

.pile-close:hover {
  color: #fff;
}

.pile-note {
  padding: 0 18px 10px;
  font-size: 12px;
  color: #666;
  border-bottom: 1px solid #1a1a2e;
}

.pile-grid {
  overflow-y: auto;
  padding: 12px 18px 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 8px;
  align-content: start;
}

.pile-card {
  background: #0d0d20;
  border-left: 3px solid #333;
  border-radius: 4px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pc-name {
  font-size: 13px;
  color: #ddd;
}

.pc-meta {
  font-size: 11px;
  color: #666;
}

.pile-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: #555;
  padding: 30px 0;
}
</style>
