/** Game state types matching server JSON shapes. */

export interface CardDisplay {
  id: string
  name: string
  name_cn: string
  type: string
  cost: number | null
  text: string
  class: string
  slots: string[]
  skill_icons: Record<string, number>
  traits: string[]
}

export interface CardInstanceDisplay {
  instance_id: string
  id: string
  name: string
  name_cn: string
  exhausted: boolean
  uses: Record<string, number> | null
  slots: string[]
  traits: string[]
}

export interface EnemyDisplay {
  instance_id: string
  id: string
  name: string
  name_cn: string
  fight: number
  health: number
  evade: number
  damage_dealt: number
  horror_dealt: number
  current_damage: number
  exhausted: boolean
  engaged: boolean
}

export interface LocationDisplay {
  name: string
  name_cn: string
  shroud: number
  clues: number
  connections: string[]
  enemies_here: number
  is_current?: boolean
}

export interface InvestigatorDisplay {
  id: string
  name: string
  name_cn: string
  class: string
  health: number
  sanity: number
  damage: number
  horror: number
  resources: number
  clues: number
  actions_remaining: number
  tome_actions_remaining: number
  hand_count: number
  deck_count: number
  discard_count: number
  defeated: boolean
  location_id: string
}

export interface ScenarioDisplay {
  id: string
  name: string
  name_cn: string
  act: { id: string; name: string; name_cn: string; clues: number } | null
  agenda: { id: string; name: string; name_cn: string; doom: number } | null
  resolution_id: string | null
}

export interface PendingChoice {
  kind: string
  card_id?: string
  prompt: string
  options: { id: string; label: string }[]
  [key: string]: unknown
}

export interface GameState {
  investigator: InvestigatorDisplay
  location: {
    id: string
    name: string
    name_cn: string
    shroud: number
    clues: number
    connections: string[]
  }
  locations: Record<string, LocationDisplay>
  hand: CardDisplay[]
  discard: CardDisplay[]
  play_area: CardInstanceDisplay[]
  enemies: EnemyDisplay[]
  log: string[]
  round: number
  phase: string
  doom: number
  doom_threshold: number
  total_clues_needed: number
  scenario: ScenarioDisplay
  treacheries: unknown[]
  pending_choice: PendingChoice | null
  game_over: { type: string; message: string } | null
}

export interface GameEventData {
  event: string
  investigator_id?: string
  amount?: number
  chaos_token?: string
  success?: boolean
  target?: string
  source?: string
  enemy_id?: string
  location_id?: string
  skill_type?: string
  difficulty?: number
  action?: string
  modified_skill?: number
  card_id?: string
}

export interface ActionResult {
  success: boolean
  message: string
  events: GameEventData[]
  state: GameState
}

export interface RoomState {
  room_id: string
  host_player_id: string
  status: 'lobby' | 'in_game' | 'finished'
  seats: {
    seat_num: number
    player_id: string | null
    investigator_id: string
    deck_preset: string
    ready: boolean
  }[]
}
