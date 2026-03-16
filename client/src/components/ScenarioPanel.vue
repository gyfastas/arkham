<script setup lang="ts">
import { ref } from 'vue'
import type { GameState } from '../state/types'

defineProps<{ state: GameState }>()

const agendaExpanded = ref(true)
const actExpanded = ref(true)
</script>

<template>
  <div class="scenario-panel">
    <div class="panel-title">{{ state.scenario.name_cn || state.scenario.name }}</div>

    <!-- Agenda (密谋) -->
    <div v-if="state.scenario.agenda" class="scenario-card agenda">
      <div class="card-top" @click="agendaExpanded = !agendaExpanded">
        <div class="card-label">
          <span class="label-icon">☠</span>
          密谋 {{ state.scenario.agenda.sequence }}/{{ state.scenario.agenda.total }}
          <span class="expand-icon">{{ agendaExpanded ? '▾' : '▸' }}</span>
        </div>
        <div class="card-name">{{ state.scenario.agenda.name_cn || state.scenario.agenda.name }}</div>
        <div class="progress-bar">
          <div class="progress-fill doom-fill" :style="{ width: state.doom_threshold > 0 ? `${(state.doom / state.doom_threshold) * 100}%` : '0%' }"></div>
          <span class="progress-text">
            <span class="doom-icon">☠</span> {{ state.doom }} / {{ state.doom_threshold }}
          </span>
        </div>
      </div>
      <div v-if="agendaExpanded && state.scenario.agenda.text_cn" class="card-body">
        <div class="card-text">{{ state.scenario.agenda.text_cn }}</div>
      </div>
    </div>

    <!-- Act (事件) -->
    <div v-if="state.scenario.act" class="scenario-card act">
      <div class="card-top" @click="actExpanded = !actExpanded">
        <div class="card-label">
          <span class="label-icon">✦</span>
          事件 {{ state.scenario.act.sequence }}/{{ state.scenario.act.total }}
          <span class="expand-icon">{{ actExpanded ? '▾' : '▸' }}</span>
        </div>
        <div class="card-name">{{ state.scenario.act.name_cn || state.scenario.act.name }}</div>
        <div class="progress-bar">
          <div class="progress-fill clue-fill" :style="{ width: state.total_clues_needed > 0 ? `${(state.investigator.clues / state.total_clues_needed) * 100}%` : '0%' }"></div>
          <span class="progress-text">
            <span class="clue-icon">✦</span> {{ state.investigator.clues }} / {{ state.total_clues_needed }}
          </span>
        </div>
      </div>
      <div v-if="actExpanded && state.scenario.act.text_cn" class="card-body">
        <div class="card-text">{{ state.scenario.act.text_cn }}</div>
      </div>
    </div>

    <!-- Game info -->
    <div class="game-info">
      <div class="info-row">
        <span class="info-label">回合</span>
        <span class="info-val">{{ state.round }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">弃牌堆</span>
        <span class="info-val">{{ state.discard.length }}</span>
      </div>
      <div v-if="state.encounter_deck_count != null" class="info-row">
        <span class="info-label">遭遇牌堆</span>
        <span class="info-val">{{ state.encounter_deck_count }}</span>
      </div>
      <div v-if="state.encounter_discard_count != null && state.encounter_discard_count > 0" class="info-row">
        <span class="info-label">遭遇弃牌</span>
        <span class="info-val">{{ state.encounter_discard_count }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.panel-title {
  padding: 8px 12px;
  font-weight: bold;
  font-size: 13px;
  color: #c0a060;
  border-bottom: 1px solid #333344;
}
.scenario-card {
  border: 1px solid #333344;
  border-radius: 6px;
  margin: 6px 8px;
  overflow: hidden;
}
.scenario-card.agenda {
  border-left: 3px solid #e74c3c;
}
.scenario-card.act {
  border-left: 3px solid #2ecc71;
}
.card-top {
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
}
.card-top:hover {
  background: #1e1e38;
}
.card-label {
  font-size: 10px;
  color: #888;
  text-transform: uppercase;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.label-icon {
  font-size: 12px;
}
.agenda .label-icon { color: #e74c3c; }
.act .label-icon { color: #2ecc71; }
.expand-icon {
  margin-left: auto;
  font-size: 10px;
  color: #666;
}
.card-name {
  font-weight: bold;
  font-size: 13px;
  color: #e0e0e0;
  margin-bottom: 6px;
}
.progress-bar {
  position: relative;
  height: 20px;
  background: #111122;
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.doom-fill {
  background: rgba(231, 76, 60, 0.3);
}
.clue-fill {
  background: rgba(241, 196, 15, 0.3);
}
.progress-text {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 100%;
  font-size: 13px;
  font-weight: bold;
}
.doom-icon { color: #e74c3c; }
.clue-icon { color: #f1c40f; }
.card-body {
  padding: 0 10px 10px;
  border-top: 1px solid #222233;
}
.card-text {
  font-size: 12px;
  color: #bbb;
  line-height: 1.6;
  padding: 8px;
  background: #0e0e20;
  border-radius: 4px;
  margin-top: 6px;
  white-space: pre-line;
}
.game-info {
  padding: 8px 12px;
  border-top: 1px solid #333344;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}
.info-label { color: #777; }
.info-val { color: #ccc; font-weight: 600; }
</style>
