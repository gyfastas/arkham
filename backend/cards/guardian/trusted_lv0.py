"""Trusted (Level 0) — Guardian Event. (04019)
快速。只能在你的回合中打出。
叠加到你控制的一张[[盟友]]支援卡。
被叠加的支援卡生命值+1，神智值+1。

简化说明：
- 目标：默认选你装备区第一张盟友支援；可用 ctx.extra["target_instance"]
  指定（必须是你控制的盟友，否则不结算叠加）。
- 叠加以真实 CardInstance 表示（attached_to=盟友实例，不占槽、不进
  play_area），+1/+1 通过提升该盟友 CardData 的 health/sanity 实现
  （引擎的承伤/击败判定只读 CardData，无按实例覆盖通道）；CardData 按
  卡 id 共享，同名牌的第二张同名盟友会一并受益（边界情况，注明）。
  叠加解除时恢复原值。
- "只能在你的回合中打出"由会话层校验（同其他 fast 事件）。
- 持久化：事件的临时实现实例会在 ROUND_ENDS 被引擎清理；本卡在打出时
  将离场清理 handler 以叠加实例 id 手动挂到事件总线，跨轮持续生效，
  叠加解除时自行摘除（不依赖注册表）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance

_ATTACH_VAR = "trusted_attachments"


class Trusted(CardImplementation):
    card_id = "trusted_lv0"

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

        target_iid = self._choose_ally(ctx, inv)
        if target_iid is None:
            ctx.extra["trusted_fizzle"] = True
            ctx.game_state.log_effect("🤝 信赖：没有可叠加的盟友支援，效果不结算")
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

        target = game_state.get_card_instance(target_iid)
        cd = game_state.get_card_data(target.card_id)
        # 记录卡 id：盟友实例先离场再发 CARD_LEAVES_PLAY，恢复时需按卡 id 定位
        game_state.scenario.vars[_ATTACH_VAR][att_iid]["target_card_id"] = (
            target.card_id)
        cd.health = (cd.health or 0) + 1
        cd.sanity = (cd.sanity or 0) + 1

        # 持久清理 handler：绑定到叠加实例 id，越过 ROUND_ENDS 临时实例清理
        if self._bus is not None:
            self._bus.register(
                event=GameEvent.CARD_LEAVES_PLAY,
                handler=self._on_leaves_play,
                priority=TimingPriority.AFTER,
                card_instance_id=att_iid,
            )

        ctx.extra["trusted_attached"] = target_iid
        game_state.log_effect(
            f"🤝 信赖：叠加到【{game_state.card_name(target.card_id)}】，生命/神智+1")

    def _choose_ally(self, ctx, inv) -> str | None:
        def is_ally(iid: str) -> bool:
            inst = ctx.game_state.get_card_instance(iid)
            data = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if data is None or data.type != CardType.ASSET:
                return False
            return "ally" in {t.lower() for t in (data.traits or [])}

        target_iid = ctx.extra.get("target_instance")
        if target_iid is not None:
            if target_iid in inv.play_area and is_ally(target_iid):
                return target_iid
            return None
        for iid in inv.play_area:
            if is_ally(iid):
                return iid
        return None

    def _on_leaves_play(self, ctx):
        """叠加的盟友（或本叠加）离场：恢复 +1/+1 并移除叠加实例。"""
        store = ctx.game_state.scenario.vars.get(_ATTACH_VAR, {})
        # ctx.target 可能是叠加实例本身，也可能是被叠加的盟友
        att_iid = None
        rec = None
        if ctx.target in store:
            att_iid, rec = ctx.target, store[ctx.target]
        else:
            for cand, r in store.items():
                if r.get("target") == ctx.target:
                    att_iid, rec = cand, r
                    break
        if att_iid is None:
            return
        store.pop(att_iid, None)

        ctx.game_state.cards_in_play.pop(att_iid, None)
        # 恢复盟友数值：盟友离场事件在实例移除后才发出，按记录的卡 id 定位
        target = ctx.game_state.get_card_instance(rec.get("target"))
        card_id = (target.card_id if target is not None
                   else rec.get("target_card_id"))
        cd = (ctx.game_state.get_card_data(card_id) if card_id else None)
        if cd is not None:
            cd.health = max(0, (cd.health or 0) - 1)
            cd.sanity = max(0, (cd.sanity or 0) - 1)

        if self._bus is not None:
            self._bus.unregister_card(att_iid)
        ctx.game_state.log_effect("🤝 信赖：叠加解除，生命/神智加值移除")
