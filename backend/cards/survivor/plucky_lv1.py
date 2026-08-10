"""Plucky (Level 1) — Survivor Asset.
快速。场上限制1张[[沉稳]]。
非直接恐惧必须分配给有胆有识后，才能分配给你的调查员卡。
[fast] 花费1资源：本次技能检定+1意志。
[fast] 花费1资源：本次技能检定+1智力。

简化说明：
- 加值沿用 ResourceSkillBoost（先支付武装、下一次对应技能检定生效，可叠加）。
- "必须优先分配"实现为 HORROR_ASSIGNED 拦截：非直接恐惧在落到调查员前
  自动先由有胆有识承担（不超过其剩余理智）；引擎只在非直接路径发此事件，
  故天然排除直接恐惧。玩家显式指定的盟友分摊在事件前已完成，不在本拦截
  范围内（从简）。恐惧承满被击败为内联结算（卡牌代码访问不到
  DamageEngine，同 aquinnah 模式）。
- "快速""场上限制1张沉稳"为打出/在场限制，需会话层支持，本实现不强制
  （引擎缺口，见报告）。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class Plucky(ResourceSkillBoost):
    card_id = "plucky_lv1"
    boosted_skills = (Skill.WILLPOWER, Skill.INTELLECT)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror_first(self, ctx):
        """非直接恐惧必须先分给有胆有识（自动承恐至剩余理智上限）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        capacity = ((cd.sanity or 0) - inst.horror) if cd else 0
        take = min(capacity, ctx.amount or 0)
        if take <= 0:
            return
        inst.horror += take
        ctx.modify_amount(-take, "plucky_soak")
        ctx.extra["plucky_soaked"] = take
        ctx.game_state.log_effect(f"🎖️ 有胆有识：优先承受{take}点恐惧")

        # 恐惧达到理智上限被击败（内联复制引擎资产击败流程）
        if cd is not None and cd.sanity is not None and inst.horror >= cd.sanity:
            vacate_asset_slots(ctx.game_state, self.instance_id)
            if self.instance_id in inv.play_area:
                inv.play_area.remove(self.instance_id)
            ctx.game_state.cards_in_play.pop(self.instance_id, None)
            inv.discard.append(self.card_id)
            ctx.game_state.log_effect("💀 有胆有识恐惧达到上限，被击败")
