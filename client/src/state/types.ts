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
  has_commit_effect?: boolean
  commit_effect_cost?: number
  commit_effect_label?: string
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

export interface ActivationDef {
  id: string
  label: string
  method: string
  actions?: number
  target?: string
  resource_cost?: number
  timing?: string
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
  activations?: ActivationDef[]
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
  slot_summary?: SlotSummary[]
  skill_bonuses?: Record<string, number>
  skills?: Record<string, number>
}

export interface SlotSummary {
  type: string
  used: number
  limit: number
  available: number
}

export interface ScenarioDisplay {
  id: string
  name: string
  name_cn: string
  act: { id: string; name: string; name_cn: string; clues: number; text_cn: string; back_text: string; back_text_cn: string; sequence: number; total: number } | null
  agenda: { id: string; name: string; name_cn: string; doom: number; text_cn: string; back_text: string; back_text_cn: string; sequence: number; total: number } | null
  resolution_id: string | null
  symbol_text?: string
}

export interface PendingChoice {
  kind: string
  card_id?: string
  prompt: string
  options: { id: string; label: string }[]
  [key: string]: unknown
}

export interface PendingSkillTest {
  investigator_id: string
  skill_type: string
  difficulty: number
  base_skill: number
  asset_bonus?: number
  possible_tokens: string[]
  target_label?: string
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
  /** 牌库内容（乱序，仅供查看构成，不代表实际顺序） */
  deck_cards: CardDisplay[]
  play_area: CardInstanceDisplay[]
  threat_cards: CardInstanceDisplay[]
  enemies: EnemyDisplay[]
  mulligan_available?: boolean
  can_advance_act?: boolean
  log: string[]
  round: number
  phase: string
  doom: number
  doom_threshold: number
  total_clues_needed: number
  scenario: ScenarioDisplay
  treacheries: unknown[]
  pending_choice: PendingChoice | null
  pending_skill_test?: PendingSkillTest | null
  game_over: { type: string; message: string } | null
  encounter_deck_count?: number
  encounter_discard_count?: number
  last_encounter?: EncounterCardDisplay | null
  slot_status?: Record<string, SlotStatusEntry>
}

export interface SlotStatusEntry {
  used: number
  base: number
  bonus: number
  restricted: number
  restricted_traits: string[]
  limit: number
  cards: string[]
}

export interface SlotConflictCandidate {
  instance_id: string
  id: string
  name: string
  name_cn: string
  slots: string[]
}

export interface SlotConflict {
  card_id: string
  card_name: string
  needed: Record<string, number>
  candidates: SlotConflictCandidate[]
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
  possible_tokens?: string[]
  base_skill?: number
  committed_icons?: number
  token_modifier?: number
  auto_fail?: boolean
  auto_success?: boolean
  asset_bonus?: number
  skill_bonus_sources?: { reason: string; delta: number }[]
  rexs_curse_redrawn_token?: string
  rexs_curse_redrawn_modifier?: number
}

export interface SkillTestAnimation {
  investigator_id?: string
  skill_type: string
  difficulty: number
  base_skill: number
  asset_bonus?: number
  committed_icons: number
  token: string
  token_modifier: number
  modified_skill: number
  success: boolean
  auto_fail?: boolean
  auto_success?: boolean
  rexs_curse_redrawn_token?: string
  rexs_curse_redrawn_modifier?: number
  possible_tokens: string[]
  target_label?: string
  committed_card_ids?: string[]
}

export interface ActionResult {
  success: boolean
  message: string
  code?: string
  slot_conflict?: SlotConflict
  events: GameEventData[]
  state: GameState
}

export interface CampaignStateData {
  save_id: string
  investigator_id: string
  campaign_id: string
  scenario_index: number
  difficulty: string
  current_scenario_id: string
  is_complete: boolean
  xp: number
  xp_earned: number
  xp_spent: number
  deck: string[]
  victory_display: string[]
  trauma_physical: number
  trauma_mental: number
  upgrade_message?: string
  upgrade_cost?: number
}

export interface CampaignSaveSummary {
  save_id: string
  campaign_id: string
  campaign_name_cn: string
  investigator_id: string
  difficulty: string
  scenario_index: number
  scenario_total: number
  current_scenario_id: string
  is_complete: boolean
  xp: number
  trauma_physical: number
  trauma_mental: number
}

export interface ChaosBagInfo {
  campaign: string
  campaign_name_cn: string
  difficulty: string
  difficulty_label: string
  difficulty_labels: Record<string, string>
  tokens: Record<string, number>
  total: number
  symbol_texts: Record<string, string>
}

export interface OptionsData {
  save_dir: string
  default_save_dir: string
  is_custom: boolean
  save_count: number
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
