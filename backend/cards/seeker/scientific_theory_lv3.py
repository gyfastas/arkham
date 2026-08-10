"""Scientific Theory (Level 3) — Seeker Asset. (08040)
快速。场上限1张[[沉稳]]。
你获得+1[intellect]和+1[combat]。
非直接伤害/恐惧在被分配给你的调查员卡之前，必须先分配给科学理论。
[快速]花费1资源：你这次技能检定+1[intellect]或+1[combat]。

简化说明：
- 花费泵与 lv1 等共用 ResourceSkillBoost（可叠加）；
- 恒定+1智力/+1战斗在 SKILL_VALUE_DETERMINED 对持有者的智力/战斗检定
  生效（引擎干跑预览同样可见）；
- "非直接伤害/恐惧优先分配"实现为 DAMAGE_ASSIGNED/HORROR_ASSIGNED 时把
  伤害/恐惧转移到本卡（引擎的直接伤害/恐惧不经该事件，语义恰好一致，
  与 lv1 同模式）；本卡生命或理智耗尽时被击败；
- "限1张Composure在场"需引擎出牌流程的组队限制钩子，未实现（引擎缺口，
  与 lv1 相同）。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ScientificTheoryLv3(ResourceSkillBoost):
    card_id = "scientific_theory_lv3"
    boosted_skills = (Skill.INTELLECT, Skill.COMBAT)

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def constant_bonus(self, ctx):
        """恒定：你的智力/战斗检定+1。"""
        if ctx.skill_type not in self.boosted_skills:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, "scientific_theory_lv3_constant")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_damage(self, ctx):
        """非直接伤害必须先分配给本卡（生命剩余为限）。"""
        self._soak(ctx, "damage")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        """非直接恐惧必须先分配给本卡（理智剩余为限）。"""
        self._soak(ctx, "horror")

    def _soak(self, ctx, kind: str) -> None:
        if ctx.amount <= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        cd = ctx.game_state.get_card_data(self.card_id)
        if inst is None or cd is None:
            return
        capacity = (cd.health if kind == "damage" else cd.sanity)
        if capacity is None:
            return
        taken = inst.damage if kind == "damage" else inst.horror
        remaining = capacity - taken
        if remaining <= 0:
            return

        soak = min(remaining, ctx.amount)
        if kind == "damage":
            inst.damage += soak
        else:
            inst.horror += soak
        ctx.modify_amount(-soak, f"scientific_theory_lv3_soak_{kind}")
        ctx.extra[f"scientific_theory_lv3_soaked_{kind}"] = soak
        label = "伤害" if kind == "damage" else "恐惧"
        ctx.game_state.log_effect(f"🔬 科学理论：{soak}点{label}分配给科学理论")

        if inst.damage >= (cd.health or 999) or inst.horror >= (cd.sanity or 999):
            self._defeat(ctx, inv)

    def _defeat(self, ctx, inv) -> None:
        """生命/理智耗尽：本卡被击败弃置。"""
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
        ctx.game_state.log_effect("🔬 科学理论：承受达到上限，被击败弃置")
