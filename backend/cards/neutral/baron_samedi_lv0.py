"""Baron Samedi (Level 0) — Neutral Asset, Weakness.
显现：将萨迈迪男爵放置入场。只要他身上的毁灭标记少于3个，他就不能离场。
强制 - 当任意数量的伤害被放置到萨迈迪男爵所在地点的调查员身上时：
在该调查员身上多放置1点伤害。
[fast] 横置萨迈迪男爵：在他身上放置1个毁灭标记。若他身上有3个或更多
毁灭标记，丢弃他。

简化说明：
- 显现将男爵放入持有者的在场区（支援卡弱点；不占用槽位——引擎的槽位
  占用由 _play_asset 处理，弱点经显现直接入场）。
- 男爵"所在地点"以持有者（owner）的当前地点近似（官方男爵不占据地点，
  规则上视为在持有者地点）。
- "+1伤害"在 DAMAGE_ASSIGNED 之后直接加到调查员身上（DAMAGE_ASSIGNED
  通道只支持减伤/取消，不支持加伤——引擎缺口）。
- "少于3毁灭不能离场"：引擎的通用离场路径不咨询卡牌（引擎缺口），
  由 can_leave_play() 公开方法供会话层遵守。
- 实现按 card_id 扫描实例（抽到时的临时注册 id 与入场实例 id 不同，
  与 cover_up 等弱点的 _find 惯例一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

DOOM_TO_DISCARD = 3


class BaronSamedi(CardImplementation):
    card_id = "baron_samedi_lv0"
    activations = [{
        "id": "place_doom",
        "label": "[快速] 横置：放置1毁灭（3+则丢弃）",
        "method": "activate_place_doom",
        "actions": 0,
    }]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        """显现：将萨迈迪男爵放置入场（持有者在场区）。"""
        if ctx.extra.get("card_id") != "baron_samedi_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "baron_samedi_lv0" in inv.hand:
            inv.hand.remove("baron_samedi_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="baron_samedi_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def additional_damage(self, ctx):
        """男爵所在地点的调查员被放置伤害时：多放置1点伤害。"""
        if ctx.cancelled or (ctx.amount or 0) <= 0:
            return
        baron = self._find_baron(ctx.game_state)
        if baron is None:
            return
        owner = ctx.game_state.get_investigator(baron.owner_id)
        victim = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or victim is None:
            return
        if victim.location_id != owner.location_id:
            return
        victim.damage += 1  # 额外伤害直接放置
        ctx.extra["baron_samedi_extra_damage"] = True
        ctx.game_state.log_effect("💀 萨迈迪男爵：额外放置1点伤害")

    def activate_place_doom(self, game_state, investigator_id) -> bool:
        """[fast] 横置男爵：放置1毁灭；3+毁灭时丢弃他。"""
        baron = self._find_baron(game_state)
        if baron is None or baron.exhausted:
            return False
        baron.exhausted = True
        baron.doom += 1
        if baron.doom >= DOOM_TO_DISCARD:
            self._discard(game_state, baron)
        return True

    def can_leave_play(self, game_state) -> bool:
        """少于3个毁灭标记时男爵不能离场（供会话层/引擎遵守）。"""
        baron = self._find_baron(game_state)
        if baron is None:
            return True
        return baron.doom >= DOOM_TO_DISCARD

    def _discard(self, game_state, baron) -> None:
        owner = game_state.get_investigator(baron.owner_id)
        if owner is not None and baron.instance_id in owner.play_area:
            owner.play_area.remove(baron.instance_id)
            owner.discard.append("baron_samedi_lv0")
        game_state.cards_in_play.pop(baron.instance_id, None)
        game_state.log_effect("💀 萨迈迪男爵：3个毁灭标记，丢弃")

    @staticmethod
    def _find_baron(game_state):
        for inv in game_state.investigators.values():
            for inst_id in inv.play_area:
                inst = game_state.get_card_instance(inst_id)
                if inst is not None and inst.card_id == "baron_samedi_lv0":
                    return inst
        return None
