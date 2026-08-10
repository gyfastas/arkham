"""Death • XIII (Level 1) — Seeker Asset, Tarot slot. (05027)
你获得+1[智力]。
[反应]当游戏开始时，若死神•XIII 在你的起始手牌中：将其放置入场。

简化说明：
- 开局放置：引擎 Game.setup() 抽起始手牌时逐张发 CARD_DRAWN，在 SETUP 阶段
  抽到本卡即从手牌放置入场（不支付费用，占用塔罗槽）；经 draw_hooks 的
  persistent 检查，本实现以临时实例 id 持续注册，后续处理器按 card_id 扫描
  装备区定位实例（与 chronophobia 同款模式）；
- 换牌（mulligan）后回到手牌的情况由会话层处理，引擎缺口见报告；
- +1智力为持续效果：本卡在你的装备区时，你的智力检定+1。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Phase, Skill, TimingPriority
from backend.models.state import CardInstance


class DeathXIII(CardImplementation):
    card_id = "death_•_xiii_lv1"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def put_into_play_on_game_begin(self, ctx):
        """游戏开始时在起始手牌中：放置入场（免费，占塔罗槽）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.game_state.scenario.current_phase != Phase.SETUP:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        inv.hand.remove(self.card_id)
        cd = ctx.game_state.get_card_data(self.card_id)
        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(cd.slots or []) if cd else [],
        )
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if mgr is not None and inst.slot_used:
            mgr.occupy(instance_id, list(inst.slot_used),
                       (cd.traits if cd else None))
        ctx.extra["death_xiii_into_play"] = instance_id
        ctx.game_state.log_effect("💀 死神•XIII：游戏开始，从起始手牌放置入场")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """本卡在你的装备区时：+1智力。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for iid in inv.play_area:
            ci = ctx.game_state.get_card_instance(iid)
            if ci is not None and ci.card_id == self.card_id:
                ctx.modify_amount(1, "death_xiii_intellect")
                return
