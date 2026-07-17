<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useGameStore } from '../stores/game'
import type { CardDisplay } from '../state/types'

const props = defineProps<{
  investigatorId: string
}>()

const emit = defineEmits<{
  confirm: [deckCards: string[]]
  back: []
}>()

const client = useSocket()
const store = useGameStore()

const filterTab = ref<'all' | 'asset' | 'event' | 'skill'>('all')
const deck = ref<string[]>([])

// --- 卡牌悬浮预览 ---
const previewCard = ref<CardDisplay | null>(null)
const previewStyle = ref<Record<string, string>>({})

function showPreview(card: CardDisplay, event: MouseEvent) {
  previewCard.value = card
  const el = event.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const spaceRight = window.innerWidth - rect.right
  const top = Math.min(Math.max(8, rect.top), window.innerHeight - 320)
  if (spaceRight > 320) {
    previewStyle.value = { left: `${rect.right + 8}px`, top: `${top}px` }
  } else {
    previewStyle.value = { right: `${window.innerWidth - rect.left + 8}px`, top: `${top}px` }
  }
}

function hidePreview() {
  previewCard.value = null
}

const TYPE_LABELS: Record<string, string> = {
  asset: '支援', event: '事件', skill: '技能', treachery: '诡计', enemy: '敌人',
}

const SKILL_ICON_LABELS: Record<string, string> = {
  willpower: '意', intellect: '智', combat: '战', agility: '敏', wild: '★',
}

const SLOT_LABELS: Record<string, string> = {
  hand: '手部', 'hand x2': '双手', body: '身体', accessory: '配件',
  ally: '盟友', arcane: '奥秘', 'arcane x2': '双奥秘',
}

const CLASS_COLORS: Record<string, string> = {
  guardian: '#2980b9',
  seeker: '#d4a017',
  rogue: '#27ae60',
  mystic: '#8e44ad',
  survivor: '#c0392b',
  neutral: '#888',
}

const FILTER_LABELS: { key: 'all' | 'asset' | 'event' | 'skill'; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'asset', label: '支援' },
  { key: 'event', label: '事件' },
  { key: 'skill', label: '技能' },
]

// --- Computed ---

const filteredCards = computed(() => {
  const cards = store.availableCards
  if (filterTab.value === 'all') return cards
  return cards.filter(c => c.type.toLowerCase() === filterTab.value)
})

const deckSize = computed(() => deck.value.length)
const canConfirm = computed(() => deckSize.value === 30)

// Count how many copies of a card are in the deck
function countInDeck(cardId: string): number {
  return deck.value.filter(id => id === cardId).length
}

// Max copies allowed
function maxCopies(card: CardDisplay): number {
  return card.unique ? 1 : 2
}

function canAddCard(card: CardDisplay): boolean {
  if (card.allowed === false) return false
  if (deckSize.value >= 30) return false
  return countInDeck(card.id) < maxCopies(card)
}

function addCard(card: CardDisplay) {
  if (!canAddCard(card)) return
  deck.value.push(card.id)
}

function removeCard(cardId: string) {
  const idx = deck.value.indexOf(cardId)
  if (idx !== -1) deck.value.splice(idx, 1)
}

// Build a display-friendly deck list grouped by card
const deckEntries = computed(() => {
  const map = new Map<string, { card: CardDisplay; count: number }>()
  for (const id of deck.value) {
    if (map.has(id)) {
      map.get(id)!.count++
    } else {
      const card = store.availableCards.find(c => c.id === id)
      if (card) map.set(id, { card, count: 1 })
    }
  }
  return Array.from(map.values())
})

function applyPreset(cards: string[]) {
  deck.value = [...cards]
}

function importDeck() {
  const input = window.prompt('粘贴卡组JSON (卡牌ID数组):')
  if (!input) return
  try {
    const parsed = JSON.parse(input)
    if (Array.isArray(parsed) && parsed.every((x: unknown) => typeof x === 'string')) {
      deck.value = parsed
      store.addToast(`导入 ${parsed.length} 张卡牌`, 'info')
    } else {
      store.addToast('格式错误: 需要字符串数组', 'error')
    }
  } catch {
    store.addToast('JSON 解析失败', 'error')
  }
}

function confirm() {
  if (!canConfirm.value) return
  emit('confirm', [...deck.value])
}

// --- Socket ---

function handleCardList(cards: CardDisplay[], presets: any[], deckReq: any, sigCards: CardDisplay[], weakCards: CardDisplay[]) {
  store.availableCards = cards
  store.deckPresets = presets
  store.deckRequirements = deckReq
  store.signatureCards = sigCards || []
  store.weaknessCards = weakCards || []
}

onMounted(() => {
  client.onCardList = handleCardList
  client.listCards(props.investigatorId)
})

onUnmounted(() => {
  if (client.onCardList === handleCardList) {
    client.onCardList = null
  }
})
</script>

<template>
  <div class="deckbuilder">
    <div class="db-header">
      <button class="btn btn-back" @click="$emit('back')">← 返回</button>
      <h2 class="db-title">构筑卡组</h2>
    </div>

    <div class="db-body">
      <!-- Left: Card Catalog -->
      <div class="catalog-panel">
        <!-- Filter Tabs -->
        <div class="filter-tabs">
          <button
            v-for="f in FILTER_LABELS"
            :key="f.key"
            class="tab-btn"
            :class="{ active: filterTab === f.key }"
            @click="filterTab = f.key"
          >
            {{ f.label }}
          </button>
        </div>

        <!-- Card Grid -->
        <div class="card-grid">
          <div
            v-for="card in filteredCards"
            :key="card.id"
            class="card-item"
            :class="{
              disabled: card.allowed === false,
              maxed: countInDeck(card.id) >= maxCopies(card),
            }"
            :style="{ borderColor: CLASS_COLORS[card.class] || '#333' }"
            @click="addCard(card)"
            @mouseenter="showPreview(card, $event)"
            @mouseleave="hidePreview"
          >
            <div class="card-top">
              <span class="card-name">{{ card.name_cn }}</span>
              <span class="card-cost" v-if="card.cost !== null">{{ card.cost }}</span>
            </div>
            <div class="card-meta">
              <span class="card-type">{{ card.type }}</span>
              <span class="card-level" v-if="card.level != null && card.level > 0">Lv.{{ card.level }}</span>
            </div>
            <div class="card-count" v-if="countInDeck(card.id) > 0">
              x{{ countInDeck(card.id) }}
            </div>
            <div class="card-locked" v-if="card.allowed === false">
              需要{{ card.level || 0 }}经验
            </div>
          </div>
        </div>

        <!-- 悬浮预览 tooltip -->
        <div v-if="previewCard" class="card-preview" :style="previewStyle">
          <div class="pv-header" :style="{ borderBottomColor: CLASS_COLORS[previewCard.class] || '#333' }">
            <span v-if="previewCard.cost !== null" class="pv-cost">{{ previewCard.cost }}</span>
            <span class="pv-name">{{ previewCard.name_cn || previewCard.name }}</span>
            <span v-if="previewCard.level != null && previewCard.level > 0" class="pv-level">Lv.{{ previewCard.level }}</span>
          </div>
          <div class="pv-meta">
            <span>{{ TYPE_LABELS[previewCard.type] || previewCard.type }}</span>
            <span v-if="previewCard.slots?.length"> · {{ previewCard.slots.map(s => SLOT_LABELS[s] || s).join('、') }}</span>
            <span v-if="previewCard.unique"> · 唯一</span>
          </div>
          <div v-if="previewCard.traits?.length" class="pv-traits">{{ previewCard.traits.join(' · ') }}</div>
          <div v-if="Object.keys(previewCard.skill_icons || {}).length" class="pv-icons">
            <span v-for="(n, k) in previewCard.skill_icons" :key="k" class="pv-icon">
              {{ SKILL_ICON_LABELS[k] || k }}×{{ n }}
            </span>
          </div>
          <div v-if="previewCard.text_cn" class="pv-text" v-html="previewCard.text_cn"></div>
          <div v-else-if="previewCard.text" class="pv-text" v-html="previewCard.text"></div>
          <div v-if="previewCard.health != null || previewCard.sanity != null" class="pv-stats">
            <span v-if="previewCard.health != null">♥{{ previewCard.health }}</span>
            <span v-if="previewCard.sanity != null">☽{{ previewCard.sanity }}</span>
          </div>
        </div>
      </div>

      <!-- Right: Deck List -->
      <div class="deck-panel">
        <div class="deck-header">
          <span class="deck-count" :class="{ full: deckSize === 30 }">{{ deckSize }} / 30</span>
        </div>

        <div class="deck-list">
          <!-- Auto-included signature cards -->
          <div v-if="store.signatureCards.length > 0 || store.weaknessCards.length > 0" class="auto-section">
            <div class="auto-label">自动加入（专属卡/弱点）</div>
            <div
              v-for="card in store.signatureCards"
              :key="'sig_' + card.id"
              class="deck-entry auto-entry"
              :style="{ borderLeftColor: '#d4a017' }"
            >
              <span class="entry-name">{{ card.name_cn || card.name }}</span>
              <span class="entry-tag sig-tag">专属</span>
            </div>
            <div
              v-for="card in store.weaknessCards"
              :key="'weak_' + card.id"
              class="deck-entry auto-entry"
              :style="{ borderLeftColor: '#c0392b' }"
            >
              <span class="entry-name">{{ card.name_cn || card.name }}</span>
              <span class="entry-tag weak-tag">弱点</span>
            </div>
          </div>
          <!-- User-selected cards -->
          <div
            v-for="entry in deckEntries"
            :key="entry.card.id"
            class="deck-entry"
            :style="{ borderLeftColor: CLASS_COLORS[entry.card.class] || '#333' }"
          >
            <span class="entry-name">{{ entry.card.name_cn }}</span>
            <span class="entry-count">x{{ entry.count }}</span>
            <button class="entry-remove" @click="removeCard(entry.card.id)" title="移除一张">-</button>
          </div>
          <div v-if="deckEntries.length === 0" class="deck-empty">
            点击左侧卡牌添加到卡组
          </div>
        </div>

        <!-- Presets -->
        <div class="deck-presets" v-if="store.deckPresets.length > 0">
          <div class="presets-label">预设卡组</div>
          <button
            v-for="preset in store.deckPresets"
            :key="preset.id"
            class="preset-btn"
            @click="applyPreset(preset.cards)"
          >
            {{ preset.name }}
          </button>
        </div>

        <!-- Actions -->
        <div class="deck-actions">
          <button class="btn btn-import" @click="importDeck">导入卡组</button>
          <button class="btn btn-confirm" :disabled="!canConfirm" @click="confirm">确认</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.deckbuilder {
  width: 100vw;
  height: 100vh;
  background: #0a0a1a;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', sans-serif;
}

.db-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: #0d0d20;
  border-bottom: 1px solid #1a1a2e;
}

.db-title {
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

.db-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Card Preview Tooltip */
.card-preview {
  position: fixed;
  z-index: 1000;
  width: 280px;
  max-height: 420px;
  overflow-y: auto;
  background: #14142b;
  border: 1px solid #333355;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6);
  pointer-events: none;
  font-size: 12px;
  color: #ccc;
}

.pv-header {
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 2px solid #333;
  padding-bottom: 6px;
  margin-bottom: 6px;
}

.pv-cost {
  background: #2c3e50;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: #fff;
  flex-shrink: 0;
}

.pv-name {
  font-weight: bold;
  color: #e8e8e8;
  font-size: 14px;
}

.pv-level {
  margin-left: auto;
  color: #d4a017;
  font-size: 11px;
}

.pv-meta {
  color: #999;
  margin-bottom: 4px;
}

.pv-traits {
  color: #7fb3d3;
  font-style: italic;
  margin-bottom: 6px;
}

.pv-icons {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.pv-icon {
  background: #1f2b3a;
  border-radius: 4px;
  padding: 1px 6px;
  color: #9fc5e8;
}

.pv-text {
  line-height: 1.6;
  color: #bbb;
}

.pv-text :deep(b) {
  color: #e0c070;
}

.pv-stats {
  margin-top: 6px;
  display: flex;
  gap: 10px;
  color: #d98880;
}

/* Catalog Panel */
.catalog-panel {
  width: 70%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #1a1a2e;
}

.filter-tabs {
  display: flex;
  gap: 4px;
  padding: 10px 16px;
  border-bottom: 1px solid #1a1a2e;
}

.tab-btn {
  background: #1a1a2e;
  border: none;
  color: #999;
  padding: 6px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}

.tab-btn.active {
  background: #2980b9;
  color: #fff;
}

.tab-btn:hover:not(.active) {
  background: #252540;
  color: #ccc;
}

.card-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
  align-content: start;
}

.card-item {
  background: #12122a;
  border: 2px solid #333;
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
  min-height: 70px;
}

.card-item:hover:not(.disabled):not(.maxed) {
  background: #1a1a3a;
  transform: translateY(-1px);
}

.card-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.card-item.maxed {
  opacity: 0.6;
  cursor: default;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}

.card-name {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
  flex: 1;
}

.card-cost {
  background: #2a2a4a;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: 6px;
}

.card-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.card-type {
  font-size: 11px;
  color: #777;
  text-transform: capitalize;
}

.card-level {
  font-size: 11px;
  color: #d4a017;
  font-weight: 600;
}

.card-count {
  position: absolute;
  top: 4px;
  right: 4px;
  background: #2980b9;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 8px;
}

.card-locked {
  font-size: 10px;
  color: #c0392b;
  margin-top: 4px;
}

/* Deck Panel */
.deck-panel {
  width: 30%;
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
}

.deck-header {
  margin-bottom: 12px;
}

.deck-count {
  font-size: 18px;
  font-weight: 700;
  color: #999;
}

.deck-count.full {
  color: #27ae60;
}

.deck-list {
  flex: 1;
  overflow-y: auto;
}

.deck-entry {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  margin-bottom: 3px;
  background: #12122a;
  border-left: 3px solid #333;
  border-radius: 3px;
  gap: 8px;
}

.entry-name {
  flex: 1;
  font-size: 13px;
  color: #ccc;
}

.entry-count {
  font-size: 12px;
  color: #888;
  font-weight: 600;
}

.entry-remove {
  background: none;
  border: 1px solid #444;
  color: #c0392b;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  line-height: 1;
}

.entry-remove:hover {
  background: #c0392b;
  color: #fff;
  border-color: #c0392b;
}

.deck-empty {
  color: #555;
  font-size: 13px;
  text-align: center;
  padding: 30px 0;
}

.auto-section {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #2a2a3e;
}

.auto-label {
  font-size: 10px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.auto-entry {
  opacity: 0.8;
}

.entry-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 6px;
  font-weight: 600;
}

.sig-tag {
  background: #3a3010;
  color: #d4a017;
}

.weak-tag {
  background: #3a1010;
  color: #e74c3c;
}

/* Presets */
.deck-presets {
  padding: 10px 0;
  border-top: 1px solid #1a1a2e;
}

.presets-label {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.preset-btn {
  background: #1a1a2e;
  border: 1px solid #333;
  color: #aaa;
  padding: 4px 12px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  margin-right: 6px;
  margin-bottom: 4px;
}

.preset-btn:hover {
  background: #252540;
  color: #fff;
}

/* Actions */
.deck-actions {
  display: flex;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid #1a1a2e;
}

.btn {
  padding: 8px 18px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-import {
  background: #1a1a2e;
  color: #ccc;
  border: 1px solid #333;
}

.btn-import:hover {
  background: #252540;
}

.btn-confirm {
  background: #27ae60;
  color: #fff;
  flex: 1;
}

.btn-confirm:hover:not(:disabled) {
  background: #2ecc71;
}
</style>
