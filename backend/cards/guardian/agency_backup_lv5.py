"""Agency Backup (Level 5) — Guardian Asset, Ally slot. (05274)
生命4、理智4。
特工支援可以被分配给你所在地点其他调查员的伤害和/或恐惧。
[快速]横置特工支援并对它造成1点伤害：对你所在地点的一名敌人造成1点伤害。
[快速]横置特工支援并对它造成1点恐惧：在你所在地点发现1条线索。

简化说明：
- "可被分配其他调查员的伤害/恐惧"：简化为自动承担——同地点其他调查员被
  分配伤害/恐惧时，自动将至多本卡剩余生命/理智的量改由本卡承担
  （官方为玩家在分配时选择；与 combat_training 的自动承恐同一简化模式）。
  直接伤害（direct）不经分配事件，天然豁免。
- 两个快速启动能力经 activations 声明；自伤/自恐可能击败本卡
  （镜像引擎离场流程）。
"""

from backend.cards._shared import deal_damage_to_enemy, defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.cards.guardian.beat_cop_lv0 import _enemy_at_location
from backend.models.enums import GameEvent, TimingPriority


class AgencyBackup(CardImplementation):
    card_id = "agency_backup_lv5"
    activations = [
        {
            "id": "punch",
            "label": "横置+自伤1：对同地点敌人造成1伤害",
            "method": "activate_punch",
            "actions": 0,
            "target": "enemy",
        },
        {
            "id": "clue",
            "label": "横置+自恐1：在同地点发现1线索",
            "method": "activate_clue",
            "actions": 0,
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    # ------------------------------------------------------------------
    # 快速启动能力
    # ------------------------------------------------------------------
    def activate_punch(self, game_state, investigator_id: str,
                       enemy_instance_id: str) -> bool:
        """横置+自伤1：对同地点一名敌人造成1伤害。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        if not _enemy_at_location(game_state, inv, enemy_instance_id):
            return False
        inst.exhausted = True
        inst.damage += 1
        deal_damage_to_enemy(game_state, self._bus, enemy_instance_id, 1,
                             defeated_by=investigator_id)
        self._check_self_defeat(game_state, inv)
        game_state.log_effect("🏢 特工支援：横置自伤1，对敌人造成1伤害")
        return True

    def activate_clue(self, game_state, investigator_id: str) -> bool:
        """横置+自恐1：在你所在地点发现1条线索。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        location = game_state.get_location(inv.location_id)
        if location is None or location.clues <= 0:
            return False
        inst.exhausted = True
        inst.horror += 1
        location.clues -= 1
        inv.clues += 1
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CLUE_DISCOVERED,
                investigator_id=investigator_id,
                location_id=inv.location_id,
                amount=1,
            ))
        self._check_self_defeat(game_state, inv)
        game_state.log_effect("🏢 特工支援：横置自恐1，发现1条线索")
        return True

    def _check_self_defeat(self, game_state, inv) -> None:
        """自伤/自恐达到上限时被击败离场。"""
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        data = game_state.get_card_data(inst.card_id)
        if data is None:
            return
        defeated = (
            (data.health is not None and inst.damage >= data.health)
            or (data.sanity is not None and inst.horror >= data.sanity)
        )
        if defeated:
            defeat_asset(game_state, self._bus, self.instance_id)
            game_state.log_effect("🏢 特工支援：伤害/恐惧达到上限，被击败")

    # ------------------------------------------------------------------
    # 代承同地点其他调查员的伤害/恐惧（自动）
    # ------------------------------------------------------------------
    def _soak(self, ctx, attr: str, capacity_attr: str, reason: str) -> None:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        if inv.investigator_id == owner.investigator_id:
            return  # 持有者自己的伤害走正常分配
        if inv.location_id != owner.location_id:
            return
        data = ctx.game_state.get_card_data(inst.card_id)
        capacity = getattr(data, capacity_attr, None) if data else None
        if capacity is None:
            return
        remaining = capacity - getattr(inst, attr)
        amount = min(remaining, ctx.amount or 0)
        if amount <= 0:
            return
        setattr(inst, attr, getattr(inst, attr) + amount)
        ctx.modify_amount(-amount, reason)
        ctx.game_state.log_effect(f"🏢 特工支援：代为承担{amount}点")
        self._check_self_defeat(ctx.game_state, owner)

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_damage(self, ctx):
        self._soak(ctx, "damage", "health", "agency_backup_soak_damage")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def soak_horror(self, ctx):
        self._soak(ctx, "horror", "sanity", "agency_backup_soak_horror")
