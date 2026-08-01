<script setup lang="ts">
import { computed } from 'vue'
import type { GameState } from '../state/types'
import { useGameStore } from '../stores/game'

const props = defineProps<{
  state: GameState
}>()
const store = useGameStore()

const emit = defineEmits<{
  action: [type: string]
}>()

const hasEnemies = computed(() => props.state.enemies.some(e => e.engaged))
const hasActionsLeft = computed(() => props.state.investigator.actions_remaining > 0)
const hasTomeActions = computed(() => props.state.investigator.tome_actions_remaining > 0)

interface ActionDef {
  type: string
  label: string
  icon: string
  show: boolean
  highlight?: boolean
}

const actions = computed<ActionDef[]>(() => [
  { type: 'INVESTIGATE', label: store.language === 'zh-Hant' ? '調查' : '调查', icon: '🔍', show: hasActionsLeft.value },
  { type: 'FIGHT', label: store.language === 'zh-Hant' ? '戰鬥' : '战斗', icon: '⚔️', show: hasActionsLeft.value && hasEnemies.value },
  { type: 'EVADE', label: store.language === 'zh-Hant' ? '閃避' : '闪避', icon: '🏃', show: hasActionsLeft.value && hasEnemies.value },
  { type: 'ENGAGE', label: store.language === 'zh-Hant' ? '交戰' : '交战', icon: '🎯', show: hasActionsLeft.value },
  { type: 'DRAW', label: store.language === 'zh-Hant' ? '抽牌' : '抽牌', icon: '🃏', show: hasActionsLeft.value },
  { type: 'RESOURCE', label: store.language === 'zh-Hant' ? '資源' : '资源', icon: '◆', show: hasActionsLeft.value },
  { type: 'END_TURN', label: store.language === 'zh-Hant' ? '結束回合' : '结束回合', icon: '⏭', show: true, highlight: true },
])
</script>

<template>
  <div class="action-bar">
    <div class="action-info">
      <span class="action-count">{{ store.language === 'zh-Hant' ? '行動' : '行动' }}: {{ state.investigator.actions_remaining }}</span>
      <span class="tome-count" v-if="hasTomeActions">{{ store.language === 'zh-Hant' ? '典籍' : '典籍' }}: {{ state.investigator.tome_actions_remaining }}</span>
    </div>
    <div class="action-buttons">
      <button
        v-for="act in actions"
        :key="act.type"
        v-show="act.show"
        class="action-btn"
        :class="[act.type.toLowerCase(), { highlight: act.highlight }]"
        @click="emit('action', act.type)"
      >
        <span class="action-icon">{{ act.icon }}</span>
        <span class="action-label">{{ act.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.action-bar {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 8px;
}
.action-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #888;
}
.action-count {
  color: #c0a060;
  font-weight: 600;
}
.tome-count {
  color: #d4a017;
}
.action-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #333344;
  border-radius: 6px;
  background: #1a1a2e;
  color: #e0e0e0;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.action-btn:hover {
  background: #2a2a44;
  border-color: #c0a060;
}
.action-btn.fight { border-color: #c0392b44; }
.action-btn.fight:hover { border-color: #e74c3c; }
.action-btn.evade { border-color: #27ae6044; }
.action-btn.evade:hover { border-color: #2ecc71; }
.action-btn.highlight {
  border-color: #c0a060;
  color: #c0a060;
}
.action-btn.highlight:hover {
  background: #c0a060;
  color: #0a0a1a;
}
.action-icon {
  font-size: 14px;
}
.action-label {
  font-weight: bold;
}
</style>
