"""Finn Edwards — Rogue Investigator.
能力：在你回合期间，你可以进行额外一个行动，该行动只能用于躲避。
远古印记：场上每有1个已消耗的敌人，+1。如果你成功且超过难度至少2点，
你可以发现所在地点的1个线索。

简化说明：
- 额外的"只能用于躲避"行动：引擎的行动通道无法限制行动类型（引擎缺口），
  实现为 INVESTIGATOR_TURN_BEGINS 置位 + 公开方法 activate_evade()（由 UI/
  会话层调用，不占普通行动数，回合结束时失效）。躲避复刻
  ActionResolver._evade：发出 EVADE_ACTION_INITIATED 后跑敏捷检定，成功则
  消耗敌人、解除交战并发出 ENEMY_EVADED；失败处理 alert 关键词反击。
  躲避本就不引发趁乱攻击（AOO_EXEMPT_ACTIONS）。
- 远古印记"你可以发现1个线索"：简化为成功超过难度2点时自动发现（官方为
  玩家可选）。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class FinnEdwards(CardImplementation):
    card_id = "finn_edwards"

    activations = [{
        "id": "evade",
        "label": "额外行动（仅躲避）：躲避一名敌人",
        "method": "activate_evade",
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._evade_action = False
        self._elder_pending = False

    def _get_finn(self, game_state, investigator_id):
        """Return the investigator state iff it is Finn Edwards."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "finn_edwards":
            return None
        return inv

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def grant_evade_action(self, ctx):
        """你的回合期间：获得一个只能用于躲避的额外行动。"""
        if self._get_finn(ctx.game_state, ctx.investigator_id) is None:
            return
        self._evade_action = True
        ctx.extra["finn_edwards_evade_action"] = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire_evade_action(self, ctx):
        """回合结束时额外行动失效。"""
        if self._get_finn(ctx.game_state, ctx.investigator_id) is None:
            return
        self._evade_action = False

    def activate_evade(self, game, investigator_id, enemy_instance_id,
                       committed_cards=None) -> bool:
        """额外行动（仅躲避）：躲避一名敌人。由 UI 调用。"""
        game_state = game.state
        inv = self._get_finn(game_state, investigator_id)
        if inv is None or not self._evade_action:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        enemy_data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None \
                or enemy_data.type != CardType.ENEMY:
            return False
        self._evade_action = False

        from backend.engine.event_bus import EventContext
        game.event_bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.EVADE_ACTION_INITIATED,
            investigator_id=investigator_id,
            enemy_id=enemy_instance_id,
        ))

        def on_success(result):
            enemy.exhausted = True
            if enemy_instance_id in inv.threat_area:
                inv.threat_area.remove(enemy_instance_id)
            location = game_state.get_location(inv.location_id)
            if location and enemy_instance_id not in location.enemies:
                location.enemies.append(enemy_instance_id)
            game.event_bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=investigator_id,
                enemy_id=enemy_instance_id,
            ))

        def on_failure(result):
            if "alert" in (enemy_data.keywords or []):
                game.damage_engine.deal_damage(
                    investigator_id,
                    damage=enemy_data.enemy_damage or 0,
                    horror=enemy_data.enemy_horror or 0,
                    source=enemy_instance_id,
                )

        game.skill_test_engine.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.AGILITY,
            difficulty=enemy_data.enemy_evade or 0,
            committed_card_ids=committed_cards or [],
            on_success=on_success,
            on_failure=on_failure,
        )
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：场上每有1个已消耗的敌人，+1。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_finn(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        exhausted = 0
        for inst in ctx.game_state.cards_in_play.values():
            if not inst.exhausted:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and cd.type == CardType.ENEMY:
                exhausted += 1
        if exhausted:
            ctx.modify_amount(exhausted, "finn_edwards_elder_sign")
        self._elder_pending = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def discover_clue_on_margin(self, ctx):
        """远古印记检定成功且超过难度至少2点：发现所在地点1个线索。"""
        if not self._elder_pending:
            return
        inv = self._get_finn(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None or location.clues <= 0:
            return
        # 事件处理器中无总线句柄，直接转移线索（与 roland_banks 一致）
        location.clues -= 1
        inv.clues += 1
        ctx.game_state.log_effect("🔎 芬恩·爱德华兹：远古印记成功超2点，发现1个线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_elder_pending(self, ctx):
        self._elder_pending = False
