<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import DeckBuilder from '../components/DeckBuilder.vue'
import {
  CAMPAIGNS, INVESTIGATOR_GROUPS, DIFFICULTIES, DIFFICULTY_LABELS, TOKEN_LABELS,
} from '../data/meta'
import { CLASS_COLORS } from '../utils/labels'
import { localizeSymbolText } from '../utils/displayText'
import type { CampaignStateData } from '../state/types'

const router = useRouter()
const client = useSocket()
const store = useGameStore()

const phase = ref<'menu' | 'wizard' | 'deckbuilder'>('menu')
const wizardStep = ref(1)
const selectedCampaign = ref('core')
const selectedDifficulty = ref('standard')
const selectedInvestigator = ref('')
const starting = ref(false)

const campaign = computed(() => CAMPAIGNS.find(c => c.id === selectedCampaign.value)!)
const bagInfo = computed(() => store.chaosBagInfo)

const TOKEN_ORDER = ['+1', '0', '-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8',
  'skull', 'cultist', 'tablet', 'elder_thing', 'auto_fail', 'elder_sign']

const bagTokens = computed(() => {
  if (!bagInfo.value) return []
  return TOKEN_ORDER
    .filter(t => (bagInfo.value!.tokens[t] || 0) > 0)
    .map(t => ({ key: t, count: bagInfo.value!.tokens[t], ...(TOKEN_LABELS[t] || { icon: t, label: t }) }))
})

// --- 步骤控制 ---

function startNewCampaign() {
  wizardStep.value = 1
  phase.value = 'wizard'
}

function nextStep() {
  if (wizardStep.value === 1 && !selectedCampaign.value) return
  if (wizardStep.value === 2 && !selectedDifficulty.value) return
  if (wizardStep.value === 3) {
    if (!selectedInvestigator.value) {
      store.addToast('请先选择调查员', 'error')
      return
    }
    phase.value = 'deckbuilder'
    return
  }
  wizardStep.value++
}

function prevStep() {
  if (wizardStep.value > 1) wizardStep.value--
  else phase.value = 'menu'
}

// 难度或战役变化 → 刷新混乱袋说明
watch([selectedCampaign, selectedDifficulty, wizardStep], () => {
  if (phase.value === 'wizard' && wizardStep.value === 2) {
    client.getChaosBagInfo(selectedCampaign.value, selectedDifficulty.value)
  }
}, { immediate: false })

// --- 开局流程 ---

function startChapter(saveId: string, investigatorId: string) {
  if (starting.value) return
  starting.value = true
  const prevRoomCb = client.onRoomUpdate
  client.onRoomUpdate = () => {
    client.onRoomUpdate = prevRoomCb
    client.setupGame('', investigatorId, undefined, undefined, undefined, saveId)
  }
  client.createRoom()
}

function continueSave(saveId: string, investigatorId: string) {
  startChapter(saveId, investigatorId)
}

function onDeckConfirm(cards: string[]) {
  // 新战役：创建存档（第一章，0 XP），成功后开第一章
  const prevCb = client.onCampaignState
  client.onCampaignState = (state: CampaignStateData | null) => {
    client.onCampaignState = prevCb
    if (!state) return
    store.campaignState = state
    startChapter(state.save_id, state.investigator_id)
  }
  client.campaignNew({
    campaign_id: selectedCampaign.value,
    investigator_id: selectedInvestigator.value,
    difficulty: selectedDifficulty.value,
    deck_cards: cards,
  })
}

function onDeckBack() {
  phase.value = 'wizard'
  wizardStep.value = 3
}

// --- Socket ---

function handleStateUpdate(state: any, events?: any) {
  starting.value = false
  store.updateState(state, events)
  router.push('/game')
}

function handleCampaignList(saves: any[]) {
  store.campaignSaves = saves
}

function handleChaosBagInfo(info: any) {
  store.chaosBagInfo = info
}

onMounted(() => {
  client.onCampaignList = handleCampaignList
  client.onChaosBagInfo = handleChaosBagInfo
  client.onStateUpdate = handleStateUpdate
  client.campaignList()
})

onUnmounted(() => {
  if (client.onCampaignList === handleCampaignList) client.onCampaignList = null
  if (client.onChaosBagInfo === handleChaosBagInfo) client.onChaosBagInfo = null
  if (client.onStateUpdate === handleStateUpdate) client.onStateUpdate = null
})

function invName(id: string): string {
  for (const g of INVESTIGATOR_GROUPS) {
    const inv = g.investigators.find(i => i.id === id)
    if (inv) return store.language === 'zh-Hant' ? inv.name_hant : inv.name_cn
  }
  return id
}
</script>

<template>
  <div class="campaign-lobby">
    <div class="cl-header">
      <button class="btn-back" @click="phase === 'menu' ? router.push('/') : (phase === 'deckbuilder' ? onDeckBack() : prevStep())">
        ← 返回
      </button>
      <h2 class="cl-title">战役模式</h2>
    </div>

    <!-- ============ 主菜单：存档列表 + 新战役 ============ -->
    <div v-if="phase === 'menu'" class="menu">
      <div class="menu-section">
        <button class="btn-new" @click="startNewCampaign">＋ 新战役</button>
      </div>

      <div class="saves-section">
        <h3 class="section-title">继续战役</h3>
        <div v-if="store.campaignSaves.length === 0" class="empty">暂无战役存档</div>
        <div
          v-for="save in store.campaignSaves"
          :key="save.save_id"
          class="save-card"
          :class="{ complete: save.is_complete }"
          @click="!save.is_complete && continueSave(save.save_id, save.investigator_id)"
        >
          <div class="save-main">
            <span class="save-campaign">{{ save.campaign_name_cn }}</span>
            <span class="save-inv">{{ invName(save.investigator_id) }}</span>
          </div>
          <div class="save-meta">
            <span v-if="save.is_complete" class="done-tag">已完结</span>
            <span v-else>第 {{ save.scenario_index + 1 }} / {{ save.scenario_total }} 章</span>
            <span>{{ DIFFICULTY_LABELS[save.difficulty] || save.difficulty }}</span>
            <span>{{ save.xp }} XP</span>
            <span v-if="save.trauma_physical || save.trauma_mental" class="trauma">
              创伤 {{ save.trauma_physical }}/{{ save.trauma_mental }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ 新战役向导 ============ -->
    <div v-else-if="phase === 'wizard'" class="wizard">
      <div class="steps">
        <span :class="{ active: wizardStep === 1 }">1 战役</span>
        <span :class="{ active: wizardStep === 2 }">2 难度</span>
        <span :class="{ active: wizardStep === 3 }">3 调查员</span>
        <span>4 构筑卡组</span>
      </div>

      <!-- Step 1: 选战役 -->
      <div v-if="wizardStep === 1" class="step-body">
        <div
          v-for="c in CAMPAIGNS"
          :key="c.id"
          class="campaign-card"
          :class="{ selected: selectedCampaign === c.id }"
          @click="selectedCampaign = c.id"
        >
          <div class="campaign-name">{{ store.language === 'zh-Hant' ? c.name_hant : c.name_cn }}</div>
          <div class="campaign-chapters">共 {{ c.chapters.length }} 章：{{ c.chapters.map(ch => store.language === 'zh-Hant' ? ch.name_hant : ch.name_cn).join(' → ') }}</div>
        </div>
      </div>

      <!-- Step 2: 选难度 + 混乱袋说明 -->
      <div v-else-if="wizardStep === 2" class="step-body">
        <div class="diff-row">
          <button
            v-for="d in DIFFICULTIES"
            :key="d"
            class="diff-btn"
            :class="{ active: selectedDifficulty === d }"
            @click="selectedDifficulty = d"
          >
            {{ DIFFICULTY_LABELS[d] }}
          </button>
        </div>

        <div v-if="bagInfo" class="bag-panel">
          <h4 class="bag-title">
            {{ campaign.name_cn }} · {{ DIFFICULTY_LABELS[selectedDifficulty] }}难度混乱袋（{{ bagInfo.total }} 枚）
          </h4>
          <div class="bag-tokens">
            <span v-for="t in bagTokens" :key="t.key" class="bag-token" :class="{ symbol: !!t.label }">
              <span class="tk-icon">{{ t.icon }}</span>
              <span v-if="t.label" class="tk-label">{{ t.label }}</span>
              <span class="tk-count">×{{ t.count }}</span>
            </span>
          </div>
          <div v-if="Object.keys(bagInfo.symbol_texts || {}).length" class="bag-symbol-texts">
            <div v-for="(text, key) in bagInfo.symbol_texts" :key="key" class="symbol-text">
              {{ localizeSymbolText(text, store.language) }}
            </div>
          </div>
        </div>
      </div>

      <!-- Step 3: 选调查员 -->
      <div v-else-if="wizardStep === 3" class="step-body">
        <div v-for="g in INVESTIGATOR_GROUPS" :key="g.label" class="inv-group">
          <div class="inv-group-label">{{ g.label }}</div>
          <div class="inv-grid">
            <div
              v-for="inv in g.investigators"
              :key="inv.id"
              class="inv-card"
              :class="{ selected: selectedInvestigator === inv.id }"
              @click="selectedInvestigator = inv.id"
            >
              <span class="inv-dot" :style="{ background: CLASS_COLORS[inv.class] }"></span>
              {{ store.language === 'zh-Hant' ? inv.name_hant : inv.name_cn }}
            </div>
          </div>
        </div>
      </div>

      <div class="wizard-actions">
        <button class="btn-next" @click="nextStep">
          {{ wizardStep === 3 ? '去构筑卡组 →' : '下一步 →' }}
        </button>
      </div>
    </div>

    <!-- ============ Step 4: 构筑卡组（0 XP） ============ -->
    <DeckBuilder
      v-else-if="phase === 'deckbuilder'"
      :investigator-id="selectedInvestigator"
      :xp="0"
      auto-preset
      @confirm="onDeckConfirm"
      @back="onDeckBack"
    />
  </div>
</template>

<style scoped>
.campaign-lobby {
  width: 100vw;
  height: 100vh;
  background: #0a0a1a;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', sans-serif;
  overflow: hidden;
}

.cl-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: #0d0d20;
  border-bottom: 1px solid #1a1a2e;
}

.cl-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #ccc;
}

.btn-back {
  background: none;
  border: 1px solid #333;
  color: #aaa;
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-back:hover {
  background: #1a1a2e;
  color: #fff;
}

/* Menu */
.menu {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.menu-section {
  margin-bottom: 28px;
}

.btn-new {
  width: 100%;
  padding: 18px;
  font-size: 17px;
  font-weight: 600;
  background: #1a2e1a;
  border: 2px solid #27ae60;
  color: #2ecc71;
  border-radius: 10px;
  cursor: pointer;
}

.btn-new:hover {
  background: #20401f;
}

.section-title {
  font-size: 15px;
  color: #999;
  margin: 0 0 12px;
}

.empty {
  color: #555;
  text-align: center;
  padding: 30px 0;
}

.save-card {
  background: #12122a;
  border: 1px solid #2a2a4e;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.save-card:hover {
  border-color: #c0a060;
}

.save-card.complete {
  opacity: 0.5;
  cursor: default;
}

.save-main {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 6px;
}

.save-campaign {
  font-size: 16px;
  font-weight: 600;
  color: #e0d0a0;
}

.save-inv {
  font-size: 13px;
  color: #999;
}

.save-meta {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #777;
}

.done-tag {
  color: #c0a060;
}

.trauma {
  color: #c0392b;
}

/* Wizard */
.wizard {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.steps {
  display: flex;
  gap: 18px;
  margin-bottom: 24px;
  font-size: 13px;
  color: #555;
}

.steps .active {
  color: #c0a060;
  font-weight: 600;
}

.step-body {
  margin-bottom: 24px;
}

.campaign-card {
  background: #12122a;
  border: 2px solid #2a2a4e;
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 12px;
  cursor: pointer;
}

.campaign-card.selected {
  border-color: #c0a060;
}

.campaign-name {
  font-size: 17px;
  font-weight: 600;
  color: #e0d0a0;
  margin-bottom: 6px;
}

.campaign-chapters {
  font-size: 12px;
  color: #777;
  line-height: 1.6;
}

.diff-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.diff-btn {
  flex: 1;
  padding: 12px;
  background: #1a1a2e;
  border: 2px solid #2a2a4e;
  color: #aaa;
  border-radius: 8px;
  cursor: pointer;
  font-size: 15px;
}

.diff-btn.active {
  border-color: #c0a060;
  color: #e0d0a0;
  font-weight: 600;
}

.bag-panel {
  background: #101024;
  border: 1px solid #2a2a4e;
  border-radius: 10px;
  padding: 16px 18px;
}

.bag-title {
  font-size: 14px;
  color: #c0a060;
  margin: 0 0 12px;
}

.bag-tokens {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.bag-token {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 13px;
}

.bag-token.symbol {
  border-color: #6a5a2e;
}

.tk-icon {
  font-weight: 700;
  color: #ddd;
}

.tk-label {
  color: #999;
  font-size: 12px;
}

.tk-count {
  color: #777;
  font-size: 12px;
}

.bag-symbol-texts {
  border-top: 1px solid #1a1a2e;
  padding-top: 10px;
}

.symbol-text {
  font-size: 12px;
  color: #888;
  line-height: 1.7;
  white-space: pre-line;
}

.inv-group {
  margin-bottom: 18px;
}

.inv-group-label {
  font-size: 13px;
  color: #777;
  margin-bottom: 8px;
}

.inv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.inv-card {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #12122a;
  border: 2px solid #2a2a4e;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 14px;
}

.inv-card.selected {
  border-color: #c0a060;
}

.inv-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.wizard-actions {
  display: flex;
  justify-content: flex-end;
}

.btn-next {
  padding: 12px 32px;
  background: #27ae60;
  border: none;
  color: #fff;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.btn-next:hover {
  background: #2ecc71;
}
</style>
