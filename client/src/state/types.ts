/** Game state types matching server JSON shapes. */

export interface CardDisplay {
  id: string
  name: string
  name_cn: string
  type: string
  cost: number | null
  text: string
  text_cn: string
  class: string
  slots: string[]
  skill_icons: Record<string, number>
  traits: string[]
  level?: number
  unique?: boolean
  health?: number | null
  sanity?: number | null
  victory?: number
  allowed?: boolean
}

export interface InvestigatorDetail {
  id: string
  name: string
  name_cn: string
  title_cn: string
  class: string
  health: number
  sanity: number
  skills: { willpower: number; intellect: number; combat: number; agility: number }
  ability_cn: string
  deck_requirements: {
    size: number
    cards: Record<string, { min_level: number; max_level: number }>
  } | null
  signature_cards: string[]
  weakness: string
}

export interface DeckPreset {
  id: string
  name: string
  cards: string[]
}

export interface CardInstanceDisplay {
  instance_id: string
  id: string
  name: string
  name_cn: string
  type: string
  cost: number | null
  text: string
  text_cn: string
  class: string
  exhausted: boolean
  damage: number
  horror: number
  health: number | null
  sanity: number | null
  uses: Record<string, number> | null
  slots: string[]
  skill_icons: Record<string, number>
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
  act: { id: string; name: string; name_cn: string; clues: number; text_cn: string; back_text: string; back_text_cn: string; sequence: number; total: number } | null
  agenda: { id: string; name: string; name_cn: string; doom: number; text_cn: string; back_text: string; back_text_cn: string; sequence: number; total: number } | null
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
  encounter_deck_count?: number
  encounter_discard_count?: number
  last_encounter?: EncounterCardDisplay | null
}

export interface EncounterCardDisplay {
  id: string
  name: string
  name_cn: string
  type: string
  text: string
  traits: string[]
  fight?: number
  health?: number
  evade?: number
  damage?: number
  horror?: number
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

export interface CampaignStateData {
  investigator_id: string
  campaign_id: string
  scenario_index: number
  xp: number
  xp_earned: number
  xp_spent: number
  deck: string[]
  victory_display: string[]
  trauma_physical: number
  trauma_mental: number
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
