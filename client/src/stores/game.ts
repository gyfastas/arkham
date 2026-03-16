import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  GameState, CardDisplay, InvestigatorDetail, DeckPreset,
  ActionResult, GameEventData, PendingChoice, CampaignStateData,
  EncounterCardDisplay,
} from '../state/types'

export const useGameStore = defineStore('game', () => {
  // Connection
  const connected = ref(false)
  const playerId = ref('')

  // Lobby state
  const selectedScenario = ref('')
  const selectedInvestigator = ref('')
  const investigatorDetail = ref<InvestigatorDetail | null>(null)
  const availableCards = ref<CardDisplay[]>([])
  const deckPresets = ref<DeckPreset[]>([])
  const deckRequirements = ref<Record<string, any> | null>(null)

  // Game state
  const state = ref<GameState | null>(null)
  const gameOver = ref<{ type: string; message: string } | null>(null)
  const lastActionResult = ref<ActionResult | null>(null)
  const pendingEvents = ref<GameEventData[]>([])

  // Campaign
  const campaignState = ref<CampaignStateData | null>(null)

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
  }

  return {
    connected, playerId,
    selectedScenario, selectedInvestigator,
    investigatorDetail, availableCards, deckPresets, deckRequirements,
    state, gameOver, lastActionResult, pendingEvents,
    campaignState,
    toasts, addToast,
    updateState, reset,
  }
})
