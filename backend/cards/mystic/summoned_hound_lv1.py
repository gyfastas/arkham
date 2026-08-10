"""Summoned Hound (Level 1) — Mystic Asset, Ally/Arcane slot. (06282)
作为打出本卡的额外费用，你必须在绑定卡牌中查找1张脱缰野兽并混洗入你的牌堆。
[fast] 在你的回合中（行动中除外），消耗本卡：攻击/调查。以基础5点[combat]
攻击，或以基础5点[intellect]调查。

简化说明：
- 额外费用在入场时结算：将 unbound_beast_lv0 洗入持有者牌堆（引擎无绑定区，
  直接从游戏外取固定 id）。
- 快速能力声明为 0 行动的 activations；"在你的回合中、行动中除外"由会话层
  控制窗口（本实现只校验横置状态）。
- 攻击：activate_fight 横置并武装，随后会话层发起战斗行动
  （weapon_instance_id 传本卡实例）；基础技能值经"5-原战斗值"修正实现
  （投入图标/标记修正正常叠加）。标准1伤害由引擎结算。
- 调查：引擎调查检定不传 source，采用武装窗口（下一次智力检定生效）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_UNBOUND_BEAST_ID = "unbound_beast_lv0"


class SummonedHound(CardImplementation):
    card_id = "summoned_hound_lv1"
    base_skill = 5
    activations = [
        {
            "id": "hound_fight",
            "label": "消耗：以基础战斗5攻击",
            "method": "activate_fight",
            "actions": 0,
            "target": "enemy",
        },
        {
            "id": "hound_investigate",
            "label": "消耗：以基础智力5调查",
            "method": "activate_investigate",
            "actions": 0,
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_skill: Skill | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def shuffle_bonded_beast(self, ctx):
        """额外费用：将绑定的脱缰野兽洗入牌堆。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.deck.append(_UNBOUND_BEAST_ID)
        random.shuffle(inv.deck)
        ctx.game_state.log_effect("🐕 受召猎犬：将【脱缰野兽】洗入牌堆")

    def _ready(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        return inst is not None and not inst.exhausted

    def activate_fight(self, game_state, investigator_id: str,
                       target_instance_id: str | None = None) -> bool:
        """消耗：武装一次基础战斗5的攻击。"""
        if not self._ready(game_state, investigator_id):
            return False
        inst = game_state.get_card_instance(self.instance_id)
        inst.exhausted = True
        self._armed_skill = Skill.COMBAT
        return True

    def activate_investigate(self, game_state, investigator_id: str) -> bool:
        """消耗：武装一次基础智力5的调查。"""
        if not self._ready(game_state, investigator_id):
            return False
        inst = game_state.get_card_instance(self.instance_id)
        inst.exhausted = True
        self._armed_skill = Skill.INTELLECT
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def set_base_skill(self, ctx):
        """基础技能值改为5（投入图标与标记修正正常叠加）。"""
        if self._armed_skill is None or ctx.skill_type != self._armed_skill:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if ctx.skill_type == Skill.COMBAT and ctx.source != self.instance_id:
            return  # 攻击需以本卡发起（weapon_instance_id 传本卡）
        base_val = inv.get_skill(ctx.skill_type)
        ctx.modify_amount(self.base_skill - base_val, "summoned_hound_base5")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_skill = None
