"""Moxie (Level 1) — Rogue Asset.
快速。场上限制1张[[沉稳]]。
非直接恐惧必须分配给刚毅果敢后才能分配给你的调查员卡。
[快速]花费1资源：本次技能检定你+1意志。
[快速]花费1资源：本次技能检定你+1敏捷。

简化说明：
- 花费泵复用 ResourceSkillBoost（可叠加，同 hard_knocks）。
- 恐惧重定向：HORROR_ASSIGNED 时把至多等于刚毅果敢剩余神智的恐惧
  移到本卡上，并等量降低调查员承受部分（直接恐惧不经该事件，
  天然排除）；刚毅果敢承满神智即被击败离场。
- "场上限制1张沉稳"为牌组/入场规则，引擎无限制通道（引擎缺口）。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class Moxie(ResourceSkillBoost):
    card_id = "moxie_lv1"
    boosted_skills = (Skill.WILLPOWER, Skill.AGILITY)

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 被击败时需要经事件总线发出 ASSET_DEFEATED 等

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        """非直接恐惧必须先分配给刚毅果敢。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if (ctx.amount or 0) < 1:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        cd = ctx.game_state.get_card_data(self.card_id)
        if inst is None or cd is None or cd.sanity is None:
            return
        remaining = cd.sanity - inst.horror
        if remaining <= 0:
            return
        moved = min(ctx.amount, remaining)
        inst.horror += moved
        ctx.modify_amount(-moved, "moxie_soak")
        ctx.extra["moxie_soaked"] = moved
        ctx.game_state.log_effect(f"🎭 刚毅果敢：代为承受{moved}点恐惧")
        if inst.horror >= cd.sanity:
            self._defeated(ctx, inv)

    def _defeated(self, ctx, inv) -> None:
        """承满神智：刚毅果敢被击败，弃置离场（复刻引擎资产击败流程）。"""
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ASSET_DEFEATED,
                target=self.instance_id,
            ))
        vacate_asset_slots(ctx.game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
        ctx.extra["moxie_defeated"] = True
