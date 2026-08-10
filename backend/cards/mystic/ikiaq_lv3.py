"""Ikiaq (Level 3) — Mystic Asset, Ally slot. (08030)
你+1[willpower]和+1[intellect]。伊奇亚克下每压有1张弱点，你-1[willpower]
和-1[intellect]。
[reaction] 当你所在地点的一位调查员抽取1张基础弱点时，横置伊奇亚克：
取消该弱点的效果，并将其面朝下压在伊奇亚克下。如果伊奇亚克离场，
其拥有者必须抽取该弱点。

简化说明：
- 基础弱点按 subtype == "basic_weakness" 判定（is_weakness_card 细分）。
- 取消经 CARD_DRAWN 的 ctx.cancel()：本卡注册早于抽牌时临时注册的弱点实现，
  WHEN 优先级内先触发并取消，弱点的 revelation 处理不再执行（依赖注册顺序，
  与 draw_hooks 的临时注册时机配合）。
- 压置的弱点记录在 scenario.vars["ikiaq_beneath_{instance_id}"]；
  离场时放回拥有者手牌（官方为"抽取"，等效入手的简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Ikiaq(CardImplementation):
    card_id = "ikiaq_lv3"

    def _beneath(self, game_state) -> list:
        return game_state.scenario.vars.setdefault(
            f"ikiaq_beneath_{self.instance_id}", [])

    def _is_basic_weakness(self, game_state, card_id) -> bool:
        cd = game_state.get_card_data(card_id)
        sub = (getattr(cd, "subtype", "") or "").lower().replace("_", "")
        return sub == "basicweakness"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        bonus = 1 - len(self._beneath(ctx.game_state))
        if bonus:
            ctx.modify_amount(bonus, f"{self.card_id}_bonus")

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_basic_weakness(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id or not self._is_basic_weakness(ctx.game_state, card_id):
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if (owner is None or drawer is None
                or self.instance_id not in owner.play_area
                or owner.location_id != drawer.location_id):
            return

        inst.exhausted = True
        if card_id in drawer.hand:
            drawer.hand.remove(card_id)
        self._beneath(ctx.game_state).append(card_id)
        ctx.cancel()  # 取消弱点效果（中断后续 CARD_DRAWN 处理）
        ctx.extra["ikiaq_cancelled"] = card_id

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def return_beneath_on_leave(self, ctx):
        """离场：压置的弱点还给拥有者手牌。"""
        if ctx.target != self.instance_id:
            return
        beneath = self._beneath(ctx.game_state)
        if not beneath:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        owner_id = ctx.investigator_id or getattr(inst, "owner_id", None)
        owner = ctx.game_state.get_investigator(owner_id)
        if owner is not None:
            owner.hand.extend(beneath)
        beneath.clear()
