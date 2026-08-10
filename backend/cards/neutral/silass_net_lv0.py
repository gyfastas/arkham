"""Silas's Net (Level 0) — Neutral Asset, Hand slot. (07015)
仅限西拉斯·马什牌组。
[action]：躲避。本次躲避你获得+1[敏捷]。若你成功且向本次技能检定投入了1张
或以上技能卡，你可以自动躲避另一个与你交战的敌人。当本次技能检定结束时，
你可以将西拉斯的渔网返回手牌，改为将你所有投入的技能卡返回手牌而非丢弃
它们。

简化说明：
- "仅限西拉斯牌组"为构筑限制，由卡组校验负责。
- 引擎躲避行动不携带来源武器实例（EVADE 无 weapon 通道），采用
  activate() 武装 + 会话层随后发起躲避行动的惯例（同 shrivelling）。
- "自动躲避另一个敌人"：自动选择第一个其他交战敌人（官方为玩家选择）。
- 收回手牌为可选能力：会话层调用 choose_return()，参照 sea_change_harpoon。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class SilassNet(CardImplementation):
    card_id = "silass_net_lv0"
    activations = [
        {"id": "evade", "label": "[行动] 躲避：+1敏捷", "method": "activate", "actions": 1},
        {"id": "return", "label": "检定结束时收回渔网与投入的技能卡", "method": "choose_return"},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._committed_skills: list[str] = []
        self._return_chosen = False
        self._evade_target: str | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """[action]：武装一次"用渔网躲避"（会话层随后发起躲避行动）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        return True

    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_target(self, ctx):
        """记录本次躲避的原目标（SKILL_TEST_* 事件不携带 enemy_id）。"""
        if self._armed:
            self._evade_target = ctx.enemy_id

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def track_committed_skills(self, ctx):
        self._committed_skills = []
        if not self._armed:
            return
        if ctx.investigator_id != self._owner_id(ctx):
            return
        for cid in ctx.committed_cards or []:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and cd.type == CardType.SKILL:
                self._committed_skills.append(cid)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, "silass_net_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def evade_another(self, ctx):
        """成功且投入了技能卡：自动躲避另一个交战敌人（自动选择第一个）。"""
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        if not self._committed_skills:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        current_target = self._evade_target
        for inst_id in list(inv.threat_area):
            if inst_id == current_target:
                continue
            inst = ctx.game_state.get_card_instance(inst_id)
            cd = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if inst is None or cd is None:
                continue
            if getattr(cd, "type", None) != CardType.ENEMY:
                continue
            # 自动躲避：横置并移出威胁区，放到地点
            inst.exhausted = True
            inv.threat_area.remove(inst_id)
            location = ctx.game_state.get_location(inv.location_id)
            if location is not None and inst_id not in location.enemies:
                location.enemies.append(inst_id)
            bus = getattr(self, "_bus", None)
            if bus is not None:
                from backend.engine.event_bus import EventContext
                bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.ENEMY_EVADED,
                    investigator_id=inv.investigator_id,
                    enemy_id=inst_id,
                ))
            ctx.extra["silass_net_extra_evade"] = inst_id
            break

    def choose_return(self, game_state, investigator_id) -> bool:
        """玩家选择：检定结束时将本卡与投入的技能卡收回手牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if not self._armed:
            return False
        self._return_chosen = True
        return True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_return(self, ctx):
        if self._return_chosen and self._armed and self._committed_skills:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and self.instance_id in inv.play_area:
                for cid in self._committed_skills:
                    if cid in inv.discard:
                        inv.discard.remove(cid)
                        inv.hand.append(cid)
                vacate_asset_slots(ctx.game_state, self.instance_id)
                inv.play_area.remove(self.instance_id)
                ctx.game_state.cards_in_play.pop(self.instance_id, None)
                inv.hand.append("silass_net_lv0")
                ctx.extra["silass_net_returned"] = True
        self._armed = False
        self._committed_skills = []
        self._return_chosen = False

    def register(self, bus, instance_id: str) -> None:
        self._bus = bus
        super().register(bus, instance_id)

    def _owner_id(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        return inst.controller_id if inst is not None else None
