"""Book of Shadows (Level 3) — Mystic Asset, Hand slot. (01070)
你拥有1个额外的奥秘槽位。
[action] 横置影之书：给你控制的一张[[法术]]支援卡添加1个充能。

简化说明：
- 奥秘槽通过 GameState.slot_managers 的 bonus_slots 授予（同 Charisma 模式）。
- 添加充能的目标默认为你控制的第一张带充能的法术支援卡（无选择 UI）；
  调用方可传 target_instance_id 指定目标。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, SlotType, TimingPriority


class BookOfShadows(CardImplementation):
    card_id = "book_of_shadows_lv3"
    activations = [{
        "id": "add_charge",
        "label": "横置：给你控制的一张法术支援加1充能",
        "method": "activate",
        "actions": 1,
    }]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """进场：+1奥秘槽位。"""
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.add_bonus(SlotType.ARCANE, 1)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if mgr is not None:
            mgr.remove_bonus(SlotType.ARCANE, 1)

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """横置：给你控制的一张法术支援卡添加1个充能。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        target = self._find_spell_target(game_state, inv, target_instance_id)
        if target is None:
            return False

        inst.exhausted = True
        target.uses["charges"] = target.uses.get("charges", 0) + 1
        game_state.log_effect(
            f"📖 影之书：【{game_state.card_name(target.card_id)}】+1充能")
        return True

    def _find_spell_target(self, game_state, inv, target_instance_id):
        """目标：你控制的带充能的法术支援卡（默认第一张，可指定）。"""
        candidates = []
        for iid in inv.play_area:
            ci = game_state.get_card_instance(iid)
            if ci is None or iid == self.instance_id:
                continue
            cd = game_state.get_card_data(ci.card_id)
            if cd is None or cd.type != CardType.ASSET:
                continue
            if "spell" not in (cd.traits or []):
                continue
            if "charges" not in ci.uses:
                continue
            candidates.append(ci)
        if target_instance_id is not None:
            for ci in candidates:
                if ci.instance_id == target_instance_id:
                    return ci
            return None
        return candidates[0] if candidates else None
