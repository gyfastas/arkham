<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import DeckBuilder from '../components/DeckBuilder.vue'
import { DIFFICULTIES, DIFFICULTY_LABELS } from '../data/meta'

const router = useRouter()
const client = useSocket()
const store = useGameStore()

const phase = ref<'setup' | 'deckbuilder'>('setup')
const customDeckCards = ref<string[]>([])
const starting = ref(false)

// --- Data ---

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#888',
}

interface ScenarioEntry { id: string; name_cn: string; name_hant: string }
interface InvestigatorEntry { id: string; name_cn: string; name_hant: string; class: string }

const UI_TEXT = {
  'zh-Hans': {
    selectScenario: '选择剧本',
    selectInvestigator: '选择调查员',
    core: '核心包',
    dunwichLegacy: '敦威治遗产',
    dunwich: '敦威治',
    health: '生命',
    sanity: '理智',
    ability: '能力',
    deckRequirements: '牌组要求',
    deckSize: '牌组大小',
    signatureCards: '标志卡',
    weakness: '弱点',
    chooseInvestigator: '选择一位调查员查看详情',
    buildDeck: '构筑卡组',
    built: '已构筑',
    startGame: '开始游戏',
    starting: '正在进入游戏…',
    language: '选择显示语言',
    guardian: '守护者',
    seeker: '探求者',
    rogue: '流浪者',
    mystic: '神秘学家',
    survivor: '求生者',
    neutral: '中立',
    selectFirst: '请先选择调查员',
    deckBuiltSuffix: '张卡组',
  },
  'zh-Hant': {
    selectScenario: '選擇劇本',
    selectInvestigator: '選擇調查員',
    core: '核心包',
    dunwichLegacy: '敦威治遺產',
    dunwich: '敦威治',
    health: '生命',
    sanity: '理智',
    ability: '能力',
    deckRequirements: '牌組要求',
    deckSize: '牌組大小',
    signatureCards: '標誌卡',
    weakness: '弱點',
    chooseInvestigator: '選擇一位調查員查看詳情',
    buildDeck: '構築牌組',
    built: '已構築',
    startGame: '開始遊戲',
    starting: '正在進入遊戲…',
    language: '選擇顯示語言',
    guardian: '守護者',
    seeker: '探求者',
    rogue: '流浪者',
    mystic: '神秘學家',
    survivor: '求生者',
    neutral: '中立',
    selectFirst: '請先選擇調查員',
    deckBuiltSuffix: '張牌組',
  },
} as const

const INVESTIGATOR_TEXT: Record<string, { name_cn: string; name_hant: string; title_cn: string; title_hant: string; ability_hant: string }> = {
  roland_banks: { name_cn: '罗兰·班克斯', name_hant: '羅蘭·班克斯', title_cn: '联邦探员', title_hant: '聯邦探員', ability_hant: '在你擊敗一名敵人後：發現你所在地點的1個線索。（每輪限制1次。）' },
  daisy_walker: { name_cn: '黛西·沃克', name_hant: '黛西·沃克', title_cn: '图书馆员', title_hant: '圖書館員', ability_hant: '在你的回合中，你可以執行1個額外行動，該行動只能用於啟動一個典籍能力。' },
  skids_otoole: { name_cn: '斯基兹·奥图尔', name_hant: '斯基茲·奧圖爾', title_cn: '前科犯', title_hant: '前科犯', ability_hant: '在你的回合中，花費2資源：你在本回合可以執行1個額外行動。（每回合限制1次。）' },
  agnes_baker: { name_cn: '阿格妮丝·贝克', name_hant: '阿格妮絲·貝克', title_cn: '女招待', title_hant: '女招待', ability_hant: '在阿格妮絲·貝克被放置1點或以上恐懼後：對你所在地點的一名敵人造成1點傷害。（每階段限制1次。）' },
  wendy_adams: { name_cn: '温蒂·亚当斯', name_hant: '溫蒂·亞當斯', title_cn: '流浪儿', title_hant: '流浪兒', ability_hant: '當你揭示一個混沌標記時，從手牌中丟掉1張牌：取消該混沌標記並放回混沌袋中，然後揭示一個新的混沌標記。（每次檢定限制1次。）' },
  zoey_samaras: { name_cn: '佐伊·萨马拉斯', name_hant: '佐伊·薩馬拉斯', title_cn: '主厨', title_hant: '主廚', ability_hant: '[reaction]在你與一名敵人交戰後：獲得1個資源。\n[elder_sign]效果：+1。如果攻擊中的這次技能檢定成功，這次攻擊造成+1傷害。' },
  rex_murphy: { name_cn: '雷克斯·墨菲', name_hant: '雷克斯·墨菲', title_cn: '记者', title_hant: '記者', ability_hant: '[reaction]在調查時技能檢定成功後，如果你超過難度至少2點：發現所在地點1個線索。\n[elder_sign]效果：+2。你可以選擇讓這次檢定自動失敗，來抽取3張卡牌。' },
  jenny_barnes: { name_cn: '珍妮·巴恩斯', name_hant: '珍妮·巴恩斯', title_cn: '普通人', title_hant: '普通人', ability_hant: '每個補給階段額外獲得1個資源。\n[elder_sign]效果：你每持有1個資源，+1。' },
  jim_culver: { name_cn: '吉姆·卡尔弗', name_hant: '吉姆·卡爾弗', title_cn: '音乐家', title_hant: '音樂家', ability_hant: '將你抽出的[skull]標記的修正值視為0。\n每次你抽出[elder_sign]標記時，你可以選擇將其視為[skull]標記。\n[elder_sign]效果：+1。' },
  ashcan_pete: { name_cn: '流浪汉皮特', name_hant: '流浪漢皮特', title_cn: '流浪者', title_hant: '流浪者', ability_hant: '開始遊戲時，將杜克放置入場。\n[free]丟棄一張手牌：準備1張你控制的支援卡。(每輪限制1次。)\n[elder_sign]效果：+2。準備杜克。' },
}

const scenarioGroups: { label: string; scenarios: ScenarioEntry[] }[] = [
  {
    label: '核心包',
    scenarios: [
      { id: 'the_gathering', name_cn: '聚集于此', name_hant: '聚集於此' },
      { id: 'the_midnight_masks', name_cn: '午夜假面', name_hant: '午夜假面' },
      { id: 'the_devourer_below', name_cn: '吞噬星辰', name_hant: '吞噬星辰' },
    ],
  },
  {
    label: '敦威治遗产',
    scenarios: [
      { id: 'extracurricular_activity', name_cn: '课外活动', name_hant: '課外活動' },
      { id: 'the_house_always_wins', name_cn: '赌场必胜', name_hant: '賭場必勝' },
      { id: 'the_miskatonic_museum', name_cn: '米斯卡塔尼克博物馆', name_hant: '米斯卡塔尼克博物館' },
      { id: 'essex_county_express', name_cn: '埃塞克斯快车', name_hant: '埃塞克斯縣快車' },
      { id: 'blood_on_the_altar', name_cn: '祭坛之血', name_hant: '祭壇之血' },
      { id: 'undimensioned_and_unseen', name_cn: '无形无踪', name_hant: '無形無蹤' },
      { id: 'where_doom_awaits', name_cn: '末日将至', name_hant: '末日將至' },
      { id: 'lost_in_time_and_space', name_cn: '迷失于时空', name_hant: '迷失於時空' },
    ],
  },
]

const investigatorGroups: { label: string; investigators: InvestigatorEntry[] }[] = [
  {
    label: '核心包',
    investigators: [
      { id: 'roland_banks', name_cn: '罗兰·班克斯', name_hant: '羅蘭·班克斯', class: 'guardian' },
      { id: 'daisy_walker', name_cn: '黛西·沃克', name_hant: '黛西·沃克', class: 'seeker' },
      { id: 'skids_otoole', name_cn: '斯基兹·奥图尔', name_hant: '斯基茲·奧圖爾', class: 'rogue' },
      { id: 'agnes_baker', name_cn: '阿格妮丝·贝克', name_hant: '阿格妮絲·貝克', class: 'mystic' },
      { id: 'wendy_adams', name_cn: '温蒂·亚当斯', name_hant: '溫蒂·亞當斯', class: 'survivor' },
    ],
  },
  {
    label: '敦威治',
    investigators: [
      { id: 'zoey_samaras', name_cn: '佐伊·萨马拉斯', name_hant: '佐伊·薩馬拉斯', class: 'guardian' },
      { id: 'rex_murphy', name_cn: '雷克斯·墨菲', name_hant: '雷克斯·墨菲', class: 'seeker' },
      { id: 'jenny_barnes', name_cn: '珍妮·巴恩斯', name_hant: '珍妮·巴恩斯', class: 'rogue' },
      { id: 'jim_culver', name_cn: '吉姆·卡尔弗', name_hant: '吉姆·卡爾弗', class: 'mystic' },
      { id: 'ashcan_pete', name_cn: '流浪汉皮特', name_hant: '流浪漢皮特', class: 'survivor' },
    ],
  },
]

// --- Computed ---

const labels = computed(() => UI_TEXT[store.language])

function localizedName(entry: { name_cn: string; name_hant: string }): string {
  return store.language === 'zh-Hant' ? entry.name_hant : entry.name_cn
}

function localizedGroupLabel(label: string): string {
  if (label === '核心包') return labels.value.core
  if (label === '敦威治遗产') return labels.value.dunwichLegacy
  if (label === '敦威治') return labels.value.dunwich
  return label
}

function classLabel(className: string): string {
  return labels.value[className as keyof typeof labels.value] || className
}

const detail = computed(() => {
  const raw = store.investigatorDetail
  if (!raw) return null
  const translation = INVESTIGATOR_TEXT[raw.id]
  if (!translation) return raw
  const traditional = store.language === 'zh-Hant'
  return {
    ...raw,
    name_cn: traditional ? translation.name_hant : translation.name_cn,
    title_cn: traditional ? translation.title_hant : translation.title_cn,
    ability_cn: traditional ? translation.ability_hant : raw.ability_cn,
  }
})

const canStart = computed(() => {
  return Boolean(store.selectedScenario && store.selectedInvestigator)
})

const skillLabels: Record<string, string> = {
  willpower: '意志',
  intellect: '智力',
  combat: '战斗',
  agility: '敏捷',
}

const traditionalSkillLabels: Record<string, string> = {
  willpower: '意志',
  intellect: '智力',
  combat: '戰鬥',
  agility: '敏捷',
}

function skillLabel(key: string): string {
  return (store.language === 'zh-Hant' ? traditionalSkillLabels : skillLabels)[key] || key
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
    store.addToast(labels.value.selectFirst, 'error')
    return
  }
  phase.value = 'deckbuilder'
}

function onDeckConfirm(cards: string[]) {
  customDeckCards.value = cards
  phase.value = 'setup'
  store.addToast(`${labels.value.built} ${cards.length} ${labels.value.deckBuiltSuffix}`, 'info')
}

function onDeckBack() {
  phase.value = 'setup'
}

async function startGame() {
  if (!canStart.value || starting.value) return
  starting.value = true

  // Set up callbacks before creating the room so a fast server response is
  // not missed. The connection check also recovers from a stale HMR/socket.
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
      store.difficulty,
    )
  }

  // Also set up error handler
  const prevErrCb = client.onError
  client.onError = (err) => {
    starting.value = false
    store.addToast(err.message || '连接错误', 'error')
    client.onError = prevErrCb
  }

  try {
    await client.ensureConnected()
    client.createRoom()
  } catch (err) {
    starting.value = false
    client.onRoomUpdate = prevRoomCb
    client.onError = prevErrCb
    store.addToast(err instanceof Error ? err.message : '无法连接到游戏服务器', 'error')
  }
}

// --- Socket callbacks ---

function handleInvestigatorDetail(d: any) {
  store.investigatorDetail = d
}

function handleStateUpdate(state: any, events?: any) {
  starting.value = false
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
  <div class="lobby" v-if="phase === 'setup'" :lang="store.language">
    <div class="lobby-columns">
      <!-- Left: Scenario Selection -->
      <div class="column col-scenario">
        <h2 class="column-title">{{ labels.selectScenario }}</h2>
        <div v-for="group in scenarioGroups" :key="group.label" class="group">
          <div class="group-label">{{ localizedGroupLabel(group.label) }}</div>
          <div
            v-for="s in group.scenarios"
            :key="s.id"
            class="list-item"
            :class="{ selected: store.selectedScenario === s.id }"
            @click="selectScenario(s.id)"
          >
            {{ localizedName(s) }}
          </div>
        </div>
      </div>

      <!-- Center: Investigator Selection -->
      <div class="column col-investigator">
        <div class="title-row">
          <h2 class="column-title">{{ labels.selectInvestigator }}</h2>
          <div class="language-picker" :aria-label="labels.language">
            <button
              type="button"
              class="language-option"
              :class="{ active: store.language === 'zh-Hans' }"
              @click="store.setLanguage('zh-Hans')"
            >简体中文</button>
            <button
              type="button"
              class="language-option"
              :class="{ active: store.language === 'zh-Hant' }"
              @click="store.setLanguage('zh-Hant')"
            >繁體中文</button>
          </div>
        </div>
        <div v-for="group in investigatorGroups" :key="group.label" class="group">
          <div class="group-label">{{ localizedGroupLabel(group.label) }}</div>
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
            {{ localizedName(inv) }}
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
            {{ classLabel(detail.class) }}
          </div>

          <div class="detail-stats">
            <div class="stat-row">
              <span class="stat-label">{{ labels.health }}</span>
              <span class="stat-value">{{ detail.health }}</span>
              <span class="stat-label" style="margin-left: 24px">{{ labels.sanity }}</span>
              <span class="stat-value">{{ detail.sanity }}</span>
            </div>
          </div>

          <div class="detail-skills">
            <div
              v-for="(val, key) in detail.skills"
              :key="key"
              class="skill-badge"
            >
              <span class="skill-name">{{ skillLabel(key as string) }}</span>
              <span class="skill-val">{{ val }}</span>
            </div>
          </div>

          <div class="detail-section" v-if="detail.ability_cn">
            <div class="section-label">{{ labels.ability }}</div>
            <div class="section-text">{{ detail.ability_cn }}</div>
          </div>

          <div class="detail-section" v-if="detail.deck_requirements">
            <div class="section-label">{{ labels.deckRequirements }}</div>
            <div class="section-text">
              {{ labels.deckSize }}: {{ detail.deck_requirements.size }}
              <template v-if="detail.deck_requirements.cards">
                <div v-for="(req, cardId) in detail.deck_requirements.cards" :key="cardId" class="req-item">
                  {{ classLabel(cardId as string) }}: Lv.{{ req.min_level }}-{{ req.max_level }}
                </div>
              </template>
            </div>
          </div>

          <div class="detail-section" v-if="detail.signature_cards?.length">
            <div class="section-label">{{ labels.signatureCards }}</div>
            <div class="section-text">{{ detail.signature_cards.join(', ') }}</div>
          </div>

          <div class="detail-section" v-if="detail.weakness">
            <div class="section-label">{{ labels.weakness }}</div>
            <div class="section-text">{{ detail.weakness }}</div>
          </div>
        </div>
        <div v-else class="detail-placeholder">
          {{ labels.chooseInvestigator }}
        </div>
      </div>
    </div>

    <!-- Bottom Bar -->
    <div class="bottom-bar">
      <button class="btn btn-secondary" @click="router.push('/')">← 主页</button>
      <button class="btn btn-secondary" @click="openDeckBuilder">{{ labels.buildDeck }}</button>
      <div class="deck-status" v-if="customDeckCards.length > 0">
        {{ labels.built }} {{ customDeckCards.length }} 张
      </div>
      <div class="difficulty-picker">
        <span class="diff-label">难度</span>
        <select v-model="store.difficulty" class="diff-select">
          <option v-for="d in DIFFICULTIES" :key="d" :value="d">{{ DIFFICULTY_LABELS[d] }}</option>
        </select>
      </div>
      <button class="btn btn-primary" :disabled="!canStart || starting" @click="startGame">
        {{ starting ? labels.starting : labels.startGame }}
      </button>
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

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.title-row .column-title {
  margin-bottom: 0;
}

.language-picker {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border: 1px solid #333344;
  border-radius: 5px;
  background: #101025;
}

.language-option {
  padding: 3px 6px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #777;
  font-size: 11px;
  line-height: 1.2;
}

.language-option:hover {
  background: #1a1a2e;
  color: #ccc;
}

.language-option.active {
  background: #1e3a5f;
  color: #fff;
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

.difficulty-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.diff-label {
  color: #888;
  font-size: 13px;
}

.diff-select {
  background: #1a1a2e;
  border: 1px solid #2a2a4e;
  color: #ddd;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}

.diff-select:focus {
  outline: none;
  border-color: #4a4a8e;
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
