<script setup lang="ts">
import { ref } from 'vue'
import type { CardDisplay } from '../state/types'
import { traitsLabel } from '../utils/labels'

const props = withDefaults(defineProps<{
  card: CardDisplay
  small?: boolean
  showTooltip?: boolean
}>(), { small: false, showTooltip: true })

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#666666',
}

const CLASS_LABELS: Record<string, string> = {
  guardian: '守卫者',
  seeker: '探求者',
  rogue: '流浪者',
  mystic: '潜修者',
  survivor: '求生者',
  neutral: '中立',
}

const SKILL_LABELS: Record<string, string> = {
  willpower: '意志',
  intellect: '智力',
  combat: '战斗',
  agility: '敏捷',
  wild: '★',
}

const SKILL_SHORT: Record<string, string> = {
  willpower: '意',
  intellect: '智',
  combat: '战',
  agility: '敏',
  wild: '★',
}

const SLOT_LABELS: Record<string, string> = {
  hand: '手部',
  'hand x2': '双手',
  body: '身体',
  accessory: '配件',
  ally: '盟友',
  arcane: '奥秘',
  'arcane x2': '双奥秘',
}

function borderColor(): string {
  return CLASS_COLORS[props.card.class] || CLASS_COLORS.neutral
}

function typeLabel(type: string): string {
  const map: Record<string, string> = { asset: '支援', event: '事件', skill: '技能' }
  return map[type] || type
}

const hovered = ref(false)
const tooltipStyle = ref<Record<string, string>>({})
const cardEl = ref<HTMLElement | null>(null)

function onEnter() {
  if (!props.showTooltip || props.small) return
  hovered.value = true
  if (cardEl.value) {
    const rect = cardEl.value.getBoundingClientRect()
    const spaceRight = window.innerWidth - rect.right
    if (spaceRight > 280) {
      tooltipStyle.value = { left: `${rect.right + 8}px`, top: `${Math.max(8, rect.top)}px` }
    } else {
      tooltipStyle.value = { right: `${window.innerWidth - rect.left + 8}px`, top: `${Math.max(8, rect.top)}px` }
    }
  }
}

function onLeave() {
  hovered.value = false
}
</script>

<template>
  <div
    ref="cardEl"
    class="card"
    :class="{ small }"
    :style="{ borderColor: borderColor() }"
    @mouseenter="onEnter"
    @mouseleave="onLeave"
  >
    <div class="card-header">
      <span v-if="card.cost !== null" class="card-cost">{{ card.cost }}</span>
      <span class="card-type">{{ typeLabel(card.type) }}</span>
    </div>
    <div class="card-name">{{ card.name_cn || card.name }}</div>
    <div v-if="!small && card.traits && card.traits.length" class="card-traits">
      {{ traitsLabel(card.traits) }}
    </div>
    <div v-if="!small && card.text_cn" class="card-text-brief" v-html="card.text_cn"></div>
    <div v-if="card.skill_icons && Object.keys(card.skill_icons).length" class="card-skills">
      <span
        v-for="(count, skill) in card.skill_icons"
        :key="skill"
        class="skill-icon"
      >{{ SKILL_SHORT[skill as string] || skill }}×{{ count }}</span>
    </div>
    <div v-if="!small" class="card-footer">
      <span v-if="card.health != null" class="hp">♥{{ card.health }}</span>
      <span v-if="card.sanity != null" class="san">☽{{ card.sanity }}</span>
      <span v-if="card.slots && card.slots.length" class="slots">{{ card.slots.map(s => SLOT_LABELS[s] || s).join(', ') }}</span>
    </div>
  </div>

  <!-- Tooltip: full card detail -->
  <Teleport to="body">
    <div v-if="hovered && showTooltip" class="card-tooltip" :style="tooltipStyle">
      <div class="tt-header" :style="{ borderBottomColor: borderColor() }">
        <span class="tt-cost" v-if="card.cost !== null">{{ card.cost }}</span>
        <span class="tt-name">{{ card.name_cn || card.name }}</span>
        <span class="tt-level" v-if="card.level != null && card.level > 0">Lv.{{ card.level }}</span>
      </div>
      <div class="tt-subtitle">
        <span class="tt-class" :style="{ color: borderColor() }">{{ CLASS_LABELS[card.class] || card.class }}</span>
        <span class="tt-type">{{ typeLabel(card.type) }}</span>
        <span v-if="card.unique" class="tt-unique">唯一</span>
      </div>
      <div v-if="card.traits && card.traits.length" class="tt-traits">
        {{ traitsLabel(card.traits) }}
      </div>
      <div v-if="card.text_cn || card.text" class="tt-text" v-html="card.text_cn || card.text">
      </div>
      <div class="tt-bottom">
        <div v-if="card.skill_icons && Object.keys(card.skill_icons).length" class="tt-skills">
          <span v-for="(count, skill) in card.skill_icons" :key="skill" class="tt-skill">
            {{ SKILL_LABELS[skill as string] || skill }} ×{{ count }}
          </span>
        </div>
        <div class="tt-stats">
          <span v-if="card.health != null" class="hp">♥ {{ card.health }}</span>
          <span v-if="card.sanity != null" class="san">☽ {{ card.sanity }}</span>
          <span v-if="card.slots && card.slots.length" class="tt-slots">
            栏位: {{ card.slots.map(s => SLOT_LABELS[s] || s).join(', ') }}
          </span>
        </div>
      </div>
      <div v-if="card.name !== card.name_cn" class="tt-en">{{ card.name }}</div>
    </div>
  </Teleport>
</template>

<style scoped>
.card {
  background: #1a1a2e;
  border: 2px solid #333344;
  border-radius: 6px;
  padding: 8px;
  width: 140px;
  font-size: 12px;
  color: #e0e0e0;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  flex-shrink: 0;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(192, 160, 96, 0.3);
}
.card.small {
  width: 100px;
  padding: 4px;
  font-size: 10px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.card-cost {
  background: #0a0a1a;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: #c0a060;
}
.card-type {
  font-size: 10px;
  color: #888;
  text-transform: uppercase;
}
.card-name {
  font-weight: bold;
  margin-bottom: 4px;
  text-align: center;
  color: #fff;
}
.card-traits {
  font-size: 10px;
  color: #c0a060;
  text-align: center;
  font-style: italic;
  margin-bottom: 4px;
}
.card-text-brief {
  font-size: 10px;
  color: #ccc;
  line-height: 1.3;
  margin-bottom: 4px;
  max-height: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-skills {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.skill-icon {
  background: #2a2a44;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10px;
  color: #c0a060;
}
.card-footer {
  display: flex;
  gap: 6px;
  font-size: 10px;
  color: #aaa;
}
.hp { color: #e74c3c; }
.san { color: #3498db; }
.slots { color: #888; }
</style>

<style>
/* Tooltip styles (global because Teleported) */
.card-tooltip {
  position: fixed;
  z-index: 9999;
  width: 260px;
  max-height: 80vh;
  overflow-y: auto;
  background: #12122a;
  border: 2px solid #c0a060;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8);
  pointer-events: none;
  font-size: 13px;
  color: #e0e0e0;
}
.tt-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 2px solid #333;
}
.tt-cost {
  background: #0a0a1a;
  border: 1px solid #c0a060;
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  color: #c0a060;
  flex-shrink: 0;
}
.tt-name {
  font-weight: bold;
  font-size: 15px;
  color: #fff;
  flex: 1;
}
.tt-level {
  color: #d4a017;
  font-weight: 600;
  font-size: 12px;
}
.tt-subtitle {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
}
.tt-class { font-weight: 600; }
.tt-type { color: #999; }
.tt-unique { color: #c0a060; font-style: italic; }
.tt-traits {
  color: #c0a060;
  font-style: italic;
  font-size: 12px;
  margin-bottom: 8px;
  text-align: center;
}
.tt-text {
  color: #ddd;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 8px;
  padding: 8px;
  background: #0a0a18;
  border-radius: 4px;
  border-left: 3px solid #333;
}
.tt-bottom {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tt-skills {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.tt-skill {
  background: #2a2a44;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  color: #c0a060;
}
.tt-stats {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #aaa;
}
.tt-stats .hp { color: #e74c3c; }
.tt-stats .san { color: #3498db; }
.tt-slots { color: #888; }
.tt-en {
  margin-top: 6px;
  font-size: 11px;
  color: #666;
  font-style: italic;
}
</style>
