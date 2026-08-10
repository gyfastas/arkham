"""Angered Spirits (Level 0) — Neutral Treachery, Signature Weakness (Akachi Onyele).
显现：放置入你的威胁区域。
[fast]消耗1张[[法术]]支援卡：将该支援卡上的1个充能移动到怒灵上。
强制 - 游戏结束时，若怒灵上的充能少于4个：你受到1点肉体创伤。

简化说明：
- "游戏结束"没有引擎事件，game_end_penalty() 由会话/战役层在终局调用。
- 未指定目标时自动选择第一张可行法术支援（官方为玩家选择）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class AngeredSpirits(CardImplementation):
    card_id = "angered_spirits_lv0"
    activations = [{"id": "move_charge", "label": "[fast]消耗法术支援：移动1充能到怒灵", "method": "activate_move_charge"}]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "angered_spirits_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "angered_spirits_lv0" in inv.hand:
            inv.hand.remove("angered_spirits_lv0")

        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="angered_spirits_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    def activate_move_charge(self, game_state, investigator_id,
                             spell_instance_id: str | None = None) -> bool:
        """[fast]消耗1张法术支援：将其1个充能移动到怒灵上。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        spirits = self._find_in_threat(game_state, inv)
        if spirits is None:
            return False

        target = None
        if spell_instance_id is not None:
            cand = game_state.get_card_instance(spell_instance_id)
            if cand is not None and self._is_valid_spell(game_state, inv, cand):
                target = cand
        else:
            # 简化：自动选择第一张可行法术支援
            for iid in inv.play_area:
                cand = game_state.get_card_instance(iid)
                if cand is not None and self._is_valid_spell(game_state, inv, cand):
                    target = cand
                    break
        if target is None:
            return False

        target.exhausted = True
        target.uses["charges"] -= 1
        spirits.uses["charges"] = spirits.uses.get("charges", 0) + 1
        game_state.log_effect(
            f"👻 怒灵：从【{game_state.card_name(target.card_id)}】移动1个充能"
        )
        return True

    def game_end_penalty(self, game_state, investigator_id) -> bool:
        """强制 - 游戏结束时充能<4：受到1点肉体创伤。返回是否触发。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        spirits = self._find_in_threat(game_state, inv)
        charges = spirits.uses.get("charges", 0) if spirits is not None else 0
        if charges >= 4:
            return False
        ic = inv.investigator_card
        if ic is not None:
            ic.physical_trauma += 1
        # 同时记入战役变量，供战役日志/结算读取
        trauma = game_state.scenario.vars.setdefault("trauma", {})
        trauma[investigator_id] = trauma.get(investigator_id, {})
        trauma[investigator_id]["physical"] = trauma[investigator_id].get("physical", 0) + 1
        game_state.log_effect("👻 怒灵：充能不足4个，受到1点肉体创伤")
        return True

    @staticmethod
    def _is_valid_spell(game_state, inv, inst) -> bool:
        if inst.instance_id not in inv.play_area or inst.exhausted:
            return False
        if inst.uses.get("charges", 0) <= 0:
            return False
        cd = game_state.get_card_data(inst.card_id)
        return cd is not None and "spell" in (cd.traits or [])

    @staticmethod
    def _find_in_threat(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "angered_spirits_lv0":
                return inst
        return None
