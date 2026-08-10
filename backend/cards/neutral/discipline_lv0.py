"""Discipline (Level 0) — Neutral Asset, Permanent (Lily Chen deck only).
你获得+1[agility]。
[行动]：逐一进行至多3个不同的战斗或躲避行动。将此支援翻面。本行动不引发
借机攻击。

简化说明：
- 破损（Broken）状态记入 scenario.vars["discipline_broken_{instance_id}"]，
  值为破损时的轮数（burden_of_destiny_lv0 写入同一键；"本轮内不能翻回"
  按轮数判定）。破损时+1[agility]失效。
- [行动]的三连战斗/躲避由会话层逐一发起（每次仍消耗行动并结算检定）；
  activate() 负责翻面并标记本回合已启动。"不引发借机攻击"由会话层在
  发起各行动时处理（引擎 AoO 按行动统一结算——引擎缺口）。
- flip_back() 供会话层在满足条件时翻回（破损当轮不可翻回）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


def _broken_key(instance_id: str) -> str:
    return f"discipline_broken_{instance_id}"


class Discipline(CardImplementation):
    card_id = "discipline_lv0"
    activations = [{
        "id": "discipline_actions",
        "label": "[行动] 至多3个战斗/躲避行动，翻面",
        "method": "activate",
        "actions": 1,
    }]

    def is_broken(self, game_state) -> bool:
        return _broken_key(self.instance_id) in game_state.scenario.vars

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        """+1[agility]（破损面时失效）。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if self.is_broken(ctx.game_state):
            return
        ctx.modify_amount(1, "discipline_agility")

    def activate(self, game_state, investigator_id) -> bool:
        """[行动]：三连战斗/躲避由会话层逐一发起；本方法负责翻面。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self.is_broken(game_state):
            return False
        game_state.scenario.vars[_broken_key(self.instance_id)] = (
            game_state.scenario.round_number
        )
        game_state.log_effect("🥋 戒律：翻至破损面")
        return True

    def flip_back(self, game_state) -> bool:
        """翻回正面；破损当轮不可翻回。"""
        key = _broken_key(self.instance_id)
        broken_round = game_state.scenario.vars.get(key)
        if broken_round is None:
            return True
        if broken_round == game_state.scenario.round_number:
            return False
        game_state.scenario.vars.pop(key, None)
        return True
