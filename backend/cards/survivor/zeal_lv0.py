"""Zeal (Level 0) — Survivor Asset. (06032)
绑定（道尔女士）。快速。
强制 - 在热诚入场后：丢弃希望和预见。
[action] 如果热诚已准备，将其消耗或丢弃：攻击。以5点基础 [combat] 值攻击。
（如果你丢弃热诚，这次检定自动成功。然后，你可以将热诚混洗入你的牌堆来将
希望或预见从你的弃牌堆放置入场。）

简化说明：
- 绑定/快速为构筑与打出规则，由会话层处理。
- 强制效果：入场时丢弃同一拥有者场上的 hope_lv0 / augur_lv0（若在场）。
- 攻击沿用 shrivelling 模式：activate_fight() 消耗（或 activate_fight_discard()
  丢弃）本卡并武装，随后由会话层以 weapon_instance_id=本卡实例发起战斗；
  战斗中基础战斗值设为5（按差值修正，投入图标/标记照常叠加）。
- 丢弃版"自动成功"经 SKILL_TEST_FAILED(WHEN) 翻转 ctx.success 实现
  （同 lucky 通道；覆盖自动失败标记，官方"自动成功"优先）。
- 丢弃版结算后：自动将热诚从弃牌堆洗入牌堆，并把弃牌堆中第一张
  hope_lv0/augur_lv0 放入场（官方为"可以"，且两卡数据尚缺时为无操作；
  放卡不入槽位、不激活实现——引擎缺口，见报告）。
"""

import random

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance

_CATS = ("hope_lv0", "augur_lv0")


class Zeal(CardImplementation):
    card_id = "zeal_lv0"
    activations = [
        {
            "id": "fight",
            "label": "消耗热诚：以5点基础战斗攻击",
            "method": "activate_fight",
            "actions": 1,
            "target": "enemy",
        },
        {
            "id": "fight_discard",
            "label": "丢弃热诚：以5点基础战斗攻击且自动成功",
            "method": "activate_fight_discard",
            "actions": 1,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._fight_armed = False
        self._auto_success = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # defeat_asset 需要事件总线句柄

    # ------------------------------------------------------------------
    # 强制：入场后丢弃希望和预见
    # ------------------------------------------------------------------
    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.FORCED)
    def discard_other_cats(self, ctx):
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        owner_id = inst.owner_id if inst else ctx.investigator_id
        for iid, ci in list(ctx.game_state.cards_in_play.items()):
            if ci.card_id in _CATS and ci.owner_id == owner_id:
                defeat_asset(ctx.game_state, getattr(self, "_bus", None), iid)
                ctx.game_state.log_effect(
                    f"🐈 热诚：丢弃【{ctx.game_state.card_name(ci.card_id)}】")

    # ------------------------------------------------------------------
    # 启动能力：攻击
    # ------------------------------------------------------------------
    def _arm_fight(self, game_state, investigator_id: str, discard: bool) -> bool:
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or inst.exhausted:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if discard:
            vacate_asset_slots(game_state, self.instance_id)
            inv.play_area.remove(self.instance_id)
            game_state.cards_in_play.pop(self.instance_id, None)
            inv.discard.append(self.card_id)
            self._auto_success = True
        else:
            inst.exhausted = True
            self._auto_success = False
        self._fight_armed = True
        return True

    def activate_fight(
        self, game_state, investigator_id: str, enemy_instance_id: str | None = None
    ) -> bool:
        """[action] 消耗热诚：以5点基础战斗攻击。"""
        ok = self._arm_fight(game_state, investigator_id, discard=False)
        if ok:
            game_state.log_effect("🐈 热诚：消耗，以5点基础战斗攻击")
        return ok

    def activate_fight_discard(
        self, game_state, investigator_id: str, enemy_instance_id: str | None = None
    ) -> bool:
        """[action] 丢弃热诚：以5点基础战斗攻击，且自动成功。"""
        ok = self._arm_fight(game_state, investigator_id, discard=True)
        if ok:
            game_state.log_effect("🐈 热诚：丢弃，以5点基础战斗攻击且自动成功")
        return ok

    # ------------------------------------------------------------------
    # 检定钩子
    # ------------------------------------------------------------------
    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def set_base_combat(self, ctx):
        """本卡发起的攻击：基础战斗值设为5。"""
        if not self._fight_armed or ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None:
                return
            base = inv.get_skill(ctx.skill_type)
        delta = 5 - base
        if delta:
            ctx.modify_amount(delta, "zeal_base_combat_5")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def force_success(self, ctx):
        """丢弃版：本次检定自动成功。"""
        if not self._fight_armed or not self._auto_success:
            return
        if ctx.source != self.instance_id:
            return
        ctx.success = True
        ctx.extra["zeal_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def after_test(self, ctx):
        """丢弃版结算后：洗回牌堆，并把弃牌堆中希望/预见放入场。"""
        try:
            if not self._fight_armed or not self._auto_success:
                return
            if ctx.source != self.instance_id:
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None or self.card_id not in inv.discard:
                return
            # 热诚洗入牌堆
            inv.discard.remove(self.card_id)
            inv.deck.insert(random.randint(0, len(inv.deck)), self.card_id)
            # 弃牌堆中第一张希望/预见放入场
            cat = next((c for c in _CATS if c in inv.discard), None)
            if cat is not None:
                inv.discard.remove(cat)
                new_iid = ctx.game_state.next_instance_id()
                ctx.game_state.cards_in_play[new_iid] = CardInstance(
                    instance_id=new_iid,
                    card_id=cat,
                    owner_id=inv.investigator_id,
                    controller_id=inv.investigator_id,
                )
                inv.play_area.append(new_iid)
                ctx.extra["zeal_returned_cat"] = cat
            ctx.extra["zeal_shuffled"] = True
            ctx.game_state.log_effect("🐈 热诚：洗入牌堆")
        finally:
            self._fight_armed = False
            self._auto_success = False
