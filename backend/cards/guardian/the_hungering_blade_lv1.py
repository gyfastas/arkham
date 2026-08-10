"""The Hungering Blade (Level 1) — Guardian Asset, Hand slot. (06018)
每副牌组限制1张。作为打出本卡牌的额外费用，你必须在你的绑定卡牌中查找
3张嗜血，并将其混洗入你的牌堆。
[行动]：攻击。每叠加1张嗜血，这次攻击你+1[战斗]。这次攻击造成+1伤害。
如果这次攻击击败了一名敌人，(从供应堆)放置1资源在本卡牌上，作为贡品。

简化说明：
- 攻击通道同 machete：会话层以 weapon_instance_id=本卡实例发起战斗
  （FIGHT 行动），本卡经 ctx.source 识别自己的攻击，无独立 activate。
- 绑定卡堆未建模：打出时的嗜血混洗从 scenario.vars["bonded_cards"]
  [owner_id]（卡 id 列表，由会话/构筑层维护）中取至多3张 bloodlust_lv0
  洗入牌堆；无该数据时不做事（不阻止打出）。
- 嗜血的叠加由嗜血自身（未实现，不在本批次）/会话层调用
  attach_bloodlust() 记录；叠加数即 +1战斗 的层数。叠加关系存于
  scenario.vars["hungering_blade_attachments"]（跨实例/轮次可查）。
- 贡品记为 inst.uses["offerings"]（从供应堆放置，不扣玩家资源）。
  嗜血显现"移除2贡品以叠加"属嗜血卡面效果，不在本卡实现。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_ATTACH_VAR = "hungering_blade_attachments"
_BONDED_VAR = "bonded_cards"
_BLOODLUST = "bloodlust_lv0"


class TheHungeringBlade(CardImplementation):
    card_id = "the_hungering_blade_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._attack_open = False  # 本卡攻击窗口（FIGHT 发起→检定结束）

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    # ------------------------------------------------------------------
    # 叠加的嗜血（scenario.vars 记录，供会话层/嗜血实现读写）
    # ------------------------------------------------------------------
    def attached_bloodlust(self, game_state) -> list[str]:
        store = game_state.scenario.vars.get(_ATTACH_VAR, {})
        return list(store.get(self.instance_id, []))

    def attach_bloodlust(self, game_state, investigator_id: str,
                         bloodlust_instance_id: str) -> bool:
        """将一份嗜血叠加到本卡（嗜血显现/会话层调用）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        store = game_state.scenario.vars.setdefault(_ATTACH_VAR, {})
        store.setdefault(self.instance_id, []).append(bloodlust_instance_id)
        game_state.log_effect("🗡️ 渴血之刃：叠加了一份嗜血")
        return True

    # ------------------------------------------------------------------
    # 打出的额外费用：3张嗜血从绑定卡洗入牌堆
    # ------------------------------------------------------------------
    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def shuffle_bloodlust_into_deck(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bonded = ctx.game_state.scenario.vars.get(_BONDED_VAR, {}).get(
            inv.investigator_id)
        if not bonded:
            return  # 绑定卡堆未建模：无数据时跳过（见 docstring）
        moved = 0
        while moved < 3 and _BLOODLUST in bonded:
            bonded.remove(_BLOODLUST)
            inv.deck.append(_BLOODLUST)
            moved += 1
        if moved:
            random.shuffle(inv.deck)
            ctx.game_state.log_effect(
                f"🗡️ 渴血之刃：{moved}张嗜血从绑定卡洗入牌堆")

    # ------------------------------------------------------------------
    # 攻击：每份叠加嗜血 +1战斗；+1伤害；击败敌人放1贡品
    # ------------------------------------------------------------------
    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def open_attack(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_open = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def bloodlust_combat_bonus(self, ctx):
        """每叠加1张嗜血，本次攻击 +1战斗。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        count = len(self.attached_bloodlust(ctx.game_state))
        if count:
            ctx.modify_amount(count, "hungering_blade_bloodlust")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """本次攻击造成 +1伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if ctx.source != self.instance_id:
            return
        ctx.extra["bonus_damage"] = int(
            ctx.extra.get("bonus_damage", 0) or 0) + 1

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def place_offering(self, ctx):
        """本卡攻击击败敌人后：从供应堆放1资源作为贡品。"""
        if not self._attack_open:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or ctx.investigator_id != owner.investigator_id:
            return
        inst.uses["offerings"] = inst.uses.get("offerings", 0) + 1
        ctx.extra["hungering_blade_offering"] = inst.uses["offerings"]
        ctx.game_state.log_effect("🗡️ 渴血之刃：击败敌人，放置1贡品")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def close_attack(self, ctx):
        self._attack_open = False
