"""Zoey Samaras — Guardian Investigator.
能力：[reaction]在你与一名敌人交战后：获得1个资源。
远古印记：+1。如果攻击中的这次技能检定成功，这次攻击造成+1伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority, CardType


class ZoeySamaras(CardImplementation):
    card_id = "zoey_samaras"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._elder_sign_attack = False

    @on_event(
        GameEvent.ENEMY_ENGAGED,
        priority=TimingPriority.REACTION,
    )
    def gain_resource_on_engage(self, ctx):
        """Reaction: After you become engaged with an enemy, gain 1 resource."""
        # Check this event is for the current investigator
        if ctx.investigator_id is None:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # Check this is Zoey's investigator
        card_data = getattr(inv, 'card_data', None)
        if card_data is None:
            return
        if card_data.id != "zoey_samaras":
            return

        # Check if there's already a pending choice for this engagement
        scenario = getattr(ctx.game_state, 'scenario', None)
        if scenario is None:
            return

        existing = scenario.vars.get("pending_choice", {})
        if existing.get("kind") == "zoey_reactions_on_engage":
            # Already handling this engagement
            return

        # Get the enemy for this engagement
        enemy_id = getattr(ctx, 'enemy_id', None) or ctx.extra.get('enemy_id')
        if not enemy_id:
            return

        enemy = ctx.game_state.get_card_instance(enemy_id)
        if enemy is None:
            return

        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None or enemy_data.type != CardType.ENEMY:
            return

        # Check if Zoey's Cross is in play and usable
        cross_usable = False
        cross_instance = None
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst and inst.card_id == "zoeys_cross_lv0":
                cross_instance = inst
                break

        if cross_instance and not cross_instance.exhausted and inv.resources >= 1:
            cross_usable = True

        enemy_name = getattr(enemy_data, 'name_cn', None) or getattr(enemy_data, 'name', '敌人')

        # Build options based on what's available
        options = [{"id": "none", "label": "不触发任何能力"}]

        if cross_usable:
            options.insert(0, {"id": "both", "label": "获得1资源 + 使用十字架（花费1资源造成1伤害）"})
            options.insert(0, {"id": "cross", "label": "使用佐伊的十字架（花费1资源造成1伤害）"})
            options.insert(0, {"id": "resource", "label": "获得1资源"})
        else:
            options.insert(0, {"id": "resource", "label": "获得1资源"})

        # Set pending choice for player to decide
        scenario.vars["pending_choice"] = {
            "kind": "zoey_reactions_on_engage",
            "enemy_id": enemy_id,
            "enemy_name": enemy_name,
            "investigator_id": ctx.investigator_id,
            "cross_usable": cross_usable,
            "cross_instance_id": cross_instance.instance_id if cross_instance else None,
            "prompt": f"<b>佐伊·萨马拉斯</b>：你与【{enemy_name}】交战，是否触发Reaction能力？",
            "options": options,
        }

    @on_event(
        GameEvent.CHAOS_TOKEN_RESOLVED,
        priority=TimingPriority.WHEN,
    )
    def elder_sign_effect(self, ctx):
        """Elder Sign: +1. If successful during an attack, +1 damage."""
        if ctx.chaos_token is None:
            return
        from backend.models.enums import ChaosTokenType
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        card_data = getattr(inv, 'card_data', None)
        if card_data is None or card_data.id != "zoey_samaras":
            return

        # +1 modifier for the skill test
        ctx.modify_amount(1, "zoey_elder_sign")

        # 本次检定抽到远古印记：若攻击（战斗检定）成功，+1伤害。
        # 成功事件是新的 ctx（extra 不共享），用实例标记跨事件传递；
        # "攻击"以战斗检定判定（ctx.source 在徒手攻击时为 None，不能单靠它）。
        self._elder_sign_attack = ctx.skill_type == Skill.COMBAT

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def elder_sign_damage_bonus(self, ctx):
        """If elder sign and this was an attack, deal +1 damage."""
        if not self._elder_sign_attack:
            return
        self._elder_sign_attack = False

        if ctx.skill_type != Skill.COMBAT:
            return

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        card_data = getattr(inv, 'card_data', None)
        if card_data is None or card_data.id != "zoey_samaras":
            return

        # bonus_damage 通道：fight 行动在成功时将其加到攻击伤害上
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
        ctx.extra["zoey_elder_sign_damage"] = True

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def elder_sign_reset(self, ctx):
        """检定结束：清除远古印记标记（失败/未消耗都归零）。"""
        self._elder_sign_attack = False
