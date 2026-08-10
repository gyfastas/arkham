<script setup lang="ts">
import type { OtherInvestigator } from '../state/types'
import { useGameStore } from '../stores/game'
import { localizeDisplayText } from '../utils/displayText'

/** GameView 传入的队友条目：公开信息 + 由实例 id 推算的展示字段 */
export interface TeammateEntry extends OtherInvestigator {
  instanceId: string
  active: boolean
  locationName: string
}

defineProps<{ teammates: TeammateEntry[] }>()
const store = useGameStore()

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#888',
}
</script>

<template>
  <div class="teammate-panel">
    <div class="panel-title">
      {{ store.language === 'zh-Hant' ? '隊友' : '队友' }} ({{ teammates.length }})
    </div>
    <div class="teammate-list">
      <div
        v-for="tm in teammates"
        :key="tm.instanceId"
        class="teammate-card"
        :class="{ active: tm.active, defeated: tm.defeated }"
      >
        <div class="tm-header">
          <span
            class="tm-class-dot"
            :style="{ backgroundColor: CLASS_COLORS[tm.class] || '#888' }"
          ></span>
          <span
            class="tm-name"
            :style="{ color: CLASS_COLORS[tm.class] || '#e0e0e0' }"
          >{{ localizeDisplayText(tm.name_cn || tm.name, store.language) }}</span>
          <span v-if="tm.active" class="tm-badge active-badge">
            {{ store.language === 'zh-Hant' ? '行動中' : '行动中' }}
          </span>
          <span v-if="tm.defeated" class="tm-badge defeated-badge">
            {{ store.language === 'zh-Hant' ? '已擊敗' : '已击败' }}
          </span>
        </div>
        <div class="tm-stats">
          <span class="tm-stat" title="生命">
            <span class="ic hp">♥</span>{{ tm.health - tm.damage }}/{{ tm.health }}
          </span>
          <span class="tm-stat" title="理智">
            <span class="ic san">☽</span>{{ tm.sanity - tm.horror }}/{{ tm.sanity }}
          </span>
          <span class="tm-stat" title="资源">
            <span class="ic res">◆</span>{{ tm.resources }}
          </span>
          <span class="tm-stat" title="线索">
            <span class="ic clue">✦</span>{{ tm.clues }}
          </span>
          <span class="tm-stat" title="手牌数">
            <span class="ic hand">🃏</span>{{ tm.hand_count }}
          </span>
        </div>
        <div class="tm-location" :title="tm.location_id">
          📍 {{ localizeDisplayText(tm.locationName, store.language) }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.teammate-panel {
  display: flex;
  flex-direction: column;
}
.panel-title {
  padding: 8px 12px;
  font-weight: bold;
  font-size: 13px;
  color: #7ec8e3;
  border-bottom: 1px solid #333344;
}
.teammate-list {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.teammate-card {
  background: #16222e;
  border: 1px solid #2a3a4e;
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
}
.teammate-card.active {
  border-color: #c0a060;
  box-shadow: 0 0 8px rgba(192, 160, 96, 0.25);
}
.teammate-card.defeated {
  opacity: 0.55;
}
.tm-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.tm-class-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}
.tm-name {
  font-weight: bold;
  font-size: 13px;
}
.tm-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: auto;
}
.tm-badge + .tm-badge {
  margin-left: 4px;
}
.active-badge {
  background: #c0a060;
  color: #0a0a1a;
  font-weight: 600;
}
.defeated-badge {
  background: #553333;
  color: #e74c3c;
}
.tm-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
  color: #e0e0e0;
}
.tm-stat {
  display: flex;
  align-items: center;
  gap: 2px;
}
.ic.hp { color: #e74c3c; }
.ic.san { color: #3498db; }
.ic.res { color: #c0a060; }
.ic.clue { color: #f1c40f; }
.ic.hand { color: #aaa; }
.tm-location {
  font-size: 11px;
  color: #8ab;
}
</style>
