"""Abigail Foreman (Level 4) — Seeker Asset, Ally slot. (06324)
[快速]：将你装备区的一张[[典籍]]支援附着到 Abigail Foreman 上，或将你装备区的
一张[[典籍]]支援与已附着的支援交换。附着于她的支援不占用手槽。（限附着1张。）
[反应]在你结算了已附着[[典籍]]支援上的[行动]能力后，横置 Abigail Foreman：
再次结算该能力的效果。

简化说明：
- 附着的典籍仍在你的装备区（仍在场、仍由你控制），仅经 SlotManager.vacate
  释放其占用的栏位；交换时被换下的典籍重新占用栏位。
- "再次结算其效果"实现为公开方法 repeat()（经 activations 声明，供 UI 在典籍
  [行动]能力结算后调用）：横置 Abigail，直接重新调用所附典籍实现的 activate
  方法（不经事件总线注册，避免污染其既有监听）。若典籍因自身费用检查
  （已横置/充能耗尽）拒绝结算，repeat 为空操作。
- 引擎缺口：生产环境的支援激活走会话层直接调用、不发 ASSET_ACTIVATED，引擎
  无法感知"典籍的[行动]能力已结算"，官方的反应自动触发需会话层接线（在结算
  所附典籍的[行动]能力后调用 repeat()）。
"""

from backend.cards.base import CardImplementation


class AbigailForeman(CardImplementation):
    card_id = "abigail_foreman_lv4"
    activations = [
        {"id": "attach", "label": "[快速]附着/交换一张典籍支援（不占手槽）",
         "method": "activate"},
        {"id": "repeat", "label": "[反应]横置：再次结算所附典籍的[行动]能力",
         "method": "repeat"},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attached: str | None = None  # 附着的典籍 instance_id

    @property
    def attached_tome(self) -> str | None:
        return self._attached

    def activate(self, game_state, investigator_id: str,
                 tome_instance_id: str | None = None) -> bool:
        """[快速]附着一张典籍；已附着时与之交换。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if tome_instance_id is None:
            tome_instance_id = self._first_tome(game_state, inv)
        if tome_instance_id is None or tome_instance_id not in inv.play_area:
            return False
        if tome_instance_id == self._attached:
            return False
        tome = game_state.get_card_instance(tome_instance_id)
        cd = game_state.get_card_data(tome.card_id) if tome else None
        if cd is None or "tome" not in [t.lower() for t in (cd.traits or [])]:
            return False

        mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        # 换下的典籍重新占用栏位
        old = self._attached
        if old is not None:
            old_inst = game_state.get_card_instance(old)
            if old_inst is not None and mgr is not None and old_inst.slot_used:
                old_cd = game_state.get_card_data(old_inst.card_id)
                mgr.occupy(old, list(old_inst.slot_used),
                           (old_cd.traits if old_cd else None))
                old_inst.attached_to = None
        # 新附着的典籍释放栏位
        if mgr is not None:
            mgr.vacate(tome_instance_id)
        tome.attached_to = self.instance_id
        self._attached = tome_instance_id
        game_state.log_effect(
            f"👩‍🏫 Abigail Foreman：附着【{game_state.card_name(tome.card_id)}】"
            "（不占手槽）"
        )
        return True

    def repeat(self, game_state, investigator_id: str) -> bool:
        """[反应]横置 Abigail：再次结算所附典籍的[行动]能力（直接重调其 activate）。

        临时实例不经事件总线注册，避免重复注册该典籍的持续监听。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self._attached is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        tome = game_state.get_card_instance(self._attached)
        if inst is None or inst.exhausted or tome is None:
            return False

        from backend.cards.registry import CardRegistry
        registry = CardRegistry()
        registry.discover_cards()
        impl_cls = registry.get_implementation(tome.card_id)
        if impl_cls is None:
            return False
        method = getattr(impl_cls, "activate", None)
        if method is None:
            return False

        inst.exhausted = True
        ok = method(impl_cls(self._attached), game_state, investigator_id)
        if ok:
            game_state.log_effect(
                f"👩‍🏫 Abigail Foreman：横置，再次结算"
                f"【{game_state.card_name(tome.card_id)}】的效果"
            )
        return True

    def _first_tome(self, game_state, inv) -> str | None:
        """装备区第一张典籍（缺省自动选择；官方为玩家自选）。"""
        for iid in inv.play_area:
            if iid == self.instance_id or iid == self._attached:
                continue
            ci = game_state.get_card_instance(iid)
            cd = game_state.get_card_data(ci.card_id) if ci else None
            if cd is not None and "tome" in [t.lower() for t in (cd.traits or [])]:
                return iid
        return None
