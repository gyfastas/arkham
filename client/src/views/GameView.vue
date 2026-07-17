<script setup lang="ts">
import { watch, computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useSocket } from '../composables/useSocket'
import type { EncounterCardDisplay } from '../state/types'

import HUD from '../components/HUD.vue'
import LogPanel from '../components/LogPanel.vue'
import MapArea from '../components/MapArea.vue'
import HandArea from '../components/HandArea.vue'
import PlayArea from '../components/PlayArea.vue'
import EnemyPanel from '../components/EnemyPanel.vue'
import ScenarioPanel from '../components/ScenarioPanel.vue'
import ActionBar from '../components/ActionBar.vue'
import ChoiceModal from '../components/ChoiceModal.vue'
import EncounterPopup from '../components/EncounterPopup.vue'

const router = useRouter()
const store = useGameStore()
const socket = useSocket()

const state = computed(() => store.state)
const pendingChoice = computed(() => state.value?.pending_choice ?? null)
const lastEncounter = ref<EncounterCardDisplay | null>(null)

// Navigate to game over screen
watch(() => store.gameOver, (go) => {
  if (go) {
    router.push('/gameover')
  }
})

// Track encounter card popups
watch(() => state.value?.last_encounter, (enc) => {
  if (enc) {
    lastEncounter.value = enc
  }
})

function dismissEncounter() {
  lastEncounter.value = null
}

// Actions
function handleAction(type: string) {
  if (type === 'END_TURN') {
    socket.endTurn()
  } else if (type === 'FIGHT') {
    const engaged = state.value?.enemies.filter(e => e.engaged) || []
    if (engaged.length === 1) {
      socket.sendAction('FIGHT', { enemy_instance_id: engaged[0].instance_id })
    } else if (engaged.length > 1) {
      store.addToast('请在敌人面板选择攻击目标', 'info')
    } else {
      store.addToast('没有交战中的敌人', 'info')
    }
  } else if (type === 'EVADE') {
    const engaged = state.value?.enemies.filter(e => e.engaged) || []
    if (engaged.length === 1) {
      socket.sendAction('EVADE', { enemy_instance_id: engaged[0].instance_id })
    } else if (engaged.length > 1) {
      store.addToast('请在敌人面板选择闪避目标', 'info')
    } else {
      store.addToast('没有交战中的敌人', 'info')
    }
  } else if (type === 'ENGAGE') {
    const unengaged = state.value?.enemies.filter(e => !e.engaged) || []
    if (unengaged.length === 1) {
      socket.sendAction('ENGAGE', { enemy_instance_id: unengaged[0].instance_id })
    } else if (unengaged.length > 1) {
      store.addToast('请在敌人面板选择交战目标', 'info')
    } else {
      store.addToast('没有可交战的敌人', 'info')
    }
  } else {
    socket.sendAction(type)
  }
}

function handlePlayCard(cardId: string) {
  socket.sendAction('PLAY', { card_id: cardId })
}

function handleMove(locationId: string) {
  socket.sendAction('MOVE', { location_id: locationId })
}

function handleAttack(enemyInstanceId: string) {
  socket.sendAction('FIGHT', { enemy_instance_id: enemyInstanceId })
}

function handleEvade(enemyInstanceId: string) {
  socket.sendAction('EVADE', { enemy_instance_id: enemyInstanceId })
}

function handleEngage(enemyInstanceId: string) {
  socket.sendAction('ENGAGE', { enemy_instance_id: enemyInstanceId })
}

function handleActivate(instanceId: string) {
  socket.sendAction('ACTIVATE_ASSET', { instance_id: instanceId })
}

function handleChoice(optionId: string) {
  socket.resolveChoice(optionId)
}
</script>

<template>
  <div v-if="state" class="game-view">
    <!-- Top HUD -->
    <HUD :state="state" class="game-hud" />

    <!-- Main content area -->
    <div class="game-main">
      <!-- Left: Log -->
      <LogPanel :log="state.log" class="game-log" />

      <!-- Center: Map + Bottom panels -->
      <div class="game-center">
        <MapArea
          :locations="state.locations"
          :current-location-id="state.location.id"
          class="game-map"
          @move="handleMove"
        />
        <div class="game-bottom">
          <PlayArea
            :assets="state.play_area"
            class="game-play-area"
            @activate="handleActivate"
          />
          <div class="game-hand-actions">
            <HandArea
              :hand="state.hand"
              @play-card="handlePlayCard"
            />
            <ActionBar :state="state" @action="handleAction" />
          </div>
        </div>
      </div>

      <!-- Right: Enemies + Scenario -->
      <div class="game-right">
        <EnemyPanel
          :enemies="state.enemies"
          @attack="handleAttack"
          @evade="handleEvade"
          @engage="handleEngage"
        />
        <ScenarioPanel :state="state" />
      </div>
    </div>

    <!-- Modals -->
    <ChoiceModal :choice="pendingChoice" @choose="handleChoice" />
    <EncounterPopup :encounter="lastEncounter" @dismiss="dismissEncounter" />
  </div>

  <!-- Loading state -->
  <div v-else class="game-loading">
    <div class="loading-text">等待游戏状态...</div>
  </div>
</template>

<style scoped>
.game-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0a1a;
  color: #e0e0e0;
  overflow: hidden;
}

.game-hud {
  flex-shrink: 0;
}

.game-main {
  flex: 1;
  display: grid;
  grid-template-columns: 220px 1fr 240px;
  grid-template-rows: minmax(0, 1fr);
  overflow: hidden;
}

.game-main > * {
  min-height: 0;
  min-width: 0;
}

.game-log {
  min-width: 0;
  overflow-y: auto;
}

.game-center {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid #333344;
  border-right: 1px solid #333344;
}

.game-map {
  flex: 1;
  overflow-y: auto;
}

.game-bottom {
  flex-shrink: 0;
  border-top: 1px solid #333344;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
}

.game-play-area {
  flex-shrink: 0;
}

.game-hand-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.game-right {
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
  background: #1a1a2e;
}

.game-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #0a0a1a;
}

.loading-text {
  color: #c0a060;
  font-size: 18px;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
</style>
