<script setup lang="ts">
import { ref } from 'vue'
import type { CardDisplay } from '../state/types'
import { useGameStore } from '../stores/game'
import Card from './Card.vue'

const props = defineProps<{ hand: CardDisplay[] }>()
const store = useGameStore()

const emit = defineEmits<{
  confirm: [cardIds: string[]]
}>()

const selected = ref<number[]>([])

function toggle(i: number) {
  const idx = selected.value.indexOf(i)
  if (idx !== -1) selected.value.splice(idx, 1)
  else selected.value.push(i)
}

function redraw() {
  emit('confirm', selected.value.map(i => props.hand[i].id))
}
</script>

<template>
  <div class="mulligan-overlay">
    <div class="mulligan-modal">
      <div class="m-title">{{ store.language === 'zh-Hant' ? '開局調度' : '开局调度' }}</div>
      <div class="m-sub">{{ store.language === 'zh-Hant' ? '選擇要重抽的手牌（官方規則：開局可調度一次），或保留全部手牌' : '选择要重抽的手牌（官方规则：开局可调度一次），或保留全部手牌' }}</div>
      <div class="m-note">{{ store.language === 'zh-Hant' ? '開局抽到的威脅或弱點牌也可以在這裡更換。' : '开局抽到的威胁或弱点牌也可以在这里更换。' }}</div>
      <div class="m-cards">
        <div
          v-for="(card, i) in hand"
          :key="i"
          class="m-card"
          :class="{ selected: selected.includes(i) }"
          @click="toggle(i)"
        >
          <Card :card="card" />
          <div class="m-check" v-if="selected.includes(i)">✓</div>
        </div>
      </div>
      <div class="m-footer">
        <button class="btn btn-keep" @click="emit('confirm', [])">保留手牌</button>
        <button
          class="btn btn-redraw"
          :disabled="!selected.length"
          @click="redraw"
        >
          {{ store.language === 'zh-Hant' ? '重抽' : '重抽' }} {{ selected.length }} {{ store.language === 'zh-Hant' ? '張' : '张' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mulligan-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.mulligan-modal {
  background: #14142b;
  border: 1px solid #4a4a7a;
  border-radius: 10px;
  padding: 18px 22px;
  width: 620px;
  max-width: 92vw;
}

.m-title {
  font-size: 18px;
  font-weight: bold;
  color: #e8e8e8;
}

.m-sub {
  font-size: 12px;
  color: #888;
  margin: 4px 0 14px;
}

.m-note {
  margin: -8px 0 12px;
  color: #d8a56c;
  font-size: 11px;
}

.m-cards {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.m-card {
  position: relative;
  width: 146px;
  padding: 2px;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.m-card:hover { border-color: #6a6aaa; }
.m-card.selected { border-color: #d4a017; }

.m-card :deep(.card) { width: 140px; min-height: 178px; }

.m-check {
  position: absolute;
  top: 4px;
  right: 6px;
  color: #d4a017;
  font-weight: bold;
}

.m-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  border: 1px solid #4a4a7a;
  border-radius: 6px;
  padding: 7px 16px;
  cursor: pointer;
  font-size: 13px;
  background: #1a1a2e;
  color: #ccc;
}

.btn-redraw {
  background: #2c5f2e;
  border-color: #3d8b40;
  color: #fff;
}

.btn-redraw:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
