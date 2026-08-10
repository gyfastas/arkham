"""Hope (Level 0) — Survivor Asset. Bonded (Miss Doyle). (06031)
Fast.
Forced - After Hope enters play: Discard Zeal and Augur.
[action] If Hope is ready, exhaust or discard him: Evade. Attempt to evade
with a base [agility] value of 5. (If you discarded Hope, this test is
automatically successful. Then, you may shuffle Hope into your deck to put
Zeal or Augur into play from your discard pile.)

简化说明：
- 躲避检定由卡牌自身回放（CardSelfTest，无投入窗口；同 waylay 模式）；
  基础敏捷5经一次性 SKILL_VALUE_DETERMINED 钩子把基础值替换为5
  （其他在场加值照常叠加）。
- 弃置版：自动成功（横置+脱离交战，发 ENEMY_EVADED），随后将霍普洗入
  牌库并将弃牌堆中第一张 Zeal/Augur 放置入场（复刻 _play_asset；猫的
  实现注册需会话层接线，同 a_chance_encounter 缺口）。
- 目标选择自动化：默认与你交战的第一个敌人，其次你所在地点的敌人；
  可传 enemy_instance_id 指定。
- 数据 fast 字段缺失（卡面为 Fast，数据 artifact，见报告）。
"""

import random

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance

_SISTERS = ("zeal_lv0", "augur_lv0")


class Hope(CardSelfTest):
    card_id = "hope_lv0"
    activations = [
        {
            "id": "evade",
            "label": "横置霍普：以基础敏捷5躲避",
            "method": "activate_evade",
            "actions": 1,
            "target": "enemy",
        },
        {
            "id": "evade_discard",
            "label": "弃置霍普：自动躲避并洗回牌库",
            "method": "activate_evade_discard",
            "actions": 1,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._base5_armed = False

    # ------------------------------------------------------------------
    # 强制效果：入场时弃置 Zeal 与 Augur
    # ------------------------------------------------------------------
    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def discard_sisters(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for iid in list(inv.play_area):
            ci = ctx.game_state.get_card_instance(iid)
            if ci is not None and ci.card_id in _SISTERS:
                vacate_asset_slots(ctx.game_state, iid)
                inv.play_area.remove(iid)
                ctx.game_state.cards_in_play.pop(iid, None)
                inv.discard.append(ci.card_id)
                ctx.game_state.log_effect(
                    f"🐈 霍普入场：弃置【{ctx.game_state.card_name(ci.card_id)}】")

    # ------------------------------------------------------------------
    # [action] 横置：以基础敏捷5躲避
    # ------------------------------------------------------------------
    def activate_evade(self, game_state, investigator_id: str,
                       enemy_instance_id: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        enemy_iid = enemy_instance_id or self._choose_enemy(game_state, inv)
        enemy = game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return False
        enemy_data = game_state.get_card_data(enemy.card_id)
        if enemy_data is None:
            return False

        inst.exhausted = True
        self._base5_armed = True
        result = self.run_self_test(
            game_state, investigator_id, Skill.AGILITY,
            enemy_data.enemy_evade or 0, source=self.instance_id,
        )
        self._base5_armed = False
        if result is None:
            return False
        success, _margin = result
        if success:
            self._evade_and_emit(game_state, inv, enemy_iid)
            game_state.log_effect(
                f"🐈 霍普：以基础敏捷5躲避【{game_state.card_name(enemy.card_id)}】成功")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def base_agility_five(self, ctx):
        """本次躲避检定基础敏捷值为5。"""
        if not self._base5_armed or ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        delta = 5 - inv.get_skill(Skill.AGILITY)
        if delta:
            ctx.modify_amount(delta, "hope_base_agility_5")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._base5_armed = False

    # ------------------------------------------------------------------
    # [action] 弃置：自动躲避，洗回牌库，唤回 Zeal/Augur
    # ------------------------------------------------------------------
    def activate_evade_discard(self, game_state, investigator_id: str,
                               enemy_instance_id: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        enemy_iid = enemy_instance_id or self._choose_enemy(game_state, inv)
        enemy = game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return False

        # 弃置霍普
        vacate_asset_slots(game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)

        # 自动成功躲避
        self._evade_and_emit(game_state, inv, enemy_iid)

        # 洗回牌库
        inv.discard.remove(self.card_id)
        inv.deck.append(self.card_id)
        random.shuffle(inv.deck)

        # 将弃牌堆中第一张 Zeal/Augur 放置入场（复刻 _play_asset）
        for cid in _SISTERS:
            if cid in inv.discard:
                cd = game_state.get_card_data(cid)
                if cd is None:
                    continue
                inv.discard.remove(cid)
                new_iid = game_state.next_instance_id()
                new_inst = CardInstance(
                    instance_id=new_iid,
                    card_id=cid,
                    owner_id=investigator_id,
                    controller_id=investigator_id,
                    slot_used=list(cd.slots or []),
                )
                game_state.cards_in_play[new_iid] = new_inst
                inv.play_area.append(new_iid)
                bus = getattr(self, "_selftest_bus", None)
                if bus is not None:
                    from backend.engine.event_bus import EventContext
                    bus.emit(EventContext(
                        game_state=game_state,
                        event=GameEvent.CARD_ENTERS_PLAY,
                        investigator_id=investigator_id,
                        target=new_iid,
                        extra={"card_id": cid},
                    ))
                break
        game_state.log_effect("🐈 霍普：弃置自动躲避，洗回牌库")
        return True

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
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
    def _evade_enemy(game_state, inv, enemy_iid) -> None:
        """躲避结算：横置、脱离交战、留在当前地点（镜像 _evade 成功分支）。"""
        enemy = game_state.get_card_instance(enemy_iid)
        if enemy is None:
            return
        enemy.exhausted = True
        for other in game_state.investigators.values():
            if enemy_iid in other.threat_area:
                other.threat_area.remove(enemy_iid)
        loc = game_state.get_location(inv.location_id)
        if loc is not None and enemy_iid not in loc.enemies:
            loc.enemies.append(enemy_iid)

    def _evade_and_emit(self, game_state, inv, enemy_iid) -> None:
        """躲避结算并发出 ENEMY_EVADED 事件。"""
        self._evade_enemy(game_state, inv, enemy_iid)
        bus = getattr(self, "_selftest_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=inv.investigator_id,
                enemy_id=enemy_iid,
            ))
