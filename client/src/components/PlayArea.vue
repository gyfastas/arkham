<script setup lang="ts">
import type { CardInstanceDisplay } from '../state/types'

defineProps<{ assets: CardInstanceDisplay[] }>()

const emit = defineEmits<{
  activate: [instanceId: string]
}>()

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#666666',
}
</script>

<template>
  <div class="play-area">
    <div class="play-label">场上支援 ({{ assets.length }})</div>
    <div class="play-cards">
      <div
        v-for="asset in assets"
        :key="asset.instance_id"
        class="asset-card"
        :class="{ exhausted: asset.exhausted }"
        :style="{ borderColor: CLASS_COLORS[asset.class] || CLASS_COLORS.neutral }"
        @click="emit('activate', asset.instance_id)"
      >
        <div class="asset-name">{{ asset.name_cn || asset.name }}</div>
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
      </div>
      <div v-if="!assets.length" class="play-empty">无场上支援</div>
    </div>
  </div>
</template>

<style scoped>
.play-area {
  display: flex;
  flex-direction: column;
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
.play-empty {
  color: #555;
  font-style: italic;
  font-size: 12px;
  padding: 8px;
}
</style>
