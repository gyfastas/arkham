"""Segment of Onyx (Level 1) — Seeker Asset. (06021)
多重。快速。
[快速]如果你场上有3张一瓣缟玛瑙：将它们放在一边，位于场外。在你的
绑定卡牌中查找并将皇后的挂坠放置入场。

简化说明：
- 引擎没有"绑定卡"存储（引擎缺口）：皇后的挂坠从卡牌数据库直接创建
  （pendant_of_the_queen_lv0，须已注册卡数据）；场上的一瓣缟玛瑙放入
  scenario.vars["set_aside_out_of_play"]（场外，非弃牌堆）；
- 放置入场复刻 _play_asset 流程（占用饰品槽、初始化 uses——数据键名
  "chargess" 笔误兼容为 charges）；引擎缺口：卡牌代码访问不到
  CardRegistry，挂坠自身的实现无法即时注册（挂坠能力不在本批次）；
- 3张以上同时在场时全部放到场外（多重词条下最多3张入组，正常不会超出）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import GameEvent
from backend.models.state import CardInstance

PENDANT_ID = "pendant_of_the_queen_lv0"


class SegmentOfOnyx(CardImplementation):
    card_id = "segment_of_onyx_lv1"
    activations = [{
        "id": "assemble",
        "label": "[快速]集齐3张：放场外，皇后的挂坠入场",
        "method": "activate",
    }]

    def activate(self, game_state, investigator_id: str) -> bool:
        """[快速]场上有3张一瓣缟玛瑙：放场外，皇后的挂坠放置入场。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        segments = [
            iid for iid in inv.play_area
            if (ci := game_state.get_card_instance(iid)) is not None
            and ci.card_id == self.card_id
        ]
        if len(segments) < 3:
            return False
        pendant_data = game_state.get_card_data(PENDANT_ID)
        if pendant_data is None:
            return False

        from backend.engine.event_bus import EventContext
        from backend.engine.slots import vacate_asset_slots

        bus = getattr(self, "_bus", None)
        set_aside = game_state.scenario.vars.setdefault(
            "set_aside_out_of_play", [])
        for iid in segments:
            vacate_asset_slots(game_state, iid)
            if iid in inv.play_area:
                inv.play_area.remove(iid)
            game_state.cards_in_play.pop(iid, None)
            set_aside.append(self.card_id)
            if bus is not None:
                bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CARD_LEAVES_PLAY,
                    investigator_id=investigator_id,
                    target=iid,
                    extra={"card_id": self.card_id, "set_aside": True},
                ))

        # 皇后的挂坠放置入场（复刻 _play_asset）
        instance_id = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=PENDANT_ID,
            owner_id=investigator_id,
            controller_id=investigator_id,
            slot_used=list(pendant_data.slots or []),
        )
        if pendant_data.uses:
            inst.uses = dict(pendant_data.uses)
            if "chargess" in inst.uses:  # 数据笔误兼容
                inst.uses["charges"] = inst.uses.pop("chargess")
        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if slot_mgr is not None and pendant_data.slots:
            slot_mgr.occupy(instance_id, pendant_data.slots, pendant_data.traits)
        game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        if bus is not None:
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=investigator_id,
                target=instance_id,
                extra={"card_id": PENDANT_ID},
            ))
        game_state.log_effect(
            f"💠 一瓣缟玛瑙：3张放到场外，【{game_state.card_name(PENDANT_ID)}】放置入场")
        return True

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
