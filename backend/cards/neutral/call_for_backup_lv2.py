"""Call for Backup (Level 2) — Neutral Event.
逐一、以任意顺序，若你控制着一张……
- [rogue]卡，你可以移动到一个连接地点。
- [guardian]卡，对你所在地点的1个敌人造成1点伤害。
- [seeker]卡，在你所在地点发现1个线索。
- [mystic]卡，从任意卡牌上治疗1点恐惧。
- [survivor]卡，从任意卡牌上治疗1点伤害。

简化说明：
- "控制着X职业卡"按在场区（play_area）卡牌的 card_class 判定。
- 各效果的目标自动选择：移动到第一个连接地点、对所在地点第一个敌人
  造成伤害、治疗持有者自身（官方为玩家选择目标；移动可选择不执行，
  本实现自动执行所有适用效果）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, PlayerClass, TimingPriority


class CallForBackup(CardImplementation):
    card_id = "call_for_backup_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve_effects(self, ctx):
        if ctx.extra.get("card_id") != "call_for_backup_lv2":
            return
        game_state = ctx.game_state
        inv = game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        classes = set()
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            cd = game_state.get_card_data(inst.card_id) if inst else None
            if cd is not None and cd.card_class is not None:
                classes.add(cd.card_class)

        applied: list[str] = []

        if PlayerClass.ROGUE in classes:
            loc = game_state.get_location(inv.location_id)
            connections = loc.connections if loc else []
            if connections:
                inv.location_id = connections[0]
                applied.append("rogue_move")

        if PlayerClass.GUARDIAN in classes:
            loc = game_state.get_location(inv.location_id)
            enemy_id = loc.enemies[0] if loc and loc.enemies else None
            if enemy_id is not None:
                deal_damage_to_enemy(
                    game_state, self._bus, enemy_id, 1,
                    defeated_by=inv.investigator_id)
                applied.append("guardian_damage")

        if PlayerClass.SEEKER in classes:
            loc = game_state.get_location(inv.location_id)
            if loc is not None and loc.clues > 0:
                loc.clues -= 1
                inv.clues += 1
                applied.append("seeker_clue")

        if PlayerClass.MYSTIC in classes:
            if inv.horror > 0:
                inv.horror -= 1
            applied.append("mystic_heal_horror")

        if PlayerClass.SURVIVOR in classes:
            if inv.damage > 0:
                inv.damage -= 1
            applied.append("survivor_heal_damage")

        ctx.extra["call_for_backup_applied"] = applied
        if applied:
            game_state.log_effect(f"📞 呼叫增援：{', '.join(applied)}")
