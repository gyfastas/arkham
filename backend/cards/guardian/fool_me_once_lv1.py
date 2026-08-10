"""Fool me once... (Level 1) — Guardian Event. (06156)
快速。在你结算完一张诡计卡的任意效果、将要弃置它时打出。
将"我不会再上当……"放置入场（你的游戏区），并将该诡计叠加到它上面。
[反应] 当任意调查员抽取被叠加诡计卡的任一副本时：弃置"我不会再上当……"，
取消该卡的显现效果。

简化说明：
- 打出时机（"结算完诡计效果将要弃置它时"）引擎没有对应事件，实现为公开
  方法 play_attaching()，由会话层在该时点调用（支付费用、入场、叠加）。
- 叠加关系记录在 scenario.vars["fool_me_once"]（{instance_id: treachery_card_id}）。
- 取消显现经 ctx.cancel() + scenario.vars["cancelled_encounter"] 约定
  （同 ward_of_protection），由会话层跳过该诡计的结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance

VAR = "fool_me_once"


class FoolMeOnce(CardImplementation):
    card_id = "fool_me_once_lv1"

    def play_attaching(self, game_state, investigator_id: str,
                       treachery_card_id: str) -> str | None:
        """(会话层调用) 打出本卡入場並叠加刚结算完的诡计卡。返回实例 id。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return None
        data = game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 1) or 1) if data else 1
        if inv.resources < cost:
            return None

        inv.resources -= cost
        inv.hand.remove(self.card_id)

        instance_id = game_state.next_instance_id()
        game_state.cards_in_play[instance_id] = CardInstance(
            instance_id=instance_id,
            card_id=self.card_id,
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        inv.play_area.append(instance_id)
        game_state.scenario.vars.setdefault(VAR, {})[instance_id] = treachery_card_id
        game_state.log_effect(
            f"🪤 我不会再上当……：入场并叠加【{game_state.card_name(treachery_card_id)}】")
        return instance_id

    @staticmethod
    def _find_instances(game_state) -> list[tuple[str, str, str]]:
        """返回 [(instance_id, treachery_card_id, owner_id)] — 所有在场叠加。"""
        attached = game_state.scenario.vars.get(VAR, {})
        out = []
        for instance_id, treachery_card_id in attached.items():
            inst = game_state.get_card_instance(instance_id)
            if inst is not None:
                out.append((instance_id, treachery_card_id, inst.owner_id))
        return out

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_copy(self, ctx):
        """任意调查员抽到被叠加诡计的副本：弃置本卡，取消其显现效果。"""
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        for instance_id, treachery_card_id, owner_id in self._find_instances(ctx.game_state):
            if card_id != treachery_card_id:
                continue
            # 弃置"我不会再上当……"
            inst = ctx.game_state.get_card_instance(instance_id)
            owner = ctx.game_state.get_investigator(owner_id)
            if owner is not None and instance_id in owner.play_area:
                owner.play_area.remove(instance_id)
                owner.discard.append(self.card_id)
            ctx.game_state.cards_in_play.pop(instance_id, None)
            ctx.game_state.scenario.vars.get(VAR, {}).pop(instance_id, None)

            ctx.cancel()
            ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
            ctx.extra["fool_me_once_cancelled"] = card_id
            ctx.game_state.log_effect(
                f"🪤 我不会再上当……：取消【{ctx.game_state.card_name(card_id)}】的显现效果")
            return
