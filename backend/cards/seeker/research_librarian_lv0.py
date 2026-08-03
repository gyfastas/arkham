"""Research Librarian (Level 0) — Seeker Asset, Ally slot.

官方规则：进场时检索牌库中的1张典籍(Tome)牌，由玩家选择加入手牌，然后洗牌。
（不是自动抽取——检索后由玩家挑选。）
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ResearchLibrarian(CardImplementation):
    card_id = "research_librarian_lv0"

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.REACTION,
    )
    def search_for_tome(self, ctx):
        """When Research Librarian enters play: search deck for a Tome card,
        let the player choose one to add to hand, then shuffle the deck."""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        tomes: list[tuple[str, str]] = []
        for card_id in inv.deck:
            cd = ctx.game_state.get_card_data(card_id)
            if cd and "tome" in [t.lower() for t in (cd.traits or [])]:
                tomes.append((card_id, cd.name_cn or cd.name))

        msgs = ctx.game_state.scenario.vars.setdefault("action_messages", [])
        if not tomes:
            msgs.append("📚 研究馆员：牌库中没有典籍（Tome）牌")
            return

        ctx.game_state.scenario.vars["pending_choice"] = {
            "kind": "search_tome",
            "investigator_id": ctx.investigator_id,
            "prompt": "<b>研究馆员</b>：检索牌库，选择1张典籍牌加入手牌（其余洗回）",
            "options": [{"id": cid, "label": name} for cid, name in tomes],
        }
        msgs.append(f"📚 研究馆员：检索到 {len(tomes)} 张典籍牌，等待选择…")
