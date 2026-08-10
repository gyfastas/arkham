"""First Watch (Level 0) — Guardian Event. (06110)
快速。当神话阶段的"抽取遭遇卡"步骤将要开始时打出。
改为不结算该步骤，查看遭遇牌堆顶的X张牌，X为调查员人数。将这些牌按你的
意愿分配给各调查员，除你自己外每名调查员至多分得1张。然后，每名调查员
逐一抽取分得给自己的牌。

简化说明：
- 打出时机窗口由会话层控制；打出后经 CARD_PLAYED 结算（与 ward_of_protection
  同一模式），并登记 scenario.vars["encounter_draw_step_replaced"] 供会话层
  跳过本回合的遭遇抽取步骤（⚠️ 引擎 MythosPhase 不消费该标记——会话/引擎
  缺口，见报告；测试直接验证结算效果）。
- 分配简化为自动：从持有者开始按玩家顺序每人1张（X=调查员人数，恰好每人
  1张；"查看"记入 ctx.extra["first_watch_looked"] 与效果日志）。
- 每名调查员的抽取发出 ENCOUNTER_CARD_DRAWN 事件并入遭遇弃牌堆
  （镜像 MythosPhase._draw_encounter_cards 的单卡流程）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class FirstWatch(CardImplementation):
    card_id = "first_watch_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def replace_draw_step(self, ctx):
        """打出时：查看遭遇牌堆顶X张并分配给各调查员抽取。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        holder = ctx.game_state.get_investigator(ctx.investigator_id)
        if holder is None:
            return
        scenario = ctx.game_state.scenario
        order = list(ctx.game_state.player_order)
        if not order:
            return
        x = len(order)
        looked = scenario.encounter_deck[:x]
        if not looked:
            ctx.extra["first_watch_looked"] = []
            return
        ctx.extra["first_watch_looked"] = list(looked)
        ctx.game_state.log_effect(
            f"👁️ 头班守夜：查看遭遇牌堆顶{len(looked)}张并分配"
            f"（{', '.join(looked)}）")

        # 从持有者开始按玩家顺序轮转分配，每人1张
        start = order.index(holder.investigator_id)
        rotated = order[start:] + order[:start]
        dealt: dict[str, str] = {}
        for idx, card_id in enumerate(looked):
            dealt[rotated[idx % len(rotated)]] = card_id

        from backend.engine.event_bus import EventContext
        for inv_id in rotated:
            card_id = dealt.get(inv_id)
            if card_id is None:
                continue
            scenario.encounter_deck.remove(card_id)
            ctx2 = EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENCOUNTER_CARD_DRAWN,
                investigator_id=inv_id,
                extra={"card_id": card_id},
            )
            # 经注册时保存的总线发出
            if self._bus is not None:
                self._bus.emit(ctx2)
            scenario.encounter_discard.append(card_id)
        ctx.extra["first_watch_dealt"] = dealt
        scenario.vars["encounter_draw_step_replaced"] = True
        ctx.game_state.log_effect("👁️ 头班守夜：替代了本回合的遭遇抽取步骤")

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
