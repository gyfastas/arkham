"""Holy Spear (Level 5) — Guardian Asset, Hand x2. (07302)
[行动]：攻击。本次攻击你获得+2战斗并造成+1伤害。当你启动本能力时，
你可以释放1个封印在圣枪上的[祝福]标记。
[行动]在混乱袋中查找2个[祝福]标记并封印在圣枪上：攻击。
本次攻击你获得+4战斗并造成+2伤害。

简化说明：
- 两个启动能力均为公开方法（会话层调用后发起 FIGHT 行动，
  weapon_instance_id 传本卡实例）：
  activate_fight(release=False)：武装 +2战斗/+1伤害 的攻击；release=True 时
  同时释放1个封印的祝福回混乱袋（官方"可以"由玩家选择，默认不释放）。
  activate_seal_fight()：从袋中封印2个祝福（不足2个则失败，不武装），
  武装 +4战斗/+2伤害 的攻击。
- 封印数记录在实例 uses["sealed"]；混沌袋经 bind_chaos_bag() 注入。
- 本卡离场时封印的祝福释放回混乱袋。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class HolySpear(CardImplementation):
    card_id = "holy_spear_lv5"
    activations = [
        {
            "id": "fight",
            "label": "[行动] 攻击：+2战斗/+1伤害（可释放1封印祝福）",
            "method": "activate_fight",
            "actions": 1,
        },
        {
            "id": "seal_fight",
            "label": "[行动] 封印2祝福后攻击：+4战斗/+2伤害",
            "method": "activate_seal_fight",
            "actions": 1,
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._armed: dict | None = None  # {"combat": int, "damage": int}

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._bag = chaos_bag

    def activate_fight(self, game_state, investigator_id: str,
                       release: bool = False) -> bool:
        """[行动] 攻击：+2战斗/+1伤害；可同时释放1个封印的祝福。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if release and inst.uses.get("sealed", 0) > 0 and self._bag is not None:
            if self._bag.release_token(ChaosTokenType.BLESS):
                inst.uses["sealed"] -= 1
                game_state.log_effect("🔱 圣枪：释放1个封印的祝福标记")
        self._armed = {"combat": 2, "damage": 1}
        return True

    def activate_seal_fight(self, game_state, investigator_id: str) -> bool:
        """[行动] 袋中封印2个祝福到本卡：攻击 +4战斗/+2伤害。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if self._bag is None:
            return False
        if self._bag.tokens.count(ChaosTokenType.BLESS) < 2:
            return False  # 不足2个祝福：无法支付封印费用
        sealed = 0
        for _ in range(2):
            if self._bag.seal_token(ChaosTokenType.BLESS):
                sealed += 1
        inst.uses["sealed"] = inst.uses.get("sealed", 0) + sealed
        self._armed = {"combat": 4, "damage": 2}
        game_state.log_effect("🔱 圣枪：封印2个祝福标记，武装强化攻击")
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed is not None and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """武装攻击的战斗加值。"""
        if not self._is_this_attack(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(self._armed["combat"], "holy_spear_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """武装攻击的伤害加值。"""
        if not self._is_this_attack(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) \
            + self._armed["damage"]

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        """离场：封印的祝福释放回混乱袋。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        sealed = inst.uses.get("sealed", 0) if inst is not None else 0
        if sealed and self._bag is not None:
            for _ in range(sealed):
                self._bag.release_token(ChaosTokenType.BLESS)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = None
