"""Combat Training (Level 1) — Guardian Asset. (03107)
快速。场上限制1张沉稳。理智1。
非直接恐惧必须先分配给战斗训练，然后才能分配给你的调查员卡。
[快速]花费1资源：本次技能检定你+1战斗。
[快速]花费1资源：本次技能检定你+1敏捷。

简化说明：
- 花费泵沿用 ResourceSkillBoost（可叠加，见 _shared.py）。
- "恐惧必须先分配给本卡"简化为自动承恐：DAMAGE/HORROR 分配事件中对持有者的
  非直接恐惧，自动将至多本卡剩余理智点数的恐惧改由本卡承担（官方为分配顺序
  规则，玩家仍可将恐惧分给其他资产）。直接恐惧不经过该事件，天然豁免。
- 本卡承恐达到理智上限即被击败离场（镜像引擎离场流程）。
- "限制1张沉稳"为同名牌限制规则，引擎无同名限制通道，未强制（注明）。
"""

from backend.cards._shared import ResourceSkillBoost, defeat_asset
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class CombatTraining(ResourceSkillBoost):
    card_id = "combat_training_lv1"
    boosted_skills = (Skill.COMBAT, Skill.AGILITY)

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        """非直接恐惧优先由本卡承担（至多本卡剩余理智）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        data = ctx.game_state.get_card_data(inst.card_id)
        if data is None or data.sanity is None:
            return
        remaining = data.sanity - inst.horror
        amount = min(remaining, ctx.amount or 0)
        if amount <= 0:
            return
        inst.horror += amount
        ctx.modify_amount(-amount, "combat_training_soak")
        ctx.game_state.log_effect(f"🧠 战斗训练：代为承担{amount}点恐惧")
        if inst.horror >= data.sanity:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("🧠 战斗训练：恐惧达到上限，被击败")
