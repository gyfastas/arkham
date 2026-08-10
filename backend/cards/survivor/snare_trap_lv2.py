"""Snare Trap (Level 2) — Survivor Event.
叠加到你所在地点。每个地点限制1张。
强制 - 在一名非精英敌人进入被叠加地点后：消耗该敌人，解除它与所有
调查员的交战状态，并对其叠加诱捕陷阱。
强制 - 在被叠加的敌人将要准备时：改为丢弃诱捕陷阱。

简化说明：
- 叠加关系记录在 scenario.vars["snare_trap"]（同 barricade 的 vars 标记
  模式；事件牌在打出结算后即入弃牌堆，"叠加"为纯标记）。
- 引擎无"敌人进入地点"通用事件：拦截 ENEMY_ENGAGED（敌人与位于被叠加
  地点的调查员交战，覆盖猎手移动交战/主动交战两条常见路径）；遭遇牌
  生成直接挂威胁区（official_core 无事件）与猎手移动进入无人地点不触发
  （引擎缺口，见报告）。
- "将要准备时改为丢弃"：引擎 upkeep 先置 ready 再发 CARD_READIED，无法
  阻止；近似为 CARD_READIED 时重新横置该敌人并移除陷阱标记（净效果
  一致：本次 upkeep 敌人保持消耗，陷阱离场）。
- "每个地点限制1张"不强制（需会话层校验，从简）。
- 跨轮持续：事件实现实例在 ROUND_ENDS 被引擎清理，跨轮监听缺口同
  barricade_lv0（见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class SnareTrap(CardImplementation):
    card_id = "snare_trap_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：叠加到你所在地点。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.game_state.scenario.vars["snare_trap"] = {
            "location_id": inv.location_id,
            "enemy_instance_id": None,
            "owner_id": ctx.investigator_id,
        }
        ctx.extra["snare_trap_location"] = inv.location_id
        ctx.game_state.log_effect("🪤 诱捕陷阱：叠加到当前地点")

    @on_event(GameEvent.ENEMY_ENGAGED, priority=TimingPriority.AFTER)
    def trap_enemy(self, ctx):
        """强制 - 非精英敌人进入被叠加地点（与地点上调查员交战）后：
        消耗该敌人，解除交战，并对其叠加诱捕陷阱。"""
        trap = ctx.game_state.scenario.vars.get("snare_trap")
        if not trap or trap.get("enemy_instance_id"):
            return
        enemy_iid = ctx.enemy_id
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None or is_elite_enemy(enemy_data):
            return
        # 交战对象须位于被叠加地点
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id != trap.get("location_id"):
            return

        # 消耗 + 解除与所有调查员的交战
        enemy.exhausted = True
        for other in ctx.game_state.investigators.values():
            if enemy_iid in other.threat_area:
                other.threat_area.remove(enemy_iid)
        loc = ctx.game_state.get_location(trap["location_id"])
        if loc is not None and enemy_iid not in loc.enemies:
            loc.enemies.append(enemy_iid)
        trap["enemy_instance_id"] = enemy_iid
        ctx.extra["snare_trap_trapped"] = enemy_iid
        ctx.game_state.log_effect(
            f"🪤 诱捕陷阱：【{ctx.game_state.card_name(enemy.card_id)}】"
            "被消耗并解除交战，陷阱叠加到它身上")

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def discard_instead_of_ready(self, ctx):
        """强制 - 被叠加的敌人将要准备时：改为丢弃诱捕陷阱
        （近似：敌人重新横置，陷阱标记移除）。"""
        trap = ctx.game_state.scenario.vars.get("snare_trap")
        if not trap or ctx.target != trap.get("enemy_instance_id"):
            return
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is not None:
            enemy.exhausted = True
        ctx.extra["snare_trap_discarded"] = True
        ctx.game_state.scenario.vars.pop("snare_trap", None)
        ctx.game_state.log_effect(
            "🪤 诱捕陷阱：被叠加敌人将要准备，改为丢弃诱捕陷阱（敌人保持消耗）")
