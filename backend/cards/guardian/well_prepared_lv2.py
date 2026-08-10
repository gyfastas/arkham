"""Well Prepared (Level 2) — Guardian Asset. (04151)
[快速]消耗准备万全：选择你控制的1张支援卡。这次技能检定你的技能值+X，
X为所选支援卡上对应的技能图标数量。

简化说明：
- 快速激活（activations 声明，actions=0）：activate() 横置本卡并记录所选
  支援；加值在该调查员下一次 SKILL_VALUE_DETERMINED 时结算（官方为当前
  这次检定；在检定外激活则遗留到下一次检定，与 ResourceSkillBoost 一致）。
- 目标：可用 target_instance_id 指定你控制的支援；默认选你控制的支援中
  技能图标总数最多者。
- X = 所选支援卡面上与检定技能对应的图标数 + 万能图标数（与引擎投入
  图标的口径一致）；若加值结算时所选支援已不受你控制，X=0。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class WellPrepared(CardImplementation):
    card_id = "well_prepared_lv2"
    activations = [{
        "id": "exhaust_boost",
        "label": "横置：选一张你控制的支援，本次检定+X（卡面对应图标数）",
        "method": "activate",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed: dict | None = None  # {"inv": ..., "target": instance_id}

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """横置准备万全：选择你控制的一张支援，本次检定技能值+X。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False

        target_iid = self._choose_asset(game_state, inv, target_instance_id)
        if target_iid is None:
            return False

        inst.exhausted = True
        self._armed = {"inv": investigator_id, "target": target_iid}
        game_state.log_effect(
            f"🎒 准备万全：横置，以【{game_state.card_name(game_state.get_card_instance(target_iid).card_id)}】"
            "的图标提升本次检定")
        return True

    def _choose_asset(self, game_state, inv, target_instance_id) -> str | None:
        if target_instance_id is not None:
            if target_instance_id not in inv.play_area:
                return None
            ci = game_state.get_card_instance(target_instance_id)
            cd = game_state.get_card_data(ci.card_id) if ci else None
            if cd is None or cd.type != CardType.ASSET:
                return None
            return target_instance_id
        best_iid, best_icons = None, -1
        for iid in inv.play_area:
            ci = game_state.get_card_instance(iid)
            cd = game_state.get_card_data(ci.card_id) if ci else None
            if cd is None or cd.type != CardType.ASSET:
                continue
            total = sum((cd.skill_icons or {}).values())
            if total > best_icons:
                best_iid, best_icons = iid, total
        return best_iid

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed or ctx.investigator_id != self._armed["inv"]:
            return
        target = ctx.game_state.get_card_instance(self._armed["target"])
        amount = 0
        if target is not None and target.controller_id == self._armed["inv"]:
            cd = ctx.game_state.get_card_data(target.card_id)
            icons = (cd.skill_icons or {}) if cd else {}
            if ctx.skill_type is not None:
                amount = (icons.get(ctx.skill_type.value, 0)
                          + icons.get("wild", 0))
        if amount:
            ctx.modify_amount(amount, "well_prepared_icons")
        self._armed = None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = None
