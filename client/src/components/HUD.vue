<script setup lang="ts">
import { computed } from 'vue'
import type { GameState } from '../state/types'
import { useGameStore } from '../stores/game'
import { localizeDisplayText } from '../utils/displayText'
import { isMultiplayer, instanceName } from '../utils/multiplayer'

const props = defineProps<{ state: GameState }>()
const store = useGameStore()

// 多人联机：回合指示（单人局不显示，避免噪音）
const isMulti = computed(() => isMultiplayer(props.state))
const yourTurn = computed(() => props.state.your_turn !== false)
const turnLabel = computed(() => {
  if (yourTurn.value) return '你的回合'
  const activeId = props.state.active_investigator_id
  const raw = activeId ? instanceName(props.state, activeId) : ''
  const name = raw ? localizeDisplayText(raw, store.language) : '其他玩家'
  return `等待 ${name}`
})

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#666666',
}

const PHASE_LABELS: Record<string, string> = {
  mythos: '神话阶段',
  investigation: '调查阶段',
  enemy: '敌人阶段',
  upkeep: '整理阶段',
}

const PHASE_LABELS_HANT: Record<string, string> = {
  mythos: '神話階段', investigation: '調查階段', enemy: '敵人階段', upkeep: '整理階段',
}
</script>

<template>
  <div class="hud">
    <div class="hud-left">
      <span
        class="inv-name"
        :style="{ color: CLASS_COLORS[state.investigator.class] || '#ccc' }"
      >{{ localizeDisplayText(state.investigator.name_cn, store.language) }}</span>
      <span
        v-if="isMulti"
        class="turn-badge"
        :class="{ mine: yourTurn, waiting: !yourTurn }"
      >{{ turnLabel }}</span>
    </div>
    <div class="hud-stats">
      <div class="stat" title="生命">
        <span class="stat-icon hp">♥</span>
        <span>{{ state.investigator.health - state.investigator.damage }}/{{ state.investigator.health }}</span>
      </div>
      <div class="stat" title="理智">
        <span class="stat-icon san">☽</span>
        <span>{{ state.investigator.sanity - state.investigator.horror }}/{{ state.investigator.sanity }}</span>
      </div>
      <div class="stat" title="资源">
        <span class="stat-icon res">◆</span>
        <span>{{ state.investigator.resources }}</span>
      </div>
      <div class="stat" title="线索">
        <span class="stat-icon clue">✦</span>
        <span>{{ state.investigator.clues }}</span>
      </div>
      <div class="stat" title="行动">
        <span class="stat-icon act">▶</span>
        <span>{{ state.investigator.actions_remaining }}</span>
      </div>
      <div class="divider" />
      <div class="stat" title="毁灭">
        <span class="stat-icon doom">☠</span>
        <span>{{ state.doom }}/{{ state.doom_threshold }}</span>
      </div>
      <div class="stat" title="牌组">
        <span class="stat-icon deck">▤</span>
        <span>{{ state.investigator.deck_count }}</span>
      </div>
      <div v-if="state.encounter_deck_count != null" class="stat" title="遭遇牌组">
        <span class="stat-icon enc">▧</span>
        <span>{{ state.encounter_deck_count }}</span>
      </div>
    </div>
    <div class="hud-right">
      <span class="round">{{ store.language === 'zh-Hant' ? '第' : '第' }}{{ state.round }}{{ store.language === 'zh-Hant' ? '輪' : '轮' }}</span>
      <span class="phase">{{ (store.language === 'zh-Hant' ? PHASE_LABELS_HANT : PHASE_LABELS)[state.phase] || state.phase }}</span>
    </div>
  </div>
</template>

<style scoped>
.hud {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1a1a2e;
  border-bottom: 1px solid #333344;
  padding: 8px 16px;
  gap: 16px;
}
.inv-name {
  font-weight: bold;
  font-size: 16px;
}
.hud-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.turn-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
}
.turn-badge.mine {
  background: #c0a060;
  color: #0a0a1a;
}
.turn-badge.waiting {
  background: transparent;
  border-color: #555566;
  color: #999;
}
.hud-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.stat {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 14px;
  color: #e0e0e0;
}
.stat-icon {
  font-size: 16px;
}
.stat-icon.hp { color: #e74c3c; }
.stat-icon.san { color: #3498db; }
.stat-icon.res { color: #c0a060; }
.stat-icon.clue { color: #f1c40f; }
.stat-icon.act { color: #2ecc71; }
.stat-icon.doom { color: #e74c3c; }
.stat-icon.deck { color: #aaa; }
.stat-icon.enc { color: #9b59b6; }
.divider {
  width: 1px;
  height: 20px;
  background: #333344;
}
.hud-right {
  display: flex;
  gap: 12px;
  align-items: center;
}
.round {
  color: #c0a060;
  font-weight: bold;
}
.phase {
  background: #2a2a44;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #e0e0e0;
}
</style>
