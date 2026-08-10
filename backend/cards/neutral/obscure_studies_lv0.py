"""Obscure Studies (Level 0) — Neutral Event. Amanda Sharpe 专属。
快速。当你发起一次技能检定时打出。
将阿曼达·夏普下的卡牌返回你的手牌，并将隐秘研习放到她之下。

简化说明：
- "阿曼达·夏普下的卡牌"存放在 scenario.vars["beneath_{investigator_id}"]
  （同 sefina_rousseau 的 beneath 约定）。
- "当你发起检定时打出"的时机限制由会话层负责（引擎 PLAY 通道无该限制
  钩子）。
- 引擎 _play_event 在 CARD_PLAYED 后无条件将事件置入弃牌堆；
  以 vars 中的 beneath 记录为准（弃牌堆残留为已知偏差）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class ObscureStudies(CardImplementation):
    card_id = "obscure_studies_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def swap_beneath(self, ctx):
        if ctx.extra.get("card_id") != "obscure_studies_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        beneath = ctx.game_state.scenario.vars.setdefault(
            beneath_key(ctx.investigator_id), []
        )
        if beneath:
            returned = beneath.pop(0)
            inv.hand.append(returned)
            ctx.game_state.log_effect(
                f"🎓 隐秘研习：【{ctx.game_state.card_name(returned)}】返回手牌"
            )
            ctx.extra["obscure_studies_returned"] = returned
        beneath.append("obscure_studies_lv0")
        ctx.game_state.log_effect("🎓 隐秘研习：放到阿曼达·夏普之下")
