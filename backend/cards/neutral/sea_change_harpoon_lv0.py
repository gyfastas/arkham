"""Sea Change Harpoon (Level 0) — Neutral Asset, Hand slot. (07014)
仅限西拉斯·马什牌组。
[action]：战斗。本次攻击你获得+1[战斗]。若你向本次技能检定投入了1张或以上
技能卡，本次攻击造成+1伤害。当本次技能检定结束时，你可以将沧海桑田鱼叉
返回手牌，改为将你所有投入的技能卡返回手牌而非丢弃它们。

简化说明：
- "仅限西拉斯牌组"为构筑限制，由卡组校验负责。
- 收回手牌为可选能力：会话层在检定期间调用 choose_return() 表达玩家选择；
  SKILL_TEST_ENDS 时若已选择且投入了技能卡，则将技能卡从弃牌堆收回手牌
  并将本卡收回手牌（引擎在 SKILL_TEST_ENDS 前已弃置投入牌，故作收回处理）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class SeaChangeHarpoon(CardImplementation):
    card_id = "sea_change_harpoon_lv0"
    activations = [{
        "id": "return",
        "label": "检定结束时收回鱼叉与投入的技能卡",
        "method": "choose_return",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._committed_skills: list[str] = []
        self._return_chosen = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def arm_attack(self, ctx):
        self._armed = ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def track_committed_skills(self, ctx):
        self._committed_skills = []
        # SKILL_TEST_COMMIT 的 ctx 不携带 source，以 FIGHT 武装状态为准
        if not self._armed:
            return
        for cid in ctx.committed_cards or []:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and cd.type == CardType.SKILL:
                self._committed_skills.append(cid)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if not self._armed or ctx.source != self.instance_id:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "sea_change_harpoon_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """投入了技能卡：+1伤害。"""
        if not self._armed or ctx.source != self.instance_id:
            return
        if self._committed_skills:
            ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1

    def choose_return(self, game_state, investigator_id) -> bool:
        """玩家选择：检定结束时将本卡与投入的技能卡收回手牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if not self._armed:
            return False
        self._return_chosen = True
        return True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_return(self, ctx):
        if self._return_chosen and self._armed and self._committed_skills:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and self.instance_id in inv.play_area:
                for cid in self._committed_skills:
                    if cid in inv.discard:
                        inv.discard.remove(cid)
                        inv.hand.append(cid)
                # 收回鱼叉本身
                vacate_asset_slots(ctx.game_state, self.instance_id)
                inv.play_area.remove(self.instance_id)
                ctx.game_state.cards_in_play.pop(self.instance_id, None)
                inv.hand.append("sea_change_harpoon_lv0")
                ctx.extra["sea_change_harpoon_returned"] = True
        self._armed = False
        self._committed_skills = []
        self._return_chosen = False
