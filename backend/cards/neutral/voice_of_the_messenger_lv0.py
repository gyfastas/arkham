"""Voice of the Messenger (Level 0) — Neutral Treachery, Weakness (Curse/Pact).
显现 - 你必须选择以下一项：
- 受到1点直接伤害，并受到1点肉体创伤。
- 受到1点直接恐惧，并受到1点精神创伤。

简化说明：
- 二选一需要玩家选择；会话层可在抽牌前将选择写入
  scenario.vars["voice_of_the_messenger_choice"][investigator_id]
  （"damage" 或 "horror"），未提供时自动选择"直接伤害+肉体创伤"
  （同 angered_spirits_lv0 的自动选择惯例）。
- 直接伤害/恐惧不经分配窗口，直接计入（同 dark_memory 的直接恐惧惯例）。
- 创伤同时写入 investigator_card（战役状态）与 scenario.vars["trauma"]
  （战役日志通道，同 angered_spirits_lv0）；无 investigator_card 时写
  InvestigatorState 动态属性（同 cover_up 的 mental_trauma 惯例）。
- 显现结算后本卡进入弃牌堆。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class VoiceOfTheMessenger(CardImplementation):
    card_id = "voice_of_the_messenger_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "voice_of_the_messenger_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "voice_of_the_messenger_lv0" in inv.hand:
            inv.hand.remove("voice_of_the_messenger_lv0")

        # 会话层预选（缺省 "damage"）
        choices = ctx.game_state.scenario.vars.get(
            "voice_of_the_messenger_choice", {})
        choice = choices.pop(inv.investigator_id, "damage")
        self.resolve_choice(ctx.game_state, inv.investigator_id, choice)

        # 显现结算后进入弃牌堆
        inv.discard.append("voice_of_the_messenger_lv0")
        ctx.extra["voice_of_the_messenger_choice"] = choice

    def resolve_choice(self, game_state, investigator_id, choice: str) -> bool:
        """结算选择："damage"=1直接伤害+1肉体创伤；"horror"=1直接恐惧+1精神创伤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or choice not in ("damage", "horror"):
            return False

        if choice == "damage":
            inv.damage += 1  # 直接伤害（不分配）
            kind = "physical"
            label = "1点直接伤害与1点肉体创伤"
        else:
            inv.horror += 1  # 直接恐惧（不分配）
            kind = "mental"
            label = "1点直接恐惧与1点精神创伤"

        ic = inv.investigator_card
        if ic is not None:
            setattr(ic, f"{kind}_trauma", getattr(ic, f"{kind}_trauma", 0) + 1)
        else:
            setattr(inv, f"{kind}_trauma",
                    getattr(inv, f"{kind}_trauma", 0) + 1)
        trauma = game_state.scenario.vars.setdefault("trauma", {})
        entry = trauma.setdefault(investigator_id, {})
        entry[kind] = entry.get(kind, 0) + 1

        game_state.log_effect(f"📯 信使之声：受到{label}")
        return True
