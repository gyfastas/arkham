<script setup lang="ts">
import { ref } from 'vue'
import type { CardDisplay } from '../state/types'

const props = defineProps<{ hand: CardDisplay[] }>()

const emit = defineEmits<{
  confirm: [cardIds: string[]]
}>()

const selected = ref<string[]>([])

function toggle(id: string) {
  const idx = selected.value.indexOf(id)
  if (idx !== -1) selected.value.splice(idx, 1)
  else selected.value.push(id)
}
</script>

<template>
  <div class="mulligan-overlay">
    <div class="mulligan-modal">
      <div class="m-title">开局调度</div>
      <div class="m-sub">选择要重抽的手牌（官方规则：开局可调度一次），或保留全部手牌</div>
      <div class="m-cards">
        <div
          v-for="(card, i) in hand"
          :key="card.id + '_' + i"
          class="m-card"
          :class="{ selected: selected.includes(card.id + '_' + i) }"
          @click="toggle(card.id + '_' + i)"
        >
          <div class="m-name">{{ card.name_cn || card.name }}</div>
          <div class="m-type">{{ card.type }}</div>
          <div class="m-check" v-if="selected.includes(card.id + '_' + i)">✓</div>
        </div>
      </div>
      <div class="m-footer">
        <button class="btn btn-keep" @click="emit('confirm', [])">保留手牌</button>
        <button
          class="btn btn-redraw"
          :disabled="!selected.length"
          @click="emit('confirm', selected.map(k => hand[Number(k.split('_')[1])].id))"
        >
          重抽 {{ selected.length }} 张
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

.m-cards {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.m-card {
  position: relative;
  width: 100px;
  background: #1a1a2e;
  border: 2px solid #333355;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.m-card:hover { border-color: #6a6aaa; }
.m-card.selected { border-color: #d4a017; }

.m-name { font-size: 12px; font-weight: bold; color: #e0e0e0; }
.m-type { font-size: 10px; color: #888; margin-top: 2px; }

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
