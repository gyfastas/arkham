"""Cryptic Grimoire (Level 4) — Seeker Asset, Hand slot. (07192)
已研究。
[反应]在你于一次技能检定中结算了1个或更多[诅咒]标记后：在神秘魔典上放置
等量的秘密。
[反应]当你将要抽取遭遇牌堆顶牌时，花费5个秘密：改为从你的牌堆抽1张牌。

简化说明：
- "已研究"的战役日志门槛由构筑层校验；
- 本引擎每次检定揭示1枚标记，故"等量"即每结算1个[诅咒]放1个秘密；
- 遭遇抽牌拦截存在引擎偏差（与 on_the_hunt 同款）：phase_mythos 在发出
  ENCOUNTER_CARD_DRAWN 前已把顶牌弹出，且事件后无条件放入遭遇弃牌堆；本卡
  在处理中把该牌放回遭遇牌堆顶，并把"事件后被重复放入弃牌堆"的同一卡 id 在
  随后的阶段事件（MYTHOS_PHASE_ENDS / INVESTIGATION_PHASE_BEGINS /
  ROUND_BEGINS）中从弃牌堆移除一次（延迟清理）。
- 会话层生产路径（game_session._process_encounter_queue）不发
  ENCOUNTER_CARD_DRAWN，该反应在生产环境需会话层接线——引擎缺口，见报告；
- 反应自动触发（官方为玩家选择是否花费5秘密；拦截遭遇抽牌为纯收益）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

SECRET_COST = 5


class CrypticGrimoireLv4(CardImplementation):
    card_id = "cryptic_grimoire_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._returned_encounters: list[str] = []

    def _owns(self, game_state, investigator_id) -> bool:
        inv = game_state.get_investigator(investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def secret_per_curse(self, ctx):
        """你在检定中每结算1个[诅咒]：放置1个秘密。"""
        if ctx.chaos_token != ChaosTokenType.CURSE:
            return
        if not self._owns(ctx.game_state, ctx.investigator_id):
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inst.uses["secrets"] = inst.uses.get("secrets", 0) + 1
        ctx.extra["cryptic_grimoire_secret"] = True
        ctx.game_state.log_effect("📖 神秘魔典(4)：结算[诅咒]，放置1个秘密")

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def replace_encounter_draw(self, ctx):
        """你将抽遭遇牌堆顶牌时：花5秘密，改为从你的牌堆抽1张。"""
        card_id = ctx.extra.get("card_id")
        if not card_id or not self._owns(ctx.game_state, ctx.investigator_id):
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secrets", 0) < SECRET_COST:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        inst.uses["secrets"] -= SECRET_COST
        # 被弹出的遭遇牌放回牌堆顶（事件后仍会被放入弃牌堆，延迟清理）
        scenario = ctx.game_state.scenario
        scenario.encounter_deck.insert(0, card_id)
        self._returned_encounters.append(card_id)

        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        ctx.extra["cryptic_grimoire_replaced"] = card_id
        ctx.game_state.log_effect(
            "📖 神秘魔典(4)：花费5秘密，改为从你的牌堆抽1张牌"
        )

    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def cleanup_returned(self, ctx):
        """延迟清理：把放回牌堆顶的遭遇牌从弃牌堆的重复记录中移除。"""
        if not self._returned_encounters:
            return
        discard = ctx.game_state.scenario.encounter_discard
        for card_id in self._returned_encounters:
            if card_id in discard:
                discard.remove(card_id)
        self._returned_encounters.clear()
