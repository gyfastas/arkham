"""Divination (Level 1) — Seeker Asset, Arcane slot. (08101)
使用(4充能)。
[行动]：调查。本次调查中你可以使用[意志]代替[智力]，并获得+1技能值。
如果你成功，花费1或2个充能。改为在你所在地点每花费1个充能发现1条线索，
代替原本的1条。如果你以0点差值成功，选择并丢弃你手牌中的1张牌。

简化说明：
- activate() 武装一次调查（与 rite_of_seeking 同款武装模式；官方卡面无横置
  要求），随后由会话层发起调查行动；
- 充能在成功后花费：缺省花费可用充能上限（lv1为2，divination_lv4 覆盖为3），
  activate(charges=...) 可指定；额外线索在基础发现的 CLUE_DISCOVERED 后补足
  （基础1条 + 补足N-1条 = 每充能1条）；
- 地点无线索时基础发现不发生，充能照花但不发线索（官方"改为每充能1条"以
  该地点有线索为前提，从简处理）；
- "以0点差值成功则弃1张手牌"：自动弃手牌第1张（官方为玩家选择）；
- 数据 uses 键兼容双 s 写法（"chargess"），见 seeker/_uses.py。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_count, uses_spend
from backend.models.enums import GameEvent, Skill, TimingPriority


class Divination(CardImplementation):
    card_id = "divination_lv1"
    skill_bonus = 1        # lv4 覆盖为 +2
    max_spend = 2          # lv4 覆盖为 3
    zero_margin_discards = 1  # lv4 覆盖为 2
    activations = [{
        "id": "investigate",
        "label": "[行动]调查：可用意志代替智力+1；成功花充能每条线索1充能",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None
        self._use_willpower = True
        self._spend_request: int | None = None
        self._pending_clues = 0

    def activate(self, game_state, investigator_id: str,
                 use_willpower: bool = True,
                 charges: int | None = None) -> bool:
        """[行动]：武装一次占卜调查（成功后花费1..max_spend充能）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if charges is not None and not (1 <= charges <= self.max_spend):
            return False
        self._armed_by = investigator_id
        self._use_willpower = use_willpower
        self._spend_request = charges
        self._pending_clues = 0
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def boost(self, ctx):
        """可用意志代替智力，并+技能值。"""
        if self._armed_by != ctx.investigator_id:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._use_willpower:
            delta = inv.get_skill(Skill.WILLPOWER) - inv.get_skill(Skill.INTELLECT)
            if delta:
                ctx.modify_amount(delta, f"{self.card_id}_substitute")
        ctx.modify_amount(self.skill_bonus, f"{self.card_id}_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def spend_charges(self, ctx):
        """成功：花费充能（每条线索1充能）；0点差值成功则弃手牌。"""
        if self._armed_by != ctx.investigator_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inst is None or inv is None:
            return
        available = uses_count(inst, "charges")
        want = self._spend_request or self.max_spend
        spend = min(want, available)
        if spend > 0 and uses_spend(inst, "charges", spend):
            self._pending_clues = spend
        # 以0点差值成功：选择并弃掉手牌（自动：弃第1张）
        if (ctx.modified_skill is not None and ctx.difficulty is not None
                and ctx.modified_skill - ctx.difficulty == 0):
            for _ in range(self.zero_margin_discards):
                if inv.hand:
                    inv.discard.append(inv.hand.pop(0))
            ctx.extra[f"{self.card_id}_zero_margin_discard"] = True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def extra_clues(self, ctx):
        """基础发现之后：补足至每充能1条线索。"""
        if not self._pending_clues or self._armed_by != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id) \
            if inv else None
        if inv is None or loc is None:
            return
        extra = min(self._pending_clues - 1, loc.clues)
        if extra > 0:
            loc.clues -= extra
            inv.clues += extra
            ctx.extra[f"{self.card_id}_total_clues"] = 1 + extra

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_by = None
        self._use_willpower = True
        self._spend_request = None
        self._pending_clues = 0
