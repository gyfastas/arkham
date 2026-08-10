"""Plucky (Level 3) — Survivor Asset. (08081)
Fast. Limit 1 [Composure] in play.
You get +1 [willpower] and +1 [intellect].
Non-direct damage/horror must be assigned to Plucky before it can be
assigned to your investigator card.
[fast] Spend 1 resource: You get +1 [willpower] or +1 [intellect] for this
skill test.

简化说明：
- 花费能力沿用 ResourceSkillBoost（先支付武装、下一次对应技能检定生效，
  可叠加；官方可在任意 fast 窗口支付，这里限本人检定）。
- "必须优先分配"实现为 DAMAGE_ASSIGNED / HORROR_ASSIGNED 拦截（同
  plucky_lv1 的恐惧版）：自动先由有胆有识承担（不超过剩余生命/理智）；
  引擎只在非直接路径发此事件，天然排除直接伤害/恐惧。承满被击败为
  内联结算（同 plucky_lv1）。
- "快速""场上限1张沉稳"为打出/在场限制，需会话层支持（引擎缺口，见报告）。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class PluckyLv3(ResourceSkillBoost):
    card_id = "plucky_lv3"
    boosted_skills = (Skill.WILLPOWER, Skill.INTELLECT)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def passive_bonus(self, ctx):
        """在场时 +1 意志、+1 智力。"""
        if ctx.skill_type not in self.boosted_skills:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "plucky_lv3_passive")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_damage_first(self, ctx):
        self._soak(ctx, "damage")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror_first(self, ctx):
        self._soak(ctx, "horror")

    def _soak(self, ctx, kind: str) -> None:
        """非直接伤害/恐惧必须先分给有胆有识（承至剩余上限）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        if cd is None:
            return
        if kind == "damage":
            capacity = (cd.health or 0) - inst.damage
        else:
            capacity = (cd.sanity or 0) - inst.horror
        take = min(capacity, ctx.amount or 0)
        if take <= 0:
            return
        if kind == "damage":
            inst.damage += take
        else:
            inst.horror += take
        ctx.modify_amount(-take, f"plucky_lv3_soak_{kind}")
        ctx.game_state.log_effect(
            f"🎖️ 有胆有识：优先承受{take}点{'伤害' if kind == 'damage' else '恐惧'}")
        self._check_defeat(ctx, inv, inst)

    def _check_defeat(self, ctx, inv, inst) -> None:
        """承伤/承恐达到上限被击败（内联复制引擎资产击败流程）。"""
        cd = ctx.game_state.get_card_data(self.card_id)
        defeated = False
        if cd.health is not None and inst.damage >= cd.health:
            defeated = True
        if cd.sanity is not None and inst.horror >= cd.sanity:
            defeated = True
        if not defeated:
            return
        vacate_asset_slots(ctx.game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        ctx.game_state.log_effect("💀 有胆有识承受达到上限，被击败")
