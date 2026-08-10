"""Tony's .38 Long Colt (Level 0) — Neutral Asset, Hand slot.托尼·摩尔根专属。
使用（3弹药）。
[反应]在你打出托尼的.38柯尔特长管手枪后：从手牌免费打出另一把
托尼的.38柯尔特长管手枪。
[行动]花费1弹药：战斗。被攻击的敌人上每有1个赏金，本次攻击+1战斗。
本次攻击造成+1伤害。如果本次攻击击败1个带有1个或以上赏金的敌人，
在赏金合同（Bounty Contracts）上放置1个赏金。

简化说明：
- 赏金以敌人实例 uses["bounty"] 计数（托尼的猎物入场时放置；赏金合同
  bounty_contracts_lv0 的实现不在本批次，移动赏金到赏金合同时若其不在场
  则仅记录日志，引擎缺口）。
- "免费打出另一把"在 CARD_ENTERS_PLAY 自动结算（官方为可选触发，简化
  为手牌中有第二把且手部槽位允许时自动打出；槽位不足则跳过并记日志）。
- 弹药费用/加值通道与 rolands_38_special 一致：FIGHT_ACTION_INITIATED 扣
  弹药（未命中同样消耗），0弹药时等同徒手攻击。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance


class Tonys38LongColt(CardImplementation):
    card_id = "tonys_38_long_colt_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._attack_paid = False   # 本次攻击已付1弹药
        self._bounties_on_target = 0  # 攻击发起时被攻击敌人上的赏金数

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    # ------------------------------------------------------------------
    # [反应]打出后：免费打出手中另一把
    # ------------------------------------------------------------------
    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.REACTION)
    def play_second_copy(self, ctx):
        if ctx.target != self.instance_id:
            return
        if ctx.extra.get("tonys_colt_chain"):  # 同一上下文不重复连锁
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "tonys_38_long_colt_lv0" not in inv.hand:
            return

        # 手部槽位检查（第二把同样占1手槽）
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        data = ctx.game_state.get_card_data("tonys_38_long_colt_lv0")
        slots = list(data.slots) if data is not None else []
        if slot_mgr is not None and slots and not slot_mgr.can_play_card(
                slots, data.traits):
            ctx.game_state.log_effect("🔫 柯尔特长管手枪：手部槽位不足，未能打出第二把")
            return

        inv.hand.remove("tonys_38_long_colt_lv0")
        new_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=new_id,
            card_id="tonys_38_long_colt_lv0",
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=slots,
        )
        if data is not None and data.uses:
            ci.uses = dict(data.uses)
        ctx.game_state.cards_in_play[new_id] = ci
        inv.play_area.append(new_id)
        if slot_mgr is not None and slots:
            slot_mgr.occupy(new_id, slots, data.traits)

        # 注册第二把的实现（卡牌代码无 registry 通道，直接实例化注册）
        Tonys38LongColt(new_id).register(self._bus, new_id)

        # 免费打出（不付资源），发出入场事件（不连锁第三把：标记上下文）
        from backend.engine.event_bus import EventContext
        enter_ctx = EventContext(
            game_state=ctx.game_state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id=inv.investigator_id,
            target=new_id,
            extra={"card_id": "tonys_38_long_colt_lv0",
                   "tonys_colt_chain": True},
        )
        self._bus.emit(enter_ctx)
        ctx.game_state.log_effect("🔫 柯尔特长管手枪：免费打出第二把")

    # ------------------------------------------------------------------
    # [行动]花费1弹药：战斗
    # ------------------------------------------------------------------
    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo_on_attack(self, ctx):
        self._attack_paid = False
        self._bounties_on_target = 0
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is not None:
            self._bounties_on_target = enemy.uses.get("bounty", 0)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """被攻击敌人上每个赏金 +1战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._bounties_on_target > 0:
            ctx.modify_amount(
                self._bounties_on_target, "tonys_colt_bounty_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "tonys_colt_extra_damage")

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def bounty_to_contracts(self, ctx):
        """击败带赏金的敌人：在赏金合同上放置1个赏金。"""
        if not self._attack_paid or self._bounties_on_target < 1:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for iid in inv.play_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is not None and inst.card_id == "bounty_contracts_lv0":
                inst.uses["bounty"] = inst.uses.get("bounty", 0) + 1
                ctx.game_state.log_effect("🔫 柯尔特长管手枪：赏金合同+1赏金")
                return
        ctx.game_state.log_effect(
            "🔫 柯尔特长管手枪：赏金合同不在场，赏金未能放置（引擎缺口）")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_flag(self, ctx):
        self._attack_paid = False
        self._bounties_on_target = 0
