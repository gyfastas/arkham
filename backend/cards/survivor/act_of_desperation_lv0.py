"""Act of Desperation (Level 0) — Survivor Event.
作为打出的额外费用，从手牌或游戏区选择并丢弃一张占用至少1个手部槽位的
[[道具]]支援卡。攻击。本次攻击+X[战斗]并造成+1伤害，X为所选支援卡的打印
资源费用。若成功且该支援卡是从你的游戏区丢弃的，获得X资源。

简化说明：
- 打出时自动选择费用最高的合法道具（可经 ctx.extra["discard_instance_id"]
  指定游戏区实例，或 ctx.extra["discard_card_id"] 指定手牌）；官方为玩家选择。
- 打出后经 active_effects 武装，由会话层发起战斗行动（同 backstab 模式）：
  +X战斗、成功时+1伤害；若成功且丢弃的是游戏区中的支援卡，获得X资源。
- "至少1个手部槽位"按卡牌数据的 slots 含 hand 判定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, SlotType, TimingPriority


class ActOfDesperation(CardImplementation):
    card_id = "act_of_desperation_lv0"

    def _is_legal_item(self, game_state, card_id) -> bool:
        cd = game_state.get_card_data(card_id)
        if cd is None:
            return False
        traits = [t.lower() for t in (cd.traits or [])]
        return "item" in traits and SlotType.HAND in (cd.slots or [])

    def _choose_target(self, ctx, inv):
        """返回 (来源, 标识, 打印费用)：游戏区实例或手牌。"""
        wanted_iid = ctx.extra.get("discard_instance_id")
        if wanted_iid:
            inst = ctx.game_state.get_card_instance(wanted_iid)
            if inst is not None and wanted_iid in inv.play_area \
                    and self._is_legal_item(ctx.game_state, inst.card_id):
                cd = ctx.game_state.get_card_data(inst.card_id)
                return ("play", wanted_iid, cd.cost or 0)
            return None
        wanted_cid = ctx.extra.get("discard_card_id")
        if wanted_cid:
            if wanted_cid in inv.hand \
                    and self._is_legal_item(ctx.game_state, wanted_cid):
                cd = ctx.game_state.get_card_data(wanted_cid)
                return ("hand", wanted_cid, cd.cost or 0)
            return None

        best = None  # (cost, source, key)
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None or not self._is_legal_item(ctx.game_state, inst.card_id):
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            cand = (cd.cost or 0, "play", iid)
            if best is None or cand[0] > best[0]:
                best = cand
        for cid in inv.hand:
            if cid == self.card_id:
                continue
            if not self._is_legal_item(ctx.game_state, cid):
                continue
            cd = ctx.game_state.get_card_data(cid)
            cand = (cd.cost or 0, "hand", cid)
            if best is None or cand[0] > best[0]:
                best = cand
        if best is None:
            return None
        return (best[1], best[2], best[0])

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discard_item_and_arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        chosen = self._choose_target(ctx, inv)
        if chosen is None:
            ctx.game_state.log_effect("🗡️ 绝望之举：没有可丢弃的手部槽位道具支援卡")
            return
        source, key, x_value = chosen

        if source == "play":
            inst = ctx.game_state.get_card_instance(key)
            card_id = inst.card_id
            vacate_asset_slots(ctx.game_state, key)
            inv.play_area.remove(key)
            ctx.game_state.cards_in_play.pop(key, None)
            inv.discard.append(card_id)
        else:
            card_id = key
            inv.hand.remove(key)
            inv.discard.append(key)

        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[self.card_id] = {"x": x_value, "from_play": source == "play"}
        ctx.extra["act_of_desperation_x"] = x_value
        ctx.game_state.log_effect(
            f"🗡️ 绝望之举：丢弃【{ctx.game_state.card_name(card_id)}】"
            f"（费用{x_value}），本次攻击+{x_value}战斗、+1伤害")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        armed = getattr(inv, "active_effects", {}).get(self.card_id)
        if not armed:
            return
        ctx.modify_amount(armed["x"], "act_of_desperation_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage_and_resources(self, ctx):
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        armed = getattr(inv, "active_effects", {}).get(self.card_id)
        if not armed:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
        if armed["from_play"] and armed["x"] > 0:
            inv.resources += armed["x"]
            ctx.game_state.log_effect(
                f"🗡️ 绝望之举：攻击成功，获得{armed['x']}资源")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop(self.card_id, None)
