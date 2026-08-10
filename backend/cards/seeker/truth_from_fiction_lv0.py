"""Truth from Fiction (Level 0) — Seeker Event. (04152)
只有当你所在地点有线索时才能打出。
在你控制的1张支援卡上放置2秘密。

简化说明：
- 目标支援由 ctx.extra["asset_instance_id"] 指定；缺省自动选择你控制的
  第一张带秘密用途（uses 含 secrets/secretss）的支援，均无则第一张支援；
- 地点无线索时效果不生效（"Play only"前置条件由会话层校验，此处空转）；
- 数据 JSON 中 uses 键有 "secretss" 笔误，读取时兼容两种键名。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


def _secret_key(inst) -> str:
    return "secretss" if "secretss" in inst.uses else "secrets"


class TruthFromFiction(CardImplementation):
    card_id = "truth_from_fiction_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def place_secrets(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        if location is None or location.clues < 1:
            ctx.extra["truth_from_fiction_failed"] = "no_clue"
            return

        inst = self._choose_asset(ctx, inv)
        if inst is None:
            ctx.extra["truth_from_fiction_failed"] = "no_asset"
            return
        key = _secret_key(inst)
        inst.uses[key] = inst.uses.get(key, 0) + 2
        ctx.extra["truth_from_fiction_asset"] = inst.instance_id
        ctx.game_state.log_effect(
            f"📜 去伪存真：在【{ctx.game_state.card_name(inst.card_id)}】上放置2秘密")

    def _choose_asset(self, ctx, inv):
        wanted = ctx.extra.get("asset_instance_id")
        if wanted:
            inst = ctx.game_state.get_card_instance(wanted)
            if inst is not None and inst.controller_id == inv.investigator_id:
                return inst
            return None
        fallback = None
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            if fallback is None:
                fallback = inst
            if "secrets" in inst.uses or "secretss" in inst.uses:
                return inst
        return fallback
