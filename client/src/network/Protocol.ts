/** Socket.IO event names — mirrors server/protocol.py */

export const ServerEvent = {
  STATE_UPDATE: 'state_update',
  ACTION_RESULT: 'action_result',
  GAME_EVENT: 'game_event',
  ROOM_UPDATE: 'room_update',
  PENDING_CHOICE: 'pending_choice',
  ERROR: 'error',
} as const

export const ClientEvent = {
  CREATE_ROOM: 'create_room',
  JOIN_ROOM: 'join_room',
  LEAVE_ROOM: 'leave_room',
  SETUP_GAME: 'setup_game',
  PLAYER_ACTION: 'player_action',
  END_TURN: 'end_turn',
  RESOLVE_CHOICE: 'resolve_choice',
  CHAT: 'chat',
} as const
