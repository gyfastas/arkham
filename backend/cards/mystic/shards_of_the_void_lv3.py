"""Shards of the Void (Level 3) — Mystic Asset, Arcane slot. (04310)
封印(0)。使用(3充能)。
[action]花费1充能或释放封印在本卡的1个混乱标记：攻击。本次攻击使用[willpower]
代替[combat]，并造成+1伤害。每有1个"0"标记封印在本卡上，本次攻击你+2[willpower]。
本次攻击中每揭示1个"0"标记，将该标记封印在本卡上，且本次攻击造成额外+1伤害。

简化说明：
- activate() 优先花费1充能；无充能时改为释放1个封印的"0"标记（归还袋中）。
  随后由会话层发起战斗行动（weapon_instance_id 传本卡实例）。
- 封印的"0"标记记录于实例级 _sealed（ChaosBag.sealed 为全局列表，卡面归属
  由本实现维护）；攻击中揭示的"0"经 bag.seal_token 从袋中移除并封印到本卡。
- 数据 JSON 中 uses 键为 "chargess"（上游笔误），经 seeker._uses 兼容读取。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_spend
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class ShardsOfTheVoid(CardImplementation):
    card_id = "shards_of_the_void_lv3"
    activations = [{
        "id": "fight",
        "label": "花1充能或释放封印的0：用意志攻击，+1伤害",
        "method": "activate",
        "actions": 1,
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._sealed: list[ChaosTokenType] = []
        self._armed = False
        self._zeros_revealed = 0

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_zero_on_enter(self, ctx):
        """入场：封印袋中1个"0"标记。"""
        if ctx.target != self.instance_id:
            return
        if self._bag is not None and self._bag.seal_token(ChaosTokenType.ZERO):
            self._sealed.append(ChaosTokenType.ZERO)
            ctx.game_state.log_effect("🌌 虚空碎裂：封印1个\"0\"标记")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        """离场：封印的标记归还袋中。"""
        if ctx.target != self.instance_id:
            return
        if self._bag is not None:
            for token in self._sealed:
                self._bag.release_token(token)
        self._sealed = []

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """花费1充能（无充能时释放1个封印的"0"）：武装一次"用意志攻击"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        if uses_spend(inst, "charges"):
            pass
        elif ChaosTokenType.ZERO in self._sealed:
            # 释放1个封印的"0"标记代替充能
            self._sealed.remove(ChaosTokenType.ZERO)
            if self._bag is not None:
                self._bag.release_token(ChaosTokenType.ZERO)
            game_state.log_effect("🌌 虚空碎裂：释放封印的\"0\"标记代替充能")
        else:
            return False
        self._armed = True
        self._zeros_revealed = 0
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """用意志代替战斗；每个封印的"0"标记 +2 意志。"""
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        bonus = 2 * len(self._sealed)
        ctx.modify_amount(
            willpower - base_val + bonus, "shards_of_the_void_substitute")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def seal_revealed_zero(self, ctx):
        """攻击中揭示的"0"：封印到本卡，本次攻击额外+1伤害。"""
        if not self._is_this_attack(ctx) or ctx.chaos_token != ChaosTokenType.ZERO:
            return
        self._zeros_revealed += 1
        if self._bag is not None:
            self._bag.seal_token(ChaosTokenType.ZERO)
        self._sealed.append(ChaosTokenType.ZERO)
        ctx.extra["shards_of_the_void_sealed_zero"] = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """+1伤害；攻击中每揭示1个"0"再+1。"""
        if not self._is_this_attack(ctx):
            return
        bonus = 1 + self._zeros_revealed
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + bonus

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._zeros_revealed = 0
