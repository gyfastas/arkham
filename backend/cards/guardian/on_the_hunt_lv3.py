"""On the Hunt (Level 3) — Guardian Event. (08028)
快速。在神话阶段你将要抽取一张遭遇卡时打出。
改为在遭遇牌堆中查找一个敌人，生成该敌人并与你交战（代替其正常生成地点），
将追猎叠加到它上面，并混洗遭遇牌堆。
[反应] 当你击败被叠加的敌人时：获得3资源。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：神话阶段轮到你抽遭遇卡且牌堆中
  有敌人时自动打出（0费），同 on_the_hunt_lv0 的约定（ lv0 只看牌顶9张，
  本卡查找整个遭遇牌堆）。
- 叠加关系记录在实例状态与 scenario.vars["on_the_hunt_lv3"]；击败奖励在
  ENEMY_DEFEATED（击败者为持有者）结算。事件牌本身官方为叠加在敌人上
  留在场中；引擎事件结算后入弃牌堆，叠加以变量记录表示（注明）。
- 引擎偏差（同 lv0）：phase_mythos 在发出 ENCOUNTER_CARD_DRAWN 前已弹出
  牌顶牌，取消后该牌顶牌仍入遭遇弃牌堆（官方为从未抽离），见 lv0 报告。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Phase, TimingPriority
from backend.models.state import CardInstance

VAR = "on_the_hunt_lv3"  # scenario.vars: {enemy_instance_id: investigator_id}


class OnTheHuntLv3(CardImplementation):
    card_id = "on_the_hunt_lv3"
    persistent_in_hand = True  # 手牌中持续监听遭遇抽取

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def hunt(self, ctx):
        """神话阶段你将抽遭遇卡时：改为从遭遇牌堆找敌人生成、交战并叠加。"""
        if ctx.game_state.scenario.current_phase != Phase.MYTHOS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        scenario = ctx.game_state.scenario
        enemy_card_id = None
        for card_id in scenario.encounter_deck:
            data = ctx.game_state.get_card_data(card_id)
            if data is not None and data.type == CardType.ENEMY:
                enemy_card_id = card_id
                break
        if enemy_card_id is None:
            return  # 牌堆没有敌人：不打出，正常抽牌

        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 0) or 0) if data else 0
        if inv.resources < cost:
            return

        # 从手牌打出（支付费用）
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # 生成该敌人并与你交战（代替其正常生成地点）
        scenario.encounter_deck.remove(enemy_card_id)
        instance_id = ctx.game_state.next_instance_id()
        ctx.game_state.cards_in_play[instance_id] = CardInstance(
            instance_id=instance_id,
            card_id=enemy_card_id,
            owner_id="scenario",
            controller_id="scenario",
        )
        inv.threat_area.append(instance_id)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_ENGAGED,
                investigator_id=inv.investigator_id,
                enemy_id=instance_id,
            ))

        # 叠加追猎到该敌人 + 混洗遭遇牌堆
        scenario.vars.setdefault(VAR, {})[instance_id] = inv.investigator_id
        random.shuffle(scenario.encounter_deck)

        # 阻止原遭遇牌的后续结算（牌顶牌仍入弃牌堆，引擎偏差见 docstring）
        ctx.cancel()
        ctx.extra["on_the_hunt_spawned"] = enemy_card_id
        ctx.game_state.log_effect(
            f"🏹 追猎：【{ctx.game_state.card_name(enemy_card_id)}】生成并与你交战，"
            "追猎叠加到它上面，混洗遭遇牌堆")

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.REACTION)
    def bounty(self, ctx):
        """你击败被叠加的敌人：获得3资源。"""
        attached = ctx.game_state.scenario.vars.get(VAR, {})
        owner_id = attached.get(ctx.target)
        if owner_id is None:
            return
        if ctx.investigator_id != owner_id:
            return
        inv = ctx.game_state.get_investigator(owner_id)
        if inv is None:
            return
        attached.pop(ctx.target, None)
        inv.resources += 3
        ctx.extra["on_the_hunt_bounty"] = 3
        ctx.game_state.log_effect("🏹 追猎：击败被叠加的敌人，获得3资源")
