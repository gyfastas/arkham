"""Enchanted Armor (Level 2) — Guardian Asset, Body + Arcane slots. (07189)
在你所在地点的任意调查员的控制下打出附魔护甲。
强制 - 有伤害和/或恐惧被放置到附魔护甲上后：附魔护甲的拥有者检定意志(X)，
X为其上伤害与恐惧的总量。如果检定失败，弃置附魔护甲，并将刚放置于其上的
伤害和/或恐惧分配到别处。

简化说明：
- 承伤/承恐检测仿 armor_of_ardennes 的增量快照：DAMAGE_ASSIGNED /
  HORROR_ASSIGNED 时比较本卡已受伤害/恐惧的增量判断是否刚被分配。
- 意志检定由卡牌实现手动结算（卡实现拿不到技能检定引擎）：从混沌袋抽
  1个标记（bind_chaos_bag 注入），意志+标记修正 ≥ X 成功；自动失败标记
  视为失败。无投入卡/事件窗口——简化注明。
- 失败时"分配到别处"简化为转移给拥有者本人（直接加到其伤害/恐惧，
  不再经过分配窗口）；并弃置本卡（镜像引擎离场流程）。
- ⚠️ 数据缺口：官方 ArkhamDB 数据将本卡生命/理智记为 -3/-3（牌面实为3/3），
  且槽位串 "body. arcane" 非合法 SlotType——加载层会跳过本卡；本实现按
  abs() 容错读取上限（见报告）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class EnchantedArmor(CardImplementation):
    card_id = "enchanted_armor_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None
        self._known: tuple[int, int] | None = None  # (damage, horror) 快照

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def _check(self, ctx) -> None:
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        prev_damage, prev_horror = self._known or (0, 0)
        placed_damage = max(0, inst.damage - prev_damage)
        placed_horror = max(0, inst.horror - prev_horror)
        self._known = (inst.damage, inst.horror)
        if placed_damage <= 0 and placed_horror <= 0:
            return

        # 强制意志检定：X = 本卡上伤害+恐惧总量
        x = inst.damage + inst.horror
        willpower = inv.get_skill(Skill.WILLPOWER)
        success = self._run_willpower_test(willpower, x)
        ctx.extra["enchanted_armor_test"] = {"x": x, "success": success}
        if success:
            ctx.game_state.log_effect(
                f"🛡️ 附魔护甲：意志检定({x})成功，伤害/恐惧留在护甲上")
            return

        # 失败：弃置护甲，刚放置的伤害/恐惧转移给拥有者
        inst.damage -= placed_damage
        inst.horror -= placed_horror
        inv.damage += placed_damage
        inv.horror += placed_horror
        ctx.extra["enchanted_armor_failed"] = {
            "damage": placed_damage, "horror": placed_horror}
        defeat_asset(ctx.game_state, self._bus, self.instance_id)
        ctx.game_state.log_effect(
            f"🛡️ 附魔护甲：意志检定({x})失败，弃置护甲，"
            f"{placed_damage}伤害/{placed_horror}恐惧转移给拥有者")

    def _run_willpower_test(self, willpower: int, difficulty: int) -> bool:
        """手动意志检定：抽1个混沌标记，意志+修正 ≥ 难度。"""
        if self._chaos_bag is None:
            return willpower >= difficulty
        token = self._chaos_bag.draw()
        if token == ChaosTokenType.AUTO_FAIL:
            return False
        modifier = CHAOS_TOKEN_VALUES.get(token) or 0
        return willpower + modifier >= difficulty

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def on_damage_placed(self, ctx):
        self._check(ctx)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.AFTER)
    def on_horror_placed(self, ctx):
        self._check(ctx)
