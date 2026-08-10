"""Impromptu Barrier (Level 0) — Survivor Event. (02232 批次)
You may play Impromptu Barrier from your discard pile. If you do, shuffle
it into your deck after resolving its effects.
Evade. The chosen enemy gets -1 evade for this evasion attempt. (If you
played Impromptu Barrier from your discard pile, you may evade an
additional enemy at the same location with evade X or lower. X is the
amount you succeed by.)

简化说明：
- 躲避检定由卡牌自身回放（CardSelfTest，无投入窗口；同 waylay 模式），
  成功后横置+脱离交战并发 ENEMY_EVADED（镜像 _evade 成功分支）。
- 目标选择自动化：默认与你交战的第一个敌人，其次你所在地点的敌人；
  可经 ctx.extra["enemy_instance_id"] 指定。
- "从弃牌堆打出"：引擎 _play 要求卡在手牌，弃牌堆直打需会话层支持
  （引擎缺口）；会话层经 ctx.extra["played_from_discard"]=True 标记，
  本实现据此追加第二个可躲避敌人并在结算后洗回牌库
  （ACTION_PERFORMED/ROUND_ENDS 扫尾，同 nothing_left_to_lose 模式）。
"""

import random

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill, TimingPriority


class ImpromptuBarrier(CardSelfTest):
    card_id = "impromptu_barrier_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._shuffle_pending: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def evade(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy_iid = ctx.extra.get("enemy_instance_id") or self._choose_enemy(
            ctx.game_state, inv)
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        # 所选敌人本次躲避 -1 躲避值
        difficulty = max(0, (enemy_data.enemy_evade or 0) - 1)
        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.AGILITY,
            difficulty, source=self.instance_id,
        )
        if result is None:
            return
        success, margin = result
        ctx.extra["impromptu_barrier_success"] = success
        if not success:
            return

        self._evade_enemy(ctx, inv, enemy_iid)
        ctx.game_state.log_effect(
            f"🚧 临时路障：躲避【{ctx.game_state.card_name(enemy.card_id)}】成功")

        # 弃牌堆打出：可再躲避同地点一个躲避值≤超出量的敌人
        if ctx.extra.get("played_from_discard"):
            second_iid = self._choose_additional(ctx, inv, enemy_iid, margin)
            if second_iid is not None:
                self._evade_enemy(ctx, inv, second_iid)
                second = ctx.game_state.get_card_instance(second_iid)
                ctx.extra["impromptu_barrier_second"] = second_iid
                ctx.game_state.log_effect(
                    f"🚧 临时路障：追加躲避【{ctx.game_state.card_name(second.card_id)}】")
            self._shuffle_pending = inv.investigator_id

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def sweep_after_action(self, ctx):
        self._sweep(ctx)

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def sweep_after_round(self, ctx):
        self._sweep(ctx)

    def _sweep(self, ctx) -> None:
        """弃牌堆打出的本卡结算后洗入牌库（而非弃置）。"""
        inv_id = self._shuffle_pending
        if inv_id is None:
            return
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is not None and self.card_id in inv.discard:
            inv.discard.remove(self.card_id)
            inv.deck.append(self.card_id)
            random.shuffle(inv.deck)
        self._shuffle_pending = None

    @staticmethod
    def _choose_enemy(game_state, inv) -> str | None:
        """目标：与你交战的第一个敌人优先，其次你所在地点的敌人。"""
        if inv.threat_area:
            return inv.threat_area[0]
        loc = game_state.get_location(inv.location_id)
        if loc is not None and loc.enemies:
            return loc.enemies[0]
        return None

    @staticmethod
    def _choose_additional(ctx, inv, first_iid, margin) -> str | None:
        """同地点躲避值≤超出量的另一个敌人（自动选第一个符合条件的）。"""
        loc = ctx.game_state.get_location(inv.location_id)
        candidates = list(loc.enemies) if loc is not None else []
        for other in ctx.game_state.investigators.values():
            if other.location_id == inv.location_id:
                candidates.extend(other.threat_area)
        for iid in candidates:
            if iid == first_iid:
                continue
            ci = ctx.game_state.get_card_instance(iid)
            cd = ctx.game_state.get_card_data(ci.card_id) if ci else None
            if cd is not None and (cd.enemy_evade or 0) <= margin:
                return iid
        return None

    def _evade_enemy(self, ctx, inv, enemy_iid) -> None:
        """躲避结算：横置、脱离交战、留在当前地点，发 ENEMY_EVADED。"""
        enemy = ctx.game_state.get_card_instance(enemy_iid)
        if enemy is None:
            return
        enemy.exhausted = True
        for other in ctx.game_state.investigators.values():
            if enemy_iid in other.threat_area:
                other.threat_area.remove(enemy_iid)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and enemy_iid not in loc.enemies:
            loc.enemies.append(enemy_iid)
        bus = getattr(self, "_selftest_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=inv.investigator_id,
                enemy_id=enemy_iid,
            ))
