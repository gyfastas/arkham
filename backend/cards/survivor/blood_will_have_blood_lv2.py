"""Blood Will Have Blood (Level 2) — Survivor Event.
快速。在一名敌人攻击你后打出。每次攻击最多1张。
本次攻击的伤害/恐惧不能分配给[[盟友]]支援卡。
你每从本次攻击受到1点伤害和/或恐惧，抽1张牌。

简化说明：
- 从手牌自动打出（persistent_in_hand）：ENEMY_ATTACKS 记录攻击来源，
  随后 DAMAGE_ASSIGNED / HORROR_ASSIGNED(AFTER) 时若来源敌人攻击的是你、
  资源足够且本次攻击尚未打出过，自动支付1资源打出，并按你实际承受的
  点数立即抽牌（伤害与恐惧两段各自结算抽牌）。
- "不能分配给盟友"：引擎的盟友分摊由 DamageEngine 内部分配表完成，
  卡牌无法拦截（引擎缺口，见报告）。
- 抽牌数按事件结算后的 ctx.amount（取消类效果之后）近似"你受到的点数"，
  盟友已分摊部分仍计入（简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BloodWillHaveBlood(CardImplementation):
    card_id = "blood_will_have_blood_lv2"
    persistent_in_hand = True  # 在手牌中持续监听敌人攻击窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_source: str | None = None   # 本次攻击你的敌人
        self._attack_target: str | None = None
        self._played_for: str | None = None       # 本次攻击已打出的来源标记

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def snapshot_attack(self, ctx):
        self._attack_source = ctx.enemy_id
        self._attack_target = ctx.investigator_id
        self._played_for = None

    def _maybe_play_and_draw(self, ctx) -> None:
        if ctx.source != self._attack_source or self._attack_source is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or ctx.investigator_id != self._attack_target:
            return
        amount = ctx.amount or 0

        if self._played_for != self._attack_source:
            # 每次攻击最多1张：首次承受时自动打出
            if self.card_id not in inv.hand or amount < 1:
                return
            cd = ctx.game_state.get_card_data(self.card_id)
            cost = (getattr(cd, "cost", 1) or 1) if cd else 1
            if inv.resources < cost:
                return
            inv.resources -= cost
            inv.hand.remove(self.card_id)
            inv.discard.append(self.card_id)
            self._played_for = self._attack_source

        # 每承受1点伤害/恐惧抽1张牌
        drawn = 0
        for _ in range(amount):
            if not inv.deck:
                break
            inv.hand.append(inv.deck.pop(0))
            drawn += 1
        if drawn:
            ctx.game_state.log_effect(
                f"🩸 血债血偿：承受{amount}点伤害/恐惧，抽{drawn}张牌")

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def draw_for_damage(self, ctx):
        self._maybe_play_and_draw(ctx)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.AFTER)
    def draw_for_horror(self, ctx):
        self._maybe_play_and_draw(ctx)
