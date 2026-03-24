<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import DeckBuilder from '../components/DeckBuilder.vue'

const router = useRouter()
const client = useSocket()
const store = useGameStore()

const phase = ref<'setup' | 'deckbuilder'>('setup')
const customDeckCards = ref<string[]>([])

// --- Data ---

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#888',
}

interface ScenarioEntry { id: string; name_cn: string }
interface InvestigatorEntry { id: string; name_cn: string; class: string }

const scenarioGroups: { label: string; scenarios: ScenarioEntry[] }[] = [
  {
    label: '核心包',
    scenarios: [
      { id: 'the_gathering', name_cn: '聚集' },
      { id: 'the_midnight_masks', name_cn: '午夜假面' },
      { id: 'the_devourer_below', name_cn: '噬灭万物' },
    ],
  },
  {
    label: '敦威治遗产',
    scenarios: [
      { id: 'extracurricular_activity', name_cn: '课外活动' },
      { id: 'the_house_always_wins', name_cn: '赌场必胜' },
      { id: 'the_miskatonic_museum', name_cn: '米斯卡塔尼克博物馆' },
      { id: 'essex_county_express', name_cn: '埃塞克斯快车' },
      { id: 'blood_on_the_altar', name_cn: '祭坛��血' },
      { id: 'undimensioned_and_unseen', name_cn: '无形无踪' },
      { id: 'where_doom_awaits', name_cn: '末日将至' },
      { id: 'lost_in_time_and_space', name_cn: '迷失于时空' },
    ],
  },
]

const investigatorGroups: { label: string; investigators: InvestigatorEntry[] }[] = [
  {
    label: '核心包',
    investigators: [
      { id: 'roland_banks', name_cn: '罗兰·班克斯', class: 'guardian' },
      { id: 'daisy_walker', name_cn: '黛西·沃克', class: 'seeker' },
      { id: 'skids_otoole', name_cn: '斯基兹·奥图尔', class: 'rogue' },
      { id: 'agnes_baker', name_cn: '阿格妮丝·贝克', class: 'mystic' },
      { id: 'wendy_adams', name_cn: '温蒂·亚当斯', class: 'survivor' },
    ],
  },
  {
    label: '敦威治',
    investigators: [
      { id: 'zoey_samaras', name_cn: '佐伊·萨马拉斯', class: 'guardian' },
      { id: 'rex_murphy', name_cn: '雷克斯·墨菲', class: 'seeker' },
      { id: 'jenny_barnes', name_cn: '珍妮·巴恩斯', class: 'rogue' },
      { id: 'jim_culver', name_cn: '吉姆·卡尔弗', class: 'mystic' },
      { id: 'ashcan_pete', name_cn: '流浪汉皮特', class: 'survivor' },
    ],
  },
]

// --- Computed ---

const detail = computed(() => store.investigatorDetail)

const canStart = computed(() => {
  return store.selectedScenario && store.selectedInvestigator
})

const skillLabels: Record<string, string> = {
  willpower: '意志',
  intellect: '智力',
  combat: '战斗',
  agility: '敏捷',
}

// --- Methods ---

function selectScenario(id: string) {
  store.selectedScenario = id
}

function selectInvestigator(id: string) {
  store.selectedInvestigator = id
  client.getInvestigator(id)
}

function openDeckBuilder() {
  if (!store.selectedInvestigator) {
    store.addToast('请先选择调查员', 'error')
    return
  }
  phase.value = 'deckbuilder'
}

function onDeckConfirm(cards: string[]) {
  customDeckCards.value = cards
  phase.value = 'setup'
  store.addToast(`已构筑 ${cards.length} 张卡组`, 'info')
}

function onDeckBack() {
  phase.value = 'setup'
}

function startGame() {
  if (!canStart.value) return

  // Set up the callback before creating room to avoid race condition
  const prevRoomCb = client.onRoomUpdate
  client.onRoomUpdate = (_room) => {
    client.onRoomUpdate = prevRoomCb

    // Determine deck preset and custom deck cards
    // If user built custom deck in deck builder, send deck_cards
    // Otherwise use first available preset for this investigator
    const hasCustomDeck = customDeckCards.value.length > 0
    let deckPreset: string | undefined = undefined
    let deckCards: string[] | undefined = undefined

    if (hasCustomDeck) {
      // User built a custom deck - send the card list, no preset
      deckCards = customDeckCards.value
      deckPreset = undefined
    } else {
      // Use preset - find the first preset for this investigator
      // The preset ID format is "{investigator_id}_starter"
      deckPreset = `${store.selectedInvestigator}_starter`
    }

    client.setupGame(
      store.selectedScenario,
      store.selectedInvestigator,
      deckPreset,
      deckCards,
    )
  }

  // Also set up error handler
  const prevErrCb = client.onError
  client.onError = (err) => {
    store.addToast(err.message || '连接错误', 'error')
    client.onError = prevErrCb
  }

  client.createRoom()
}

// --- Socket callbacks ---

function handleInvestigatorDetail(d: any) {
  store.investigatorDetail = d
}

function handleStateUpdate(state: any, events?: any) {
  store.updateState(state, events)
  router.push('/game')
}

onMounted(() => {
  client.onInvestigatorDetail = handleInvestigatorDetail
  client.onStateUpdate = handleStateUpdate
})

onUnmounted(() => {
  if (client.onInvestigatorDetail === handleInvestigatorDetail) {
    client.onInvestigatorDetail = null
  }
  if (client.onStateUpdate === handleStateUpdate) {
    client.onStateUpdate = null
  }
  client.onRoomUpdate = null
})
</script>

<template>
  <div class="lobby" v-if="phase === 'setup'">
    <div class="lobby-columns">
      <!-- Left: Scenario Selection -->
      <div class="column col-scenario">
        <h2 class="column-title">选择剧本</h2>
        <div v-for="group in scenarioGroups" :key="group.label" class="group">
          <div class="group-label">{{ group.label }}</div>
          <div
            v-for="s in group.scenarios"
            :key="s.id"
            class="list-item"
            :class="{ selected: store.selectedScenario === s.id }"
            @click="selectScenario(s.id)"
          >
            {{ s.name_cn }}
          </div>
        </div>
      </div>

      <!-- Center: Investigator Selection -->
      <div class="column col-investigator">
        <h2 class="column-title">选择调查员</h2>
        <div v-for="group in investigatorGroups" :key="group.label" class="group">
          <div class="group-label">{{ group.label }}</div>
          <div
            v-for="inv in group.investigators"
            :key="inv.id"
            class="list-item investigator-item"
            :class="{ selected: store.selectedInvestigator === inv.id }"
            @click="selectInvestigator(inv.id)"
          >
            <span
              class="class-dot"
              :style="{ backgroundColor: CLASS_COLORS[inv.class] || '#888' }"
            ></span>
            {{ inv.name_cn }}
          </div>
        </div>
      </div>

      <!-- Right: Investigator Detail -->
      <div class="column col-detail">
        <div v-if="detail" class="detail-panel">
          <h2 class="detail-name">
            {{ detail.name_cn }}
            <span class="detail-title" v-if="detail.title_cn">{{ detail.title_cn }}</span>
          </h2>
          <div class="detail-en">{{ detail.name }}</div>
          <div
            class="detail-class-badge"
            :style="{ backgroundColor: CLASS_COLORS[detail.class] || '#888' }"
          >
            {{ detail.class }}
          </div>

          <div class="detail-stats">
            <div class="stat-row">
              <span class="stat-label">生命</span>
              <span class="stat-value">{{ detail.health }}</span>
              <span class="stat-label" style="margin-left: 24px">理智</span>
              <span class="stat-value">{{ detail.sanity }}</span>
            </div>
          </div>

          <div class="detail-skills">
            <div
              v-for="(val, key) in detail.skills"
              :key="key"
              class="skill-badge"
            >
              <span class="skill-name">{{ skillLabels[key as string] || key }}</span>
              <span class="skill-val">{{ val }}</span>
            </div>
          </div>

          <div class="detail-section" v-if="detail.ability_cn">
            <div class="section-label">能力</div>
            <div class="section-text">{{ detail.ability_cn }}</div>
          </div>

          <div class="detail-section" v-if="detail.deck_requirements">
            <div class="section-label">牌组要求</div>
            <div class="section-text">
              牌组大小: {{ detail.deck_requirements.size }}
              <template v-if="detail.deck_requirements.cards">
                <div v-for="(req, cardId) in detail.deck_requirements.cards" :key="cardId" class="req-item">
                  {{ cardId }}: Lv.{{ req.min_level }}-{{ req.max_level }}
                </div>
              </template>
            </div>
          </div>

          <div class="detail-section" v-if="detail.signature_cards?.length">
            <div class="section-label">标志卡</div>
            <div class="section-text">{{ detail.signature_cards.join(', ') }}</div>
          </div>

          <div class="detail-section" v-if="detail.weakness">
            <div class="section-label">弱点</div>
            <div class="section-text">{{ detail.weakness }}</div>
          </div>
        </div>
        <div v-else class="detail-placeholder">
          选择一位调查员查看详情
        </div>
      </div>
    </div>

    <!-- Bottom Bar -->
    <div class="bottom-bar">
      <button class="btn btn-secondary" @click="openDeckBuilder">构筑卡组</button>
      <div class="deck-status" v-if="customDeckCards.length > 0">
        已构筑 {{ customDeckCards.length }} 张
      </div>
      <button class="btn btn-primary" :disabled="!canStart" @click="startGame">开始游戏</button>
    </div>
  </div>

  <!-- Deck Builder Phase -->
  <DeckBuilder
    v-else-if="phase === 'deckbuilder'"
    :investigator-id="store.selectedInvestigator"
    @confirm="onDeckConfirm"
    @back="onDeckBack"
  />
</template>

<style scoped>
.lobby {
  width: 100vw;
  height: 100vh;
  background: #0a0a1a;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', sans-serif;
}

.lobby-columns {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.column {
  padding: 16px;
  overflow-y: auto;
  border-right: 1px solid #1a1a2e;
}

.col-scenario {
  width: 22%;
}

.col-investigator {
  width: 22%;
}

.col-detail {
  width: 56%;
  border-right: none;
}

.column-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: #ccc;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.group {
  margin-bottom: 16px;
}

.group-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
  padding: 2px 0;
  border-bottom: 1px solid #1a1a2e;
}

.list-item {
  padding: 8px 12px;
  margin: 2px 0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.15s;
}

.list-item:hover {
  background: #1a1a2e;
}

.list-item.selected {
  background: #1e3a5f;
  color: #fff;
}

.investigator-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.class-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Detail Panel */
.detail-panel {
  padding: 8px;
}

.detail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #555;
  font-size: 16px;
}

.detail-name {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
  color: #fff;
}

.detail-title {
  font-size: 14px;
  font-weight: 400;
  color: #999;
  margin-left: 8px;
}

.detail-en {
  font-size: 13px;
  color: #777;
  margin-bottom: 10px;
}

.detail-class-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 3px;
  font-size: 12px;
  color: #fff;
  text-transform: capitalize;
  margin-bottom: 16px;
}

.detail-stats {
  margin-bottom: 16px;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  font-size: 13px;
  color: #999;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.detail-skills {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.skill-badge {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px 14px;
  text-align: center;
  min-width: 60px;
}

.skill-name {
  display: block;
  font-size: 11px;
  color: #888;
  margin-bottom: 4px;
}

.skill-val {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.detail-section {
  margin-bottom: 14px;
}

.section-label {
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.section-text {
  font-size: 14px;
  color: #ccc;
  line-height: 1.5;
}

.req-item {
  font-size: 13px;
  color: #aaa;
  margin-top: 2px;
}

/* Bottom Bar */
.bottom-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: #0d0d20;
  border-top: 1px solid #1a1a2e;
}

.deck-status {
  font-size: 13px;
  color: #8e8;
}

.btn {
  padding: 10px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-primary {
  background: #2980b9;
  color: #fff;
  margin-left: auto;
}

.btn-primary:hover:not(:disabled) {
  background: #3498db;
}

.btn-secondary {
  background: #1a1a2e;
  color: #ccc;
  border: 1px solid #333;
}

.btn-secondary:hover {
  background: #252540;
}
</style>
