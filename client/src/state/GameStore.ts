/** Client-side game state store with Phaser event emission. */

import Phaser from 'phaser'
import type { GameState, GameEventData } from './types'

export const STORE_EVENTS = {
  STATE_CHANGED: 'state-changed',
  HAND_CHANGED: 'hand-changed',
  LOCATIONS_CHANGED: 'locations-changed',
  INVESTIGATOR_CHANGED: 'investigator-changed',
  ENEMIES_CHANGED: 'enemies-changed',
  PLAY_AREA_CHANGED: 'play-area-changed',
  LOG_CHANGED: 'log-changed',
  GAME_OVER: 'game-over',
  PENDING_CHOICE: 'pending-choice',
} as const

export class GameStore {
  private _state: GameState | null = null
  readonly events = new Phaser.Events.EventEmitter()

  get state(): GameState | null { return this._state }

  update(newState: GameState): void {
    const prev = this._state
    this._state = newState

    // Emit granular change events
    if (!prev || JSON.stringify(prev.hand) !== JSON.stringify(newState.hand)) {
      this.events.emit(STORE_EVENTS.HAND_CHANGED, newState.hand)
    }
    if (!prev || JSON.stringify(prev.locations) !== JSON.stringify(newState.locations)) {
      this.events.emit(STORE_EVENTS.LOCATIONS_CHANGED, newState.locations)
    }
    if (!prev || JSON.stringify(prev.investigator) !== JSON.stringify(newState.investigator)) {
      this.events.emit(STORE_EVENTS.INVESTIGATOR_CHANGED, newState.investigator)
    }
    if (!prev || JSON.stringify(prev.enemies) !== JSON.stringify(newState.enemies)) {
      this.events.emit(STORE_EVENTS.ENEMIES_CHANGED, newState.enemies)
    }
    if (!prev || JSON.stringify(prev.play_area) !== JSON.stringify(newState.play_area)) {
      this.events.emit(STORE_EVENTS.PLAY_AREA_CHANGED, newState.play_area)
    }
    if (!prev || prev.log.length !== newState.log.length) {
      this.events.emit(STORE_EVENTS.LOG_CHANGED, newState.log)
    }
    if (newState.game_over && (!prev || !prev.game_over)) {
      this.events.emit(STORE_EVENTS.GAME_OVER, newState.game_over)
    }
    if (newState.pending_choice) {
      this.events.emit(STORE_EVENTS.PENDING_CHOICE, newState.pending_choice)
    }

    this.events.emit(STORE_EVENTS.STATE_CHANGED, newState)
  }

  clear(): void {
    this._state = null
  }
}
