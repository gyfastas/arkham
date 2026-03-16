<script setup lang="ts">
import { computed } from 'vue'
import type { LocationDisplay } from '../state/types'

const props = defineProps<{
  locations: Record<string, LocationDisplay>
  currentLocationId: string
}>()

const emit = defineEmits<{
  move: [locationId: string]
}>()

/** Check if a location ID is connected to the current location */
function isConnectedById(locId: string): boolean {
  const current = props.locations[props.currentLocationId]
  if (!current) return false
  // connections are stored as location IDs
  return current.connections.includes(locId) || props.locations[locId]?.connections.includes(props.currentLocationId)
}

/** Build a name lookup: locId → display name */
const nameById = computed(() => {
  const m: Record<string, string> = {}
  for (const [id, loc] of Object.entries(props.locations)) {
    m[id] = loc.name_cn || loc.name
  }
  return m
})

function handleClick(locId: string, loc: LocationDisplay) {
  if (!loc.is_current && isConnectedById(locId)) {
    emit('move', locId)
  }
}
</script>

<template>
  <div class="map-area">
    <div class="map-title">地图</div>
    <div class="map-grid">
      <div
        v-for="(loc, locId) in locations"
        :key="locId"
        class="location-node"
        :class="{
          current: loc.is_current,
          connected: !loc.is_current && isConnectedById(String(locId)),
          unreachable: !loc.is_current && !isConnectedById(String(locId)),
        }"
        @click="handleClick(String(locId), loc)"
      >
        <div class="loc-header">
          <div class="loc-name">{{ loc.name_cn || loc.name }}</div>
          <div class="loc-badge current-badge" v-if="loc.is_current">当前</div>
          <div class="loc-badge move-badge" v-else-if="isConnectedById(String(locId))">可移动</div>
        </div>
        <div class="loc-stats">
          <span class="shroud" title="帷幕值 (调查难度)">
            <span class="stat-label">帷幕</span>
            <span class="stat-val">{{ loc.shroud }}</span>
          </span>
          <span class="clues" title="剩余线索数">
            <span class="stat-label">线索</span>
            <span class="stat-val">{{ loc.clues }}</span>
          </span>
        </div>
        <div v-if="loc.enemies_here > 0" class="loc-enemies">
          👹×{{ loc.enemies_here }}
        </div>
        <div v-if="loc.connections.length" class="loc-connections">
          <span class="conn-label">连接:</span>
          <span
            v-for="connId in loc.connections"
            :key="connId"
            class="conn-tag"
            :class="{ 'conn-current': connId === currentLocationId }"
          >{{ nameById[connId] || connId }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-area {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.map-title {
  padding: 8px 12px;
  font-weight: bold;
  font-size: 13px;
  color: #c0a060;
  border-bottom: 1px solid #333344;
}
.map-grid {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  align-content: flex-start;
  overflow-y: auto;
}
.location-node {
  background: #1a1a2e;
  border: 2px solid #333344;
  border-radius: 8px;
  padding: 10px;
  min-width: 150px;
  max-width: 220px;
  flex: 1 0 150px;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
}
.location-node.current {
  border-color: #c0a060;
  box-shadow: 0 0 12px rgba(192, 160, 96, 0.4);
  background: #1e1e38;
}
.location-node.connected {
  border-color: #4a6fa5;
  cursor: pointer;
}
.location-node.connected:hover {
  border-color: #c0a060;
  box-shadow: 0 0 8px rgba(192, 160, 96, 0.25);
  transform: translateY(-2px);
}
.location-node.unreachable {
  opacity: 0.5;
}
.loc-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.loc-name {
  font-weight: bold;
  color: #e0e0e0;
  font-size: 13px;
  flex: 1;
}
.loc-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  flex-shrink: 0;
}
.current-badge {
  background: #c0a060;
  color: #0a0a1a;
}
.move-badge {
  background: #2980b9;
  color: #fff;
}
.loc-stats {
  display: flex;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
}
.shroud, .clues {
  display: flex;
  align-items: center;
  gap: 3px;
}
.stat-label {
  font-size: 10px;
  color: #777;
}
.shroud .stat-val {
  color: #9b59b6;
  font-weight: bold;
  background: #1e1030;
  padding: 0 5px;
  border-radius: 3px;
  font-size: 13px;
}
.clues .stat-val {
  color: #f1c40f;
  font-weight: bold;
  background: #1e1a10;
  padding: 0 5px;
  border-radius: 3px;
  font-size: 13px;
}
.loc-enemies {
  font-size: 12px;
  color: #e74c3c;
  margin-top: 4px;
}
.loc-connections {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  margin-top: 6px;
}
.conn-label {
  font-size: 10px;
  color: #666;
}
.conn-tag {
  font-size: 10px;
  color: #999;
  background: #111122;
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid #222244;
}
.conn-tag.conn-current {
  border-color: #c0a060;
  color: #c0a060;
}
</style>
