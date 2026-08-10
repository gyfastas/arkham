"""Telescopic Sight (Level 3) — Guardian Event. (05230)
快速。叠加到你控制的一张占用2个手部槽位的[[枪械]]支援卡。被叠加支援卡不能被
用来攻击与你交战的敌人。
[reaction]在你使用被叠加的支援卡执行<b>攻击</b>行动时，如果你未与敌人交战，
消耗瞄准镜：这次攻击可以选择位于一个连接地点的一名非[[精英]]敌人作为目标。
这次攻击忽略冷漠和反击关键词。

简化说明：
- 叠加目标经 ctx.extra["attach_to"] 指定，缺省自动选择你装备区第一张占2个
  手部槽位的枪械；叠加关系记录在 scenario.vars["telescopic_sight"]。
- "不能攻击与你交战的敌人"经 FIGHT_ACTION_INITIATED 取消实现（目标在你
  威胁区时取消攻击，行动不消耗）。
- 反应能力为公开方法 activate_snipe()：校验未交战且未用过，标记本次攻击
  允许以连接地点非精英敌人为目标（引擎 _fight 本就不校验目标地点，故主要
  作用是权限标记）；忽略反击无引擎通道（on_failure 直接结算反击伤害，
  不经事件总线），忽略冷漠由会话层目标校验负责——均列为引擎/会话缺口。
- 引擎缺口：事件实现实例在 ROUND_ENDS 被自动注销，永久叠加效果跨轮持续
  需要引擎支持，见报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority

_VAR = "telescopic_sight"


class TelescopicSight(CardImplementation):
    card_id = "telescopic_sight_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attached: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach(self, ctx):
        """打出后：叠加到你控制的2手枪械。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = ctx.extra.get("attach_to") or self._first_two_hand_firearm(
            ctx.game_state, inv)
        if target_iid is None or target_iid not in inv.play_area:
            ctx.extra["telescopic_sight_fizzle"] = True
            return
        if not self._is_two_hand_firearm(ctx.game_state, target_iid):
            ctx.extra["telescopic_sight_fizzle"] = True
            return

        ctx.game_state.scenario.vars[_VAR] = {
            "asset": target_iid,
            "controller": inv.investigator_id,
            "used": False,
        }
        self._attached = target_iid
        ctx.extra["telescopic_sight_attached"] = target_iid
        target = ctx.game_state.get_card_instance(target_iid)
        ctx.game_state.log_effect(
            f"🔭 瞄准镜：叠加到【{ctx.game_state.card_name(target.card_id)}】")

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def block_engaged_targets(self, ctx):
        """用被叠加枪械攻击与你交战的敌人：取消该攻击。"""
        record = ctx.game_state.scenario.vars.get(_VAR)
        if record is None or ctx.source != record.get("asset"):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.enemy_id in inv.threat_area:
            ctx.cancel()
            ctx.game_state.log_effect(
                "🔭 瞄准镜：被叠加枪械不能攻击与你交战的敌人，攻击取消")

    def activate_snipe(self, game_state, investigator_id: str,
                       enemy_instance_id: str) -> bool:
        """[reaction] 消耗瞄准镜：本次攻击可瞄准连接地点的非精英敌人。

        由会话层在以被叠加枪械发起攻击时调用；返回 False 表示条件不满足。
        """
        record = game_state.scenario.vars.get(_VAR)
        if record is None or record.get("used"):
            return False
        if record.get("controller") != investigator_id:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.threat_area:
            return False  # 须未与敌人交战
        enemy = game_state.get_card_instance(enemy_instance_id)
        enemy_data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return False
        if "elite" in (enemy_data.keywords or []):
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is None:
            return False
        enemy_loc = _enemy_location(game_state, enemy_instance_id)
        if enemy_loc not in (loc.connections or []):
            return False
        record["used"] = True
        record["snipe_target"] = enemy_instance_id
        game_state.log_effect(
            f"🔭 瞄准镜：消耗，本次攻击瞄准连接地点的"
            f"【{game_state.card_name(enemy.card_id)}】（忽略冷漠与反击）")
        return True

    # ------------------------------------------------------------------

    @staticmethod
    def _is_two_hand_firearm(game_state, instance_id) -> bool:
        inst = game_state.get_card_instance(instance_id)
        data = game_state.get_card_data(inst.card_id) if inst else None
        if inst is None or data is None:
            return False
        if "firearm" not in (data.traits or []):
            return False
        hand_slots = [s for s in (inst.slot_used or data.slots or [])
                      if s == SlotType.HAND]
        return len(hand_slots) == 2

    @classmethod
    def _first_two_hand_firearm(cls, game_state, inv) -> str | None:
        for iid in inv.play_area:
            if cls._is_two_hand_firearm(game_state, iid):
                return iid
        return None


def _enemy_location(game_state, enemy_instance_id) -> str | None:
    for loc in game_state.locations.values():
        if enemy_instance_id in loc.enemies:
            return loc.location_id
    for inv in game_state.investigators.values():
        if enemy_instance_id in inv.threat_area:
            return inv.location_id
    return None
