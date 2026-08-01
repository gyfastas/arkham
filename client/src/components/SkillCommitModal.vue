<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CardDisplay } from '../state/types'

const props = defineProps<{
  skillType: string
  actionLabel: string
  hand: CardDisplay[]
}>()

const emit = defineEmits<{
  confirm: [committed: string[]]
  cancel: []
}>()

const SKILL_LABELS: Record<string, string> = {
  willpower: '意志',
  intellect: '智力',
  combat: '战斗',
  agility: '敏捷',
  wild: '万能',
}

const SKILL_ICONS: Record<string, string> = {
  willpower: '🧠',
  intellect: '📖',
  combat: '⚔️',
  agility: '🏃',
}

const selected = ref<number[]>([])  // hand 数组下标（同名卡有多张，不能用 card.id）

// 可投入的卡：含有本次技能类型图标或万能图标的卡
const eligibleCards = computed(() =>
  props.hand
    .map((card, index) => ({ card, index }))
    .filter(({ card }) => {
      const icons = card.skill_icons || {}
      return (icons[props.skillType] || 0) > 0 || (icons['wild'] || 0) > 0
    })
)

function iconCount(card: CardDisplay): number {
  const icons = card.skill_icons || {}
  return (icons[props.skillType] || 0) + (icons['wild'] || 0)
}

// 每种卡限投1张（官方规则：同名卡每次检定只能投入1张）
function toggle(index: number, card: CardDisplay) {
  const i = selected.value.indexOf(index)
  if (i !== -1) {
    selected.value.splice(i, 1)
    return
  }
  // 同名卡互斥：选中这张时，取消已选中的同名卡
  const dup = eligibleCards.value.find(
    ({ index: idx, card: c }) =>
      idx !== index && c.id === card.id && selected.value.includes(idx)
  )
  if (dup) {
    selected.value.splice(selected.value.indexOf(dup.index), 1)
  }
  selected.value.push(index)
}

const totalIcons = computed(() =>
  eligibleCards.value
    .filter(({ index }) => selected.value.includes(index))
    .reduce((sum, { card }) => sum + iconCount(card), 0)
)

function confirm() {
  emit('confirm', selected.value.map(i => props.hand[i].id))
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('cancel')">
    <div class="commit-modal">
      <div class="commit-title">
        <span class="skill-icon">{{ SKILL_ICONS[skillType] || '🎲' }}</span>
        {{ actionLabel }} — {{ SKILL_LABELS[skillType] || skillType }}检定
      </div>
      <div class="commit-sub">选择要投入的技能卡（每种限1张）</div>

      <div v-if="eligibleCards.length" class="commit-cards">
        <div
          v-for="{ card, index } in eligibleCards"
          :key="index"
          class="commit-card"
          :class="{ selected: selected.includes(index) }"
          @click="toggle(index, card)"
        >
          <div class="cc-name">{{ card.name_cn || card.name }}</div>
          <div class="cc-icons">
            <span v-for="(n, k) in card.skill_icons" :key="k" class="cc-icon">
              {{ SKILL_LABELS[k] || k }}×{{ n }}
            </span>
          </div>
          <div v-if="card.text_cn" class="cc-text" v-html="card.text_cn"></div>
          <div class="cc-check" v-if="selected.includes(index)">✓</div>
        </div>
      </div>
      <div v-else class="commit-empty">手中没有可投入的技能卡</div>

      <div class="commit-footer">
        <div class="commit-total">投入加值：+{{ totalIcons }}</div>
        <div class="commit-buttons">
          <button class="btn btn-cancel" @click="emit('cancel')">取消</button>
          <button class="btn btn-skip" @click="emit('confirm', [])">不投入</button>
          <button class="btn btn-confirm" @click="confirm">
            检定{{ selected.length ? `（投${selected.length}张）` : '' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.commit-modal {
  background: #14142b;
  border: 1px solid #4a4a7a;
  border-radius: 10px;
  padding: 16px 20px;
  width: 640px;
  max-width: 92vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
}

.commit-title {
  font-size: 17px;
  font-weight: bold;
  color: #e8e8e8;
  margin-bottom: 4px;
}

.skill-icon {
  margin-right: 6px;
}

.commit-sub {
  font-size: 12px;
  color: #888;
  margin-bottom: 12px;
}

.commit-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.commit-card {
  position: relative;
  background: #1a1a2e;
  border: 2px solid #333355;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.commit-card:hover {
  border-color: #6a6aaa;
}

.commit-card.selected {
  border-color: #d4a017;
  background: #25253e;
}

.cc-name {
  font-weight: bold;
  color: #e0e0e0;
  font-size: 13px;
  margin-bottom: 4px;
}

.cc-icons {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.cc-icon {
  background: #1f2b3a;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 11px;
  color: #9fc5e8;
}

.cc-text {
  font-size: 11px;
  color: #999;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.cc-check {
  position: absolute;
  top: 6px;
  right: 8px;
  color: #d4a017;
  font-weight: bold;
}

.commit-empty {
  color: #888;
  text-align: center;
  padding: 24px 0;
}

.commit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #333355;
  padding-top: 12px;
}

.commit-total {
  color: #d4a017;
  font-weight: bold;
}

.commit-buttons {
  display: flex;
  gap: 8px;
}

.btn {
  border: 1px solid #4a4a7a;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 13px;
  background: #1a1a2e;
  color: #ccc;
}

.btn:hover {
  background: #25253e;
}

.btn-confirm {
  background: #2c5f2e;
  border-color: #3d8b40;
  color: #fff;
}

.btn-confirm:hover {
  background: #357a38;
}

.btn-skip {
  color: #999;
}
</style>
