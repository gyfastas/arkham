"""Monterey Jack — Rogue Investigator. (08007)
能力：[reaction]当你的回合结束时，如果你本轮开始时的地点与你现在地点相隔1个
地点：获得1资源或抽取1张卡牌（如果相隔至少2个地点，改为执行两项）。
远古印记：+1。如果你本轮开始时的地点与你现在地点相隔至少1个地点，
获得1资源或抽取1张卡牌。

简化说明：
- "相隔N个地点"按地点连接图的最短路径（BFS）计算；任一端地点不存在时
  按0处理。
- 本轮开始时的地点在 ROUND_BEGINS 记录（仅记录蒙特雷本人）。
- 回合结束触发的"获得1资源或抽1张牌"为二选一：采用 pending_choice +
  公开方法 resolve_turn_end()（参考 wendy_adams 惯例；server 端未接入
  本 kind，需 UI/测试直接调用）。相隔2+地点时两项自动执行（无二选一）。
- 远古印记的二选一在检定同步流程中无法等待选择，实现为
  scenario.vars["monterey_elder_sign_choice"] 预设（"resource"/"card"，
  公开方法 choose_elder_sign_choice() 设置，默认 "resource"）。
- 抽牌直接移动牌库顶到手牌，不发 CARD_DRAWN（同 mark_harrigan 惯例）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

PENDING_KIND = "monterey_jack_turn_end"
PRESET_KEY = "monterey_elder_sign_choice"


def _location_distance(game_state, from_id: str, to_id: str) -> int:
    """两地点间最短路径（按连接数）；不可达或地点缺失返回0。"""
    if not from_id or not to_id or from_id == to_id:
        return 0
    if game_state.get_location(from_id) is None or \
            game_state.get_location(to_id) is None:
        return 0
    visited = {from_id}
    queue = [(from_id, 0)]
    while queue:
        current, dist = queue.pop(0)
        loc = game_state.get_location(current)
        if loc is None:
            continue
        for conn in loc.connections:
            if conn in visited:
                continue
            if conn == to_id:
                return dist + 1
            visited.add(conn)
            queue.append((conn, dist + 1))
    return 0


class MontereyJack(CardImplementation):
    card_id = "monterey_jack"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._round_start_location: str | None = None

    def _get_jack(self, game_state, investigator_id):
        """Return the investigator state iff it is Monterey Jack."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "monterey_jack":
            return None
        return inv

    def _draw_one(self, game_state, inv) -> None:
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))

    def _moved_distance(self, game_state, inv) -> int:
        return _location_distance(
            game_state, self._round_start_location, inv.location_id)

    # ------------------------------------------------------------------
    # [reaction] 回合结束时：相隔1地点 → 二选一；相隔2+ → 两项
    # ------------------------------------------------------------------

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def record_round_start(self, ctx):
        """记录蒙特雷本轮开始时的地点。"""
        self._round_start_location = None
        for inv_id, inv in ctx.game_state.investigators.items():
            if self._get_jack(ctx.game_state, inv_id) is not None:
                self._round_start_location = inv.location_id
                break

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.REACTION)
    def on_turn_ends(self, ctx):
        """回合结束时按移动距离给资源/抽牌。"""
        inv = self._get_jack(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        distance = self._moved_distance(ctx.game_state, inv)
        if distance <= 0:
            return

        if distance >= 2:
            inv.resources += 1
            self._draw_one(ctx.game_state, inv)
            ctx.game_state.log_effect(
                "🤠 蒙特雷·杰克：本轮跨越2+地点，获得1资源并抽1张牌")
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return
        scenario.vars["pending_choice"] = {
            "kind": PENDING_KIND,
            "investigator_id": ctx.investigator_id,
            "prompt": "<b>蒙特雷·杰克</b>：你本轮移动了1个地点，选择奖励：",
            "options": [
                {"id": "resource", "label": "获得1资源"},
                {"id": "card", "label": "抽取1张卡牌"},
            ],
        }

    def resolve_turn_end(self, game_state, investigator_id, choice: str) -> bool:
        """执行回合结束的二选一："resource" / "card"。由 UI 调用。"""
        scenario = getattr(game_state, "scenario", None)
        pending = scenario.vars.get("pending_choice", {}) if scenario else {}
        if pending.get("kind") != PENDING_KIND:
            return False
        if pending.get("investigator_id") != investigator_id:
            return False
        inv = self._get_jack(game_state, investigator_id)
        if inv is None:
            return False

        if choice == "resource":
            inv.resources += 1
        elif choice == "card":
            self._draw_one(game_state, inv)
        else:
            return False
        scenario.vars.pop("pending_choice", None)
        game_state.log_effect("🤠 蒙特雷·杰克：回合结束奖励已结算")
        return True

    # ------------------------------------------------------------------
    # 远古印记：+1；本轮移动过则获得1资源或抽1张牌（预设二选一）
    # ------------------------------------------------------------------

    def choose_elder_sign_choice(self, game_state, investigator_id,
                                 choice: str | None) -> bool:
        """预设远古印记的二选一（"resource"/"card"；None 清除）。由 UI 调用。"""
        if self._get_jack(game_state, investigator_id) is None:
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False
        if choice is None:
            scenario.vars.pop(PRESET_KEY, None)
            return True
        if choice not in ("resource", "card"):
            return False
        scenario.vars[PRESET_KEY] = choice
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1；本轮开始地点与当前地点相隔1+时获得奖励。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_jack(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "monterey_jack_elder_sign")

        if self._moved_distance(ctx.game_state, inv) < 1:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        choice = scenario.vars.get(PRESET_KEY, "resource") if scenario else "resource"
        if choice == "card":
            self._draw_one(ctx.game_state, inv)
            ctx.game_state.log_effect("🤠 蒙特雷·杰克：远古印记，抽1张牌")
        else:
            inv.resources += 1
            ctx.game_state.log_effect("🤠 蒙特雷·杰克：远古印记，获得1资源")
