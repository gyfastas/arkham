<script setup lang="ts">
import { computed } from 'vue'
import type { CardInstanceDisplay, SlotStatusEntry } from '../state/types'

const props = defineProps<{
  assets: CardInstanceDisplay[]
  threatCards?: CardInstanceDisplay[]
  slotStatus?: Record<string, SlotStatusEntry>
}>()

const emit = defineEmits<{
  activate: [instanceId: string]
  activateCard: [instanceId: string, activationId: string]
}>()

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#666666',
}

const SLOT_META: Record<string, { icon: string; label: string }> = {
  hand: { icon: '🖐', label: '手' },
  arcane: { icon: '🔮', label: '奥术' },
  accessory: { icon: '💍', label: '饰品' },
  body: { icon: '🧥', label: '身体' },
  ally: { icon: '👥', label: '盟友' },
  tarot: { icon: '🃏', label: '塔罗' },
}

const TRAIT_CN: Record<string, string> = {
  tome: '典籍',
  spell: '法术',
  ally: '盟友',
}

const slotBar = computed(() => {
  if (!props.slotStatus) return []
  const nameByInstance = new Map(
    (props.assets || []).map(a => [a.instance_id, a.name_cn || a.name])
  )
  return Object.entries(props.slotStatus)
    .filter(([, s]) => s.limit > 0)
    .map(([type, s]) => {
      const meta = SLOT_META[type] || { icon: '▫', label: type }
      const cardNames = s.cards
        .map(iid => nameByInstance.get(iid) || iid)
        .join('、')
      const restrictedNote = s.restricted > 0
        ? `（含${s.restricted}个${s.restricted_traits.map(t => TRAIT_CN[t] || t).join('/')}专用）`
        : ''
      return {
        type,
        icon: meta.icon,
        label: meta.label,
        used: s.used,
        limit: s.limit,
        full: s.used >= s.limit,
        title: `${meta.label}槽位 ${s.used}/${s.limit}${restrictedNote}${cardNames ? '\n占用：' + cardNames : ''}`,
      }
    })
})
</script>

<template>
  <div class="play-area">
    <!-- 槽位指示条 -->
    <div v-if="slotBar.length" class="slot-bar">
      <span
        v-for="slot in slotBar"
        :key="slot.type"
        class="slot-badge"
        :class="{ full: slot.full }"
        :title="slot.title"
      >{{ slot.icon }} {{ slot.used }}/{{ slot.limit }}</span>
    </div>
    <div class="play-label">场上支援 ({{ assets.length }})</div>
    <div class="play-cards">
      <div
        v-for="asset in assets"
        :key="asset.instance_id"
        class="asset-card"
        :class="{ exhausted: asset.exhausted }"
        :style="{ borderColor: CLASS_COLORS[asset.class] || CLASS_COLORS.neutral }"
      >
        <div class="asset-name" @click="emit('activate', asset.instance_id)">{{ asset.name_cn || asset.name }}</div>
        <div class="asset-info">
          <span v-if="asset.health != null" class="hp">♥{{ (asset.health ?? 0) - asset.damage }}/{{ asset.health }}</span>
          <span v-if="asset.sanity != null" class="san">☽{{ (asset.sanity ?? 0) - asset.horror }}/{{ asset.sanity }}</span>
        </div>
        <div v-if="asset.uses" class="asset-uses">
          <span v-for="(count, useType) in asset.uses" :key="useType" class="use-badge">
            {{ useType }}: {{ count }}
          </span>
        </div>
        <div v-if="asset.exhausted" class="exhausted-label">已消耗</div>
        <div v-if="asset.slots.length" class="asset-slots">{{ asset.slots.join(', ') }}</div>
        <div v-if="asset.activations?.length" class="asset-actions">
          <button
            v-for="act in asset.activations"
            :key="act.id"
            class="act-btn"
            :title="act.label"
            @click.stop="emit('activateCard', asset.instance_id, act.id)"
          >⚡{{ act.label }}</button>
        </div>
      </div>
      <div v-if="!assets.length" class="play-empty">无场上支援</div>
    </div>

    <!-- 威胁区（弱点卡） -->
    <template v-if="threatCards && threatCards.length">
      <div class="play-label threat-label">威胁区 ({{ threatCards.length }})</div>
      <div class="play-cards">
        <div
          v-for="card in threatCards"
          :key="card.instance_id"
          class="asset-card threat-card"
        >
          <div class="asset-name">{{ card.name_cn || card.name }}</div>
          <div v-if="card.uses" class="asset-uses">
            <span v-for="(count, useType) in card.uses" :key="useType" class="use-badge">
              {{ useType }}: {{ count }}
            </span>
          </div>
          <div v-if="card.activations?.length" class="asset-actions">
            <button
              v-for="act in card.activations"
              :key="act.id"
              class="act-btn threat-btn"
              :title="act.label"
              @click.stop="emit('activateCard', card.instance_id, act.id)"
            >⚡{{ act.label }}</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.play-area {
  display: flex;
  flex-direction: column;
}
.slot-bar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 2px 4px 6px;
}
.slot-badge {
  background: #23233a;
  border: 1px solid #3a3a55;
  border-radius: 4px;
  font-size: 11px;
  color: #b8b8d0;
  padding: 1px 6px;
  cursor: default;
  white-space: nowrap;
}
.slot-badge.full {
  border-color: #c0392b;
  color: #f0a090;
  background: #3a2328;
}
.play-label {
  font-size: 12px;
  color: #c0a060;
  font-weight: bold;
  margin-bottom: 6px;
  padding-left: 4px;
}
.play-cards {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px;
}
.asset-card {
  background: #1a1a2e;
  border: 2px solid #333344;
  border-radius: 6px;
  padding: 8px;
  min-width: 110px;
  max-width: 140px;
  font-size: 11px;
  color: #e0e0e0;
  cursor: pointer;
  transition: transform 0.15s, opacity 0.2s;
  flex-shrink: 0;
}
.asset-card:hover {
  transform: translateY(-2px);
}
.asset-card.exhausted {
  opacity: 0.5;
  transform: rotate(6deg);
}
.asset-name {
  font-weight: bold;
  font-size: 12px;
  margin-bottom: 4px;
  color: #fff;
}
.asset-info {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}
.hp { color: #e74c3c; }
.san { color: #3498db; }
.asset-uses {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.use-badge {
  background: #2a2a44;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  color: #c0a060;
}
.exhausted-label {
  color: #e74c3c;
  font-size: 10px;
  font-style: italic;
  margin-top: 4px;
}
.asset-slots {
  font-size: 10px;
  color: #666;
  margin-top: 2px;
}

.asset-actions {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
}

.act-btn {
  background: #2a3a52;
  border: 1px solid #4a6a9a;
  border-radius: 4px;
  color: #b8d4f0;
  font-size: 10px;
  padding: 2px 6px;
  cursor: pointer;
  text-align: left;
}

.act-btn:hover {
  background: #35486a;
  border-color: #6a9aca;
}

.threat-label {
  color: #c06a60;
  margin-top: 8px;
}

.threat-card {
  border-color: #8a3a34 !important;
}

.threat-btn {
  background: #4a2a2a;
  border-color: #8a4a44;
  color: #f0b8b0;
}

.threat-btn:hover {
  background: #5d3535;
}
.play-empty {
  color: #555;
  font-style: italic;
  font-size: 12px;
  padding: 8px;
}
</style>
