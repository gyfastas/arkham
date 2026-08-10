"""The Painted World (Level 0) — Neutral Event, Signature (Sefina Rousseau).
不能放在赛菲娜·卢梭下。
打出画中世界时，将其作为赛菲娜·卢梭下的一张非卓越事件卡。
不要丢弃画中世界，改为将其从游戏中移除。

简化说明：
- "赛菲娜·卢梭下的卡牌"存放在 scenario.vars["beneath_{investigator_id}"]
  （与 stars_of_hyades_lv0 共用），由会话层/赛菲娜能力写入。
- 复制目标自动选择赛菲娜下的第一张事件卡（官方为玩家选择）；卡数据没有
  exceptional 字段，视为全部非卓越。
- 复制效果的执行需要会话层按选中的事件结算（卡牌 handler 无法访问
  CardRegistry 来临时激活被复制事件的实现）；选择结果写入
  ctx.extra["painted_world_copy"]。
- 移出游戏记录在 scenario.vars["removed_from_game"]（与 abandoned_and_alone
  同一惯例）。注意：engine.actions._play_event 在 CARD_PLAYED 结算后无条件
  将事件放入弃牌堆，handler 内无法拦截——需要引擎支持"移出游戏"出牌通道；
  当前若它出现在弃牌堆，以 removed_from_game 记录为准。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class ThePaintedWorld(CardImplementation):
    card_id = "the_painted_world_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "the_painted_world_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        scenario = ctx.game_state.scenario

        beneath = scenario.vars.setdefault(beneath_key(inv.investigator_id), [])
        events = [
            cid for cid in beneath
            if (cd := ctx.game_state.get_card_data(cid)) is not None
            and cd.type == CardType.EVENT
        ]
        # 简化：自动选择第一张事件（官方为玩家选择）
        copy_id = ctx.extra.get("copy_card_id") or (events[0] if events else None)
        ctx.extra["painted_world_copy"] = copy_id
        if copy_id:
            ctx.game_state.log_effect(
                f"🖼️ 画中世界：作为【{ctx.game_state.card_name(copy_id)}】的复制打出"
            )

        # 移出游戏而非丢弃
        scenario.vars.setdefault("removed_from_game", []).append("the_painted_world_lv0")
        if "the_painted_world_lv0" in inv.discard:
            inv.discard.remove("the_painted_world_lv0")
        ctx.extra["painted_world_removed"] = True
