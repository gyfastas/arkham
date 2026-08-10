<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LocationAttachment, LocationDisplay, EnemyDisplay } from '../state/types'
import { useGameStore } from '../stores/game'
import { localizeDisplayText } from '../utils/displayText'
import { traitsLabel } from '../utils/labels'

/** 队友地图标记（由 GameView 从 other_investigators 换算） */
export interface TeammateMarker {
  name: string
  location_id: string
  active: boolean
  defeated: boolean
}

const props = withDefaults(defineProps<{
  locations: Record<string, LocationDisplay>
  currentLocationId: string
  teammates?: TeammateMarker[]
}>(), {
  teammates: () => [],
})

const emit = defineEmits<{
  move: [locationId: string]
  unlockDoor: [skill: string]
}>()
const store = useGameStore()

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
    m[id] = localizeDisplayText(loc.name_cn || loc.name, store.language)
  }
  return m
})

/** locId → 该地点的队友标记 */
const teammatesByLoc = computed(() => {
  const m: Record<string, TeammateMarker[]> = {}
  for (const tm of props.teammates) {
    if (!tm.location_id) continue
    ;(m[tm.location_id] ||= []).push(tm)
  }
  return m
})

function handleClick(locId: string, loc: LocationDisplay) {
  if (!loc.is_current && isConnectedById(locId)) {
    emit('move', locId)
  }
}

// --- 敌人详情弹窗 ---
const enemyPopupLoc = ref<string | null>(null)
const enemyPopupList = computed<EnemyDisplay[]>(() => {
  if (!enemyPopupLoc.value) return []
  return props.locations[enemyPopupLoc.value]?.enemy_list || []
})

function openEnemyPopup(locId: string) {
  enemyPopupLoc.value = locId
}

function enemyText(e: EnemyDisplay): string {
  return localizeDisplayText(e.text_cn || e.text || '', store.language)
}

// --- 附属卡详情弹窗 ---
const attachPopup = ref<{ locId: string; card: LocationAttachment } | null>(null)

function openAttachPopup(locId: string, card: LocationAttachment) {
  attachPopup.value = { locId, card }
}

function attachText(card: LocationAttachment): string {
  return localizeDisplayText(card.text_cn || card.text || '', store.language)
}

const attachIsCurrent = computed(() => attachPopup.value?.locId === props.currentLocationId)
</script>

<template>
  <div class="map-area">
    <div class="map-title">{{ store.language === 'zh-Hant' ? '地圖' : '地图' }}</div>
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
          <div class="loc-name">{{ localizeDisplayText(loc.name_cn || loc.name, store.language) }}</div>
          <div class="loc-badge current-badge" v-if="loc.is_current">{{ store.language === 'zh-Hant' ? '當前' : '当前' }}</div>
          <div class="loc-badge move-badge" v-else-if="isConnectedById(String(locId))">{{ store.language === 'zh-Hant' ? '可移動' : '可移动' }}</div>
        </div>
        <div class="loc-stats">
          <span class="shroud" title="帷幕值 (调查难度)">
            <span class="stat-label">{{ store.language === 'zh-Hant' ? '帷幕' : '帷幕' }}</span>
            <span class="stat-val">{{ loc.shroud }}</span>
          </span>
          <span class="clues" title="剩余线索数">
            <span class="stat-label">{{ store.language === 'zh-Hant' ? '線索' : '线索' }}</span>
            <span class="stat-val">{{ loc.clues }}</span>
          </span>
        </div>
        <div class="loc-markers">
          <div
            v-for="tm in (teammatesByLoc[String(locId)] || [])"
            :key="tm.name"
            class="loc-teammate"
            :class="{ active: tm.active, defeated: tm.defeated }"
            :title="tm.defeated ? '已被击败' : (tm.active ? '正在行动' : '队友所在地点')"
          >
            🧑 {{ tm.name }}
          </div>
          <div
            v-if="loc.enemies_here > 0"
            class="loc-enemies clickable"
            title="点击查看敌人详情"
            @click.stop="openEnemyPopup(String(locId))"
          >
            👹×{{ loc.enemies_here }}
          </div>
          <div
            v-for="att in (loc.attachments || [])"
            :key="att.instance_id"
            class="loc-attachment clickable"
            title="点击查看附属卡详情"
            @click.stop="openAttachPopup(String(locId), att)"
          >
            📎 {{ localizeDisplayText(att.name_cn || att.name, store.language) }}
          </div>
        </div>
        <div v-if="loc.connections.length" class="loc-connections">
            <span class="conn-label">{{ store.language === 'zh-Hant' ? '連接:' : '连接:' }}</span>
          <span
            v-for="connId in loc.connections"
            :key="connId"
            class="conn-tag"
            :class="{ 'conn-current': connId === currentLocationId }"
          >{{ nameById[connId] || connId }}</span>
        </div>
      </div>
    </div>

    <!-- 敌人详情弹窗 -->
    <Teleport to="body">
      <div v-if="enemyPopupLoc" class="popup-overlay" @click.self="enemyPopupLoc = null">
        <div class="popup-modal">
          <div class="popup-header">
            <span class="popup-title">{{ nameById[enemyPopupLoc] || enemyPopupLoc }} 的敌人</span>
            <button class="popup-close" @click="enemyPopupLoc = null">✕</button>
          </div>
          <div class="popup-body">
            <div v-for="e in enemyPopupList" :key="e.instance_id" class="enemy-card">
              <div class="ec-name">
                {{ localizeDisplayText(e.name_cn || e.name, store.language) }}
                <span v-if="e.exhausted" class="ec-badge">已消耗</span>
              </div>
              <div class="ec-stats">
                <span title="战斗">⚔ {{ e.fight }}</span>
                <span title="生命">♥ {{ e.health - e.current_damage }}/{{ e.health }}</span>
                <span title="闪避">🏃 {{ e.evade }}</span>
                <span title="伤害">🗡 {{ e.damage_dealt }}</span>
                <span title="恐惧">🧠 {{ e.horror_dealt }}</span>
                <span v-if="e.doom" title="毁灭">☠ {{ e.doom }}</span>
              </div>
              <div v-if="e.traits?.length" class="ec-traits">{{ traitsLabel(e.traits) }}</div>
              <div v-if="e.keywords?.length" class="ec-keywords">
                <span v-for="k in e.keywords" :key="k" class="ec-kw">{{ traitsLabel(k) }}</span>
              </div>
              <div v-if="enemyText(e)" class="ec-text">{{ enemyText(e) }}</div>
            </div>
            <div v-if="!enemyPopupList.length" class="popup-empty">没有敌人</div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 附属卡详情弹窗 -->
    <Teleport to="body">
      <div v-if="attachPopup" class="popup-overlay" @click.self="attachPopup = null">
        <div class="popup-modal">
          <div class="popup-header">
            <span class="popup-title">
              {{ localizeDisplayText(attachPopup.card.name_cn || attachPopup.card.name, store.language) }}
              <span class="popup-sub">附属：{{ nameById[attachPopup.locId] || attachPopup.locId }}</span>
            </span>
            <button class="popup-close" @click="attachPopup = null">✕</button>
          </div>
          <div class="popup-body">
            <div v-if="attachPopup.card.traits?.length" class="ec-traits">{{ traitsLabel(attachPopup.card.traits) }}</div>
            <div v-if="attachText(attachPopup.card)" class="ec-text">{{ attachText(attachPopup.card) }}</div>
            <div v-if="attachPopup.card.id === 'locked_door' && attachIsCurrent" class="attach-actions">
              <button class="unlock-btn" @click="emit('unlockDoor', 'combat'); attachPopup = null">⚔ 战斗检定（3）</button>
              <button class="unlock-btn" @click="emit('unlockDoor', 'agility'); attachPopup = null">🏃 敏捷检定（3）</button>
            </div>
            <div v-else-if="attachPopup.card.id === 'locked_door'" class="attach-hint">需要移动到该地点才能开锁</div>
          </div>
        </div>
      </div>
    </Teleport>
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
.loc-markers {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.loc-enemies {
  font-size: 12px;
  color: #e74c3c;
}

.loc-teammate {
  font-size: 11px;
  color: #7ec8e3;
  background: #12202e;
  border: 1px solid #2a4a5e;
  border-radius: 3px;
  padding: 1px 6px;
}

.loc-teammate.active {
  border-color: #c0a060;
  color: #c0a060;
}

.loc-teammate.defeated {
  opacity: 0.5;
  text-decoration: line-through;
}

.clickable {
  cursor: pointer;
}

.clickable:hover {
  text-decoration: underline;
}

.loc-attachment {
  font-size: 11px;
  color: #d4a017;
  background: #1e1a10;
  border: 1px solid #4a3a10;
  border-radius: 3px;
  padding: 1px 6px;
}

/* Popups */
.popup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1500;
}

.popup-modal {
  background: #14142b;
  border: 1px solid #333355;
  border-radius: 10px;
  width: 420px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.7);
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #1a1a2e;
}

.popup-title {
  font-size: 15px;
  font-weight: 600;
  color: #e0d0a0;
}

.popup-sub {
  font-size: 11px;
  color: #777;
  margin-left: 8px;
  font-weight: 400;
}

.popup-close {
  background: none;
  border: none;
  color: #888;
  font-size: 15px;
  cursor: pointer;
}

.popup-close:hover {
  color: #fff;
}

.popup-body {
  overflow-y: auto;
  padding: 12px 16px;
}

.enemy-card {
  background: #0d0d20;
  border: 1px solid #2a2a4e;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.ec-name {
  font-size: 14px;
  font-weight: 600;
  color: #eee;
  margin-bottom: 4px;
}

.ec-badge {
  font-size: 10px;
  color: #999;
  border: 1px solid #444;
  border-radius: 3px;
  padding: 0 4px;
  margin-left: 6px;
  font-weight: 400;
}

.ec-stats {
  display: flex;
  gap: 10px;
  font-size: 13px;
  color: #ccc;
  margin-bottom: 4px;
}

.ec-traits {
  font-size: 11px;
  color: #8a9;
  margin-bottom: 3px;
}

.ec-keywords {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.ec-kw {
  font-size: 10px;
  color: #d4a017;
  border: 1px solid #4a3a10;
  border-radius: 3px;
  padding: 0 5px;
}

.ec-text {
  font-size: 12px;
  color: #999;
  line-height: 1.6;
  white-space: pre-line;
}

.popup-empty {
  text-align: center;
  color: #555;
  padding: 24px 0;
}

.attach-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.unlock-btn {
  flex: 1;
  background: #1a2e1a;
  border: 1px solid #27ae60;
  color: #2ecc71;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.unlock-btn:hover {
  background: #20401f;
}

.attach-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #777;
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
