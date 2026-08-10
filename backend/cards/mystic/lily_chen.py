"""Lily Chen — Mystic Investigator. (08010)
能力：游戏开始时将你牌组里每张演武（Discipline）放置入场，[[Unbroken]]面朝上。
远古印记：+2。这次检定结束后，将你控制的1张[[Broken]]演武翻转至其[[Unbroken]]面。

简化说明：
- "游戏开始时演武入场"：Game.setup() 激活本实现后不发出任何事件，实现为
  公开方法 setup_disciplines()（供 UI 在 setup 后直接调用）+ ROUND_BEGINS
  懒触发兜底（第一轮开始时自动入场），与 mark_harrigan 的索菲同一惯例。
  因此起手抓牌/调度时演武仍在牌库中（官方应在起手前入场）——遗留简化。
- 演武实例的 CardImplementation 注册需要 CardRegistry 引用（卡实现拿不
  到）——引擎缺口：以本途径入场的演武其 on_event 能力（+1[agility] 等）
  不生效，会话层可对 scenario.vars["lily_chen_disciplines"] 中的实例补注册
  （同 mark_harrigan 对索菲的说明）。
- 破损状态沿用 discipline_lv0 / burden_of_destiny_lv0 的既定约定：
  scenario.vars["discipline_broken_{instance_id}"] = 破损时的轮数。
- 远古印记的"翻回1张破功演武"简化为自动选择第一张可翻回的破损演武
  （官方为玩家选择）。尊重命运重担"本轮内不能翻回"：破损轮数等于当前
  轮数的演武不可被翻回（该键无法区分破损来源，对演武自身行动造成的破损
  也一并按此限制——保守处理，见 discipline_lv0）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority
from backend.models.state import CardInstance

DISCIPLINE_CARD_ID = "discipline_lv0"


def _broken_key(instance_id: str) -> str:
    return f"discipline_broken_{instance_id}"


class LilyChen(CardImplementation):
    card_id = "lily_chen"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._setup_done = False
        self._flip_pending = False

    def _get_lily(self, game_state, investigator_id):
        """Return the investigator state iff it is Lily Chen."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "lily_chen":
            return None
        return inv

    def _broken_disciplines(self, game_state, inv) -> list[str]:
        """控制着的破损演武 instance_id 列表。"""
        out = []
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is None or inst.card_id != DISCIPLINE_CARD_ID:
                continue
            if _broken_key(inst_id) in game_state.scenario.vars:
                out.append(inst_id)
        return out

    # ------------------------------------------------------------------
    # 游戏开始时：牌组里每张演武放置入场（Unbroken 面朝上）
    # ------------------------------------------------------------------

    def _place_disciplines(self, game_state, investigator_id) -> list[str]:
        """把牌库中所有演武放置入场（幂等），返回新入场实例 id 列表。"""
        inv = self._get_lily(game_state, investigator_id)
        if inv is None:
            return []
        placed = []
        for card_id in [cid for cid in inv.deck if cid == DISCIPLINE_CARD_ID]:
            inv.deck.remove(card_id)
            inst_id = game_state.next_instance_id()
            inst = CardInstance(
                instance_id=inst_id,
                card_id=card_id,
                owner_id=investigator_id,
                controller_id=investigator_id,
            )
            game_state.cards_in_play[inst_id] = inst
            inv.play_area.append(inst_id)
            # Unbroken 面朝上：确保无破损标记
            game_state.scenario.vars.pop(_broken_key(inst_id), None)
            placed.append(inst_id)
        if placed:
            game_state.scenario.vars.setdefault(
                "lily_chen_disciplines", []).extend(placed)
            game_state.log_effect(
                f"🥋 陈丽丽：{len(placed)}张演武放置入场（运功面朝上）")
        return placed

    def setup_disciplines(self, game_state, investigator_id) -> list[str]:
        """游戏开始时将牌库中的演武放置入场。由 UI 在 setup 后调用（幂等）。"""
        return self._place_disciplines(game_state, investigator_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def on_round_begins(self, ctx):
        """第一轮开始时兜底让演武入场。"""
        if self._setup_done:
            return
        self._setup_done = True
        for inv_id in ctx.game_state.investigators:
            if self._get_lily(ctx.game_state, inv_id) is not None:
                self._place_disciplines(ctx.game_state, inv_id)

    # ------------------------------------------------------------------
    # 远古印记：+2。检定结束后将1张破功演武翻回运功面。
    # ------------------------------------------------------------------

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2；若有破损演武，标记检定结束后翻回。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_lily(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "lily_chen_elder_sign")
        if self._broken_disciplines(ctx.game_state, inv):
            self._flip_pending = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def elder_sign_flip(self, ctx):
        """检定结束：翻回第一张可翻回的破损演武。"""
        if not self._flip_pending:
            return
        self._flip_pending = False
        inv = self._get_lily(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        current_round = ctx.game_state.scenario.round_number
        for inst_id in self._broken_disciplines(ctx.game_state, inv):
            key = _broken_key(inst_id)
            broken_round = ctx.game_state.scenario.vars.get(key)
            # 命运重担："本轮内不能将其翻回"
            if broken_round is not None and broken_round == current_round:
                continue
            ctx.game_state.scenario.vars.pop(key, None)
            ctx.game_state.log_effect("🥋 陈丽丽：远古印记，演武翻回运功面")
            return
