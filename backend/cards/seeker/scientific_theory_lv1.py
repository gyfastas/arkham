"""Scientific Theory (Level 1) — Seeker Asset.
快速。场上限1张[[Composure]]。
非直接恐惧必须先分配给科学理论，然后才能分配给你的调查员卡。
[快速]花费1资源：本次技能检定+1[intellect]。
[快速]花费1资源：本次技能检定+1[combat]。

简化说明：
- 花费泵与 Physical Training 等共用 ResourceSkillBoost（可叠加）；
- "非直接恐惧优先分配"实现为 HORROR_ASSIGNED 时把恐惧转移到本卡
  （引擎的直接恐惧不经该事件，语义恰好一致）；
- 本卡理智耗尽时被击败（经事件总线补发 ASSET_DEFEATED / CARD_LEAVES_PLAY）；
- "限1张Composure在场"需要引擎出牌流程的组队限制钩子，未实现（引擎缺口）。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ScientificTheory(ResourceSkillBoost):
    card_id = "scientific_theory_lv1"
    boosted_skills = (Skill.INTELLECT, Skill.COMBAT)

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        """非直接恐惧必须先分配给本卡（理智剩余为限）。"""
        if ctx.amount <= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        cd = ctx.game_state.get_card_data(self.card_id)
        if inst is None or cd is None or cd.sanity is None:
            return
        remaining = cd.sanity - inst.horror
        if remaining <= 0:
            return

        soak = min(remaining, ctx.amount)
        inst.horror += soak
        ctx.modify_amount(-soak, "scientific_theory_soak")
        ctx.extra["scientific_theory_soaked"] = soak
        ctx.game_state.log_effect(f"🔬 科学理论：{soak}点恐惧分配给科学理论")

        if inst.horror >= cd.sanity:
            self._defeat(ctx, inv)

    def _defeat(self, ctx, inv) -> None:
        """理智耗尽：本卡被击败弃置。"""
        from backend.engine.event_bus import EventContext
        from backend.engine.slots import vacate_asset_slots

        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ASSET_DEFEATED,
                target=self.instance_id,
            ))
        vacate_asset_slots(ctx.game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        if bus is not None:
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
        ctx.game_state.log_effect("🔬 科学理论：理智耗尽，被击败弃置")
