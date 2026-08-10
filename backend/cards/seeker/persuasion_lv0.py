"""Persuasion (Level 0) — Seeker Event. (04105)
谈判。选择你所在地点的一个非弱点的[[类人]]敌人，检定智力(3)。这次检定
难度+X，X为该敌人的恐惧值。如果你成功，将所选的敌人洗回遭遇牌堆。
如果所选的敌人为[[精英]]，改为自动躲避它。

简化说明：
- 目标默认为你所在地点的第一个非弱点类人敌人（与你交战者优先），可用
  ctx.extra["enemy_instance_id"] 指定；
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线），
  难度 = 3 + 敌人恐惧值；
- 成功：非精英敌人洗回遭遇牌堆（离场不发 ENEMY_DEFEATED、不进胜利牌堆，
  直接入遭遇牌堆后洗牌）；精英敌人改为自动躲避（横置、脱离交战、置于
  其所在地点，发 ENEMY_EVADED）；
- 谈判属 AoO_EXEMPT 行动（引擎 Action.PARLEY），但打出事件走 PLAY 行动
  会被趁乱攻击——武装一次性豁免标记取消随后的 ATTACK_OF_OPPORTUNITY
  （与 ill_see_you_in_hell 一致）。
"""

import random

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import is_weakness_card


class Persuasion(CardSelfTest):
    card_id = "persuasion_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._aoo_free: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def parley(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy = self._choose_target(ctx, inv)
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return

        difficulty = 3 + (enemy_data.enemy_horror or 0)
        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.INTELLECT, difficulty,
            source=self.instance_id,
        )
        if result is None:
            return
        success, _margin = result
        ctx.extra["persuasion_success"] = success

        if success:
            if "elite" in (enemy_data.keywords or []):
                self._auto_evade(ctx, inv, enemy)
                ctx.extra["persuasion_evaded"] = enemy.instance_id
            else:
                self._shuffle_into_encounter_deck(ctx, enemy)
                ctx.extra["persuasion_shuffled"] = enemy.instance_id

        # 谈判不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    def _choose_target(self, ctx, inv):
        """你所在地点的非弱点类人敌人（交战优先）；可显式指定。"""
        enemy_iid = ctx.extra.get("enemy_instance_id")
        if enemy_iid:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None and self._is_humanoid(ctx, enemy):
                return enemy
            return None
        candidates = list(inv.threat_area)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            candidates += list(loc.enemies)
        for iid in candidates:
            enemy = ctx.game_state.get_card_instance(iid)
            if enemy is not None and self._is_humanoid(ctx, enemy):
                return enemy
        return None

    @staticmethod
    def _is_humanoid(ctx, enemy) -> bool:
        data = ctx.game_state.get_card_data(enemy.card_id)
        if data is None or is_weakness_card(data):
            return False
        return "humanoid" in [t.lower() for t in (data.traits or [])]

    def _shuffle_into_encounter_deck(self, ctx, enemy) -> None:
        """非精英敌人洗回遭遇牌堆（非击败：无胜利结算）。"""
        eid = enemy.instance_id
        ctx.game_state.cards_in_play.pop(eid, None)
        for inv in ctx.game_state.investigators.values():
            if eid in inv.threat_area:
                inv.threat_area.remove(eid)
        for loc in ctx.game_state.locations.values():
            if eid in loc.enemies:
                loc.enemies.remove(eid)
        ctx.game_state.scenario.encounter_deck.append(enemy.card_id)
        random.shuffle(ctx.game_state.scenario.encounter_deck)
        ctx.game_state.log_effect(
            f"💬 游说：【{ctx.game_state.card_name(enemy.card_id)}】洗回遭遇牌堆"
        )

    def _auto_evade(self, ctx, inv, enemy) -> None:
        """精英敌人：自动躲避（横置、脱离交战、置于所在地点）。"""
        eid = enemy.instance_id
        enemy.exhausted = True
        for other in ctx.game_state.investigators.values():
            if eid in other.threat_area:
                other.threat_area.remove(eid)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and eid not in loc.enemies:
            loc.enemies.append(eid)
        bus = getattr(self, "_selftest_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=inv.investigator_id,
                enemy_id=eid,
            ))
        ctx.game_state.log_effect(
            f"💬 游说：【{ctx.game_state.card_name(enemy.card_id)}】为精英，改为自动躲避"
        )

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
