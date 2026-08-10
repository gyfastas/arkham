"""Eye of Chaos (Level 0) — Mystic Asset, Arcane slot. ( INTC )
使用(3充能)。[action]花费1充能：调查。本次调查使用[willpower]代替[intellect]。
如果成功，额外发现所在地点1个线索。如果本次调查中揭示了[curse]标记，你可以
发现1个连接地点的1个线索，或在混沌之眼上放置1充能。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起调查行动，本实现在检定时以意志
  代替智力（同 rite_of_seeking 惯例，无横置要求）。
- [curse] 奖励二选一无选择 UI：自动优先发现首个有线索的连接地点的1线索；
  没有可取的连接地点线索时改为在混沌之眼上放置1充能。
  可用 ctx.extra（SKILL_TEST_ENDS）前的 choose_charge=True 强制选充能——
  此处简化为固定优先线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class EyeOfChaos(CardImplementation):
    card_id = "eye_of_chaos_lv0"
    willpower_bonus = 0   # lv4 覆盖：本次检定 +2 意志
    per_curse_token = False  # lv4 覆盖：每个[curse]标记各触发一次奖励
    activations = [{
        "id": "investigate",
        "label": "花1充能：用意志调查，成功额外+1线索",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._curse_count = 0

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1充能：武装一次"用意志调查"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        self._armed = True
        self._curse_count = 0
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(
            willpower - base_val + self.willpower_bonus,
            f"{self.card_id}_substitute",
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_curse(self, ctx):
        if self._armed and ctx.chaos_token == ChaosTokenType.CURSE:
            self._curse_count += 1

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def bonus_clue(self, ctx):
        """成功：额外发现所在地点1个线索。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra[f"{self.card_id}_extra_clue"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_curse_reward(self, ctx):
        """[curse]奖励：发现连接地点1线索，或在混沌之眼上放1充能。"""
        if self._armed and self._curse_count > 0:
            times = self._curse_count if self.per_curse_token else 1
            for _ in range(times):
                self._curse_reward_once(ctx)
        self._armed = False
        self._curse_count = 0

    def _curse_reward_once(self, ctx) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # 优先发现首个有线索的连接地点的1线索（简化：官方为二选一）
        loc = ctx.game_state.get_location(inv.location_id)
        for conn_id in (loc.connections if loc else []):
            conn = ctx.game_state.get_location(conn_id)
            if conn is not None and conn.clues > 0:
                conn.clues -= 1
                inv.clues += 1
                ctx.extra[f"{self.card_id}_connecting_clue"] = conn_id
                return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None:
            inst.uses["charges"] = inst.uses.get("charges", 0) + 1
            ctx.extra[f"{self.card_id}_charge_placed"] = True
