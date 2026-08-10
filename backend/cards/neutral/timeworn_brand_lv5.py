"""Timeworn Brand (Level 5) — Neutral Asset, Hand slot. Relic Weapon Melee.
[行动]如果古旧锈剑 处于就绪状态：战斗。本次攻击+2战斗，造成+1伤害。
[行动]横置古旧锈剑：战斗。本次攻击将你的意志加入技能值，造成+3伤害。
如果本次攻击击败1个[[精英]]敌人，抽3张牌。（每场游戏限一次。）

简化说明：
- 两种攻击模式各为一个启动能力（activate_fight / activate_fight_exhaust），
  武装后由会话层发起战斗行动（weapon_instance_id 传本卡实例），与
  shrivelling_lv0 的"武装→检定"流程一致。
- 模式一卡面要求"处于就绪状态"但不横置（可每行动重复使用）；模式二以横置
  为代价。
- 精英判定读取敌人卡数据的 traits（含 "elite"，大小写不敏感）。
- "每场游戏限一次"记在本实现实例上（与卡实例同生命周期，整场游戏唯一）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TimewornBrand(CardImplementation):
    card_id = "timeworn_brand_lv5"
    activations = [
        {"id": "fight", "label": "[行动]战斗：+2战斗，+1伤害",
         "method": "activate_fight", "actions": 1},
        {"id": "fight_exhaust", "label": "[行动]横置战斗：+意志，+3伤害",
         "method": "activate_fight_exhaust", "actions": 1},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._mode = 0  # 0=未武装, 1=就绪攻击(+2战斗/+1伤害), 2=横置攻击(+意志/+3伤害)
        self._elite_draw_used = False  # 每场游戏限一次

    def activate_fight(self, game_state, investigator_id: str) -> bool:
        """[行动]就绪状态：武装一次 +2战斗/+1伤害 的攻击。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None:
            return False
        if self.instance_id not in inv.play_area or inst.exhausted:
            return False
        self._mode = 1
        return True

    def activate_fight_exhaust(self, game_state, investigator_id: str) -> bool:
        """[行动]横置本卡：武装一次 +意志/+3伤害 的攻击。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None:
            return False
        if self.instance_id not in inv.play_area or inst.exhausted:
            return False
        inst.exhausted = True
        self._mode = 2
        return True

    def _armed(self, ctx) -> bool:
        return self._mode and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_boost(self, ctx):
        if not self._armed(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        if self._mode == 1:
            ctx.modify_amount(2, "timeworn_brand_combat_bonus")
        else:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None:
                ctx.modify_amount(
                    inv.get_skill(Skill.WILLPOWER), "timeworn_brand_add_willpower")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """攻击成功：模式一 +1伤害，模式二 +3伤害。"""
        if not self._armed(ctx):
            return
        bonus = 1 if self._mode == 1 else 3
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + bonus

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def draw_on_elite_defeat(self, ctx):
        """模式二击败精英敌人：抽3张牌（每场游戏限一次）。"""
        if self._mode != 2 or self._elite_draw_used:
            return
        if ctx.investigator_id is None:
            return
        enemy = ctx.game_state.get_card_data(ctx.extra.get("card_id", ""))
        traits = [t.lower() for t in (enemy.traits if enemy else [])]
        if "elite" not in traits:
            return
        self._elite_draw_used = True
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        drawn = []
        for _ in range(3):
            if not inv.deck:
                break
            card_id = inv.deck.pop(0)
            inv.hand.append(card_id)
            drawn.append(card_id)
        ctx.game_state.log_effect(
            f"🗡️ 古旧锈剑：击败精英敌人，抽{len(drawn)}张牌（每场游戏限一次）")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._mode = 0
