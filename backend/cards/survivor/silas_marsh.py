"""Silas Marsh — Survivor Investigator. (07005)
能力：[reaction]你在你执行的技能检定中揭示混乱标记后：将你投入到此检定的一张
技能卡返回你的手牌。（每轮限制一次。）
远古印记：+0。你可以将你弃牌堆的一张技能卡投入这次检定。这次检定结束后，
不丢弃该技能卡，改为将其返回你的手牌。

简化说明：
- 投入的技能卡在 ST.8 才从手牌进弃牌堆（engine/skill_test._st8_end），
  因此"返回手牌"实现为：CHAOS_TOKEN_REVEALED 时把所选技能卡先移出手牌
  （ST.8 的弃置循环找不到它），SKILL_TEST_ENDS 时放回手牌；其已贡献的
  图标在 CHAOS_TOKEN_RESOLVED 以负修正扣回。
- 返回哪张技能卡官方为玩家选择；同步检定流程中无法等待输入，简化为自动
  选择"与本次检定技能匹配图标+万能图标最少"的投入技能卡（并列取先投入者），
  并在 ctx.extra["silas_marsh_returned"] 记录。
- 远古印记"你可以投入弃牌堆的一张技能卡"同样简化为自动选择弃牌堆顶
  （最晚弃入）的技能卡；其图标作为本次检定的修正加入，检定结束后从弃牌堆
  返回手牌。投入卡的牌面效果（如 Perception 的抽牌）不触发——临时激活
  需 CardRegistry，卡牌代码拿不到（引擎缺口，同 ever_vigilant 惯例）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)


class SilasMarsh(CardImplementation):
    card_id = "silas_marsh"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_round = False
        self._committed_skills: list[str] = []
        self._pending_return: str | None = None       # 反应能力扣留的技能卡
        self._return_icons = 0
        self._elder_sign_committed: str | None = None  # 远古印记投入的技能卡

    def _get_silas(self, game_state, investigator_id):
        """Return the investigator state iff it is Silas Marsh."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "silas_marsh":
            return None
        return inv

    def _matching_icons(self, game_state, card_id, skill_type) -> int:
        data = game_state.get_card_data(card_id)
        icons = (data.skill_icons or {}) if data else {}
        if skill_type is None:
            return icons.get("wild", 0)
        return icons.get(skill_type.value, 0) + icons.get("wild", 0)

    # ------------------------------------------------------------------
    # [reaction] 揭示标记后：将投入的一张技能卡返回手牌（每轮限1次）
    # ------------------------------------------------------------------

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        self._used_this_round = False

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def track_committed_skills(self, ctx):
        """记录 Silas 本次检定投入的技能卡。"""
        if self._get_silas(ctx.game_state, ctx.investigator_id) is None:
            return
        self._committed_skills = [
            cid for cid in (ctx.committed_cards or [])
            if (cd := ctx.game_state.get_card_data(cid)) is not None
            and cd.type == CardType.SKILL
        ]

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.REACTION)
    def return_committed_skill(self, ctx):
        """揭示标记后：自动把"贡献图标最少"的投入技能卡扣留起来（稍后回手）。"""
        if self._used_this_round or not self._committed_skills:
            return
        inv = self._get_silas(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        chosen = min(
            self._committed_skills,
            key=lambda cid: self._matching_icons(
                ctx.game_state, cid, ctx.skill_type),
        )
        if chosen not in inv.hand:
            return
        inv.hand.remove(chosen)  # 扣留：避免 ST.8 被弃掉
        self._pending_return = chosen
        self._return_icons = self._matching_icons(
            ctx.game_state, chosen, ctx.skill_type)
        self._used_this_round = True
        ctx.extra["silas_marsh_returned"] = chosen
        ctx.game_state.log_effect(
            f"⚓ 赛拉斯·马什：【{ctx.game_state.card_name(chosen)}】将返回手牌")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def resolve_token(self, ctx):
        """扣回被返回技能卡的图标 / 远古印记效果。"""
        inv = self._get_silas(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        # 反应能力：扣回被返回技能卡已贡献的图标
        if self._pending_return is not None and self._return_icons:
            ctx.modify_amount(-self._return_icons, "silas_marsh_return_skill")

        # 远古印记：+0。自动投入弃牌堆顶的技能卡，检定结束后返回手牌。
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        for cid in reversed(inv.discard):
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and cd.type == CardType.SKILL:
                icons = self._matching_icons(ctx.game_state, cid, ctx.skill_type)
                if icons:
                    ctx.modify_amount(icons, "silas_marsh_elder_sign_commit")
                self._elder_sign_committed = cid
                ctx.extra["silas_marsh_elder_sign_committed"] = cid
                ctx.game_state.log_effect(
                    f"⚓ 赛拉斯·马什：远古印记，从弃牌堆投入"
                    f"【{ctx.game_state.card_name(cid)}】")
                break

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def cleanup_test(self, ctx):
        """检定结束：扣留/弃牌堆投入的技能卡返回手牌。"""
        inv = self._get_silas(ctx.game_state, ctx.investigator_id)
        if inv is None and (self._pending_return or self._elder_sign_committed):
            # 兜底：ctx 不是 Silas 的检定（理论上不会发生，检定为串行）时
            # 直接定位 Silas，避免扣留卡丢失。
            for cand in ctx.game_state.investigators.values():
                if self._get_silas(ctx.game_state, cand.investigator_id):
                    inv = cand
                    break
        if inv is not None:
            if self._pending_return is not None:
                inv.hand.append(self._pending_return)
            if (self._elder_sign_committed is not None
                    and self._elder_sign_committed in inv.discard):
                inv.discard.remove(self._elder_sign_committed)
                inv.hand.append(self._elder_sign_committed)
        self._committed_skills = []
        self._pending_return = None
        self._return_icons = 0
        self._elder_sign_committed = None
