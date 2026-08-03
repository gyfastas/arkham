import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  GameState, CardDisplay, InvestigatorDetail, DeckPreset,
  ActionResult, GameEventData, PendingChoice, CampaignStateData,
  EncounterCardDisplay, CampaignSaveSummary, ChaosBagInfo,
} from '../state/types'

export type GameLanguage = 'zh-Hans' | 'zh-Hant'

const LANGUAGE_STORAGE_KEY = 'arkham-language'

function loadLanguage(): GameLanguage {
  const saved = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  return saved === 'zh-Hans' || saved === 'zh-Hant' ? saved : 'zh-Hans'
}

export const useGameStore = defineStore('game', () => {
  // Connection
  const connected = ref(false)
  const playerId = ref('')

  // Lobby state
  const selectedScenario = ref('')
  const selectedInvestigator = ref('')
  // Keep the original card data untouched; this preference controls display
  // language and can be expanded when translated fields are added later.
  const language = ref<GameLanguage>(loadLanguage())
  const investigatorDetail = ref<InvestigatorDetail | null>(null)
  const availableCards = ref<CardDisplay[]>([])
  const deckPresets = ref<DeckPreset[]>([])
  const deckRequirements = ref<Record<string, any> | null>(null)
  const signatureCards = ref<CardDisplay[]>([])
  const weaknessCards = ref<CardDisplay[]>([])

  // Game state
  const state = ref<GameState | null>(null)
  const gameOver = ref<{ type: string; message: string } | null>(null)
  const lastActionResult = ref<ActionResult | null>(null)
  const pendingEvents = ref<GameEventData[]>([])

  // Campaign
  const campaignState = ref<CampaignStateData | null>(null)
  const campaignSaves = ref<CampaignSaveSummary[]>([])
  const chaosBagInfo = ref<ChaosBagInfo | null>(null)
  const difficulty = ref<string>('standard')

  // Toast messages
  const toasts = ref<{ id: number; message: string; type: 'error' | 'info' }[]>([])
  let toastId = 0

  function addToast(message: string, type: 'error' | 'info' = 'info') {
    const id = ++toastId
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
    }, 3000)
  }

  function setLanguage(next: GameLanguage) {
    language.value = next
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, next)
  }

  function updateState(newState: GameState, events?: GameEventData[]) {
    state.value = newState
    if (events) pendingEvents.value = events
    if (newState.game_over && !gameOver.value) {
      gameOver.value = newState.game_over
    }
  }

  function reset() {
    state.value = null
    gameOver.value = null
    lastActionResult.value = null
    pendingEvents.value = []
    investigatorDetail.value = null
    availableCards.value = []
    deckPresets.value = []
    deckRequirements.value = null
    campaignState.value = null
    chaosBagInfo.value = null
  }

  return {
    connected, playerId,
    selectedScenario, selectedInvestigator,
    language, setLanguage,
    investigatorDetail, availableCards, deckPresets, deckRequirements, signatureCards, weaknessCards,
    state, gameOver, lastActionResult, pendingEvents,
    campaignState, campaignSaves, chaosBagInfo, difficulty,
    toasts, addToast,
    updateState, reset,
  }
})
