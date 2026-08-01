<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SlotConflict } from '../state/types'

const props = defineProps<{
  conflict: SlotConflict
}>()

const emit = defineEmits<{
  confirm: [discardIds: string[]]
  cancel: []
}>()

const SLOT_LABELS: Record<string, string> = {
  hand: '手',
  arcane: '奥术',
  accessory: '饰品',
  body: '身体',
  ally: '盟友',
  tarot: '塔罗',
}

const selected = ref<string[]>([])

const neededTotal = computed(() =>
  Object.values(props.conflict.needed || {}).reduce((a, b) => a + b, 0)
)

const neededText = computed(() =>
  Object.entries(props.conflict.needed || {})
    .map(([slot, n]) => `${SLOT_LABELS[slot] || slot}×${n}`)
    .join('、')
)

function toggle(instanceId: string) {
  const idx = selected.value.indexOf(instanceId)
  if (idx !== -1) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push(instanceId)
  }
}

const canConfirm = computed(() => selected.value.length >= neededTotal.value)

function slotLabel(slots: string[]): string {
  return slots.map(s => SLOT_LABELS[s] || s).join('+')
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('cancel')">
    <div class="slot-modal">
      <div class="slot-title">📦 槽位不足</div>
      <div class="slot-sub">
        打出【{{ conflict.card_name }}】需要腾出槽位：{{ neededText }}。
        选择要弃置的场上支援（至少 {{ neededTotal }} 张）：
      </div>

      <div v-if="conflict.candidates.length" class="slot-cards">
        <div
          v-for="card in conflict.candidates"
          :key="card.instance_id"
          class="slot-card"
          :class="{ selected: selected.includes(card.instance_id) }"
          @click="toggle(card.instance_id)"
        >
          <div class="sc-name">{{ card.name_cn || card.name }}</div>
          <div class="sc-slots">占用：{{ slotLabel(card.slots) }}</div>
          <div class="sc-check" v-if="selected.includes(card.instance_id)">✓</div>
        </div>
      </div>
      <div v-else class="slot-empty">场上没有可弃置的支援卡</div>

      <div class="slot-footer">
        <div class="slot-count" :class="{ ok: canConfirm }">
          已选 {{ selected.length }} / {{ neededTotal }}
        </div>
        <div class="slot-buttons">
          <button class="btn btn-cancel" @click="emit('cancel')">取消</button>
          <button
            class="btn btn-confirm"
            :disabled="!canConfirm"
            @click="emit('confirm', [...selected])"
          >弃置并打出</button>
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

.slot-modal {
  background: #14142b;
  border: 1px solid #4a4a7a;
  border-radius: 10px;
  padding: 16px 20px;
  width: 560px;
  max-width: 92vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
}

.slot-title {
  font-size: 17px;
  font-weight: bold;
  color: #e8e8e8;
  margin-bottom: 4px;
}

.slot-sub {
  font-size: 12px;
  color: #aaa;
  margin-bottom: 12px;
  line-height: 1.5;
}

.slot-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.slot-card {
  position: relative;
  background: #1a1a2e;
  border: 2px solid #333355;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.slot-card:hover {
  border-color: #6a6aaa;
}

.slot-card.selected {
  border-color: #c0392b;
  background: #2e1f24;
}

.sc-name {
  font-weight: bold;
  color: #e0e0e0;
  font-size: 13px;
  margin-bottom: 4px;
}

.sc-slots {
  font-size: 11px;
  color: #888;
}

.sc-check {
  position: absolute;
  top: 6px;
  right: 8px;
  color: #c0392b;
  font-weight: bold;
}

.slot-empty {
  color: #888;
  text-align: center;
  padding: 24px 0;
}

.slot-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #333355;
  padding-top: 12px;
}

.slot-count {
  color: #888;
  font-weight: bold;
}

.slot-count.ok {
  color: #3d8b40;
}

.slot-buttons {
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

.btn-confirm:hover:not(:disabled) {
  background: #357a38;
}

.btn-confirm:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
