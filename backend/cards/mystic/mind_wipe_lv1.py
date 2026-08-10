"""Mind Wipe (Level 1) — Mystic Event. (01068)
快速。在一个阶段开始后打出。选择你所在地点的一个非[[精英]]敌人。
将该敌人的印刷文本框视为空白（[[特性]]除外），直到本阶段结束。

简化说明：
- 通过 scenario.vars["mind_wiped"] 标记；敌方阶段（猎手移动等）读取该标记
  （engine 已在 phase_enemy 接入）；阶段结束自动清除。
- "阶段开始后打出"的时机关口：引擎内不存在阶段外打牌的入口，故天然满足，
  未做额外检查。
- 目标默认选你所在地点（含交战）的第一个非精英敌人，可用
  ctx.extra["enemy_instance_id"] 指定（官方卡面仅限所在地点，不含连接地点）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.scenarios.official_core import is_elite_enemy
from backend.models.enums import GameEvent, TimingPriority


class MindWipe(CardImplementation):
    card_id = "mind_wipe_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def blank_enemy(self, ctx):
        if ctx.extra.get("card_id") != "mind_wipe_lv1":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy = None
        enemy_iid = ctx.extra.get("enemy_instance_id")
        if enemy_iid:
            enemy = ctx.game_state.get_card_instance(enemy_iid)

        if enemy is None:
            # 默认：所在地点（含交战）的第一个非精英敌人
            candidates = list(inv.threat_area)
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None:
                candidates += list(loc.enemies)
            for iid in candidates:
                inst = ctx.game_state.get_card_instance(iid)
                if inst is None:
                    continue
                cd = ctx.game_state.get_card_data(inst.card_id)
                if cd is not None and not is_elite_enemy(cd):
                    enemy = inst
                    enemy_iid = iid
                    break

        if enemy is None or enemy_iid is None:
            return
        cd = ctx.game_state.get_card_data(enemy.card_id)
        if cd is not None and is_elite_enemy(cd):
            return

        ctx.game_state.scenario.vars.setdefault("mind_wiped", {})[enemy_iid] = True
        ctx.extra["mind_wiped_enemy"] = enemy_iid

    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.AFTER)
    def clear_phase_end(self, ctx):
        ctx.game_state.scenario.vars.pop("mind_wiped", None)
