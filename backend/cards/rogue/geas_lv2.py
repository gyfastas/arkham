"""Geas (Level 2) — Rogue Asset. (07265)
卓绝。你+1意志、+1智力、+1战斗、+1敏捷。
强制 - 在誓约入场后：许下如下格式的诺言——"我在我的每个回合中不会
（抽/打出/投入）任何卡牌。"若你在誓约在场时违背此诺言，弃置誓约并向
混沌袋加入10个[curse]标记。

简化说明：
- 诺言内容需玩家选择：choose_promise() 公开方法（"draw"/"play"/"commit"），
  未选择时默认 "play"（最常见选择）。
- 违背判定仅在持有者的回合中跟踪（INVESTIGATOR_TURN_BEGINS/ENDS）：
  draw=CARD_DRAWN、play=CARD_PLAYED/CARD_ENTERS_PLAY、commit=投入卡牌
  的 SKILL_TEST_COMMIT。
- 违背时弃置本卡并向混沌袋加入[curse]（按官方规则袋中[curse]上限10个封顶，
  同 promise_of_power）；混沌袋经 bind_chaos_bag() 注入。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority

_MAX_CURSE_TOKENS = 10
_PROMISES = ("draw", "play", "commit")


class Geas(CardImplementation):
    card_id = "geas_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None
        self._promise: str | None = None
        self._my_turn = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 违背诺言离场时需经事件总线发出 CARD_LEAVES_PLAY

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    def choose_promise(self, game_state, investigator_id: str, promise: str) -> bool:
        """选择诺言："draw"（不抽牌）/"play"（不打牌）/"commit"（不投入）。"""
        if promise not in _PROMISES:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.owner_id != investigator_id:
            return False
        self._promise = promise
        return True

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def default_promise(self, ctx):
        """入场后须许诺（简化：未显式选择时默认 "play"）。"""
        if ctx.target == self.instance_id and self._promise is None:
            self._promise = "play"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def passive_boost(self, ctx):
        """你+1意志、+1智力、+1战斗、+1敏捷。"""
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT,
                                  Skill.COMBAT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "geas_passive")

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_start(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        self._my_turn = inst is not None and inst.owner_id == ctx.investigator_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.owner_id == ctx.investigator_id:
            self._my_turn = False

    def _is_owner_turn_action(self, ctx) -> bool:
        if not self._my_turn or self._promise is None:
            return False
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        return ctx.investigator_id == inst.owner_id

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def watch_draw(self, ctx):
        if self._promise == "draw" and self._is_owner_turn_action(ctx):
            self._break_promise(ctx)

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def watch_play_event(self, ctx):
        if self._promise == "play" and self._is_owner_turn_action(ctx):
            self._break_promise(ctx)

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def watch_play_asset(self, ctx):
        if ctx.target == self.instance_id:
            return  # 誓约自身入场不算
        if self._promise == "play" and self._is_owner_turn_action(ctx):
            self._break_promise(ctx)

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def watch_commit(self, ctx):
        if self._promise != "commit" or not ctx.committed_cards:
            return
        if self._is_owner_turn_action(ctx):
            self._break_promise(ctx)

    def _break_promise(self, ctx) -> None:
        """违背诺言：弃置誓约并向混沌袋加入[curse]（上限10个）。"""
        from backend.engine.event_bus import EventContext

        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inst.owner_id)
        if slot_mgr is not None:
            slot_mgr.vacate(self.instance_id)
        if inv is not None and self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
            inv.discard.append(self.card_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)

        added = 0
        if self._chaos_bag is not None:
            existing = sum(1 for t in self._chaos_bag.tokens + self._chaos_bag.sealed
                           if t == ChaosTokenType.CURSE)
            for _ in range(min(10, max(0, _MAX_CURSE_TOKENS - existing))):
                self._chaos_bag.add_token(ChaosTokenType.CURSE)
                added += 1
        ctx.extra["geas_broken"] = True
        ctx.extra["geas_curses_added"] = added
        ctx.game_state.log_effect(
            f"⛓ 誓约被违背：弃置誓约，混沌袋加入{added}个[curse]标记")
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inst.owner_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
