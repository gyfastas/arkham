/** Socket.IO client wrapper for game server communication. */

import { io, Socket } from 'socket.io-client'
import { ServerEvent, ClientEvent } from './Protocol'
import type { GameState, ActionResult, RoomState, GameEventData, CardDisplay, InvestigatorDetail, DeckPreset, CampaignStateData, CampaignSaveSummary, ChaosBagInfo, OptionsData } from '../state/types'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected'

export class SocketClient {
  private socket: Socket | null = null
  private _playerId: string = ''
  private _state: ConnectionState = 'disconnected'
  private connectionPromise: Promise<void> | null = null

  // Callbacks
  onStateUpdate: ((state: GameState, events?: GameEventData[]) => void) | null = null
  onActionResult: ((result: ActionResult) => void) | null = null
  onRoomUpdate: ((room: RoomState) => void) | null = null
  onError: ((error: { message: string; code: string }) => void) | null = null
  onConnect: (() => void) | null = null
  onDisconnect: (() => void) | null = null

  get playerId(): string { return this._playerId }
  get state(): ConnectionState { return this._state }

  connect(url?: string): Promise<void> {
    if (this._state === 'connected' && this.socket) {
      return Promise.resolve()
    }
    if (this.connectionPromise) {
      return this.connectionPromise
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      this._state = 'connecting'
      this.socket = io(url || window.location.origin, {
        transports: ['websocket', 'polling'],
      })

      this.socket.on('connect', () => {
        this._state = 'connected'
        this.onConnect?.()
      })

      this.socket.on('welcome', (data: { player_id: string; rooms: RoomState[] }) => {
        this._playerId = data.player_id
        resolve()
      })

      this.socket.on('disconnect', () => {
        this._state = 'disconnected'
        this.onDisconnect?.()
      })

      this.socket.on('connect_error', (err: Error) => {
        this._state = 'disconnected'
        reject(err)
      })

      this.socket.on(ServerEvent.STATE_UPDATE, (data: { state: GameState; events?: GameEventData[] }) => {
        this.onStateUpdate?.(data.state, data.events)
      })

      this.socket.on(ServerEvent.ACTION_RESULT, (data: ActionResult) => {
        this.onActionResult?.(data)
      })

      this.socket.on(ServerEvent.ROOM_UPDATE, (data: RoomState) => {
        this.onRoomUpdate?.(data)
      })

      this.socket.on(ServerEvent.ERROR, (data: { message: string; code: string }) => {
        this.onError?.(data)
      })

      this.socket.on('card_list', (data: { cards: CardDisplay[]; presets?: DeckPreset[]; deck_requirements?: any; signature_cards?: CardDisplay[]; weakness_cards?: CardDisplay[] }) => {
        this.onCardList?.(data.cards, data.presets || [], data.deck_requirements || null, data.signature_cards || [], data.weakness_cards || [])
      })

      this.socket.on('investigator_detail', (data: InvestigatorDetail) => {
        this.onInvestigatorDetail?.(data)
      })

      this.socket.on('campaign_state', (data: CampaignStateData | null) => {
        this.onCampaignState?.(data)
      })

      this.socket.on('campaign_list', (data: { campaigns: CampaignSaveSummary[] }) => {
        this.onCampaignList?.(data.campaigns || [])
      })

      this.socket.on('chaos_bag_info', (data: ChaosBagInfo) => {
        this.onChaosBagInfo?.(data)
      })

      this.socket.on('options', (data: OptionsData) => {
        this.onOptions?.(data)
      })
    })

    this.connectionPromise = this.connectionPromise.finally(() => {
      this.connectionPromise = null
    })
    return this.connectionPromise
  }

  async ensureConnected(): Promise<void> {
    if (this._state === 'connected' && this.socket) return
    await this.connect()
  }

  disconnect(): void {
    this.socket?.disconnect()
    this.socket = null
    this._state = 'disconnected'
    this.connectionPromise = null
  }

  createRoom(): void {
    this.socket?.emit(ClientEvent.CREATE_ROOM, {})
  }

  joinRoom(roomId: string): void {
    this.socket?.emit(ClientEvent.JOIN_ROOM, { room_id: roomId })
  }

  leaveRoom(): void {
    this.socket?.emit(ClientEvent.LEAVE_ROOM, {})
  }

  setupGame(scenarioId: string, investigatorId: string, deckPreset?: string, deckCards?: string[], difficulty?: string, saveId?: string): void {
    const payload: Record<string, unknown> = {
      scenario_id: scenarioId,
      investigator_id: investigatorId,
      deck_preset: deckPreset || '',
    }
    if (deckCards && deckCards.length > 0) {
      payload.deck_cards = deckCards
    }
    if (difficulty) payload.difficulty = difficulty
    if (saveId) payload.save_id = saveId
    this.socket?.emit(ClientEvent.SETUP_GAME, payload)
  }

  listCards(investigatorId: string, xp: number = 0): void {
    this.socket?.emit(ClientEvent.LIST_CARDS, { investigator_id: investigatorId, xp })
  }

  getInvestigator(investigatorId: string): void {
    this.socket?.emit(ClientEvent.GET_INVESTIGATOR, { investigator_id: investigatorId })
  }

  onCardList: ((cards: CardDisplay[], presets: DeckPreset[], deckReq: any, signatureCards: CardDisplay[], weaknessCards: CardDisplay[]) => void) | null = null
  onInvestigatorDetail: ((detail: InvestigatorDetail) => void) | null = null
  onCampaignState: ((state: CampaignStateData | null) => void) | null = null
  onCampaignList: ((saves: CampaignSaveSummary[]) => void) | null = null
  onChaosBagInfo: ((info: ChaosBagInfo) => void) | null = null
  onOptions: ((options: OptionsData) => void) | null = null

  getCampaignState(): void {
    this.socket?.emit(ClientEvent.CAMPAIGN_STATE, {})
  }

  campaignNew(data: { campaign_id: string; investigator_id: string; difficulty: string; deck_cards: string[] }): void {
    this.socket?.emit(ClientEvent.CAMPAIGN_NEW, data)
  }

  campaignList(): void {
    this.socket?.emit(ClientEvent.CAMPAIGN_LIST, {})
  }

  campaignContinue(saveId: string, advance: boolean = false): void {
    this.socket?.emit(ClientEvent.CAMPAIGN_CONTINUE, { save_id: saveId, advance })
  }

  campaignUpgradeDeck(saveId: string, newDeck: string[]): void {
    this.socket?.emit(ClientEvent.CAMPAIGN_UPGRADE, { save_id: saveId, new_deck: newDeck })
  }

  getChaosBagInfo(campaign: string, difficulty: string): void {
    this.socket?.emit(ClientEvent.GET_CHAOS_BAG_INFO, { campaign, difficulty })
  }

  getOptions(): void {
    this.socket?.emit(ClientEvent.GET_OPTIONS, {})
  }

  setSaveDir(saveDir: string): void {
    this.socket?.emit(ClientEvent.SET_OPTIONS, { save_dir: saveDir })
  }

  sendAction(action: string, params: Record<string, unknown> = {}): void {
    this.socket?.emit(ClientEvent.PLAYER_ACTION, { action, ...params })
  }

  endTurn(): void {
    this.socket?.emit(ClientEvent.END_TURN, {})
  }

  resolveChoice(choiceId: string): void {
    this.socket?.emit(ClientEvent.RESOLVE_CHOICE, { choice_id: choiceId })
  }
}
