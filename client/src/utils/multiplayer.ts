/** 多人联机辅助：调查员实例 id（"player"/"player2"/...）与显示信息的换算。
 *
 * 服务端的实例 id 按座位顺序分配：座位序号 i（从 0 开始）→ "player"{i+1}
 * （i=0 时为 "player"）。``other_investigators`` 保持 player_order 的相对
 * 顺序、仅剔除 viewer 自己，因此可以用 viewer 的实例 id 把完整顺序重建出来。
 */

import type { GameState, OtherInvestigator } from '../state/types'

/** "player" → 0，"player2" → 1，"player3" → 2，... */
export function instanceIndex(instanceId: string): number {
  if (!instanceId || instanceId === 'player') return 0
  const n = parseInt(instanceId.slice('player'.length), 10)
  return Number.isFinite(n) && n >= 2 ? n - 1 : 0
}

/** 0 → "player"，1 → "player2"，... */
export function instanceIdAt(index: number): string {
  return index <= 0 ? 'player' : `player${index + 1}`
}

/** 本客户端（viewer）的调查员实例 id */
export function viewerInstanceId(state: GameState): string {
  return state.investigator?.instance_id || 'player'
}

/** 是否多人局（存在队友） */
export function isMultiplayer(state: GameState): boolean {
  return (state.other_investigators?.length ?? 0) > 0
}

/** other_investigators 中第 i 项对应的调查员实例 id */
export function otherEntryInstanceId(state: GameState, otherIndex: number): string {
  const viewerIdx = instanceIndex(viewerInstanceId(state))
  return instanceIdAt(otherIndex >= viewerIdx ? otherIndex + 1 : otherIndex)
}

/** 按 player_order 顺序的全体调查员（含 viewer 自己，插入在其座位位置） */
export function orderedInvestigators(
  state: GameState,
): { instanceId: string; name: string; name_cn: string; isViewer: boolean }[] {
  const viewerId = viewerInstanceId(state)
  const viewerIdx = instanceIndex(viewerId)
  const others = state.other_investigators ?? []
  const full: { instanceId: string; name: string; name_cn: string; isViewer: boolean }[] =
    others.map((o: OtherInvestigator, i: number) => ({
      instanceId: otherEntryInstanceId(state, i),
      name: o.name,
      name_cn: o.name_cn,
      isViewer: false,
    }))
  full.splice(Math.min(viewerIdx, full.length), 0, {
    instanceId: viewerId,
    name: state.investigator?.name ?? '',
    name_cn: state.investigator?.name_cn ?? '',
    isViewer: true,
  })
  return full
}

/** 实例 id → 显示名（viewer 自己返回空串，由调用方显示「你」） */
export function instanceName(state: GameState, instanceId: string): string {
  const found = orderedInvestigators(state).find(x => x.instanceId === instanceId)
  if (!found || found.isViewer) return ''
  return found.name_cn || found.name
}

/** pending_choice 的属主实例 id：显式 investigator_id 优先，缺省归当前行动者 */
export function pendingChoiceOwnerId(state: GameState): string {
  const pc = state.pending_choice
  if (!pc) return ''
  return (pc.investigator_id as string | undefined) || state.active_investigator_id || ''
}
