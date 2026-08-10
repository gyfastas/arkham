"""De Vermis Mysteriis (Level 2) — Mystic Asset, Hand slot. (05235)
[action]消耗蠕虫的秘密并在其上放置1个毁灭标记：从你的弃牌堆打出一张
[[法术]]或[[洞察]]事件卡，其资源费用降低1点。在该事件卡结算后，将其
移出游戏。

简化说明：
- activate() 消耗本卡、放置1毁灭、支付减免后费用，并把目标事件从弃牌堆
  取出；随后经事件总线补发 CARD_PLAYED（监听"打出事件"的效果可响应），
  结算后将目标移出游戏（scenario.vars["removed_from_game"]，同
  quantum_flux 惯例）。
- 事件自身效果的完整重放需要 registry/会话层（卡牌代码拿不到——引擎缺口）；
  会话层可在 activate 前按减免后费用正常结算目标事件。
- 目标自动选择：弃牌堆中第一张法术/洞察事件（可用 target_card_id 参数指定）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class DeVermisMysteriis(CardImplementation):
    card_id = "de_vermis_mysteriis_lv2"
    activations = [{
        "id": "replay",
        "label": "消耗+1毁灭：从弃牌堆打出法术/洞察事件，费用-1，结算后移出游戏",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def activate(self, game_state, investigator_id: str,
                 target_card_id: str | None = None) -> str | None:
        """[action]消耗+1毁灭：从弃牌堆打出法术/洞察事件（费用-1），结算后移出游戏。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return None

        target = None
        if target_card_id is not None:
            if target_card_id in inv.discard and self._is_valid(game_state, target_card_id):
                target = target_card_id
        else:
            for cid in inv.discard:
                if self._is_valid(game_state, cid):
                    target = cid
                    break
        if target is None:
            return None

        cd = game_state.get_card_data(target)
        cost = max(0, (getattr(cd, "cost", 0) or 0) - 1)
        if inv.resources < cost:
            return None

        inst.exhausted = True
        inst.doom += 1
        inv.resources -= cost
        inv.discard.remove(target)

        # 补发 CARD_PLAYED（监听类效果可响应）；事件自身效果由会话层结算
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_PLAYED,
                investigator_id=investigator_id,
                source=self.instance_id,
                extra={"card_id": target, "de_vermis_mysteriis": True},
            ))

        # 结算后移出游戏
        game_state.scenario.vars.setdefault("removed_from_game", []).append(target)
        game_state.log_effect(
            f"📖 蠕虫的秘密：从弃牌堆打出【{game_state.card_name(target)}】"
            f"（费用-{1}），结算后移出游戏")
        return target

    @staticmethod
    def _is_valid(game_state, card_id: str) -> bool:
        cd = game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.EVENT:
            return False
        traits = [t.lower() for t in (cd.traits or [])]
        return "spell" in traits or "insight" in traits
