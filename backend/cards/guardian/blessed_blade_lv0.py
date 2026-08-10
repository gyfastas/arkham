"""Blessed Blade (Level 0) — Guardian Asset, Hand slot. (07018)
[行动]如果蒙福之刃处于就绪状态：攻击。本次攻击你获得+1战斗。
如果本次攻击中揭示了[bless]或[elder_sign]标记，本次攻击造成+1伤害。
在本次攻击揭示混乱标记前，你可以横置蒙福之刃，将1个[bless]标记加入混乱袋。

简化说明：
- 攻击加成/标记判定参照 .35温彻斯特；本武器无弹药消耗。
- "如果处于就绪状态才能攻击"：横置（用于加祝福标记）后不能再以本卡发起攻击，
  FIGHT_ACTION_INITIATED 时若已横置则取消攻击。
- "横置加祝福标记"为启动能力（快速）：战斗中揭示标记前由玩家经
  ACTIVATE_CARD 调用；混沌袋经 bind_chaos_bag() 注入（registry 已接线）。
- 官方祝福标记在检定揭示后移出混沌袋；引擎抽标记不移出袋，天然等效（注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority

_BONUS_TOKENS = {ChaosTokenType.BLESS, ChaosTokenType.ELDER_SIGN}


class BlessedBlade(CardImplementation):
    card_id = "blessed_blade_lv0"
    activations = [{
        "id": "add_bless",
        "label": "横置：向混沌袋加入1个祝福标记",
        "method": "activate_add_bless",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._fighting = False
        self._revealed_token = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def activate_add_bless(self, game_state, investigator_id: str) -> bool:
        """横置本卡：向混沌袋加入1个祝福标记。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted or self._chaos_bag is None:
            return False
        inst.exhausted = True
        self._chaos_bag.add_token(ChaosTokenType.BLESS)
        game_state.log_effect("⚔️ 蒙福之刃：横置，向混沌袋加入1个祝福标记")
        return True

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def check_ready(self, ctx):
        """本卡已横置时不能以它发起攻击。"""
        self._fighting = False
        if ctx.source != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.exhausted:
            ctx.cancel()
            ctx.game_state.log_effect("⚔️ 蒙福之刃：已横置，无法攻击")
            return
        self._fighting = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """以本卡攻击时 +1 战斗。"""
        if ctx.source != self.instance_id or not self._fighting:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "blessed_blade_combat_bonus")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def record_token(self, ctx):
        if ctx.source != self.instance_id or not self._fighting:
            return
        self._revealed_token = ctx.chaos_token

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """揭示了祝福/远古印记：本次攻击+1伤害。"""
        if ctx.source != self.instance_id or not self._fighting:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._revealed_token in _BONUS_TOKENS:
            ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
            ctx.extra["blessed_blade_bonus"] = True
            ctx.game_state.log_effect("⚔️ 蒙福之刃：揭示祝福/远古印记，+1伤害")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._fighting = False
        self._revealed_token = None
