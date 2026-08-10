"""Alter Fate (Level 3) — Survivor Event.
快速。在任何快速玩家窗口打出。
选择并丢弃场上一张没有叠加在[[精英]]敌人上的非弱点诡计卡。

简化说明：
- 打出时自动选择目标（可经 ctx.extra["target_instance_id"] 指定）：
  搜索所有调查员威胁区与地点叠加区中类型为诡计、非弱点、
  未叠加在精英敌人上的卡牌实例。
- 场景诡计卡进遭遇弃牌堆；玩家弱点以外的玩家诡计卡进其拥有者弃牌堆。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import is_weakness_card
from backend.scenarios.official_core import is_elite_enemy


class AlterFate(CardImplementation):
    card_id = "alter_fate_lv3"

    def _is_legal_target(self, game_state, instance_id) -> bool:
        inst = game_state.get_card_instance(instance_id)
        if inst is None:
            return False
        cd = game_state.get_card_data(inst.card_id)
        if cd is None or cd.type != CardType.TREACHERY:
            return False
        if is_weakness_card(cd) or "weakness" in [t.lower() for t in (cd.traits or [])]:
            return False
        # 叠加在精英敌人上的除外
        anchor = game_state.get_card_instance(getattr(inst, "attached_to", None) or "")
        if anchor is not None:
            anchor_cd = game_state.get_card_data(anchor.card_id)
            if anchor_cd is not None and anchor_cd.type == CardType.ENEMY \
                    and is_elite_enemy(anchor_cd):
                return False
        return True

    def _choose_target(self, ctx):
        wanted = ctx.extra.get("target_instance_id")
        if wanted:
            return wanted if self._is_legal_target(ctx.game_state, wanted) else None
        for inv in ctx.game_state.investigators.values():
            for iid in inv.threat_area:
                if self._is_legal_target(ctx.game_state, iid):
                    return iid
        for loc in ctx.game_state.locations.values():
            for iid in loc.attachments:
                if self._is_legal_target(ctx.game_state, iid):
                    return iid
        for iid, inst in ctx.game_state.cards_in_play.items():
            if inst.card_id and self._is_legal_target(ctx.game_state, iid):
                return iid
        return None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discard_treachery(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        target_iid = self._choose_target(ctx)
        if target_iid is None:
            ctx.game_state.log_effect("✨ 改变命运：场上没有合法的非弱点诡计卡")
            return

        inst = ctx.game_state.get_card_instance(target_iid)
        card_id = inst.card_id
        # 从威胁区 / 地点叠加区移除
        for inv in ctx.game_state.investigators.values():
            if target_iid in inv.threat_area:
                inv.threat_area.remove(target_iid)
        for loc in ctx.game_state.locations.values():
            if target_iid in loc.attachments:
                loc.attachments.remove(target_iid)
        ctx.game_state.cards_in_play.pop(target_iid, None)

        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is not None:
            owner.discard.append(card_id)
        else:
            ctx.game_state.scenario.encounter_discard.append(card_id)
        ctx.extra["alter_fate_discarded"] = card_id
        ctx.game_state.log_effect(
            f"✨ 改变命运：丢弃【{ctx.game_state.card_name(card_id)}】")
