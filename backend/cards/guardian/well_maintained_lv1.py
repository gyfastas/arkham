"""Well-Maintained (Level 1) — Guardian Event. (05152)
快速。只能在你回合中打出。
叠加到你控制的一张[[道具]]支援卡。每张支援卡限制1张。
[反应]在被叠加的支援卡被丢弃后：将其返回其所有者手牌，叠加到该支援卡的
每张其它[[升级]]卡也返回各自所有者的手牌。

简化说明：
- 目标：默认选你装备区第一张道具支援；可用 ctx.extra["target_instance"]
  指定（必须是你控制的道具，否则不结算叠加）。"每张支援卡限制1张"不强制
  （会话层校验，从简）。
- 叠加以真实 CardInstance（attached_to=道具实例，不占槽）表示。
- 触发：引擎无 CARD_DISCARDED 发出点（缺口，同 moonstone_lv0 记载）；
  改听 CARD_LEAVES_PLAY，且要求 ctx.extra["card_id"] 存在——
  DamageEngine/_shared 的离场路径先把卡放入弃牌堆再发事件，可安全返还；
  actions 槽位替换路径先发事件后入弃牌堆且无 card_id，该路径不触发返还
  （注明）。
- 其他升级叠加的返还：为这些叠加实例补发 CARD_LEAVES_PLAY，使其自身的
  解除逻辑（如 trusted_lv0 的数值恢复）正常触发。
- 持久化同 trusted_lv0：打出时将触发 handler 以叠加实例 id 手动挂到
  事件总线，越过 ROUND_ENDS 的临时实例清理，触发后自行摘除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance

_ATTACH_VAR = "well_maintained"


class WellMaintained(CardImplementation):
    card_id = "well_maintained_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = self._choose_item(ctx, inv)
        if target_iid is None:
            ctx.extra["well_maintained_fizzle"] = True
            ctx.game_state.log_effect("🔧 保养良好：没有可叠加的道具支援，效果不结算")
            return

        game_state = ctx.game_state
        att_iid = game_state.next_instance_id()
        game_state.cards_in_play[att_iid] = CardInstance(
            instance_id=att_iid,
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            attached_to=target_iid,
        )
        game_state.scenario.vars.setdefault(_ATTACH_VAR, {})[att_iid] = {
            "target": target_iid,
            "owner": inv.investigator_id,
        }
        if self._bus is not None:
            self._bus.register(
                event=GameEvent.CARD_LEAVES_PLAY,
                handler=self._on_leaves_play,
                priority=TimingPriority.AFTER,
                card_instance_id=att_iid,
            )

        ctx.extra["well_maintained_attached"] = target_iid
        target = game_state.get_card_instance(target_iid)
        game_state.log_effect(
            f"🔧 保养良好：叠加到【{game_state.card_name(target.card_id)}】")

    def _choose_item(self, ctx, inv) -> str | None:
        def is_item(iid: str) -> bool:
            inst = ctx.game_state.get_card_instance(iid)
            data = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if data is None or data.type != CardType.ASSET:
                return False
            return "item" in {t.lower() for t in (data.traits or [])}

        target_iid = ctx.extra.get("target_instance")
        if target_iid is not None:
            if target_iid in inv.play_area and is_item(target_iid):
                return target_iid
            return None
        for iid in inv.play_area:
            if is_item(iid):
                return iid
        return None

    def _on_leaves_play(self, ctx):
        """被叠加的道具被丢弃后：道具与其他升级叠加返回各自所有者手牌。"""
        store = ctx.game_state.scenario.vars.get(_ATTACH_VAR, {})
        att_iid = None
        rec = None
        if ctx.target in store:
            att_iid, rec = ctx.target, store[ctx.target]
            # 叠加实例自身离场：仅清理
            store.pop(att_iid, None)
            ctx.game_state.cards_in_play.pop(att_iid, None)
            if self._bus is not None:
                self._bus.unregister_card(att_iid)
            return
        for cand, r in store.items():
            if r.get("target") == ctx.target:
                att_iid, rec = cand, r
                break
        if att_iid is None:
            return
        # DamageEngine 路径在 emit 前已把卡放入弃牌堆；无 card_id 的路径
        # （actions 槽位替换）不触发返还（见 docstring）
        item_card_id = ctx.extra.get("card_id")
        if not item_card_id:
            return
        store.pop(att_iid, None)
        game_state = ctx.game_state
        owner = game_state.get_investigator(rec.get("owner"))
        item_iid = rec.get("target")

        # 道具返回所有者手牌
        if owner is not None:
            if item_card_id in owner.discard:
                owner.discard.remove(item_card_id)
            if item_card_id not in owner.hand:
                owner.hand.append(item_card_id)
            game_state.log_effect(
                f"🔧 保养良好：【{game_state.card_name(item_card_id)}】返回所有者手牌")

        # 其他升级叠加返回各自所有者手牌（补发离场事件以触发其解除逻辑）
        for inst in list(game_state.cards_in_play.values()):
            if inst.attached_to != item_iid or inst.instance_id == att_iid:
                continue
            cd = game_state.get_card_data(inst.card_id)
            traits = {t.lower() for t in (cd.traits or [])} if cd else set()
            if "upgrade" not in traits:
                continue
            game_state.cards_in_play.pop(inst.instance_id, None)
            if self._bus is not None:
                self._bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CARD_LEAVES_PLAY,
                    investigator_id=inst.owner_id,
                    target=inst.instance_id,
                    extra={"card_id": inst.card_id},
                ))
            upgr_owner = game_state.get_investigator(inst.owner_id)
            if upgr_owner is not None:
                if inst.card_id in upgr_owner.discard:
                    upgr_owner.discard.remove(inst.card_id)
                    upgr_owner.hand.append(inst.card_id)
                    game_state.log_effect(
                        f"🔧 保养良好：升级【{game_state.card_name(inst.card_id)}】"
                        "返回所有者手牌")

        # 本卡（保养良好）按官方结算进入弃牌堆：叠加实例移除即可
        game_state.cards_in_play.pop(att_iid, None)
        if self._bus is not None:
            self._bus.unregister_card(att_iid)
        ctx.extra["well_maintained_returned"] = item_card_id
