"""The Necronomicon: John Dee Translation — Neutral Asset (Signature Weakness).
揭示：放入威胁区域，上面放3个恐惧。有恐惧时不能离场。
你揭示的每个[elder_sign]标记都视为[auto_fail]标记。
[行动]：将1个恐惧从死灵之书移到黛西·沃克身上。然后，若死灵之书上没有
恐惧，弃掉它。

实现说明：
- elder_sign→auto_fail 经 CHAOS_TOKEN_RESOLVED 设置
  ctx.extra["force_auto_fail"]（引擎 skill_test._st4 已支持）。注意剧本的
  调查员专属 elder_sign 效果若监听同一事件且只检查标记类型，可能仍会
  触发——剧本层需自行检查 force_auto_fail，特此注明。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class TheNecronomicon(CardImplementation):
    card_id = "the_necronomicon"
    activations = [{"id": "horror", "label": "移1恐惧到自己身上", "method": "activate", "actions": 1}]

    @on_event(
        GameEvent.CARD_DRAWN,
        priority=TimingPriority.WHEN,
    )
    def revelation(self, ctx):
        """Revelation: When drawn, put into threat area with 3 horror tokens.

        The Necronomicon enters play in the threat area (not hand),
        with 3 horror tokens on it.
        """
        if ctx.extra.get("card_id") != "the_necronomicon":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # Remove from hand if it was added there
        if "the_necronomicon" in inv.hand:
            inv.hand.remove("the_necronomicon")

        # Create card instance in play (threat area)
        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="the_necronomicon",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ci.uses = {"horror": 3}
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(
        GameEvent.CHAOS_TOKEN_RESOLVED,
        priority=TimingPriority.WHEN,
    )
    def elder_sign_is_auto_fail(self, ctx):
        """Treat each [elder_sign] you reveal as a [auto_fail] (while The
        Necronomicon is in your threat area)."""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for inst_id in inv.threat_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "the_necronomicon":
                ctx.extra["force_auto_fail"] = True
                return

    def activate(self, game_state, investigator_id):
        """[action]: Move 1 horror from The Necronomicon to Daisy Walker.
        Then, if The Necronomicon has no horror on it, discard it.
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False

        ci = game_state.get_card_instance(self.instance_id)
        if ci is None or ci.uses.get("horror", 0) <= 0:
            return False

        ci.uses["horror"] -= 1
        inv.horror += 1

        # Then, if no horror left, discard it
        if ci.uses["horror"] <= 0:
            if self.instance_id in inv.threat_area:
                inv.threat_area.remove(self.instance_id)
            inv.discard.append(ci.card_id)
            del game_state.cards_in_play[self.instance_id]

        return True
