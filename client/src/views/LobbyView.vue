<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import DeckBuilder from '../components/DeckBuilder.vue'
import { CAMPAIGNS, DIFFICULTIES, DIFFICULTY_LABELS, INVESTIGATOR_GROUPS } from '../data/meta'
import type { RoomState } from '../state/types'

const route = useRoute()
const router = useRouter()
const client = useSocket()
const store = useGameStore()

const phase = ref<'setup' | 'deckbuilder'>('setup')
const customDeckCards = ref<string[]>([])
const starting = ref(false)

// --- 多人联机房间 ---
const mode = ref<'single' | 'multi'>(route.query.mode === 'multi' ? 'multi' : 'single')
const room = ref<RoomState | null>(null)
const joinRoomId = ref('')
const joining = ref(false)   // create/join 请求中
const readying = ref(false)  // setup_game 已发送、等待 room_update 确认

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
    tabSingle: '单人游戏',
    tabMulti: '多人合作',
    createRoomTitle: '创建房间',
    createRoomDesc: '创建 2-4 人合作房间，把房间 ID 发给队友',
    createRoomBtn: '创建房间',
    joinRoomTitle: '加入房间',
    joinRoomPlaceholder: '输入房间 ID',
    joinRoomBtn: '加入',
    leaveRoom: '离开房间',
    ready: '准备',
    readying: '准备中…',
    updatePick: '更新选择',
    roomId: '房间 ID',
    copy: '复制',
    copied: '已复制',
    seatEmpty: '空位',
    seatMe: '我',
    seatReady: '已准备',
    seatPicking: '选择中…',
    multiHint: '剧本与难度以最后点击「准备」的玩家所选为准',
    waitOthers: '已准备，等待其他玩家…',
    connecting: '连接中…',
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
    tabSingle: '單人遊戲',
    tabMulti: '多人合作',
    createRoomTitle: '創建房間',
    createRoomDesc: '創建 2-4 人合作房間，把房間 ID 發給隊友',
    createRoomBtn: '創建房間',
    joinRoomTitle: '加入房間',
    joinRoomPlaceholder: '輸入房間 ID',
    joinRoomBtn: '加入',
    leaveRoom: '離開房間',
    ready: '準備',
    readying: '準備中…',
    updatePick: '更新選擇',
    roomId: '房間 ID',
    copy: '複製',
    copied: '已複製',
    seatEmpty: '空位',
    seatMe: '我',
    seatReady: '已準備',
    seatPicking: '選擇中…',
    multiHint: '劇本與難度以最後點擊「準備」的玩家所選為準',
    waitOthers: '已準備，等待其他玩家…',
    connecting: '連接中…',
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

const scenarioGroups = CAMPAIGNS.map(c => ({
  label: c.name_cn,
  label_hant: c.name_hant,
  scenarios: c.chapters as ScenarioEntry[],
}))

const investigatorGroups = INVESTIGATOR_GROUPS

// --- Computed ---

const labels = computed(() => UI_TEXT[store.language])

function localizedName(entry: { name_cn: string; name_hant: string }): string {
  return store.language === 'zh-Hant' ? entry.name_hant : entry.name_cn
}

function localizedGroupLabel(group: { label: string; label_hant?: string } | string): string {
  const label = typeof group === 'string' ? group : group.label
  if (label === '核心包') return labels.value.core
  if (label === '敦威治遗产') return labels.value.dunwichLegacy
  if (label === '敦威治') return labels.value.dunwich
  if (typeof group !== 'string' && store.language === 'zh-Hant' && group.label_hant) return group.label_hant
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

// --- 多人联机 computed ---

const myPlayerId = computed(() => client.playerId || store.playerId)

const mySeat = computed(() =>
  room.value?.seats.find(s => s.player_id !== null && s.player_id === myPlayerId.value) ?? null,
)

const amReady = computed(() => Boolean(mySeat.value?.ready))

const inRoom = computed(() => room.value !== null)

const investigatorNames = computed<Record<string, { name_cn: string; name_hant: string }>>(() =>
  Object.fromEntries(
    investigatorGroups.flatMap(g => g.investigators.map(i => [i.id, { name_cn: i.name_cn, name_hant: i.name_hant }])),
  ),
)

function seatInvestigatorName(id: string): string {
  const entry = investigatorNames.value[id]
  return entry ? localizedName(entry) : id
}

function playerTail(playerId: string): string {
  return playerId.slice(-4)
}

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

/** 发送 setup_game：选定调查员/牌组并标记 ready（单人局收到房间后直接开局） */
function sendSetup() {
  // If user built custom deck in deck builder, send deck_cards
  // Otherwise use preset for this investigator ("{investigator_id}_starter")
  const hasCustomDeck = customDeckCards.value.length > 0
  client.setupGame(
    store.selectedScenario,
    store.selectedInvestigator,
    hasCustomDeck ? undefined : `${store.selectedInvestigator}_starter`,
    hasCustomDeck ? customDeckCards.value : undefined,
    store.difficulty,
  )
}

async function startGame() {
  if (!canStart.value || starting.value) return
  starting.value = true
  try {
    await client.ensureConnected()
    client.createRoom()
  } catch (err) {
    starting.value = false
    store.addToast(err instanceof Error ? err.message : '无法连接到游戏服务器', 'error')
  }
}

// --- 多人房间操作 ---

async function createRoomMulti() {
  if (joining.value) return
  joining.value = true
  try {
    await client.ensureConnected()
    client.createRoom()
  } catch (err) {
    joining.value = false
    store.addToast(err instanceof Error ? err.message : '无法连接到游戏服务器', 'error')
  }
}

async function joinRoomMulti() {
  const id = joinRoomId.value.trim()
  if (!id || joining.value) return
  joining.value = true
  try {
    await client.ensureConnected()
    client.joinRoom(id)
  } catch (err) {
    joining.value = false
    store.addToast(err instanceof Error ? err.message : '无法连接到游戏服务器', 'error')
  }
}

function leaveRoom() {
  client.leaveRoom()
  room.value = null
  readying.value = false
}

function readyUp() {
  if (!store.selectedInvestigator) {
    store.addToast(labels.value.selectFirst, 'error')
    return
  }
  if (readying.value) return
  readying.value = true
  sendSetup()
}

function copyRoomId() {
  const id = room.value?.room_id
  if (!id) return
  navigator.clipboard?.writeText(id).then(
    () => store.addToast(labels.value.copied, 'info'),
    () => store.addToast(id, 'info'),
  )
}

function goHome() {
  if (room.value) client.leaveRoom()
  room.value = null
  router.push('/')
}

// --- Socket callbacks ---

function handleInvestigatorDetail(d: any) {
  store.investigatorDetail = d
}

function handleRoomUpdate(r: RoomState) {
  room.value = r
  joining.value = false
  readying.value = false
  // 单人快速游戏：房间创建成功 → 立即 setup 开局（保持原有流程）
  if (mode.value === 'single' && starting.value) {
    sendSetup()
  }
}

function handleStateUpdate(state: any, events?: any) {
  starting.value = false
  readying.value = false
  store.updateState(state, events)
  router.push('/game')
}

function handleError(err: { message: string }) {
  starting.value = false
  joining.value = false
  readying.value = false
  store.addToast(err.message || '连接错误', 'error')
}

let prevOnError: typeof client.onError = null

onMounted(() => {
  // 多人 ready 必须带剧本；未选时给默认值（单人模式同样受益）
  if (!store.selectedScenario) store.selectedScenario = 'the_gathering'
  client.onInvestigatorDetail = handleInvestigatorDetail
  client.onStateUpdate = handleStateUpdate
  client.onRoomUpdate = handleRoomUpdate
  prevOnError = client.onError
  client.onError = handleError
})

onUnmounted(() => {
  if (client.onInvestigatorDetail === handleInvestigatorDetail) {
    client.onInvestigatorDetail = null
  }
  if (client.onStateUpdate === handleStateUpdate) {
    client.onStateUpdate = null
  }
  if (client.onRoomUpdate === handleRoomUpdate) {
    client.onRoomUpdate = null
  }
  if (client.onError === handleError) {
    client.onError = prevOnError
  }
})
</script>

<template>
  <div class="lobby" v-if="phase === 'setup'" :lang="store.language">
    <!-- Mode Tabs（多人进房后隐藏，避免误触；单人局的房间是临时的，不隐藏） -->
    <div class="mode-tabs" v-if="!(mode === 'multi' && inRoom)">
      <button
        type="button"
        class="mode-tab"
        :class="{ active: mode === 'single' }"
        @click="mode = 'single'"
      >{{ labels.tabSingle }}</button>
      <button
        type="button"
        class="mode-tab"
        :class="{ active: mode === 'multi' }"
        @click="mode = 'multi'"
      >{{ labels.tabMulti }}</button>
    </div>

    <!-- 多人：未进房 → 创建/加入面板 -->
    <div v-if="mode === 'multi' && !inRoom" class="room-entry">
      <div class="room-entry-cards">
        <div class="room-entry-card">
          <h2 class="entry-title">{{ labels.createRoomTitle }}</h2>
          <p class="entry-desc">{{ labels.createRoomDesc }}</p>
          <button class="btn btn-primary entry-btn" :disabled="joining" @click="createRoomMulti">
            {{ joining ? labels.connecting : labels.createRoomBtn }}
          </button>
        </div>
        <div class="room-entry-card">
          <h2 class="entry-title">{{ labels.joinRoomTitle }}</h2>
          <input
            v-model="joinRoomId"
            class="room-id-input"
            type="text"
            :placeholder="labels.joinRoomPlaceholder"
            @keyup.enter="joinRoomMulti"
          />
          <button
            class="btn btn-primary entry-btn"
            :disabled="joining || !joinRoomId.trim()"
            @click="joinRoomMulti"
          >{{ labels.joinRoomBtn }}</button>
        </div>
      </div>
      <button class="btn btn-secondary" @click="router.push('/')">← 主页</button>
    </div>

    <!-- 选人/选剧本三栏（单人始终显示；多人进房后显示） -->
    <div class="lobby-columns" v-else>
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

    <!-- 多人：座位条（4 个座位） -->
    <div v-if="mode === 'multi' && room" class="seats-bar">
      <div class="room-info">
        <span class="room-id-label">{{ labels.roomId }}：</span>
        <code class="room-id">{{ room.room_id }}</code>
        <button type="button" class="copy-btn" @click="copyRoomId">{{ labels.copy }}</button>
        <span class="multi-hint">{{ labels.multiHint }}</span>
      </div>
      <div class="seats">
        <div
          v-for="seat in room.seats"
          :key="seat.seat_num"
          class="seat"
          :class="{
            empty: !seat.player_id,
            me: seat.player_id !== null && seat.player_id === myPlayerId,
            ready: seat.ready,
          }"
        >
          <template v-if="seat.player_id">
            <span class="seat-player">
              #{{ playerTail(seat.player_id) }}
              <span v-if="seat.player_id === myPlayerId" class="seat-me">（{{ labels.seatMe }}）</span>
            </span>
            <span class="seat-inv">{{ seatInvestigatorName(seat.investigator_id) }}</span>
            <span class="seat-status" :class="{ on: seat.ready }">
              {{ seat.ready ? `✓ ${labels.seatReady}` : `… ${labels.seatPicking}` }}
            </span>
          </template>
          <span v-else class="seat-empty">{{ labels.seatEmpty }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom Bar -->
    <div class="bottom-bar" v-if="mode === 'single' || inRoom">
      <button class="btn btn-secondary" @click="goHome">← 主页</button>
      <button v-if="mode === 'multi'" class="btn btn-secondary" @click="leaveRoom">{{ labels.leaveRoom }}</button>
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
      <button
        v-if="mode === 'single'"
        class="btn btn-primary"
        :disabled="!canStart || starting"
        @click="startGame"
      >
        {{ starting ? labels.starting : labels.startGame }}
      </button>
      <template v-else>
        <span v-if="amReady" class="wait-others">{{ labels.waitOthers }}</span>
        <button
          class="btn btn-primary"
          :disabled="!store.selectedInvestigator || readying"
          @click="readyUp"
        >
          {{ amReady ? labels.updatePick : (readying ? labels.readying : labels.ready) }}
        </button>
      </template>
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

/* Mode Tabs */
.mode-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 16px 0;
}

.mode-tab {
  padding: 8px 22px;
  border: 1px solid #2a2a4e;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: #0d0d20;
  color: #888;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.mode-tab:hover {
  color: #ccc;
}

.mode-tab.active {
  background: #1a1a2e;
  color: #c0a060;
}

/* Room Entry (create / join) */
.room-entry {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.room-entry-cards {
  display: flex;
  gap: 24px;
}

.room-entry-card {
  width: 300px;
  padding: 28px 24px;
  background: #12122a;
  border: 1px solid #2a2a4e;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.entry-title {
  margin: 0;
  font-size: 18px;
  color: #e0d0a0;
}

.entry-desc {
  margin: 0;
  font-size: 13px;
  color: #777;
  line-height: 1.6;
}

.entry-btn {
  align-self: flex-start;
  margin-left: 0;
}

.room-id-input {
  background: #0d0d20;
  border: 1px solid #2a2a4e;
  color: #eee;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 14px;
  letter-spacing: 1px;
}

.room-id-input:focus {
  outline: none;
  border-color: #4a4a8e;
}

/* Seats Bar */
.seats-bar {
  padding: 8px 24px;
  background: #0d0d20;
  border-top: 1px solid #1a1a2e;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.room-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #999;
}

.room-id-label {
  color: #888;
}

.room-id {
  color: #c0a060;
  background: #1a1a2e;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 14px;
  letter-spacing: 1px;
}

.copy-btn {
  padding: 2px 10px;
  font-size: 12px;
}

.multi-hint {
  margin-left: auto;
  font-size: 12px;
  color: #666;
}

.seats {
  display: flex;
  gap: 12px;
}

.seat {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: #14142b;
  border: 1px solid #2a2a4e;
  border-radius: 8px;
  font-size: 13px;
}

.seat.empty {
  justify-content: center;
  color: #444;
  border-style: dashed;
}

.seat.me {
  border-color: #c0a060;
}

.seat-player {
  color: #999;
  font-family: monospace;
}

.seat-me {
  color: #c0a060;
}

.seat-inv {
  color: #e0e0e0;
  font-weight: 600;
}

.seat-status {
  margin-left: auto;
  font-size: 12px;
  color: #777;
}

.seat-status.on {
  color: #2ecc71;
}

.wait-others {
  font-size: 13px;
  color: #2ecc71;
}
</style>
