"""Buried Secrets (Level 0) — Neutral Treachery, Weakness.
显现：放置入你的威胁区域。
若你的地点可以被调查，你不能移动（剧本卡效果除外）。
[行动]：调查。若成功，改为不发现线索，丢弃埋葬的秘密。若失败，你可以
受到2点恐惧将其洗入你的牌组。

简化说明：
- "不能移动"：引擎的 _move 不咨询事件取消（引擎缺口），本实现提供
  blocks_move() 供会话层过滤；"可以被调查"近似为地点存在（引擎中任何
  已揭示地点均可调查）。
- [行动]调查经 activate() 发起（消耗1行动，走标准调查流程）；成功时
  经 CLUE_DISCOVERED 事后校正（线索退回地点，同 cover_up 惯例）并丢弃本卡。
- 失败后"可以受2点恐惧洗回牌组"不自动执行，由会话层调用
  take_horror_to_shuffle()（官方为可选）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import Action, GameEvent, Skill, TimingPriority


class BuriedSecrets(CardImplementation):
    card_id = "buried_secrets_lv0"
    activations = [{
        "id": "investigate",
        "label": "[行动] 调查（成功则丢弃埋葬的秘密）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending_inv: str | None = None  # 经本卡启动的调查进行中
        self._failed = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "buried_secrets_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "buried_secrets_lv0" in inv.hand:
            inv.hand.remove("buried_secrets_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="buried_secrets_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    def activate(self, game, investigator_id: str) -> bool:
        """[行动]：调查（会话层调用）。成功则改为丢弃本卡。"""
        inv = game.state.get_investigator(investigator_id)
        if inv is None or self._find_secrets(game.state, inv) is None:
            return False
        if inv.actions_remaining <= 0:
            return False
        self._pending_inv = investigator_id
        self._failed = False
        try:
            game.action_resolver.perform_action(
                investigator_id, Action.INVESTIGATE)
        finally:
            self._pending_inv = None
        return True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def discard_instead_of_clues(self, ctx):
        """经本卡调查成功：改为不发现线索，丢弃埋葬的秘密。"""
        if self._pending_inv is None or ctx.investigator_id != self._pending_inv:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inst = self._find_secrets(ctx.game_state, inv)
        if inst is None:
            return
        # 事后校正：线索退回地点
        amount = ctx.amount or 1
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None:
            loc.clues += amount
        inv.clues = max(0, inv.clues - amount)
        self._discard(ctx.game_state, inv, inst)
        ctx.extra["buried_secrets_discarded"] = True
        ctx.game_state.log_effect("🪦 埋葬的秘密：调查成功，丢弃（未发现线索）")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def on_failure(self, ctx):
        """经本卡调查失败：可受2点恐惧洗回牌组（标记，由会话层抉择）。"""
        if self._pending_inv is None or ctx.investigator_id != self._pending_inv:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        self._failed = True
        ctx.extra["buried_secrets_failed"] = True

    def take_horror_to_shuffle(self, game_state, investigator_id) -> bool:
        """调查失败后（会话层调用）：受2点恐惧，将本卡洗入牌组。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_secrets(game_state, inv)
        if inst is None:
            return False
        inv.horror += 2  # 直接恐惧（不分配）
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        import random
        inv.deck.append("buried_secrets_lv0")
        random.shuffle(inv.deck)
        return True

    def blocks_move(self, game_state, investigator_id) -> bool:
        """会话层过滤用：本卡在威胁区时持有者不能移动（剧本效果除外）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return self._find_secrets(game_state, inv) is not None

    def _discard(self, game_state, inv, inst) -> None:
        if inst.instance_id in inv.threat_area:
            inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("buried_secrets_lv0")

    @staticmethod
    def _find_secrets(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "buried_secrets_lv0":
                return inst
        return None
