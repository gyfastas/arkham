<template>
  <div class="gameover">
    <!-- 升级卡组模式（全屏） -->
    <DeckBuilder
      v-if="upgrading && store.campaignState"
      :investigator-id="store.campaignState.investigator_id"
      :xp="store.campaignState.xp"
      mode="upgrade"
      :initial-deck="store.campaignState.deck"
      @confirm="onUpgradeConfirm"
      @back="upgrading = false"
    />

    <div v-else class="panel">
      <div class="icon">{{ isWin ? '🏆' : '💀' }}</div>
      <h1 :class="isWin ? 'win' : 'lose'">
        {{ isWin ? '调查成功' : '调查失败' }}
      </h1>
      <p class="message">{{ message }}</p>

      <!-- 战役结算 -->
      <div v-if="campaign" class="xp-summary">
        <h3>战役结算 · {{ DIFFICULTY_LABELS[campaign.difficulty] || campaign.difficulty }}难度</h3>
        <p>本章获得经验: +{{ chapterXp }} XP</p>
        <p>可用经验: {{ campaign.xp }} XP（累计获得 {{ campaign.xp_earned }} / 已花费 {{ campaign.xp_spent }}）</p>
        <p v-if="campaign.trauma_physical || campaign.trauma_mental" class="trauma">
          创伤：身体 {{ campaign.trauma_physical }} / 精神 {{ campaign.trauma_mental }}
        </p>
        <p v-if="upgradeMsg" class="upgrade-msg">{{ upgradeMsg }}</p>
      </div>

      <div class="actions">
        <template v-if="campaign">
          <button v-if="!campaign.is_complete" @click="upgrading = true">升级卡牌（{{ campaign.xp }} XP）</button>
          <button v-if="!campaign.is_complete" class="primary" :disabled="advancing" @click="nextChapter">
            {{ advancing ? '进入中…' : '进入下一章 →' }}
          </button>
          <div v-else class="campaign-complete">🎉 战役已完结！</div>
        </template>
        <button @click="backToHome">{{ campaign ? '返回主页' : '返回大厅' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import DeckBuilder from '../components/DeckBuilder.vue'
import { DIFFICULTY_LABELS } from '../data/meta'
import type { CampaignStateData } from '../state/types'

const router = useRouter()
const client = useSocket()
const store = useGameStore()

const isWin = computed(() => store.gameOver?.type === 'win')
const message = computed(() => store.gameOver?.message || '游戏结束')
const campaign = computed(() => store.campaignState)

const upgrading = ref(false)
const advancing = ref(false)
const upgradeMsg = ref('')
const xpBefore = ref<number | null>(null)

const chapterXp = computed(() => {
  if (!campaign.value) return 0
  if (xpBefore.value === null) return campaign.value.xp_earned
  return campaign.value.xp_earned - xpBefore.value
})

function onUpgradeConfirm(newDeck: string[]) {
  if (!campaign.value) return
  client.campaignUpgradeDeck(campaign.value.save_id, newDeck)
}

function nextChapter() {
  if (!campaign.value || advancing.value) return
  advancing.value = true
  // 推进章节 → 拿到新状态后开下一章
  const prevCb = client.onCampaignState
  client.onCampaignState = (state: CampaignStateData | null) => {
    client.onCampaignState = prevCb
    if (!state) return
    store.campaignState = state
    const prevRoomCb = client.onRoomUpdate
    client.onRoomUpdate = () => {
      client.onRoomUpdate = prevRoomCb
      client.setupGame('', state.investigator_id, undefined, undefined, undefined, state.save_id)
    }
    client.createRoom()
  }
  client.campaignContinue(campaign.value.save_id, true)
}

function handleStateUpdate(state: any, events?: any) {
  advancing.value = false
  store.updateState(state, events)
  router.push('/game')
}

function handleCampaignState(state: CampaignStateData | null) {
  if (!state) return
  const prev = store.campaignState
  if (prev && state.xp_spent > prev.xp_spent) {
    upgradeMsg.value = `已花费 ${state.xp_spent - prev.xp_spent} XP 升级牌组`
    upgrading.value = false
  }
  store.campaignState = state
}

function backToHome() {
  store.reset()
  router.push('/')
}

onMounted(() => {
  xpBefore.value = store.campaignState ? store.campaignState.xp_earned : null
  // 刷新战役结算（服务端已在游戏结束时结算并写盘）
  if (store.campaignState) client.getCampaignState()
  const prevCb = client.onCampaignState
  client.onCampaignState = (state: CampaignStateData | null) => {
    handleCampaignState(state)
    if (typeof prevCb === 'function') prevCb(state)
  }
  client.onStateUpdate = handleStateUpdate
})

onUnmounted(() => {
  if (client.onStateUpdate === handleStateUpdate) client.onStateUpdate = null
})
</script>

<style scoped>
.gameover {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a1a;
}
.panel {
  background: #1a1a2e;
  border: 2px solid #333344;
  border-radius: 12px;
  padding: 48px 64px;
  text-align: center;
  max-width: 520px;
}
.icon {
  font-size: 64px;
  margin-bottom: 16px;
}
h1 {
  font-size: 28px;
  margin-bottom: 12px;
}
h1.win { color: #c0a060; }
h1.lose { color: #e74c3c; }
.message {
  color: #aaa;
  font-size: 15px;
  margin-bottom: 24px;
  line-height: 1.5;
}
.xp-summary {
  background: #111122;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
  text-align: left;
}
.xp-summary h3 {
  color: #c0a060;
  font-size: 14px;
  margin-bottom: 8px;
}
.xp-summary p {
  color: #aaa;
  font-size: 13px;
  margin: 4px 0;
}
.xp-summary .trauma {
  color: #e74c3c;
}
.upgrade-msg {
  color: #2ecc71 !important;
}
.actions {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}
.campaign-complete {
  color: #c0a060;
  font-size: 16px;
  padding: 8px;
}
button {
  padding: 10px 32px;
  font-size: 15px;
  background: #2a2a4e;
  border: 1px solid #c0a060;
  color: #c0a060;
  border-radius: 6px;
  cursor: pointer;
  min-width: 220px;
}
button:hover:not(:disabled) {
  background: #3a3a6e;
}
button.primary {
  background: #27ae60;
  border-color: #27ae60;
  color: #fff;
}
button.primary:hover:not(:disabled) {
  background: #2ecc71;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
