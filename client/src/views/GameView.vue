<script setup lang="ts">
import { watch, computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useSocket } from '../composables/useSocket'
import type { EncounterCardDisplay, GameEventData, PendingSkillTest, SkillTestAnimation } from '../state/types'

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
import MulliganModal from '../components/MulliganModal.vue'
import SkillTestOverlay from '../components/SkillTestOverlay.vue'
import DeckPanel from '../components/DeckPanel.vue'

const router = useRouter()
const store = useGameStore()
const socket = useSocket()

const state = computed(() => store.state)
const pendingChoice = computed(() => state.value?.pending_choice ?? null)
const lastEncounter = ref<EncounterCardDisplay | null>(null)
const skillTestAnimation = ref<SkillTestAnimation | null>(null)
const skillTestMode = ref<'commit' | 'spinning'>('commit')
let handledSkillTestKey = ''

// 技能检定投入卡牌面板
interface CommitRequest {
  skillType: string
  actionLabel: string
  actionType: string
  params: Record<string, unknown>
  pending?: PendingSkillTest
}
const commitRequest = ref<CommitRequest | null>(null)

watch([() => store.connected, () => state.value], ([connected, currentState]) => {
  if (connected && !currentState && router.currentRoute.value.name === 'game') {
    router.replace('/')
  }
}, { immediate: true })

function targetLabelForSkill(skillType: string): string {
  return skillType === 'combat'
    ? '敌人战斗值'
    : skillType === 'intellect'
      ? '地点隐蔽值'
      : skillType === 'willpower'
        ? '遭遇检定难度'
        : '检定难度'
}

function getSkillDifficulty(skillType: string, params: Record<string, unknown>): number {
  if (skillType === 'intellect') return state.value?.location.shroud ?? 0
  const enemyId = params.enemy_instance_id as string | undefined
  const enemy = enemyId ? state.value?.enemies.find(item => item.instance_id === enemyId) : null
  if (skillType === 'combat') return enemy?.fight ?? 0
  if (skillType === 'agility') return enemy?.evade ?? 0
  return 0
}

function getBaseSkill(skillType: string): number {
  const skills = store.investigatorDetail?.skills
  return skills?.[skillType as keyof typeof skills] ?? 0
}

function createSkillTestDraft(skillType: string, params: Record<string, unknown>, pending?: PendingSkillTest): SkillTestAnimation {
  const baseSkill = pending?.base_skill ?? getBaseSkill(skillType)
  const difficulty = pending?.difficulty ?? getSkillDifficulty(skillType, params)
  // 装备/盟友常数加值（服务端 dry-run 预览）
  const assetBonus = pending?.asset_bonus
    ?? state.value?.investigator.skill_bonuses?.[skillType]
    ?? 0
  return {
    investigator_id: pending?.investigator_id ?? state.value?.investigator.id,
    skill_type: skillType,
    difficulty,
    base_skill: baseSkill,
    asset_bonus: assetBonus,
    committed_icons: 0,
    token: '',
    token_modifier: 0,
    modified_skill: baseSkill + assetBonus,
    success: false,
    possible_tokens: pending?.possible_tokens ?? [],
    target_label: pending?.target_label ?? targetLabelForSkill(skillType),
    committed_card_ids: [],
  }
}

function openCommitModal(skillType: string, actionLabel: string, actionType: string, params: Record<string, unknown> = {}) {
  commitRequest.value = { skillType, actionLabel, actionType, params }
  skillTestAnimation.value = createSkillTestDraft(skillType, params)
  skillTestMode.value = 'commit'
}

function handleSkillRoll(payload: { committed: string[]; effectCardIds: string[]; weaponInstanceId?: string }) {
  const committed = payload.committed
  const req = commitRequest.value
  commitRequest.value = null
  if (!req) return

  const remaining = new Map<string, number>()
  for (const cardId of committed) {
    remaining.set(cardId, (remaining.get(cardId) || 0) + 1)
  }
  const committedIcons = state.value?.hand.reduce((sum, card) => {
      const count = remaining.get(card.id) || 0
      if (count <= 0) return sum
      remaining.set(card.id, count - 1)
      const icons = card.skill_icons || {}
      return sum + (icons[req.skillType] || 0) + (icons.wild || 0)
    }, 0) ?? 0

  if (skillTestAnimation.value) {
    skillTestAnimation.value = {
      ...skillTestAnimation.value,
      committed_card_ids: committed,
      committed_icons: committedIcons,
      modified_skill: skillTestAnimation.value.base_skill
        + (skillTestAnimation.value.asset_bonus ?? 0)
        + committedIcons,
    }
  }
  skillTestMode.value = 'spinning'
  socket.sendAction(req.actionType, {
    ...req.params,
    committed_cards: committed,
    effect_card_ids: payload.effectCardIds,
    ...(payload.weaponInstanceId ? { weapon_instance_id: payload.weaponInstanceId } : {}),
  })
}

function handleMulligan(cardIds: string[]) {
  socket.sendAction('MULLIGAN', { card_ids: cardIds })
}

// 槽位不足 → 选择弃置支援重试
const slotConflict = ref<SlotConflict | null>(null)

watch(() => store.lastActionResult, (result) => {
  if (result && !result.success && result.code === 'slots_full' && result.slot_conflict) {
    slotConflict.value = result.slot_conflict
  }
})

function handleSlotDiscardConfirm(discardIds: string[]) {
  const conflict = slotConflict.value
  slotConflict.value = null
  if (!conflict) return
  socket.sendAction('PLAY', { card_id: conflict.card_id, slot_discards: discardIds })
}

function handleSlotDiscardCancel() {
  slotConflict.value = null
}

function handleAdvanceAct() {
  socket.sendAction('ADVANCE_ACT')
}

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

function startSkillTestAnimation(events: GameEventData[]) {
  const reveal = events.find(event => event.event === 'CHAOS_TOKEN_REVEALED' && event.skill_type)
  if (!reveal?.chaos_token) return

  const resolved = events.find(event =>
    event.event === 'CHAOS_TOKEN_RESOLVED' &&
    event.investigator_id === reveal.investigator_id,
  )
  const outcome = events.find(event =>
    (event.event === 'SKILL_TEST_SUCCESSFUL' || event.event === 'SKILL_TEST_FAILED') &&
    event.investigator_id === reveal.investigator_id,
  )
  if (!outcome) return

  const key = `${reveal.investigator_id}:${reveal.skill_type}:${reveal.chaos_token}:${outcome.modified_skill}:${outcome.success}`
  if (key === handledSkillTestKey) return
  handledSkillTestKey = key
  skillTestMode.value = 'spinning'

  const targetLabel = reveal.skill_type === 'combat'
    ? '敌人战斗值'
    : reveal.skill_type === 'intellect'
      ? '地点隐蔽值'
      : '检定难度'

  const redrawnToken = outcome.rexs_curse_redrawn_token
  skillTestAnimation.value = {
    investigator_id: reveal.investigator_id,
    skill_type: reveal.skill_type,
    difficulty: reveal.difficulty ?? outcome.difficulty ?? 0,
    base_skill: reveal.base_skill ?? 0,
    committed_icons: reveal.committed_icons ?? 0,
    token: redrawnToken ?? reveal.chaos_token,
    token_modifier: outcome.rexs_curse_redrawn_modifier
      ?? resolved?.token_modifier
      ?? resolved?.amount
      ?? 0,
    modified_skill: outcome.modified_skill ?? 0,
    success: outcome.success ?? outcome.event === 'SKILL_TEST_SUCCESSFUL',
    auto_fail: outcome.auto_fail,
    auto_success: outcome.auto_success,
    asset_bonus: outcome.asset_bonus ?? 0,
    rexs_curse_redrawn_token: redrawnToken,
    rexs_curse_redrawn_modifier: outcome.rexs_curse_redrawn_modifier,
    possible_tokens: reveal.possible_tokens || [],
    target_label: targetLabel,
  }
}

function finishSkillTestAnimation() {
  skillTestAnimation.value = null
  skillTestMode.value = 'commit'
}

watch(() => store.pendingEvents, (events) => {
  if (events?.length) startSkillTestAnimation(events)
}, { deep: true })

let pendingSkillTestKey = ''
watch(() => state.value?.pending_skill_test, (pending) => {
  if (!pending) return
  const key = `${pending.investigator_id}:${pending.skill_type}:${pending.difficulty}`
  if (key === pendingSkillTestKey && skillTestAnimation.value) return
  pendingSkillTestKey = key
  commitRequest.value = {
    skillType: pending.skill_type,
    actionLabel: '遭遇检定',
    actionType: 'SKILL_TEST_ROLL',
    params: {},
    pending,
  }
  skillTestAnimation.value = createSkillTestDraft(pending.skill_type, {}, pending)
  skillTestMode.value = 'commit'
})

// Actions
function handleAction(type: string) {
  if (type === 'END_TURN') {
    socket.endTurn()
  } else if (type === 'INVESTIGATE') {
    openCommitModal('intellect', '调查', 'INVESTIGATE')
  } else if (type === 'FIGHT') {
    const engaged = state.value?.enemies.filter(e => e.engaged) || []
    if (engaged.length === 1) {
      openCommitModal('combat', '战斗', 'FIGHT', { enemy_instance_id: engaged[0].instance_id })
    } else if (engaged.length > 1) {
      store.addToast('请在敌人面板选择攻击目标', 'info')
    } else {
      store.addToast('没有交战中的敌人', 'info')
    }
  } else if (type === 'EVADE') {
    const engaged = state.value?.enemies.filter(e => e.engaged) || []
    if (engaged.length === 1) {
      openCommitModal('agility', '闪避', 'EVADE', { enemy_instance_id: engaged[0].instance_id })
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
  openCommitModal('combat', '战斗', 'FIGHT', { enemy_instance_id: enemyInstanceId })
}

function handleEvade(enemyInstanceId: string) {
  openCommitModal('agility', '闪避', 'EVADE', { enemy_instance_id: enemyInstanceId })
}

function handleEngage(enemyInstanceId: string) {
  socket.sendAction('ENGAGE', { enemy_instance_id: enemyInstanceId })
}

function handleActivate(instanceId: string) {
  socket.sendAction('ACTIVATE_ASSET', { instance_id: instanceId })
}

function handleActivateCard(instanceId: string, activationId: string, targetInstanceId?: string) {
  socket.sendAction('ACTIVATE_CARD', {
    instance_id: instanceId,
    activation_id: activationId,
    ...(targetInstanceId ? { target_instance_id: targetInstanceId } : {}),
  })
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
            :threat-cards="state.threat_cards || []"
            :slot-summary="state.investigator.slot_summary || []"
            class="game-play-area"
            @activate="handleActivate"
            @activate-card="handleActivateCard"
          />
          <div class="game-hand-actions">
            <HandArea
              :hand="state.hand"
              :resources="state.investigator.resources"
              @play-card="handlePlayCard"
            />
            <ActionBar class="game-action-bar" :state="state" @action="handleAction" />
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
        <DeckPanel :deck="state.deck_cards || []" :discard="state.discard || []" />
        <ScenarioPanel :state="state" @advance-act="handleAdvanceAct" />
      </div>
    </div>

    <!-- Modals -->
    <ChoiceModal :choice="pendingChoice" @choose="handleChoice" />
    <EncounterPopup :encounter="lastEncounter" @dismiss="dismissEncounter" />
    <MulliganModal
      v-if="state.mulligan_available"
      :hand="state.hand"
      @confirm="handleMulligan"
    />
    <SkillTestOverlay
      :test="skillTestAnimation"
      :hand="state.hand"
      :assets="state.play_area"
      :enemies="state.enemies"
      :resources="state.investigator.resources"
      :mode="skillTestMode"
      @roll="handleSkillRoll"
      @activate-card="handleActivateCard"
      @complete="finishSkillTestAnimation"
    />
    <SlotDiscardModal
      v-if="slotConflict"
      :conflict="slotConflict"
      @confirm="handleSlotDiscardConfirm"
      @cancel="handleSlotDiscardCancel"
    />
  </div>

  <!-- Loading state -->
  <div v-else class="game-loading">
    <div class="loading-content">
      <div class="loading-text">等待游戏状态...</div>
      <button class="return-lobby-button" type="button" @click="router.replace('/')">返回大厅</button>
    </div>
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
  max-height: min(62vh, 640px);
  overflow-y: auto;
  overflow-x: hidden;
}

.game-play-area {
  min-width: 0;
  width: 100%;
  flex: 0 0 auto;
  max-height: none;
  overflow: visible;
}

.game-hand-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  width: 100%;
  max-height: none;
  overflow: visible;
}

.game-action-bar {
  position: sticky;
  bottom: 0;
  z-index: 6;
  padding-top: 4px;
  background: #0a0a1a;
}

@media (max-width: 1050px) {
  .game-bottom {
    max-height: 480px;
  }
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

.loading-content {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 18px;
}

.return-lobby-button {
  padding: 8px 18px;
  border: 1px solid #5c527e;
  border-radius: 6px;
  background: #1a1a2e;
  color: #d7c98e;
  cursor: pointer;
  font-size: 13px;
}

.return-lobby-button:hover {
  border-color: #c0a060;
  background: #252347;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
</style>
