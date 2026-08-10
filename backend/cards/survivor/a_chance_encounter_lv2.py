"""A Chance Encounter (Level 2) — Survivor Event.
选择任意玩家弃牌堆中的一张打印资源费用为X的[[盟友]]支援。将该支援
放置入场，置于你的控制之下。（X为打出本卡时支付的费用）

简化说明：
- X 费用：数据中 cost 记为 -2（可变费用占位）。引擎 _play 按 cost=-2
  收费会错误地 +2 资源；本实现按所选盟友的打印费用校正，使净支出为 X
  （再收 X − 引擎已收取的 cost，即 X+2）。
- 目标选择简化：自动选所有玩家弃牌堆中你付得起的、打印费用最高的盟友
  （官方为玩家自选 X 与目标）；无合法目标时校正引擎误收费用、效果落空。
- 放置入场：自建 CardInstance 入你的装备区、占用槽位并触发
  CARD_ENTERS_PLAY（复刻 _play_asset 流程；盟友自身费用不另付——X 已付）。
  所有者简化为打出者（官方保留原所有者，离场时回其弃牌堆）。
- 引擎缺口：卡牌代码访问不到 CardRegistry，入场盟友的实现无法即时注册
  （其持续能力待引擎/会话接线后生效），见报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class AChanceEncounter(CardImplementation):
    card_id = "a_chance_encounter_lv2"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 供 CARD_ENTERS_PLAY 事件使用

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def put_ally_into_play(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        my_cd = ctx.game_state.get_card_data(self.card_id)
        engine_cost = (my_cd.cost or 0) if my_cd else 0  # -2：引擎已"收取"

        # 候选：所有玩家弃牌堆中的盟友支援，取你付得起的最高打印费用
        best = None  # (printed_cost, owner_inv, card_id, card_data)
        for other in ctx.game_state.investigators.values():
            for cid in other.discard:
                cd = ctx.game_state.get_card_data(cid)
                if cd is None or cd.type != CardType.ASSET:
                    continue
                if "ally" not in (cd.traits or []):
                    continue
                printed = cd.cost or 0
                if printed < 0:
                    continue
                # 可支付判定：引擎已收取 engine_cost（=-2，实为+2资源），
                # 校正后净支出 X=printed 不超过打出前资源
                # ⟺ 当前资源 >= printed - engine_cost
                if inv.resources < printed - engine_cost:
                    continue
                if best is None or printed > best[0]:
                    best = (printed, other, cid, cd)

        if best is None:
            # 无合法目标：撤销引擎误收的费用（engine_cost=-2 → 退回2资源），
            # 效果落空
            inv.resources += engine_cost
            ctx.extra["a_chance_encounter_fizzled"] = True
            return

        printed, owner, cid, cd = best
        # 校正净支出为 X（= 盟友打印费用）：引擎已收 engine_cost，
        # 再收 printed - engine_cost 使合计为 printed
        inv.resources -= (printed - engine_cost)
        owner.discard.remove(cid)

        # 放置入场，置于你的控制之下（复刻 _play_asset）
        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=cid,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(cd.slots or []),
        )
        if cd.uses:
            inst.uses = dict(cd.uses)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if slot_mgr and cd.slots:
            slot_mgr.occupy(instance_id, cd.slots, cd.traits)
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)

        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=inv.investigator_id,
                target=instance_id,
                extra={"card_id": cid},
            ))

        ctx.extra["a_chance_encounter_ally"] = cid
        ctx.extra["a_chance_encounter_instance"] = instance_id
        ctx.extra["a_chance_encounter_x"] = printed
        ctx.game_state.log_effect(
            f"🤝 偶遇：支付X={printed}，【{ctx.game_state.card_name(cid)}】"
            "从弃牌堆放置入场")
