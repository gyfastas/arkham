/** Socket.IO client wrapper for game server communication. */

import { io, Socket } from 'socket.io-client'
import { ServerEvent, ClientEvent } from './Protocol'
import type { GameState, ActionResult, RoomState, GameEventData } from '../state/types'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected'

export class SocketClient {
  private socket: Socket | null = null
  private _playerId: string = ''
  private _state: ConnectionState = 'disconnected'

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
    return new Promise((resolve, reject) => {
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
    })
  }

  disconnect(): void {
    this.socket?.disconnect()
    this.socket = null
    this._state = 'disconnected'
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

  setupGame(scenarioId: string, investigatorId: string, deckPreset?: string): void {
    this.socket?.emit(ClientEvent.SETUP_GAME, {
      scenario_id: scenarioId,
      investigator_id: investigatorId,
      deck_preset: deckPreset || '',
    })
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
